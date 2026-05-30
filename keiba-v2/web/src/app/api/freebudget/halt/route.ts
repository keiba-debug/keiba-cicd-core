/**
 * POST /api/freebudget/halt
 *
 * 自動投票スケジューラを「当日 halt」する (web「停止」= 緊急ブレーキ)。
 * scheduler の `--halt` を spawn し、 live/dry 両方の state に halted=True を立てる。
 *
 * ★設計 (シズネ流の安全側操作)★:
 *   - 停止は ★安全側★ の操作 (投票を増やさず止めるだけ) なので、 start の LIVE 起動の
 *     ような金額照合ゲートは課さない。 誤爆しても損害は「止まる」だけ。
 *   - state 書き込みは Python (scheduler --halt) に集約。 web から JSON を直接書かない
 *     (SoT 単一窓口)。
 *   - ★halt は sticky★: 一度止めると当日は web から再開できない (halt は「異常だから
 *     止める」ための機構。 再開は state ファイル手動操作という意図的な手間を要求する)。
 *
 * Request body: { date?: string, reason?: string }
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

// 停止理由に渡せる文字を制限 (コマンドライン引数への混入対策。 shell:true で spawn する
// ため、 自由文字列をそのまま渡さず英数とハイフン/アンダースコアのみ許可する)。
function sanitizeReason(raw: unknown): string {
  const s = typeof raw === 'string' ? raw : '';
  const cleaned = s.replace(/[^A-Za-z0-9_-]/g, '').slice(0, 60);
  return cleaned || 'manual_stop_via_web';
}

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => ({}));
  const date = resolveDate(body.date);
  // shell:true で spawn するため、 date を厳格に YYYY-MM-DD に限定 (引数混入対策)
  if (!DATE_RE.test(date)) {
    return NextResponse.json(
      { ok: false, error: `date が不正 (YYYY-MM-DD 必須): ${date}` }, { status: 400 });
  }
  const reason = sanitizeReason(body.reason);

  const args = [
    '-m', 'ml.strategies.freebudget_scheduler',
    '--date', date, '--halt', '--halt-reason', reason,
  ];

  return new Promise<NextResponse>((resolve) => {
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
      if (code === 0) {
        resolve(NextResponse.json({ ok: true, output: out.trim(), date }));
      } else {
        resolve(NextResponse.json(
          { ok: false, error: (err || out).trim() || `exit code: ${code}` },
          { status: 500 }));
      }
    });
    child.on('error', (e: Error) => {
      resolve(NextResponse.json({ ok: false, error: String(e) }, { status: 500 }));
    });
  });
}
