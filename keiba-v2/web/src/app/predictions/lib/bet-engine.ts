/**
 * bet-engine.ts — TypeScript版 買い目エンジン
 *
 * Python bet_engine.py のコアロジックをTypeScriptに移植。
 * ライブオッズでの購入プラン再計算に使用。
 *
 * ML出力（rank_v, ar_deviation, pred_proba_v_raw等）は predictions.json から取得し、
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
  winArdGapTiers: [number, number][]; // [minArd, minGap][]
  // ARd VBルート (能力 vs 市場の直接乖離)
  ardVbMinArd: number;   // 0=disabled, 65=recommended
  ardVbMinOdds: number;  // 0=disabled, 10=recommended
  placeMinGap: number;
  placeMinEv: number;
  kellyFraction: number;
  kellyCap: number;
  dangerGapBoost: number;
  crossAlloc: boolean;
  strongWinPct: number;
  normalWinPct: number;
  maxWinPerRace: number;
  minBet: number;
  betUnit: number;
}

// VB Floor: 購入プラン⊆VB候補 を保証する最低条件
// Python bet_engine.py の VB_FLOOR_* と手動同期
const VB_FLOOR = {
  minWinEv: 1.0,
  minArd: 50.0,
  ardVbMinArd: 65.0,
  ardVbMinOdds: 10.0,
} as const;

// --- プリセット (Python PRESETS と完全一致) ---

const ENGINE_PRESETS: Record<ServerPresetKey, BetEngineParams> = {
  standard: {
    winMinGap: 5,
    winMinEv: 1.5,
    winVRatioMin: 0.75,
    winVBypassGap: 7,
    winVBypassEv: 3.0,
    winArdGapTiers: [[65, 3], [55, 4], [45, 5]],
    ardVbMinArd: 65.0,   // ARd VBルート: ARd>=65
    ardVbMinOdds: 10.0,  // ARd VBルート: odds>=10
    placeMinGap: 99, // Place無効化
    placeMinEv: 1.0,
    kellyFraction: 0.25,
    kellyCap: 0.10,
    dangerGapBoost: 0, // v5.33: gap boost廃止
    crossAlloc: false, // v5.35: WinOnly (bankroll sim最適)
    strongWinPct: 100,
    normalWinPct: 100,
    maxWinPerRace: 2,
    minBet: 100,
    betUnit: 100,
  },
  wide: {
    winMinGap: 5,
    winMinEv: 0.0, // EV disabled
    winVRatioMin: 0.75,
    winVBypassGap: 7,
    winVBypassEv: 3.0,
    winArdGapTiers: [[65, 3], [55, 4], [45, 5]],
    ardVbMinArd: 65.0,
    ardVbMinOdds: 10.0,
    placeMinGap: 99,
    placeMinEv: 1.0,
    kellyFraction: 0.25,
    kellyCap: 0.10,
    dangerGapBoost: 0,
    crossAlloc: false, // v5.35: WinOnly (bankroll sim最適)
    strongWinPct: 100,
    normalWinPct: 100,
    maxWinPerRace: 2,
    minBet: 100,
    betUnit: 100,
  },
  aggressive: {
    winMinGap: 5,
    winMinEv: 1.8,
    winVRatioMin: 0.75,
    winVBypassGap: 7,
    winVBypassEv: 3.0,
    winArdGapTiers: [[65, 3], [55, 4], [45, 5]],
    ardVbMinArd: 65.0,
    ardVbMinOdds: 10.0,
    placeMinGap: 99,
    placeMinEv: 1.0,
    kellyFraction: 0.25,
    kellyCap: 0.10,
    dangerGapBoost: 0,
    crossAlloc: false, // v5.35: WinOnly (bankroll sim最適)
    strongWinPct: 100,
    normalWinPct: 100,
    maxWinPerRace: 2,
    minBet: 100,
    betUnit: 100,
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

/** 危険馬検出: odds<=8 & ARd<53 & V%<15% (v5.33) */
function detectDanger(
  entries: LiveEntry[],
): Record<number, boolean> {
  const danger: Record<number, boolean> = {};
  for (const e of entries) {
    const odds = e.liveOdds;
    const ard = e.arDeviation ?? 0;
    const predV = e.predProbaV ?? 0;
    if (odds > 0 && odds <= 8.0 && ard < 53 && predV < 0.15) {
      danger[e.umaban] = true;
    }
  }
  return danger;
}

/**
 * 単勝評価 (Gap primary + EV secondary)
 * Returns [shouldBet, units]
 */
function evaluateWin(
  gap: number,
  params: BetEngineParams,
  isDanger: boolean,
  arDeviation: number | null,
  winEv: number | null,
): [boolean, number] {
  let minGap: number | null = null;

  // ARd段階フィルター
  if (params.winArdGapTiers.length > 0) {
    for (const [tierArd, tierGap] of params.winArdGapTiers) {
      if (arDeviation != null && arDeviation >= tierArd) {
        minGap = tierGap;
        break;
      }
    }
    if (minGap == null) return [false, 0]; // どのティアにも該当しない

    if (isDanger) minGap += params.dangerGapBoost;
    if (gap < minGap) return [false, 0];
  } else {
    // フラット閾値 (フォールバック)
    minGap = params.winMinGap;
    if (isDanger) minGap += params.dangerGapBoost;
    if (gap < minGap) return [false, 0];
  }

  // EV filter (0=disabled)
  if (params.winMinEv > 0) {
    if (winEv == null || winEv < params.winMinEv) return [false, 0];
  }

  // ベット倍率
  let units: number;
  if (gap >= minGap + 3) units = 3;
  else if (gap >= minGap + 1) units = 2;
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
  rankV: number;
  rankWv: number;
  predProbaVRaw: number | null;
  predProbaV: number | null;
  predProbaWv: number | null;
  arDeviation: number | null;
  predictedMargin: number | null;
  // Recalculated
  gap: number;       // liveOddsRank - rankV
  winGap: number;    // liveOddsRank - rankWv
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

    // V%比率用: レース内最大V%
    let raceMaxV = 0;
    if (params.winVRatioMin > 0) {
      raceMaxV = Math.max(0, ...liveEntries.map(e => e.predProbaVRaw ?? 0));
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
      if (!(vbEvOk && vbArdOk) && !vbArdRoute) continue;

      // --- 単勝 pre-filter: V%比率 ---
      let winPrefilterPass: boolean;
      if (params.winVRatioMin > 0) {
        const vPct = e.predProbaVRaw ?? 0;
        const vRatio = raceMaxV > 0 ? vPct / raceMaxV : 0;
        winPrefilterPass = vRatio >= params.winVRatioMin;
        // バイパス
        if (!winPrefilterPass && params.winVBypassGap > 0 && params.winVBypassEv > 0) {
          if (e.gap >= params.winVBypassGap && (e.winEv ?? 0) >= params.winVBypassEv) {
            winPrefilterPass = true;
          }
        }
      } else {
        winPrefilterPass = e.rankV <= 3;
      }

      let winOk = false, winUnits = 0;
      if (winPrefilterPass) {
        [winOk, winUnits] = evaluateWin(
          e.gap, params, isDanger, e.arDeviation, e.winEv,
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
      const placePrefilterPass = params.winVRatioMin > 0 ? winPrefilterPass : e.rankV <= 3;
      let placeOk = false, kellyFrac = 0.0;
      if (placePrefilterPass) {
        [placeOk, kellyFrac] = evaluatePlace(
          e.gap, e.predProbaVRaw, e.livePlaceOddsMin, params, isDanger, e.arDeviation,
        );
      }

      if (!winOk && !placeOk) continue;

      // strength判定 (tier相対)
      let strongGap = params.winMinGap + 2;
      if (params.winArdGapTiers.length > 0 && e.arDeviation != null) {
        for (const [tierArd, tierGap] of params.winArdGapTiers) {
          if (e.arDeviation >= tierArd) {
            strongGap = tierGap + 2;
            break;
          }
        }
      }

      let betType: '単勝' | '複勝' | '単複';
      let strength: 'strong' | 'normal';
      if (winOk && placeOk) {
        betType = '単複';
        strength = (ardVbPass || e.gap >= strongGap || e.gap >= params.placeMinGap + 2) ? 'strong' : 'normal';
      } else if (winOk) {
        betType = '単勝';
        strength = (ardVbPass || e.gap >= strongGap) ? 'strong' : 'normal';
      } else {
        betType = '複勝';
        strength = e.gap >= params.placeMinGap + 2 ? 'strong' : 'normal';
      }

      raceRecs.push({
        raceId: race.race_id,
        entry: e,
        betType,
        strength,
        winAmount: winOk ? winUnits * params.betUnit : 0,
        placeAmount: 0, // apply_budget で設定
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

  // Step 3: LiveEntry構築
  return withOdds.map(({ entry: e, liveWinOdds, livePlaceMin }) => {
    const liveRank = rankMap[e.umaban] ?? e.odds_rank ?? 99;
    const gap = liveRank - e.rank_v;
    const winGap = liveRank - (e.rank_wv ?? e.rank_v);

    // EV再計算 — calibrated確率を使用（Python IsotonicRegressionと一致）
    const winProb = e.pred_proba_wv_cal ?? e.pred_proba_wv;
    const winEv = (winProb != null && liveWinOdds > 0)
      ? winProb * liveWinOdds
      : e.win_ev ?? null;
    const placeEv = (e.pred_proba_v_raw != null && livePlaceMin != null && livePlaceMin > 0)
      ? e.pred_proba_v_raw * livePlaceMin
      : e.place_ev ?? null;

    return {
      umaban: e.umaban,
      horseName: e.horse_name,
      liveOdds: liveWinOdds,
      liveOddsRank: liveRank,
      livePlaceOddsMin: livePlaceMin,
      rankV: e.rank_v,
      rankWv: e.rank_wv ?? e.rank_v,
      predProbaVRaw: e.pred_proba_v_raw ?? null,
      predProbaV: e.pred_proba_v ?? null,
      predProbaWv: e.pred_proba_wv ?? null,
      arDeviation: e.ar_deviation ?? null,
      predictedMargin: e.predicted_margin ?? null,
      gap,
      winGap,
      winEv,
      placeEv,
    };
  });
}

/** 1レースN単勝制約 */
function applyWinPerRaceLimit(recs: LiveRec[], maxWin: number): void {
  if (maxWin <= 0) return;

  const winCandidates = recs.filter(r => r.betType === '単勝' || r.betType === '単複');
  if (winCandidates.length <= maxWin) return;

  winCandidates.sort((a, b) => -(a.entry.gap - b.entry.gap) || -(a.entry.liveOdds - b.entry.liveOdds));

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
    if ((r.betType === '複勝' || r.betType === '単複') && r.kellyCapped > 0) {
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
