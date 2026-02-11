/**
 * 購入前チェックAPI
 * 
 * POST /api/bankroll/check
 * Body: { betType: string, amount: number }
 */

import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs/promises';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/**
 * 設定ファイルを読み込む
 */
async function loadConfig(): Promise<any> {
  try {
    const configPath = path.join(
      process.cwd(),
      '..',
      'KeibaCICD.AI',
      'data',
      'bankroll',
      'config.json'
    );
    const configData = await fs.readFile(configPath, 'utf-8');
    return JSON.parse(configData);
  } catch (error) {
    return {
      settings: {
        total_bankroll: 100000,
        daily_limit_percent: 5.0,
        race_limit_percent: 2.0,
        consecutive_loss_limit: 3,
      },
    };
  }
}

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
    const { betType, amount } = body;

    if (!betType || typeof amount !== 'number' || amount <= 0) {
      return NextResponse.json(
        { error: 'betTypeとamountが必要です' },
        { status: 400 }
      );
    }

    const config = await loadConfig();
    const today = new Date();
    const year = today.getFullYear();
    const month = today.getMonth() + 1;
    const dateStr = `${year}${String(month).padStart(2, '0')}${String(today.getDate()).padStart(2, '0')}`;

    // 馬券種別統計を取得
    const scriptPath = path.join(
      process.cwd(),
      '..',
      'KeibaCICD.AI',
      'tools',
      'target_reader.py'
    );

    let betTypeStats: any = {};
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

    // 日別サマリーを取得
    let dailySummary: any = {};
    try {
      dailySummary = await executePythonScript(scriptPath, ['--date', dateStr]);
    } catch (error) {
      console.error('日別サマリー取得エラー:', error);
    }

    const totalBankroll = config.settings?.total_bankroll || 100000;
    const dailyLimitPercent = config.settings?.daily_limit_percent || 5.0;
    const raceLimitPercent = config.settings?.race_limit_percent || 2.0;
    const dailyLimit = Math.floor(totalBankroll * (dailyLimitPercent / 100));
    const raceLimit = Math.floor(totalBankroll * (raceLimitPercent / 100));
    const todaySpent = dailySummary.total_bet || 0;
    const remaining = dailyLimit - todaySpent;

    const warnings: string[] = [];
    const errors: string[] = [];

    // 1. 馬券種別回収率チェック
    if (betTypeStats && betTypeStats[betType]) {
      const stats = betTypeStats[betType];
      if (stats.recovery_rate < 50) {
        warnings.push(
          `${betType}は回収率${stats.recovery_rate.toFixed(1)}%です`
        );
      }
    }

    // 2. 1レース上限チェック
    if (amount > raceLimit) {
      errors.push(`1レース上限(${raceLimit.toLocaleString()}円)を超過しています`);
    }

    // 3. 1日上限チェック
    if (amount > remaining) {
      errors.push(
        `本日の残り予算(${remaining.toLocaleString()}円)を超過しています`
      );
    }

    // 4. 残り予算が少ない場合の警告
    if (remaining < raceLimit && amount > remaining * 0.5) {
      warnings.push('残り予算が少なくなっています');
    }

    const canBet = errors.length === 0;

    return NextResponse.json({
      canBet,
      warnings,
      errors,
      limits: {
        dailyLimit,
        raceLimit,
        remaining,
        todaySpent,
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
