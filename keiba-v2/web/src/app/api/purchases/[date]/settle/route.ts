/**
 * 購入結果自動反映API
 *
 * POST /api/purchases/{date}/settle
 *
 * Python ml.settle_purchases を実行し、mykeibadb の確定配当で精算する。
 */

import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import { ADMIN_CONFIG } from '@/lib/admin/config';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ date: string }> }
) {
  try {
    const { date } = await params;

    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) {
      return NextResponse.json({ error: 'Invalid date format' }, { status: 400 });
    }

    // force=trueで既確定分も再計算（クエリパラメータまたはbody）
    let force = false;
    try {
      const body = await request.json();
      force = !!body.force;
    } catch { /* no body is fine */ }
    if (request.nextUrl.searchParams.get('force') === 'true') force = true;

    const args = ['-m', 'ml.settle_purchases', '--date', date];
    if (force) args.push('--force');
    const output = await runPython(args);

    // Python の最後の行が JSON 結果
    const lines = output.trim().split('\n');
    let result: Record<string, unknown> = {};
    // 末尾から JSON ブロックを探す
    const jsonStart = lines.findIndex(l => l.trim().startsWith('{'));
    if (jsonStart >= 0) {
      const jsonStr = lines.slice(jsonStart).join('\n');
      try {
        result = JSON.parse(jsonStr);
      } catch {
        result = { success: true, output };
      }
    } else {
      result = { success: true, output };
    }

    return NextResponse.json(result);
  } catch (error) {
    console.error('[SettleAPI] Error:', error);
    const msg = error instanceof Error ? error.message : String(error);
    return NextResponse.json(
      { error: '結果反映に失敗しました', details: msg },
      { status: 500 }
    );
  }
}

function runPython(args: string[]): Promise<string> {
  return new Promise((resolve, reject) => {
    const child = spawn(ADMIN_CONFIG.pythonPath, args, {
      cwd: ADMIN_CONFIG.v2Path,
      shell: true,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    });

    let stdout = '';
    let stderr = '';

    child.stdout?.on('data', (data: Buffer) => { stdout += data.toString('utf-8'); });
    child.stderr?.on('data', (data: Buffer) => { stderr += data.toString('utf-8'); });

    child.on('close', (code: number | null) => {
      if (code === 0) {
        resolve(stdout);
      } else {
        reject(new Error(`exit code ${code}: ${stderr || stdout}`));
      }
    });

    child.on('error', (error: Error) => { reject(error); });
  });
}
