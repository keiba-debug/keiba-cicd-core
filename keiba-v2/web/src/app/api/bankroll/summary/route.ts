/**
 * 収支サマリーAPI
 * 
 * GET /api/bankroll/summary?year=2026&month=1
 * GET /api/bankroll/summary?date=20260125
 */

import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import { promisify } from 'util';
import path from 'path';
import { ADMIN_CONFIG } from '@/lib/admin/config';

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
        // JSON出力をパース
        const jsonStr = stdout.trim();
        if (!jsonStr) {
          reject(new Error('スクリプトからの出力がありません'));
          return;
        }

        // 最後のJSONオブジェクトを抽出（ログが混在する場合）
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

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const yearStr = searchParams.get('year');
    const monthStr = searchParams.get('month');
    const dateStr = searchParams.get('date');

    // スクリプトパス（keiba-ai/tools/target_reader.py）
    const scriptPath = path.join(ADMIN_CONFIG.aiToolsPath, 'target_reader.py');

    let result: any;

    if (dateStr) {
      // 日別サマリー
      if (dateStr.length !== 8) {
        return NextResponse.json(
          { error: '日付形式が不正です。YYYYMMDD形式で指定してください。' },
          { status: 400 }
        );
      }

      result = await executePythonScript(scriptPath, ['--date', dateStr]);
    } else if (yearStr && monthStr) {
      // 月間サマリー
      const year = parseInt(yearStr, 10);
      const month = parseInt(monthStr, 10);

      if (isNaN(year) || isNaN(month) || month < 1 || month > 12) {
        return NextResponse.json(
          { error: '年または月が不正です。' },
          { status: 400 }
        );
      }

      result = await executePythonScript(scriptPath, [
        '--year',
        yearStr,
        '--month',
        monthStr,
      ]);
    } else {
      return NextResponse.json(
        {
          error: 'パラメータが不足しています。',
          usage: {
            daily: '/api/bankroll/summary?date=20260125',
            monthly: '/api/bankroll/summary?year=2026&month=1',
          },
        },
        { status: 400 }
      );
    }

    return NextResponse.json(result);
  } catch (error) {
    console.error('[BankrollSummaryAPI] Error:', error);
    return NextResponse.json(
      {
        error: '収支サマリーの取得に失敗しました',
        message: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
