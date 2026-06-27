/**
 * bankroll 上限解決ロジック (限度額判定の Single Source)
 *
 * 設計背景: docs/auto-purchase/10_BANKROLL_CONTROL.md §3, §5
 *
 * 責務:
 *  - config.json の limit_mode (absolute / percent / both) を解決
 *  - race_overrides.{raceId} を最優先で適用
 *  - 後方互換: 新規フィールド未設定なら percent ベースにフォールバック
 *
 * API route から直接呼ばれる (check / config / race-override の3エンドポイントで共通)
 */
import * as fs from 'fs/promises';
import * as fsSync from 'fs';
import * as path from 'path';
import { AI_DATA_PATH } from '@/lib/config';
import { writeAtomic, withFileLock } from '@/lib/io/atomic-write';

export type LimitMode = 'absolute' | 'percent' | 'both';
export type LimitSource = 'override' | 'absolute' | 'percent';

export interface RaceOverride {
  per_race_max_yen: number;
  reason: string;
  created_at: string;
}

export interface BankrollConfig {
  created_at?: string;
  updated_at?: string;
  settings?: {
    total_bankroll?: number;
    daily_limit_percent?: number;
    race_limit_percent?: number;
    /**
     * 本日のスタート額 (入金額) — Session145。 資金管理メニューで設定し原則この額を入金する。
     * 入金額 = その日に賭ける総額の上限 = 最大負け額 (入金時点で確定)。 日次上限の最優先源。
     * scheduler は当日初回パスで state.day_budget_yen に凍結して使う。
     */
    daily_start_balance_yen?: number;
    today_budget_override?: number;
    consecutive_loss_limit?: number;
    kelly_fraction?: number;
    use_current_balance?: boolean;
    per_race_max_yen?: number;
    per_day_max_yen?: number;
    limit_mode?: LimitMode;
    limit_priority?: 'absolute_first' | 'percent_first' | 'min';
    /**
     * gap単勝 本投票 (Session 176) — 市場較正監査で確定したエッジ「gap≥5単勝×(未勝利/条件/重賞)」
     * を最初の収益源にする隔離口座。combo とは別 (gap_tansho_scheduler が読む)。
     *  gap_enabled: master switch (false=投票しない)。
     *  gap_initial_bankroll_yen: 初期残高 (既定30万)。 残高 = 初期 + 実現PnL (比例サイジングの素)。
     *  gap_bet_pct: 1点 = 残高 × この% (既定1.0)。
     *  gap_day_pct: 日次cap = 残高 × この% (既定5.0・暴走ガード)。
     */
    gap_enabled?: boolean;
    gap_initial_bankroll_yen?: number;
    gap_bet_pct?: number;
    gap_day_pct?: number;
    /**
     * 本命EV単 本投票 (Session 177) — 推奨馬券画面の主力プリセット tansho_ippon
     * (rank_w=1×gap≥3×EV≥1.3×接戦) を自動投票の2本目スリーブにする隔離口座。gap とは別建て。
     *  tansho_ev_enabled: master switch (false=投票しない)。
     *  tansho_ev_initial_bankroll_yen: 初期残高 (既定30万)。
     *  tansho_ev_bet_pct: 1点 = 残高 × この% (既定2.0)。
     *  tansho_ev_day_pct: 日次cap = 残高 × この% (既定10.0)。
     */
    tansho_ev_enabled?: boolean;
    tansho_ev_initial_bankroll_yen?: number;
    tansho_ev_bet_pct?: number;
    tansho_ev_day_pct?: number;
    /**
     * スリーブ全体の日次純投資ハード上限 (Session 177・§5/§11-1a)。 複数スリーブの
     * Σ純投資 ≤ この額 を sleeve_orchestrator が runner 直前にアサート (誤って増えない専用キー)。
     * 未設定なら Σ sleeve day_cap にフォールバック (単一スリーブ時 = そのスリーブの cap)。
     */
    sleeve_total_day_cap_yen?: number;
    /**
     * スリーブの ★レース合算 per_race 上限★ (Session 178・案A 二段化の合算上限・§11-7-7/§11-8)。
     * 同一レースで複数スリーブが乗ったときの ★合計★ をこの額以内に収める (超過は固定順=低優先から
     * レース単位で丸ごと見送り)。 ★runner の番人 per_race_max_yen と一致必須★ (食い違うと merge
     * 溢れ→runner exit5→day-halt)。 web は per_race_max_yen と同値で保存し、 orchestrator は起動時に
     * 一致を検証して不一致なら投票しない (fail-safe)。 未設定なら per_race_max_yen にフォールバック。
     */
    sleeve_per_race_cap_yen?: number;
  };
  rules?: {
    no_increase_after_loss?: boolean;
    confidence_adjustment?: boolean;
    no_dynamic_adjustment?: boolean;
  };
  race_overrides?: Record<string, RaceOverride>;
  target_integration?: {
    enabled?: boolean;
    data_root?: string;
    my_data_folder?: string;
  };
  notes?: string;
}

export interface ResolvedLimits {
  dailyLimit: number;
  raceLimit: number;
  raceLimitSource: LimitSource;
  dailyLimitSource: 'absolute' | 'percent';
  overrideReason: string | null;
  // デバッグ用: 各経路の値も返す
  detail: {
    fromOverride: number | null;
    fromAbsoluteRace: number | null;
    fromPercentRace: number;
    fromAbsoluteDaily: number | null;
    fromPercentDaily: number;
    limitMode: LimitMode;
    todayBudgetOverride: number | null;
    dailyStartBalance: number | null;
  };
}

export const CONFIG_PATH = path.join(AI_DATA_PATH, 'bankroll', 'config.json');
export const HISTORY_DIR = path.join(AI_DATA_PATH, 'bankroll', 'history');

/**
 * config.json を読み込む。 ファイル無し / parse 失敗時はデフォルト構造を返す。
 */
export async function loadConfig(): Promise<BankrollConfig> {
  try {
    const data = await fs.readFile(CONFIG_PATH, 'utf-8');
    return JSON.parse(data) as BankrollConfig;
  } catch {
    return {
      settings: {
        total_bankroll: 100000,
        daily_limit_percent: 5,
        race_limit_percent: 2,
        per_race_max_yen: 3000,
        per_day_max_yen: 10000,
        limit_mode: 'absolute',
        limit_priority: 'absolute_first',
      },
      rules: { no_dynamic_adjustment: true },
      race_overrides: {},
    };
  }
}

/**
 * 1レース・1日上限を解決する。
 *
 * 優先順位:
 *   1. race_overrides.{raceId}.per_race_max_yen (最優先)
 *   2. limit_mode に応じて absolute / percent / both
 *   3. 新規フィールド未設定なら percent にフォールバック
 *
 * @param config bankroll config.json の内容
 * @param raceId 16桁 race_id (省略可、override は適用されない)
 */
export function resolveLimits(config: BankrollConfig, raceId?: string): ResolvedLimits {
  const settings = config.settings ?? {};
  const totalBankroll = settings.total_bankroll ?? 100000;
  const dailyPct = settings.daily_limit_percent ?? 5;
  const racePct = settings.race_limit_percent ?? 2;

  const fromPercentRace = Math.floor(totalBankroll * (racePct / 100));
  const fromPercentDaily = Math.floor(totalBankroll * (dailyPct / 100));

  // 絶対額フィールド未設定なら percent フォールバック (後方互換)
  const fromAbsoluteRace = typeof settings.per_race_max_yen === 'number'
    ? settings.per_race_max_yen
    : null;
  const fromAbsoluteDaily = typeof settings.per_day_max_yen === 'number'
    ? settings.per_day_max_yen
    : null;

  const limitMode: LimitMode = settings.limit_mode
    ?? (fromAbsoluteRace !== null ? 'absolute' : 'percent');

  // race_overrides 最優先
  const override = raceId ? config.race_overrides?.[raceId] : undefined;
  const fromOverride = override?.per_race_max_yen ?? null;

  let raceLimit: number;
  let raceLimitSource: LimitSource;
  if (fromOverride !== null) {
    raceLimit = fromOverride;
    raceLimitSource = 'override';
  } else if (limitMode === 'absolute' && fromAbsoluteRace !== null) {
    raceLimit = fromAbsoluteRace;
    raceLimitSource = 'absolute';
  } else if (limitMode === 'both' && fromAbsoluteRace !== null) {
    // both = 厳しい方 (min) — 上限の意味を守る (10 §7 #3)
    raceLimit = Math.min(fromAbsoluteRace, fromPercentRace);
    raceLimitSource = fromAbsoluteRace <= fromPercentRace ? 'absolute' : 'percent';
  } else {
    raceLimit = fromPercentRace;
    raceLimitSource = 'percent';
  }

  // 日次上限解決:
  //   limit_mode=absolute かつ per_day_max_yen 設定済 → per_day_max_yen 採用 (today_budget_override 無視)
  //   それ以外で today_budget_override 設定済 → 旧挙動温存
  //   絶対額なし → percent
  // 経緯: シズネレビュー af17447ae78bb3da5 N1 — 過去設定の today_budget_override が
  //   absolute モードと矛盾するとふくだ意図と乖離する。 ふくだ判断 (Session 126) で「無視」採択
  const todayBudgetOverride = typeof settings.today_budget_override === 'number'
    ? settings.today_budget_override
    : null;
  // 本日のスタート額 (入金額) は日次上限の最優先源 (Session145)。 設定>0 のときは
  //   limit_mode/per_day_max_yen/today_budget_override より優先する (= 入金額が檻)。
  const fromStartBalance = typeof settings.daily_start_balance_yen === 'number'
    && settings.daily_start_balance_yen > 0
    ? settings.daily_start_balance_yen
    : null;

  let dailyLimit: number;
  let dailyLimitSource: 'absolute' | 'percent';
  if (fromStartBalance !== null) {
    dailyLimit = fromStartBalance;
    dailyLimitSource = 'absolute';
  } else if (limitMode === 'absolute' && fromAbsoluteDaily !== null) {
    dailyLimit = fromAbsoluteDaily;
    dailyLimitSource = 'absolute';
  } else if (todayBudgetOverride !== null) {
    dailyLimit = todayBudgetOverride;
    dailyLimitSource = 'absolute';
  } else if (limitMode === 'both' && fromAbsoluteDaily !== null) {
    dailyLimit = Math.min(fromAbsoluteDaily, fromPercentDaily);
    dailyLimitSource = fromAbsoluteDaily <= fromPercentDaily ? 'absolute' : 'percent';
  } else {
    dailyLimit = fromPercentDaily;
    dailyLimitSource = 'percent';
  }

  return {
    dailyLimit,
    raceLimit,
    raceLimitSource,
    dailyLimitSource,
    overrideReason: override?.reason ?? null,
    detail: {
      fromOverride,
      fromAbsoluteRace,
      fromPercentRace,
      fromAbsoluteDaily,
      fromPercentDaily,
      limitMode,
      todayBudgetOverride,
      dailyStartBalance: fromStartBalance,
    },
  };
}

/**
 * config.json のスナップショットを履歴 JSONL に追記 (7年保持要件: 10 §6)
 * 失敗しても本体の書き込みは止めない (ログ欠損 < 状態欠損)
 */
export async function appendConfigHistory(
  before: BankrollConfig | null,
  after: BankrollConfig,
  source: string
): Promise<void> {
  try {
    if (!fsSync.existsSync(HISTORY_DIR)) {
      await fs.mkdir(HISTORY_DIR, { recursive: true });
    }
    const now = new Date();
    const yyyy = now.getFullYear();
    const mm = String(now.getMonth() + 1).padStart(2, '0');
    const histPath = path.join(HISTORY_DIR, `config_${yyyy}-${mm}.jsonl`);
    const entry = {
      ts: now.toISOString(),
      source,
      before,
      after,
    };
    await fs.appendFile(histPath, JSON.stringify(entry) + '\n', 'utf-8');
  } catch (e) {
    console.error('[bankroll/limit-resolver] config history append failed:', e);
  }
}

/**
 * race_id を 16桁数字かバリデート
 */
export function isValidRaceId(raceId: string): boolean {
  return /^\d{16}$/.test(raceId);
}

/**
 * config.json を「ロック取得 → before 読み → patch → atomic 書き込み → history 追記」で更新する。
 *
 * シズネレビュー af17447ae78bb3da5 M1 対応:
 *   並走 PUT (config POST と race-override PUT/DELETE) でロストアップデートが起きていた問題を、
 *   atomic-write の withFileLock + writeAtomic で塞ぐ。
 *
 * @param mutator before の config を受け取って after を返す pure 関数 (config object は freeze 推奨)
 * @param source  history JSONL の source タグ (例: "config_post", "race_override_put:{raceId}")
 * @returns 書き込み後の after config
 */
export async function updateConfigLocked(
  mutator: (before: BankrollConfig) => BankrollConfig,
  source: string
): Promise<BankrollConfig> {
  return withFileLock(CONFIG_PATH, async () => {
    const before = await loadConfig();
    const after = mutator(before);
    after.updated_at = new Date().toISOString().split('T')[0];
    writeAtomic(CONFIG_PATH, JSON.stringify(after, null, 2));
    await appendConfigHistory(before, after, source);
    return after;
  });
}
