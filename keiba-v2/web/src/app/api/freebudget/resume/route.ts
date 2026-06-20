/**
 * POST /api/freebudget/resume
 *
 * 自動投票スケジューラの当日 halt を解除して「再開」する (web「再開」= halt の対)。
 * bettype (multi-bettype = 現行本番) と freebudget (単勝) 両 scheduler の `--resume` を
 * spawn し、 live/dry 両方の state の halted=False + consecutive_failures=0 に戻す。
 *
 * ★設計★:
 *   - 旧設計では halt は sticky (web から再開不可) だった。 だが実運用の停止理由の多くは
 *     ★一時的★ (フォアグラウンドロック=SetForegroundWindow 失敗・PC操作中) で、 その都度
 *     state ファイルを手で直すのは非現実的。 そこで「再開」を ★明示的な手動操作★ として用意する。
 *   - state 書き込みは Python (scheduler --resume) に集約 (SoT 単一窓口。 web から JSON を
 *     直接書かない)。
 *   - 再開は consecutive_failures も 0 に戻す (再開直後に1失敗で即 re-halt しないため)。
 *   - ★再開後も根因 (TARGET 窓が前面でない等) が残っていれば次パスで再び失敗→再 halt する★。
 *     再開はあくまで「異常を確認・解消した上で」押す操作 (UI 側で注意喚起する)。
 *
 * Request body: { date?: string }
 * Response: { ok: true, output: string } | { ok: false, error: string }
 */
import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';
import { resolveDate } from '@/lib/data/freebudget-scheduler-reader';

export const dynamic = 'force-dynamic';

const CONFIG = {
  v2Path: path.resolve(process.cwd(), '..'),
  pythonPath: process.env.PYTHON_PATH ||
    path.resolve(process.cwd(), '..', '.venv', 'Scripts', 'python.exe'),
};

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

// 1 つの scheduler module に --resume を投げて出力を集める。
function spawnResume(module: string, date: string): Promise<{ ok: boolean; text: string }> {
  const args = ['-m', module, '--date', date, '--resume'];
  return new Promise((resolve) => {
    const child = spawn(CONFIG.pythonPath, args, {
      cwd: CONFIG.v2Path,
      shell: true,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    });
    let out = '';
    let err = '';
    child.stdout?.on('data', (d: Buffer) => { out += d.toString('utf-8'); });
    child.stderr?.on('data', (d: Buffer) => { err += d.toString('utf-8'); });
    child.on('close', (code: number | null) => {
      resolve({ ok: code === 0, text: (out || err).trim() || `exit ${code}` });
    });
    child.on('error', (e: Error) => { resolve({ ok: false, text: String(e) }); });
  });
}

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => ({}));
  const date = resolveDate(body.date);
  if (!DATE_RE.test(date)) {
    return NextResponse.json(
      { ok: false, error: `date が不正 (YYYY-MM-DD 必須): ${date}` }, { status: 400 });
  }

  // bettype (現行本番) を先に・freebudget (単勝) も続けて解除 (どちらの停止でも再開できる)。
  const bettype = await spawnResume('ml.strategies.bettype_scheduler', date);
  const freebudget = await spawnResume('ml.strategies.freebudget_scheduler', date);

  const output = `bettype: ${bettype.text}\nfreebudget: ${freebudget.text}`;
  if (bettype.ok || freebudget.ok) {
    return NextResponse.json({ ok: true, output, date });
  }
  return NextResponse.json({ ok: false, error: output }, { status: 500 });
}
