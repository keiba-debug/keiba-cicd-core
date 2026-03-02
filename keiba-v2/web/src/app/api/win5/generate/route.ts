/**
 * WIN5推奨馬 生成API
 * POST /api/win5/generate { date: "YYYY-MM-DD" }
 *
 * python -m ml.win5_pick --date YYYY-MM-DD を実行
 */

import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import { ADMIN_CONFIG } from '@/lib/admin/config';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function POST(req: NextRequest) {
  const body = await req.json();
  const date = body.date;
  if (!date || !/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    return NextResponse.json({ error: 'date parameter required (YYYY-MM-DD)' }, { status: 400 });
  }

  try {
    const output = await runCommand(['-m', 'ml.win5_pick', '--date', date]);
    return NextResponse.json({ success: true, output });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}

function runCommand(args: string[]): Promise<string> {
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
