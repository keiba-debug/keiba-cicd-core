/**
 * アラート情報API
 * 
 * GET /api/bankroll/alerts
 */

import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs/promises';
import { AI_DATA_PATH } from '@/lib/config';
import { ADMIN_CONFIG } from '@/lib/admin/config';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

interface Alert {
  type: 'warning' | 'error' | 'info';
  message: string;
  severity: 'low' | 'medium' | 'high';
}

// サーバー側キャッシュ（日付ベース、1分間保持）
interface CacheEntry {
  data: any;
  timestamp: number;
}

const cache = new Map<string, CacheEntry>();
const CACHE_TTL = 60000; // 1分間

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
    const configPath = path.join(AI_DATA_PATH, 'bankroll', 'config.json');
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
        use_current_balance: true,
      },
    };
  }
}

/**
 * 現在資金を取得
 */
async function loadCurrentBalance(): Promise<number> {
  try {
    const fundHistoryPath = path.join(AI_DATA_PATH, 'fund_history.json');
    const content = await fs.readFile(fundHistoryPath, 'utf-8');
    const history = JSON.parse(content);
    
    // 現在残高を計算
    let balance = history.config?.initial_balance || 100000;
    for (const entry of history.entries || []) {
      balance += entry.amount;
    }
    return balance;
  } catch (error) {
    // エラー時はデフォルト値
    return 100000;
  }
}

export async function GET(request: NextRequest) {
  try {
    const today = new Date();
    const year = today.getFullYear();
    const month = today.getMonth() + 1;
    const dateStr = `${year}${String(month).padStart(2, '0')}${String(today.getDate()).padStart(2, '0')}`;

    // キャッシュキー: 日付ベース（同じ日なら同じデータ）
    const cacheKey = dateStr;
    const cached = cache.get(cacheKey);

    // キャッシュヒット（1分以内）
    if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
      console.log(`[Bankroll Alerts] Cache hit for ${cacheKey}`);
      return NextResponse.json(cached.data);
    }

    console.log(`[Bankroll Alerts] Cache miss for ${cacheKey}, fetching fresh data...`);

    const config = await loadConfig();

    // 馬券種別統計を取得
    const scriptPath = path.join(ADMIN_CONFIG.aiToolsPath, 'target_reader.py');

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
    const useCurrentBalance = config.settings?.use_current_balance ?? true;
    const totalBankroll = config.settings?.total_bankroll || 100000;
    const dailyLimitPercent = config.settings?.daily_limit_percent || 5.0;
    const raceLimitPercent = config.settings?.race_limit_percent || 2.0;
    
    // 計算基準を決定（現在資金ベースか投資枠ベースか）
    const currentBalance = await loadCurrentBalance();
    const baseAmount = useCurrentBalance ? currentBalance : totalBankroll;
    
    const dailyLimit = Math.floor(baseAmount * (dailyLimitPercent / 100));
    const raceLimit = Math.floor(baseAmount * (raceLimitPercent / 100));
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

    const responseData = {
      alerts,
      count: alerts.length,
      dailyLimit,
      raceLimit,
      remaining,
      todaySpent,
      // 追加情報
      baseAmount,
      currentBalance,
      useCurrentBalance,
    };

    // キャッシュに保存
    cache.set(cacheKey, {
      data: responseData,
      timestamp: Date.now(),
    });

    // 古いキャッシュエントリを削除（メモリリーク防止）
    if (cache.size > 10) {
      const oldestKey = Array.from(cache.keys())[0];
      cache.delete(oldestKey);
    }

    return NextResponse.json(responseData);
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
