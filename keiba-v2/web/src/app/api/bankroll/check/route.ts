/**
 * 購入前チェックAPI
 * 
 * POST /api/bankroll/check
 * Body: { betType: string, amount: number }
 */

import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';
import { ADMIN_CONFIG } from '@/lib/admin/config';
import { loadConfig, resolveLimits, isValidRaceId } from '@/lib/bankroll/limit-resolver';

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

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { betType, amount, raceId } = body as { betType?: string; amount?: number; raceId?: string };

    if (!betType || typeof amount !== 'number' || amount <= 0) {
      return NextResponse.json(
        { error: 'betTypeとamountが必要です' },
        { status: 400 }
      );
    }

    // raceId は省略可。 指定時のみ race_overrides を引く
    const validRaceId = raceId && isValidRaceId(raceId) ? raceId : undefined;

    const config = await loadConfig();
    const today = new Date();
    const year = today.getFullYear();
    const month = today.getMonth() + 1;
    const dateStr = `${year}${String(month).padStart(2, '0')}${String(today.getDate()).padStart(2, '0')}`;

    const scriptPath = path.join(ADMIN_CONFIG.aiToolsPath, 'target_reader.py');

    let betTypeStats: Record<string, { recovery_rate?: number }> = {};
    try {
      betTypeStats = await executePythonScript(scriptPath, [
        '--year',
        year.toString(),
        '--month',
        month.toString(),
        '--stats',
      ]);
    } catch (error) {
      console.error('統計取得エラー:', error);
    }

    let dailySummary: { total_bet?: number } = {};
    try {
      dailySummary = await executePythonScript(scriptPath, ['--date', dateStr]);
    } catch (error) {
      console.error('日別サマリー取得エラー:', error);
    }

    const limits = resolveLimits(config, validRaceId);
    const todaySpent = dailySummary.total_bet || 0;
    const remaining = limits.dailyLimit - todaySpent;

    const warnings: string[] = [];
    const errors: string[] = [];

    // 1. 馬券種別回収率チェック
    if (betTypeStats && betTypeStats[betType]) {
      const stats = betTypeStats[betType];
      if (typeof stats.recovery_rate === 'number' && stats.recovery_rate < 50) {
        warnings.push(
          `${betType}は回収率${stats.recovery_rate.toFixed(1)}%です`
        );
      }
    }

    // 2. 1レース上限チェック (race_overrides 適用済みの限度額)
    if (amount > limits.raceLimit) {
      const srcLabel = limits.raceLimitSource === 'override' ? '上書き' :
        limits.raceLimitSource === 'absolute' ? '絶対額' : 'percent';
      errors.push(`1レース上限(${limits.raceLimit.toLocaleString()}円, src=${srcLabel})を超過しています`);
    }

    // 3. 1日上限チェック
    if (amount > remaining) {
      errors.push(
        `本日の残り予算(${remaining.toLocaleString()}円)を超過しています`
      );
    }

    // 4. 残り予算が少ない場合の警告
    if (remaining < limits.raceLimit && amount > remaining * 0.5) {
      warnings.push('残り予算が少なくなっています');
    }

    // 5. override 適用時の透明性 (10 §5.3): 上書きが効いてることをユーザーに見せる
    if (limits.raceLimitSource === 'override' && limits.overrideReason) {
      warnings.push(`レース上書き適用中: ${limits.overrideReason}`);
    }

    const canBet = errors.length === 0;

    return NextResponse.json({
      canBet,
      warnings,
      errors,
      limits: {
        dailyLimit: limits.dailyLimit,
        raceLimit: limits.raceLimit,
        remaining,
        todaySpent,
        raceLimitSource: limits.raceLimitSource,
        dailyLimitSource: limits.dailyLimitSource,
        overrideReason: limits.overrideReason,
        detail: limits.detail,
      },
      betTypeStats: betTypeStats[betType] || null,
    });
  } catch (error) {
    console.error('[BankrollCheckAPI] Error:', error);
    return NextResponse.json(
      {
        error: '購入前チェックに失敗しました',
        message: error instanceof Error ? error.message : String(error),
        canBet: false,
        warnings: [],
        errors: ['チェック処理中にエラーが発生しました'],
      },
      { status: 500 }
    );
  }
}
