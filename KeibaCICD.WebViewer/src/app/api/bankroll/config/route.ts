/**
 * 予算設定API
 * 
 * GET /api/bankroll/config - 設定取得
 * POST /api/bankroll/config - 設定更新
 */

import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs/promises';
import path from 'path';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const CONFIG_PATH = path.join(
  process.cwd(),
  '..',
  '..',
  'keiba-ai',
  'data',
  'bankroll',
  'config.json'
);

export async function GET() {
  try {
    const configData = await fs.readFile(CONFIG_PATH, 'utf-8');
    const config = JSON.parse(configData);

    // 計算値を追加
    const totalBankroll = config.settings?.total_bankroll || 0;
    const dailyLimitPercent = config.settings?.daily_limit_percent || 5.0;
    const raceLimitPercent = config.settings?.race_limit_percent || 2.0;

    return NextResponse.json({
      ...config,
      calculated: {
        dailyLimit: Math.floor(totalBankroll * (dailyLimitPercent / 100)),
        raceLimit: Math.floor(totalBankroll * (raceLimitPercent / 100)),
      },
    });
  } catch (error) {
    console.error('[BankrollConfigAPI] Error:', error);
    return NextResponse.json(
      {
        error: '設定の取得に失敗しました',
        message: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { total_bankroll, daily_limit_percent, race_limit_percent } = body;

    // 既存の設定を読み込む
    let config: any = {};
    try {
      const configData = await fs.readFile(CONFIG_PATH, 'utf-8');
      config = JSON.parse(configData);
    } catch (error) {
      // ファイルが存在しない場合はデフォルト設定を使用
      config = {
        created_at: new Date().toISOString().split('T')[0],
        updated_at: new Date().toISOString().split('T')[0],
        settings: {
          total_bankroll: 100000,
          daily_limit_percent: 5.0,
          race_limit_percent: 2.0,
          consecutive_loss_limit: 3,
          kelly_fraction: 0.25,
        },
        rules: {
          no_increase_after_loss: true,
          confidence_adjustment: true,
        },
        target_integration: {
          enabled: true,
          data_root: process.env.JV_DATA_ROOT_DIR ?? '',
          my_data_folder: 'MY_DATA',
        },
      };
    }

    // 設定を更新
    if (total_bankroll !== undefined) {
      config.settings.total_bankroll = total_bankroll;
    }
    if (daily_limit_percent !== undefined) {
      config.settings.daily_limit_percent = daily_limit_percent;
    }
    if (race_limit_percent !== undefined) {
      config.settings.race_limit_percent = race_limit_percent;
    }

    config.updated_at = new Date().toISOString().split('T')[0];

    // 設定を保存
    await fs.writeFile(CONFIG_PATH, JSON.stringify(config, null, 2), 'utf-8');

    // 計算値を追加して返す
    const totalBankroll = config.settings.total_bankroll || 0;
    const dailyLimitPercent = config.settings.daily_limit_percent || 5.0;
    const raceLimitPercent = config.settings.race_limit_percent || 2.0;

    return NextResponse.json({
      ...config,
      calculated: {
        dailyLimit: Math.floor(totalBankroll * (dailyLimitPercent / 100)),
        raceLimit: Math.floor(totalBankroll * (raceLimitPercent / 100)),
      },
    });
  } catch (error) {
    console.error('[BankrollConfigAPI] Error:', error);
    return NextResponse.json(
      {
        error: '設定の更新に失敗しました',
        message: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
