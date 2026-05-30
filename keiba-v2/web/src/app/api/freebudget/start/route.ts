/**
 * POST /api/freebudget/start
 *
 * 自動投票スケジューラの「単発パス」を起動する (web「開始」/「dry-run で確認」)。
 * 既存 /api/admin/execute の spawn + SSE パターンを踏襲。
 *
 * ★安全機構 (シズネ Session 134 🔴-2 / 135 🔴-B の web 版)★:
 *   - body.confirm === true (live) のときのみ --confirm --i-understand-live を付与。
 *   - そのとき body.acknowledged === true と body.confirmed_total_yen を必須化し、
 *     funded artifact (freebudget_bets.json) の total_yen と一致するかを API 側で照合。
 *     不一致 / 未取得なら 400 で拒否 = 「web が見せた金額」と「実投票内容」の一致を保証。
 *   - body.confirm が false/未指定なら dry-run (投票せず計画のみ)。 ゲート不要。
 *
 * ★無人 arming は引き続き NO-GO★: この API は「人が朝に明示的に叩く」人ゲート①。
 *   IPAT 入金 = 物理ゲート②。 二層は崩さない。
 *
 * Request body:
 *   { date?: string, confirm?: boolean, acknowledged?: boolean,
 *     confirmed_total_yen?: number }
 */
import { NextRequest } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';
import {
  getFundedTotalYen, getSchedulerStatus, resolveDate,
} from '@/lib/data/freebudget-scheduler-reader';

export const dynamic = 'force-dynamic';

const CONFIG = {
  v2Path: path.resolve(process.cwd(), '..'),
  pythonPath: process.env.PYTHON_PATH ||
    path.resolve(process.cwd(), '..', '.venv', 'Scripts', 'python.exe'),
};

type LogFn = (message: string, level?: string) => void;

function executeCommand(args: string[], onLog: LogFn): Promise<void> {
  return new Promise((resolve, reject) => {
    const child = spawn(CONFIG.pythonPath, args, {
      cwd: CONFIG.v2Path,
      shell: true,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    });
    child.stdout?.on('data', (data: Buffer) => {
      for (const line of data.toString('utf-8').split('\n')) {
        if (line.trim()) onLog(line.trim(), 'info');
      }
    });
    child.stderr?.on('data', (data: Buffer) => {
      for (const line of data.toString('utf-8').split('\n')) {
        if (line.trim()) onLog(line.trim(), 'warn');
      }
    });
    child.on('close', (code: number | null) => {
      // scheduler は halt 時 exit 3 を返す → エラー扱いせずログで通知済なので resolve
      if (code === 0 || code === 3) resolve();
      else reject(new Error(`exit code: ${code}`));
    });
    child.on('error', (err: Error) => reject(err));
  });
}

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => ({}));
  const date = resolveDate(body.date);
  // shell:true で spawn するため、 date を厳格に YYYY-MM-DD に限定 (引数混入対策)
  if (!DATE_RE.test(date)) {
    return new Response(
      JSON.stringify({ error: `date が不正 (YYYY-MM-DD 必須): ${date}` }),
      { status: 400, headers: { 'Content-Type': 'application/json' } });
  }
  const wantLive = body.confirm === true;

  const jsonError = (msg: string, status = 400) => new Response(
    JSON.stringify({ error: msg }),
    { status, headers: { 'Content-Type': 'application/json' } });

  // ★live 起動の事前ゲート (SSE を開く前に同期チェックして 400 を返せるようにする)★
  if (wantLive) {
    // 🔴-2: LIVE は当日のみ (過去日/未来日への誤投票を構造的に防ぐ。 dry-run は任意日OK)。
    //   ※「前日に翌日分を arm」 は無人 arming 議論に戻るため意図的に塞ぐ。
    if (date !== resolveDate('today')) {
      return jsonError(`LIVE 投票は当日 (${resolveDate('today')}) のみ可能です (指定: ${date})。 dry-run は任意日で確認できます。`);
    }
    // 🟡-1: halt 中は LIVE を API 層でも弾く (緊急ブレーキの信頼性を多層化。 UI 無効化に
    //   依存せず curl 直叩きでもバイパスさせない)。 scheduler も state.halted で止めるが二重で。
    if (getSchedulerStatus(date).halted) {
      return jsonError('当日は halted (停止中) です。 LIVE 起動はできません。', 409);
    }
    if (body.acknowledged !== true) {
      return jsonError('live 起動には acknowledged=true が必須 (金額確認)');
    }
    const fundedTotal = getFundedTotalYen(date);
    if (fundedTotal == null) {
      return jsonError(`funded artifact (freebudget_bets.json) が未生成。 先に買い目を生成してください (${date})`);
    }
    // 🟡-2: 円は整数。 浮動小数で割れて永久に通らない/緩く通る事故を防ぐため両辺を整数化して比較。
    const confirmed = body.confirmed_total_yen;
    if (typeof confirmed !== 'number' || !Number.isFinite(confirmed) ||
        Math.round(confirmed) !== Math.round(fundedTotal)) {
      return jsonError(
        `金額照合エラー: 確認額 ${confirmed} ≠ 実買い目合計 ${fundedTotal}円。 ` +
        `買い目が変わった可能性があります。 画面を再読み込みして金額を確認し直してください。`);
    }
  }

  const args = ['-m', 'ml.strategies.freebudget_scheduler', '--date', date];
  if (wantLive) {
    args.push('--confirm', '--i-understand-live');
  }
  // confirm=false なら何も足さない = dry-run 単発パス

  const stream = new ReadableStream({
    async start(controller) {
      const encoder = new TextEncoder();
      const sendEvent = (type: string, data: object) => {
        controller.enqueue(
          encoder.encode(`data: ${JSON.stringify({ type, ...data })}\n\n`));
      };
      const log: LogFn = (message, level = 'info') => sendEvent('log', { message, level });

      try {
        log(`自動投票スケジューラ起動: ${date} ${wantLive ? 'LIVE (実投票)' : 'dry-run (計画のみ)'}`);
        await executeCommand(args, log);
        sendEvent('done', { mode: wantLive ? 'live' : 'dry-run' });
      } catch (err) {
        sendEvent('error', { message: String(err) });
      } finally {
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    },
  });
}
