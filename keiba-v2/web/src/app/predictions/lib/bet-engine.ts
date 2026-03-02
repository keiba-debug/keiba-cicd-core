/**
 * bet-engine.ts — TypeScript版 買い目エンジン
 *
 * Python bet_engine.py のコアロジックをTypeScriptに移植。
 * ライブオッズでの購入プラン再計算に使用。
 *
 * v5.44: Composite VB Score方式に移行。
 * 4シグナル(dev_gap/rank_gap/EV/ARd)を段階的にスコア化し、
 * 合計スコアで選定。rank_gapはベット倍率に使用。
 *
 * ML出力（rank_p, ar_deviation, pred_proba_p_raw等）は predictions.json から取得し、
 * オッズのみ mykeibadb の最新値で上書きして再計算する。
 */

import type { PredictionRace, PredictionEntry, ServerBetRecommendation } from '@/lib/data/predictions-reader';
import type { OddsMap } from './types';
import type { ServerPresetKey, AllocMode } from './bet-logic';
import { rescaleBudget, equalDistribute } from './bet-logic';

// =====================================================================
// パラメータ定義 (Python BetStrategyParams に対応)
// =====================================================================

interface BetEngineParams {
  winMinGap: number;
  winMinEv: number;
  winVRatioMin: number;
  winVBypassGap: number;
  winVBypassEv: number;
  winArdGapTiers: [number, number][]; // [minArd, minGap][] — rank gap用 (レガシー)
  winArdDevTiers: [number, number][]; // [minArd, minDevGap][] — dev_gap用 (レガシー)
  // Composite VB Score (v5.44)
  winMinVbScore: number;   // 0=disabled (legacy tier), 5.0=recommended
  vbStrongScore: number;   // strong分類閾値 (7.0=recommended)
  // ARd VBルート (能力 vs 市場の直接乖離)
  ardVbMinArd: number;   // 0=disabled, 65=recommended
  ardVbMinOdds: number;  // 0=disabled, 10=recommended
  placeMinGap: number;
  placeMinEv: number;
  kellyFraction: number;
  kellyCap: number;
  winMaxRank: number;       // rank_p pre-filter fallback (v_ratio_min>0なら無視)
  dangerGapBoost: number;
  crossAlloc: boolean;
  strongWinPct: number;
  normalWinPct: number;
  maxWinPerRace: number;
  minBet: number;
  betUnit: number;
  // --- Place上乗せ (単勝ベース + 条件付き複勝追加) ---
  placeAddon: boolean;
  placeAddonMinPev: number;
  placeAddonMinArd: number;
  placeAddonAmount: number;
}

// VB Floor: 購入プラン⊆VB候補 を保証する最低条件
// Python bet_engine.py の VB_FLOOR_* と手動同期
const VB_FLOOR = {
  minWinEv: 1.0,
  minArd: 50.0,
  ardVbMinArd: 65.0,
  ardVbMinOdds: 10.0,
  minDevGap: 0.7,     // 偏差値gapルート: dev_gap下限
  devMinArd: 45.0,     // 偏差値gapルート: ARd下限
} as const;

// --- プリセット (Python PRESETS と完全一致) ---
// v5.44: Composite VB Score方式。EV>=1.0をハードフロアとして全プリセット共通で適用。

const ENGINE_PRESETS: Record<ServerPresetKey, BetEngineParams> = {
  standard: {
    winMinGap: 5,
    winMinEv: 1.0,            // EV >= 1.0 hard floor
    winMinVbScore: 5.5,       // Composite score >= 5.5
    vbStrongScore: 7.0,
    winVRatioMin: 0.75,
    winVBypassGap: 7,
    winVBypassEv: 3.0,
    winArdGapTiers: [],       // Not used with composite score
    winArdDevTiers: [],       // Not used with composite score
    ardVbMinArd: 65.0,
    ardVbMinOdds: 10.0,
    winMaxRank: 3,
    placeMinGap: 99,
    placeMinEv: 1.0,
    kellyFraction: 0.25,
    kellyCap: 0.10,
    dangerGapBoost: 0,
    crossAlloc: false,
    strongWinPct: 100,
    normalWinPct: 100,
    maxWinPerRace: 2,
    minBet: 100,
    betUnit: 100,
    placeAddon: true,
    placeAddonMinPev: 1.3,
    placeAddonMinArd: 50.0,
    placeAddonAmount: 200,
  },
  wide: {
    winMinGap: 5,
    winMinEv: 1.0,            // EV >= 1.0 hard floor
    winMinVbScore: 5.0,       // Composite score >= 5.0 (wider net)
    vbStrongScore: 7.0,
    winVRatioMin: 0.75,
    winVBypassGap: 7,
    winVBypassEv: 3.0,
    winArdGapTiers: [],
    winArdDevTiers: [],
    ardVbMinArd: 65.0,
    ardVbMinOdds: 10.0,
    winMaxRank: 3,
    placeMinGap: 99,
    placeMinEv: 1.0,
    kellyFraction: 0.25,
    kellyCap: 0.10,
    dangerGapBoost: 0,
    crossAlloc: false,
    strongWinPct: 100,
    normalWinPct: 100,
    maxWinPerRace: 2,
    minBet: 100,
    betUnit: 100,
    placeAddon: true,
    placeAddonMinPev: 1.3,
    placeAddonMinArd: 50.0,
    placeAddonAmount: 200,
  },
  aggressive: {
    winMinGap: 5,
    winMinEv: 1.0,            // EV >= 1.0 hard floor
    winMinVbScore: 6.0,       // Composite score >= 6.0 (high conviction)
    vbStrongScore: 7.0,
    winVRatioMin: 0.75,
    winVBypassGap: 7,
    winVBypassEv: 3.0,
    winArdGapTiers: [],
    winArdDevTiers: [],
    ardVbMinArd: 65.0,
    ardVbMinOdds: 10.0,
    winMaxRank: 3,
    placeMinGap: 99,
    placeMinEv: 1.0,
    kellyFraction: 0.25,
    kellyCap: 0.10,
    dangerGapBoost: 0,
    crossAlloc: false,
    strongWinPct: 100,
    normalWinPct: 100,
    maxWinPerRace: 2,
    minBet: 100,
    betUnit: 100,
    placeAddon: true,
    placeAddonMinPev: 1.3,
    placeAddonMinArd: 50.0,
    placeAddonAmount: 200,
  },
};

// =====================================================================
// コア関数
// =====================================================================

/** Kelly Criterion: f* = (b*p - q) / b */
function calcKellyFraction(prob: number, odds: number): number {
  const b = odds - 1.0;
  if (b <= 0 || prob <= 0) return 0.0;
  const q = 1.0 - prob;
  const f = (b * prob - q) / b;
  return Math.max(0.0, f);
}

/** 金額を unit 単位に丸める (切り捨て) */
function roundToUnit(amount: number, unit: number = 100): number {
  return Math.floor(amount / unit) * unit;
}

/** 危険馬検出: odds<=8 & ARd<53 & P%<15% (v5.33) */
function detectDanger(
  entries: LiveEntry[],
): Record<number, boolean> {
  const danger: Record<number, boolean> = {};
  for (const e of entries) {
    const odds = e.liveOdds;
    const ard = e.arDeviation ?? 0;
    const predP = e.predProbaP ?? 0;
    if (odds > 0 && odds <= 8.0 && ard < 53 && predP < 0.15) {
      danger[e.umaban] = true;
    }
  }
  return danger;
}

/**
 * コンポジットVBスコア: 全シグナルを統合した一元評価
 *
 * Score breakdown (max 10.0):
 *   dev_gap:  0-3 points (偏差値乖離: 的中率重視)
 *   rank_gap: 0-3 points (ランク差: 穴馬ROI)
 *   EV:       0-2 points (期待値)
 *   ARd:      0-2 points (能力偏差値)
 */
function computeVbScore(
  devGap: number,
  gap: number,
  winEv: number | null,
  arDeviation: number | null,
): number {
  let score = 0.0;

  // dev_gap: 偏差値ベースの本質的な乖離
  if (devGap >= 1.5) score += 3.0;
  else if (devGap >= 1.0) score += 2.0;
  else if (devGap >= 0.5) score += 1.0;

  // rank_gap: ランク差による穴馬検出
  if (gap >= 7) score += 3.0;
  else if (gap >= 5) score += 2.0;
  else if (gap >= 3) score += 1.0;

  // EV: 期待値
  const ev = winEv ?? 0;
  if (ev >= 2.0) score += 2.0;
  else if (ev >= 1.5) score += 1.5;
  else if (ev >= 1.0) score += 1.0;

  // ARd: レース内能力偏差値
  const ard = arDeviation ?? 0;
  if (ard >= 65) score += 2.0;
  else if (ard >= 55) score += 1.5;
  else if (ard >= 50) score += 1.0;

  return score;
}

/**
 * 単勝評価 (composite score or tier-based)
 *
 * v5.44: Composite VB Score方式に移行。
 * 4シグナル(dev_gap/rank_gap/EV/ARd)を合計スコアで選定。
 * rank_gapはベット倍率に使用。
 *
 * Returns [shouldBet, units]
 */
function evaluateWin(
  gap: number,
  params: BetEngineParams,
  isDanger: boolean,
  arDeviation: number | null,
  winEv: number | null,
  devGap: number,
  vbScore: number,
): [boolean, number] {
  let passed = false;

  // === Mode 1: Composite Score ===
  if (params.winMinVbScore > 0) {
    if (vbScore >= params.winMinVbScore) {
      passed = true;
    }
  } else {
    // === Mode 2: Legacy tier-based ===
    // Route 1: dev_gap tier
    if (params.winArdDevTiers.length > 0) {
      for (const [tierArd, tierDev] of params.winArdDevTiers) {
        if (arDeviation != null && arDeviation >= tierArd) {
          if (devGap >= tierDev) passed = true;
          break;
        }
      }
    }

    // Route 2: rank_gap tier
    if (!passed && params.winArdGapTiers.length > 0) {
      for (const [tierArd, tierGap] of params.winArdGapTiers) {
        if (arDeviation != null && arDeviation >= tierArd) {
          let minGap = tierGap;
          if (isDanger) minGap += params.dangerGapBoost;
          if (gap >= minGap) passed = true;
          break;
        }
      }
    }

    // Route 3: フラット閾値
    if (!passed && params.winArdDevTiers.length === 0 && params.winArdGapTiers.length === 0) {
      let minGap = params.winMinGap;
      if (isDanger) minGap += params.dangerGapBoost;
      if (gap >= minGap) passed = true;
    }
  }

  if (!passed) return [false, 0];

  // EV filter (0=disabled)
  if (params.winMinEv > 0) {
    if (winEv == null || winEv < params.winMinEv) return [false, 0];
  }

  // ベット倍率: rank_gapが大きいとき攻める
  let units: number;
  if (gap >= 7) units = 3;
  else if (gap >= 5) units = 2;
  else units = 1;

  return [true, units];
}

/**
 * 複勝評価 (gap + EV + Kelly)
 * Returns [shouldBet, kellyFrac]
 */
function evaluatePlace(
  gap: number,
  pTop3: number | null,
  placeOdds: number | null,
  params: BetEngineParams,
  isDanger: boolean,
  arDeviation: number | null,
): [boolean, number] {
  let minGap = params.placeMinGap;
  if (isDanger) minGap += params.dangerGapBoost;
  if (gap < minGap) return [false, 0.0];

  // EV フィルタ
  if (pTop3 != null && placeOdds != null && placeOdds > 0) {
    const ev = pTop3 * placeOdds;
    if (ev < params.placeMinEv) return [false, 0.0];

    const kelly = calcKellyFraction(pTop3, placeOdds);
    let kellySized = kelly * params.kellyFraction;
    kellySized = Math.min(kellySized, params.kellyCap);
    if (kellySized <= 0) return [false, 0.0];
    return [true, kellySized];
  }

  return [true, 0.02]; // fallback
}

// =====================================================================
// ライブエントリ (オッズ差し替え済みの中間型)
// =====================================================================

interface LiveEntry {
  umaban: number;
  horseName: string;
  liveOdds: number;
  liveOddsRank: number;
  livePlaceOddsMin: number | null;
  // ML outputs (static)
  rankP: number;
  rankW: number;
  predProbaPRaw: number | null;
  predProbaP: number | null;
  predProbaW: number | null;
  arDeviation: number | null;
  predictedMargin: number | null;
  // Recalculated
  gap: number;       // liveOddsRank - rankP
  winGap: number;    // liveOddsRank - rankW
  devGap: number;    // z-score(model) - z-score(market)
  vbScore: number;   // composite VB score (0-10)
  winEv: number | null;
  placeEv: number | null;
}

interface LiveRec {
  raceId: string;
  entry: LiveEntry;
  betType: '単勝' | '複勝' | '単複';
  strength: 'strong' | 'normal';
  winAmount: number;
  placeAmount: number;
  kellyRaw: number;
  kellyCapped: number;
  isDanger: boolean;
  dangerScore: number;
}

// =====================================================================
// パイプライン
// =====================================================================

/**
 * ライブオッズで購入プラン再計算
 *
 * predictions.json の ML 出力 + mykeibadb ライブオッズ → 推奨買い目
 */
export function generateLiveRecommendations(
  races: PredictionRace[],
  oddsMap: OddsMap,
  presetKey: ServerPresetKey,
  budget: number,
  allocMode: AllocMode,
): ServerBetRecommendation[] {
  const params = ENGINE_PRESETS[presetKey];
  if (!params) return [];

  const allRecs: LiveRec[] = [];

  for (const race of races) {
    const raceOdds = oddsMap[race.race_id];

    // ライブエントリ構築: オッズを差し替え、rank/gap/EVを再計算
    const liveEntries = buildLiveEntries(race.entries, race.race_id, raceOdds);
    if (liveEntries.length === 0) continue;

    // 危険馬検出
    const dangerMap = detectDanger(liveEntries);

    // P%比率用: レース内最大P%
    let raceMaxP = 0;
    if (params.winVRatioMin > 0) {
      raceMaxP = Math.max(0, ...liveEntries.map(e => e.predProbaPRaw ?? 0));
    }

    const raceRecs: LiveRec[] = [];

    for (const e of liveEntries) {
      const isDanger = !!dangerMap[e.umaban];
      const dangerScore = isDanger ? 1.0 : 0.0;

      // === VB Floor Gate: 購入プラン⊆VB候補 ===
      const vbEvOk = (e.winEv ?? 0) >= VB_FLOOR.minWinEv;
      const vbArdOk = (e.arDeviation ?? 0) >= VB_FLOOR.minArd;
      const vbArdRoute = (e.arDeviation ?? 0) >= VB_FLOOR.ardVbMinArd
                         && e.liveOdds >= VB_FLOOR.ardVbMinOdds;
      const vbDevRoute = e.devGap >= VB_FLOOR.minDevGap
                         && (e.arDeviation ?? 0) >= VB_FLOOR.devMinArd;
      if (!(vbEvOk && vbArdOk) && !vbArdRoute && !vbDevRoute) continue;

      // --- 単勝 pre-filter: P%比率 ---
      let winPrefilterPass: boolean;
      if (params.winVRatioMin > 0) {
        const pPct = e.predProbaPRaw ?? 0;
        const pRatio = raceMaxP > 0 ? pPct / raceMaxP : 0;
        winPrefilterPass = pRatio >= params.winVRatioMin;
        // バイパス: P%比率未達でも高Gap+高EVなら通過
        if (!winPrefilterPass && params.winVBypassGap > 0 && params.winVBypassEv > 0) {
          if (e.gap >= params.winVBypassGap && (e.winEv ?? 0) >= params.winVBypassEv) {
            winPrefilterPass = true;
          }
        }
        // dev_gapバイパス: 偏差値的に大きく乖離していれば通過
        if (!winPrefilterPass && e.devGap >= 1.0) {
          winPrefilterPass = true;
        }
      } else {
        winPrefilterPass = e.rankP <= params.winMaxRank;
      }

      let winOk = false, winUnits = 0;
      if (winPrefilterPass) {
        [winOk, winUnits] = evaluateWin(
          e.gap, params, isDanger, e.arDeviation, e.winEv, e.devGap, e.vbScore,
        );
      }

      // --- ARd VBルート (能力 vs 市場の直接乖離) ---
      let ardVbPass = false;
      if (!winOk && params.ardVbMinArd > 0 && params.ardVbMinOdds > 0) {
        if (e.arDeviation != null && e.arDeviation >= params.ardVbMinArd
            && e.liveOdds >= params.ardVbMinOdds) {
          winOk = true;
          winUnits = 1;
          ardVbPass = true;
        }
      }

      // --- 複勝 pre-filter ---
      const placePrefilterPass = params.winVRatioMin > 0 ? winPrefilterPass : e.rankP <= 3;
      let placeOk = false, kellyFrac = 0.0;
      if (placePrefilterPass) {
        [placeOk, kellyFrac] = evaluatePlace(
          e.gap, e.predProbaPRaw, e.livePlaceOddsMin, params, isDanger, e.arDeviation,
        );
      }

      if (!winOk && !placeOk) continue;

      // strength判定 (composite score or legacy)
      let isStrong: boolean;
      if (params.winMinVbScore > 0) {
        // Composite Score mode: スコアで強弱判定
        isStrong = ardVbPass || e.vbScore >= params.vbStrongScore;
      } else {
        // Legacy mode
        isStrong = ardVbPass || e.devGap >= 1.5;
        if (!isStrong) {
          let strongGap = params.winMinGap + 2;
          if (params.winArdGapTiers.length > 0 && e.arDeviation != null) {
            for (const [tierArd, tierGap] of params.winArdGapTiers) {
              if (e.arDeviation >= tierArd) {
                strongGap = tierGap + 2;
                break;
              }
            }
          }
          if (e.gap >= strongGap) isStrong = true;
        }
      }

      let betType: '単勝' | '複勝' | '単複';
      let strength: 'strong' | 'normal';
      if (winOk && placeOk) {
        betType = '単複';
        strength = isStrong ? 'strong' : 'normal';
      } else if (winOk) {
        betType = '単勝';
        strength = isStrong ? 'strong' : 'normal';
      } else {
        betType = '複勝';
        strength = e.gap >= params.placeMinGap + 2 ? 'strong' : 'normal';
      }

      // --- Place上乗せ: 単勝候補に条件付きで複勝追加 ---
      let addonPlaceAmount = 0;
      if (winOk && params.placeAddon) {
        const pev = e.placeEv ?? 0;
        const ard = e.arDeviation ?? 0;
        if (pev >= params.placeAddonMinPev && ard >= params.placeAddonMinArd) {
          addonPlaceAmount = params.placeAddonAmount;
          betType = '単複';
        }
      }

      raceRecs.push({
        raceId: race.race_id,
        entry: e,
        betType,
        strength,
        winAmount: winOk ? winUnits * params.betUnit : 0,
        placeAmount: addonPlaceAmount, // place_addon or 0 (Kelly複勝はapplyBudgetで設定)
        kellyRaw: kellyFrac > 0 && params.kellyFraction > 0
          ? Math.round((kellyFrac / params.kellyFraction) * 10000) / 10000
          : 0,
        kellyCapped: Math.round(kellyFrac * 10000) / 10000,
        isDanger,
        dangerScore,
      });
    }

    // 1レースN単勝制約
    applyWinPerRaceLimit(raceRecs, params.maxWinPerRace);
    allRecs.push(...raceRecs);
  }

  // 予算スケーリング
  applyBudget(allRecs, budget, params);

  // クロス配分
  if (params.crossAlloc) {
    applyCrossAllocation(allRecs, params);
  }

  // ServerBetRecommendation[] に変換
  const serverRecs: ServerBetRecommendation[] = allRecs.map(r => ({
    race_id: r.raceId,
    umaban: r.entry.umaban,
    horse_name: r.entry.horseName,
    bet_type: r.betType,
    strength: r.strength,
    win_amount: r.winAmount,
    place_amount: r.placeAmount,
    gap: r.entry.gap,
    dev_gap: Math.round(r.entry.devGap * 1000) / 1000,
    vb_score: Math.round(r.entry.vbScore * 10) / 10,
    win_gap: r.entry.winGap,
    predicted_margin: r.entry.predictedMargin != null
      ? Math.round(r.entry.predictedMargin * 10) / 10
      : 0,
    win_ev: r.entry.winEv != null ? Math.round(r.entry.winEv * 10000) / 10000 : null,
    place_ev: r.entry.placeEv != null ? Math.round(r.entry.placeEv * 10000) / 10000 : null,
    kelly_raw: r.kellyRaw,
    kelly_capped: r.kellyCapped,
    is_danger: r.isDanger,
    danger_score: r.dangerScore,
    odds: r.entry.liveOdds,
    place_odds_min: r.entry.livePlaceOddsMin,
    ar_deviation: r.entry.arDeviation != null
      ? Math.round(r.entry.arDeviation * 10) / 10
      : null,
  }));

  // allocMode に応じた配分
  if (allocMode === 'equal') {
    return equalDistribute(serverRecs, budget);
  }
  return rescaleBudget(serverRecs, budget);
}

// =====================================================================
// 内部関数
// =====================================================================

/** PredictionEntry[] + ライブオッズ → LiveEntry[] (オッズ差し替え・再計算済み) */
function buildLiveEntries(
  entries: PredictionEntry[],
  raceId: string,
  raceOdds: Record<number, { winOdds: number; placeOddsMin: number | null; placeOddsMax: number | null }> | undefined,
): LiveEntry[] {
  // Step 1: ライブオッズで上書き
  const withOdds = entries.map(e => {
    const live = raceOdds?.[e.umaban];
    const liveWinOdds = (live?.winOdds && live.winOdds > 0) ? live.winOdds : (e.odds || 0);
    const livePlaceMin = live?.placeOddsMin ?? e.place_odds_min ?? null;
    return { entry: e, liveWinOdds, livePlaceMin };
  });

  // Step 2: ライブオッズで人気順を再計算
  const sorted = [...withOdds]
    .filter(x => x.liveWinOdds > 0)
    .sort((a, b) => a.liveWinOdds - b.liveWinOdds);

  const rankMap: Record<number, number> = {};
  sorted.forEach((x, i) => { rankMap[x.entry.umaban] = i + 1; });

  // Step 3: dev_gap計算用 — z-score(model) vs z-score(market)
  const predValues = withOdds.map(({ entry: e }) => e.pred_proba_p_raw ?? e.pred_proba_p ?? 0);
  const impliedValues = withOdds.map(({ liveWinOdds }) => liveWinOdds > 0 ? 1.0 / liveWinOdds : 0);
  const { mean: predMean, std: predStd } = meanStd(predValues);
  const { mean: impMean, std: impStd } = meanStd(impliedValues);

  // Step 4: LiveEntry構築
  return withOdds.map(({ entry: e, liveWinOdds, livePlaceMin }, i) => {
    const liveRank = rankMap[e.umaban] ?? e.odds_rank ?? 99;
    const gap = liveRank - e.rank_p;
    const winGap = liveRank - (e.rank_w ?? e.rank_p);

    // dev_gap計算
    const modelZ = predStd > 0 ? (predValues[i] - predMean) / predStd : 0;
    const marketZ = impStd > 0 ? (impliedValues[i] - impMean) / impStd : 0;
    const devGap = modelZ - marketZ;

    // EV再計算 — calibrated確率を使用（Python IsotonicRegressionと一致）
    const winProb = e.pred_proba_w_cal ?? e.pred_proba_w;
    const winEv = (winProb != null && liveWinOdds > 0)
      ? winProb * liveWinOdds
      : e.win_ev ?? null;
    const placeEv = (e.pred_proba_p_raw != null && livePlaceMin != null && livePlaceMin > 0)
      ? e.pred_proba_p_raw * livePlaceMin
      : e.place_ev ?? null;

    // Composite VB Score
    const vbScore = computeVbScore(devGap, gap, winEv, e.ar_deviation ?? null);

    return {
      umaban: e.umaban,
      horseName: e.horse_name,
      liveOdds: liveWinOdds,
      liveOddsRank: liveRank,
      livePlaceOddsMin: livePlaceMin,
      rankP: e.rank_p,
      rankW: e.rank_w ?? e.rank_p,
      predProbaPRaw: e.pred_proba_p_raw ?? null,
      predProbaP: e.pred_proba_p ?? null,
      predProbaW: e.pred_proba_w ?? null,
      arDeviation: e.ar_deviation ?? null,
      predictedMargin: e.predicted_margin ?? null,
      gap,
      winGap,
      devGap,
      vbScore,
      winEv,
      placeEv,
    };
  });
}

/** mean & std (sample std, min 1e-8) */
function meanStd(values: number[]): { mean: number; std: number } {
  if (values.length === 0) return { mean: 0, std: 1e-8 };
  const mean = values.reduce((s, v) => s + v, 0) / values.length;
  const variance = values.reduce((s, v) => s + (v - mean) ** 2, 0) / values.length;
  return { mean, std: Math.max(Math.sqrt(variance), 1e-8) };
}

/** 1レースN単勝制約 */
function applyWinPerRaceLimit(recs: LiveRec[], maxWin: number): void {
  if (maxWin <= 0) return;

  const winCandidates = recs.filter(r => r.betType === '単勝' || r.betType === '単複');
  if (winCandidates.length <= maxWin) return;

  // vbScore降順ソート (複合スコアで優先順位)
  winCandidates.sort((a, b) =>
    -(a.entry.vbScore - b.entry.vbScore) || -(a.entry.devGap - b.entry.devGap) || -(a.entry.liveOdds - b.entry.liveOdds)
  );

  for (const r of winCandidates.slice(maxWin)) {
    if (r.betType === '単勝') {
      if (r.kellyCapped > 0) {
        r.betType = '複勝';
        r.winAmount = 0;
      } else {
        const idx = recs.indexOf(r);
        if (idx >= 0) recs.splice(idx, 1);
      }
    } else if (r.betType === '単複') {
      r.betType = '複勝';
      r.winAmount = 0;
    }
  }
}

/** Kelly fraction → 実金額変換 + 予算スケーリング */
function applyBudget(recs: LiveRec[], budget: number, params: BetEngineParams): void {
  if (recs.length === 0) return;

  // Place金額を仮計算
  for (const r of recs) {
    if (r.placeAmount > 0) {
      // place_addon等で既にセット済み → そのまま
    } else if ((r.betType === '複勝' || r.betType === '単複') && r.kellyCapped > 0) {
      const raw = r.kellyCapped * budget;
      r.placeAmount = Math.max(params.minBet, roundToUnit(raw, params.betUnit));
    } else if (r.betType === '複勝' && r.kellyCapped <= 0) {
      r.placeAmount = params.minBet;
    }
  }

  // 合計チェック
  const total = recs.reduce((s, r) => s + r.winAmount + r.placeAmount, 0);
  if (total > budget && total > 0) {
    const scale = budget / total;
    for (const r of recs) {
      if (r.winAmount > 0) {
        r.winAmount = Math.max(params.minBet, roundToUnit(r.winAmount * scale, params.betUnit));
      }
      if (r.placeAmount > 0) {
        r.placeAmount = Math.max(params.minBet, roundToUnit(r.placeAmount * scale, params.betUnit));
      }
    }
  }
}

/** クロス配分: strength別に単複金額を分割 */
function applyCrossAllocation(recs: LiveRec[], params: BetEngineParams): void {
  for (const r of recs) {
    const total = r.winAmount + r.placeAmount;
    if (total <= 0) continue;

    const winPct = r.strength === 'strong' ? params.strongWinPct : params.normalWinPct;
    const placePct = 100 - winPct;

    r.winAmount = Math.max(params.minBet, roundToUnit(total * winPct / 100, params.betUnit));
    r.placeAmount = Math.max(params.minBet, roundToUnit(total * placePct / 100, params.betUnit));

    if (r.winAmount > 0 && r.placeAmount > 0) {
      r.betType = '単複';
    } else if (r.winAmount > 0) {
      r.betType = '単勝';
    } else {
      r.betType = '複勝';
    }
  }
}
