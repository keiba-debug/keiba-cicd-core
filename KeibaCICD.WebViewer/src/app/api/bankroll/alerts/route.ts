/**
 * アラート情報API
 * 
 * GET /api/bankroll/alerts
 */

import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs/promises';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

interface Alert {
  type: 'warning' | 'error' | 'info';
  message: string;
  severity: 'low' | 'medium' | 'high';
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

/**
 * 設定ファイルを読み込む
 */
async function loadConfig(): Promise<any> {
  try {
    const configPath = path.join(
      process.cwd(),
      '..',
      '..',
      'keiba-ai',
      'data',
      'bankroll',
      'config.json'
    );
    const configData = await fs.readFile(configPath, 'utf-8');
    return JSON.parse(configData);
  } catch (error) {
    // デフォルト設定を返す
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

export async function GET(request: NextRequest) {
  try {
    const config = await loadConfig();
    const today = new Date();
    const year = today.getFullYear();
    const month = today.getMonth() + 1;
    const dateStr = `${year}${String(month).padStart(2, '0')}${String(today.getDate()).padStart(2, '0')}`;

    // 馬券種別統計を取得
    const scriptPath = path.join(
      process.cwd(),
      '..',
      '..',
      'keiba-ai',
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
      // エラー時は空の統計を返す
      console.error('統計取得エラー:', error);
    }

    // 日別サマリーを取得
    let dailySummary: any = {};
    try {
      dailySummary = await executePythonScript(scriptPath, [
        '--year',
        year.toString(),
        '--month',
        month.toString(),
        '--date',
        dateStr,
      ]);
    } catch (error) {
      console.error('日別サマリー取得エラー:', error);
    }

    const alerts: Alert[] = [];

    // 馬券種別回収率の警告は馬券種別実績エリアで表示するため、ここでは表示しない

    // 1. 残り予算チェック
    const totalBankroll = config.settings?.total_bankroll || 100000;
    const dailyLimitPercent = config.settings?.daily_limit_percent || 5.0;
    const raceLimitPercent = config.settings?.race_limit_percent || 2.0;
    const dailyLimit = Math.floor(totalBankroll * (dailyLimitPercent / 100));
    const raceLimit = Math.floor(totalBankroll * (raceLimitPercent / 100));
    const todaySpent = dailySummary.total_bet || 0;
    const remaining = dailyLimit - todaySpent;

    if (remaining < raceLimit) {
      alerts.push({
        type: 'warning',
        message: `残り予算が${remaining.toLocaleString()}円です。1レース上限(${raceLimit.toLocaleString()}円)を下回っています`,
        severity: remaining < raceLimit / 2 ? 'high' : 'medium',
      });
    }

    if (todaySpent >= dailyLimit * 0.8) {
      alerts.push({
        type: 'info',
        message: `本日の予算の${Math.floor((todaySpent / dailyLimit) * 100)}%を使用しました`,
        severity: 'medium',
      });
    }

    // 3. 連敗チェック（簡易版 - 実際の実装ではbankroll_managerから取得）
    // ここでは仮の実装
    const consecutiveLosses = 0; // TODO: bankroll_managerから取得
    if (consecutiveLosses >= 2) {
      alerts.push({
        type: 'warning',
        message: `${consecutiveLosses}連敗中です。次の購入は慎重に`,
        severity: consecutiveLosses >= 3 ? 'high' : 'medium',
      });
    }

    return NextResponse.json({
      alerts,
      count: alerts.length,
      dailyLimit,
      raceLimit,
      remaining,
      todaySpent,
    });
  } catch (error) {
    console.error('[BankrollAlertsAPI] Error:', error);
    return NextResponse.json(
      {
        error: 'アラート情報の取得に失敗しました',
        message: error instanceof Error ? error.message : String(error),
        alerts: [],
        count: 0,
      },
      { status: 500 }
    );
  }
}
