/**
 * 資金配分ガイドAPI
 * 
 * GET /api/bankroll/allocation?year=2026&month=1
 */

import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
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
        const jsonStr = stdout.trim();
        if (!jsonStr) {
          resolve({});
          return;
        }

        const jsonMatch = jsonStr.match(/\{[\s\S]*\}/);
        if (!jsonMatch) {
          resolve({});
          return;
        }

        const result = JSON.parse(jsonMatch[0]);
        resolve(result);
      } catch (error) {
        resolve({});
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

    if (!yearStr || !monthStr) {
      const today = new Date();
      const year = today.getFullYear();
      const month = today.getMonth() + 1;

      const scriptPath = path.join(ADMIN_CONFIG.aiToolsPath, 'target_reader.py');

      const betTypeStats = await executePythonScript(scriptPath, [
        '--year',
        year.toString(),
        '--month',
        month.toString(),
        '--stats',
      ]);

      return calculateAllocation(betTypeStats);
    }

    const year = parseInt(yearStr, 10);
    const month = parseInt(monthStr, 10);

    if (isNaN(year) || isNaN(month) || month < 1 || month > 12) {
      return NextResponse.json(
        { error: '年または月が不正です。' },
        { status: 400 }
      );
    }

    const scriptPath = path.join(ADMIN_CONFIG.aiToolsPath, 'target_reader.py');

    const betTypeStats = await executePythonScript(scriptPath, [
      '--year',
      yearStr,
      '--month',
      monthStr,
      '--stats',
    ]);

    return calculateAllocation(betTypeStats);
  } catch (error) {
    console.error('[BankrollAllocationAPI] Error:', error);
    return NextResponse.json(
      {
        error: '資金配分ガイドの取得に失敗しました',
        message: error instanceof Error ? error.message : String(error),
        allocation: [],
      },
      { status: 500 }
    );
  }
}

function calculateAllocation(betTypeStats: any): NextResponse {
  if (!betTypeStats || typeof betTypeStats !== 'object') {
    return NextResponse.json({ allocation: [], has_data: false });
  }

  // メタ情報を取得
  const meta = betTypeStats._meta || {};
  const hasData = meta.has_data || false;
  const fileExists = meta.file_exists || false;

  // メタ情報を除外して統計データのみを処理
  const statsData = { ...betTypeStats };
  delete statsData._meta;

  // 回収率でソート
  const sortedStats = Object.entries(statsData)
    .map(([betType, stats]: [string, any]) => ({
      betType,
      recoveryRate: stats.recovery_rate || 0,
      count: stats.count || 0,
      stats,
    }))
    .filter((item) => item.count > 0)
    .sort((a, b) => b.recoveryRate - a.recoveryRate);

  if (sortedStats.length === 0) {
    return NextResponse.json({
      allocation: [],
      has_data: hasData,
      file_exists: fileExists,
    });
  }

  // 回収率に基づいて配分を計算
  // 回収率100%以上: 40%, 80-100%: 30%, 50-80%: 20%, 50%未満: 10%
  const allocation = sortedStats.map((item, index) => {
    let percentage = 10; // デフォルト

    if (item.recoveryRate >= 100) {
      percentage = 40;
    } else if (item.recoveryRate >= 80) {
      percentage = 30;
    } else if (item.recoveryRate >= 50) {
      percentage = 20;
    } else {
      percentage = 10;
    }

    // 最初の3つに集中配分
    if (index === 0 && item.recoveryRate >= 100) {
      percentage = 40;
    } else if (index === 1 && sortedStats[0].recoveryRate >= 100) {
      percentage = 30;
    } else if (index === 2) {
      percentage = 20;
    }

    return {
      betType: item.betType,
      percentage,
      recoveryRate: item.recoveryRate,
      recommendation:
        item.recoveryRate >= 100
          ? '好調'
          : item.recoveryRate >= 80
            ? '安定'
            : item.recoveryRate >= 50
              ? '普通'
              : '控えめ',
      stats: item.stats,
    };
  });

  // 合計が100%になるように調整
  const total = allocation.reduce((sum, item) => sum + item.percentage, 0);
  if (total !== 100) {
    const diff = 100 - total;
    if (allocation.length > 0) {
      allocation[0].percentage += diff;
    }
  }

  return NextResponse.json({
    allocation,
    totalPercentage: allocation.reduce((sum, item) => sum + item.percentage, 0),
    has_data: hasData,
    file_exists: fileExists,
  });
}
