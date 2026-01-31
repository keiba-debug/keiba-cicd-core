/**
 * 日別詳細API
 * 
 * GET /api/bankroll/daily/20260125
 */

import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/**
 * Pythonスクリプトを実行してJSONを取得
 */
function executePythonScript(
  scriptPath: string,
  args: string[],
  cwd?: string
): Promise<any> {
  return new Promise((resolve, reject) => {
    const pythonPath = process.env.PYTHON_PATH || 'python';
    const scriptFullPath = path.resolve(scriptPath);
    const workingDir = cwd || process.cwd();

    const child = spawn(pythonPath, [scriptFullPath, ...args], {
      cwd: workingDir,
      shell: true,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    });

    let stdout = '';
    let stderr = '';

    child.stdout?.on('data', (data: Buffer) => {
      stdout += data.toString('utf-8');
    });

    child.stderr?.on('data', (data: Buffer) => {
      stderr += data.toString('utf-8');
    });

    child.on('close', (code: number | null) => {
      if (code !== 0) {
        reject(new Error(`プロセス終了コード: ${code}\n${stderr}`));
        return;
      }

      try {
        const jsonStr = stdout.trim();
        if (!jsonStr) {
          reject(new Error('スクリプトからの出力がありません'));
          return;
        }

        const jsonMatch = jsonStr.match(/\{[\s\S]*\}/);
        if (!jsonMatch) {
          reject(new Error('JSON出力が見つかりません'));
          return;
        }

        const result = JSON.parse(jsonMatch[0]);
        resolve(result);
      } catch (error) {
        reject(new Error(`JSON解析エラー: ${error}\n出力: ${stdout}`));
      }
    });

    child.on('error', (error: Error) => {
      reject(error);
    });
  });
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ date: string }> }
) {
  try {
    const { date: dateStr } = await params;

    if (!dateStr || dateStr.length !== 8) {
      return NextResponse.json(
        { error: '日付形式が不正です。YYYYMMDD形式で指定してください。' },
        { status: 400 }
      );
    }

    const scriptPath = path.join(
      process.cwd(),
      '..',
      '..',
      'keiba-ai',
      'tools',
      'target_reader.py'
    );

    const result = await executePythonScript(scriptPath, ['--date', dateStr]);

    return NextResponse.json(result);
  } catch (error) {
    console.error('[BankrollDailyAPI] Error:', error);
    return NextResponse.json(
      {
        error: '日別詳細の取得に失敗しました',
        message: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
