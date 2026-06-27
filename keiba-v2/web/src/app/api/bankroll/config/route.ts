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
  // gap単勝 本投票 (Session 176): web から有効化・初期残高・1点比率を設定 (隔離口座)
  gap_enabled?: boolean;
  gap_initial_bankroll_yen?: number | null;
  gap_bet_pct?: number | null;
  gap_day_pct?: number | null;
  // 本命EV単 本投票 (Session 177): 2本目スリーブ (隔離口座・gap と同型)
  tansho_ev_enabled?: boolean;
  tansho_ev_initial_bankroll_yen?: number | null;
  tansho_ev_bet_pct?: number | null;
  tansho_ev_day_pct?: number | null;
  // スリーブ全体の日次純投資ハード上限 (Session 177)。null=削除(Σにフォールバック)
  sleeve_total_day_cap_yen?: number | null;
  // スリーブのレース合算 per_race 上限 (Session 178・案A)。null=削除(per_race_max_yenにフォールバック)
  // ★per_race_max_yen と一致必須★。web は両者を同値で保存する (BudgetForm が連動送信)。
  sleeve_per_race_cap_yen?: number | null;
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
  // gap単勝 本投票 (Session 176)。 null は削除 (= 既定にフォールバック)。
  if (patch.gap_enabled !== undefined) next.settings.gap_enabled = patch.gap_enabled;
  if (patch.gap_initial_bankroll_yen !== undefined) {
    if (patch.gap_initial_bankroll_yen === null) delete next.settings.gap_initial_bankroll_yen;
    else next.settings.gap_initial_bankroll_yen = patch.gap_initial_bankroll_yen;
  }
  if (patch.gap_bet_pct !== undefined) {
    if (patch.gap_bet_pct === null) delete next.settings.gap_bet_pct;
    else next.settings.gap_bet_pct = patch.gap_bet_pct;
  }
  if (patch.gap_day_pct !== undefined) {
    if (patch.gap_day_pct === null) delete next.settings.gap_day_pct;
    else next.settings.gap_day_pct = patch.gap_day_pct;
  }
  // 本命EV単 本投票 (Session 177)。 null は削除 (= 既定にフォールバック)。
  if (patch.tansho_ev_enabled !== undefined) next.settings.tansho_ev_enabled = patch.tansho_ev_enabled;
  if (patch.tansho_ev_initial_bankroll_yen !== undefined) {
    if (patch.tansho_ev_initial_bankroll_yen === null) delete next.settings.tansho_ev_initial_bankroll_yen;
    else next.settings.tansho_ev_initial_bankroll_yen = patch.tansho_ev_initial_bankroll_yen;
  }
  if (patch.tansho_ev_bet_pct !== undefined) {
    if (patch.tansho_ev_bet_pct === null) delete next.settings.tansho_ev_bet_pct;
    else next.settings.tansho_ev_bet_pct = patch.tansho_ev_bet_pct;
  }
  if (patch.tansho_ev_day_pct !== undefined) {
    if (patch.tansho_ev_day_pct === null) delete next.settings.tansho_ev_day_pct;
    else next.settings.tansho_ev_day_pct = patch.tansho_ev_day_pct;
  }
  if (patch.sleeve_total_day_cap_yen !== undefined) {
    if (patch.sleeve_total_day_cap_yen === null) delete next.settings.sleeve_total_day_cap_yen;
    else next.settings.sleeve_total_day_cap_yen = patch.sleeve_total_day_cap_yen;
  }
  if (patch.sleeve_per_race_cap_yen !== undefined) {
    if (patch.sleeve_per_race_cap_yen === null) delete next.settings.sleeve_per_race_cap_yen;
    else next.settings.sleeve_per_race_cap_yen = patch.sleeve_per_race_cap_yen;
  }
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
