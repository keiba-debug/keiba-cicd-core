/**
 * 予算設定API
 * 
 * GET /api/bankroll/config - 設定取得
 * POST /api/bankroll/config - 設定更新
 */

import { NextRequest, NextResponse } from 'next/server';
import {
  loadConfig,
  resolveLimits,
  updateConfigLocked,
  type BankrollConfig,
  type LimitMode,
} from '@/lib/bankroll/limit-resolver';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const config = await loadConfig();
    const limits = resolveLimits(config);
    return NextResponse.json({
      ...config,
      calculated: {
        // 後方互換: 既存呼び出し元が依存しているフィールド
        dailyLimit: limits.dailyLimit,
        raceLimit: limits.raceLimit,
        // 新規: 限度額がどこから来たかの透明性 (10 §5.3)
        raceLimitSource: limits.raceLimitSource,
        dailyLimitSource: limits.dailyLimitSource,
        detail: limits.detail,
      },
    });
  } catch (error) {
    console.error('[BankrollConfigAPI] GET Error:', error);
    return NextResponse.json(
      {
        error: '設定の取得に失敗しました',
        message: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}

interface ConfigPatchBody {
  total_bankroll?: number;
  daily_limit_percent?: number;
  race_limit_percent?: number;
  daily_start_balance_yen?: number | null;
  today_budget_override?: number | null;
  use_current_balance?: boolean;
  per_race_max_yen?: number | null;
  per_day_max_yen?: number | null;
  limit_mode?: LimitMode;
  limit_priority?: 'absolute_first' | 'percent_first' | 'min';
}

function applyPatch(config: BankrollConfig, patch: ConfigPatchBody): BankrollConfig {
  const next: BankrollConfig = JSON.parse(JSON.stringify(config));
  next.settings = next.settings ?? {};
  if (patch.total_bankroll !== undefined) next.settings.total_bankroll = patch.total_bankroll;
  if (patch.daily_limit_percent !== undefined) next.settings.daily_limit_percent = patch.daily_limit_percent;
  if (patch.race_limit_percent !== undefined) next.settings.race_limit_percent = patch.race_limit_percent;
  if (patch.daily_start_balance_yen !== undefined) {
    if (patch.daily_start_balance_yen === null) {
      delete next.settings.daily_start_balance_yen;
    } else {
      next.settings.daily_start_balance_yen = patch.daily_start_balance_yen;
    }
  }
  if (patch.use_current_balance !== undefined) next.settings.use_current_balance = patch.use_current_balance;
  if (patch.today_budget_override !== undefined) {
    if (patch.today_budget_override === null) {
      delete next.settings.today_budget_override;
    } else {
      next.settings.today_budget_override = patch.today_budget_override;
    }
  }
  if (patch.per_race_max_yen !== undefined) {
    if (patch.per_race_max_yen === null) {
      delete next.settings.per_race_max_yen;
    } else {
      next.settings.per_race_max_yen = patch.per_race_max_yen;
    }
  }
  if (patch.per_day_max_yen !== undefined) {
    if (patch.per_day_max_yen === null) {
      delete next.settings.per_day_max_yen;
    } else {
      next.settings.per_day_max_yen = patch.per_day_max_yen;
    }
  }
  if (patch.limit_mode !== undefined) next.settings.limit_mode = patch.limit_mode;
  if (patch.limit_priority !== undefined) next.settings.limit_priority = patch.limit_priority;
  next.updated_at = new Date().toISOString().split('T')[0];
  return next;
}

export async function POST(request: NextRequest) {
  try {
    const patch = (await request.json()) as ConfigPatchBody;
    const after = await updateConfigLocked(
      (before) => applyPatch(before, patch),
      'config_post'
    );

    const limits = resolveLimits(after);
    return NextResponse.json({
      ...after,
      calculated: {
        dailyLimit: limits.dailyLimit,
        raceLimit: limits.raceLimit,
        raceLimitSource: limits.raceLimitSource,
        dailyLimitSource: limits.dailyLimitSource,
        detail: limits.detail,
      },
    });
  } catch (error) {
    console.error('[BankrollConfigAPI] POST Error:', error);
    return NextResponse.json(
      {
        error: '設定の更新に失敗しました',
        message: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
