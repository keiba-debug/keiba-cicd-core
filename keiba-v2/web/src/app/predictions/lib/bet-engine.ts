/**
 * bet-engine.ts — TypeScript版 買い目エンジン
 *
 * v7.3: Intersection Filter方式に移行。
 * rank_w=1 の馬に対して win_vb_gap × win_ev × predicted_margin の
 * 3条件交差でフィルタ。複勝は買わない（全条件マイナスROI）。
 *
 * v8.0: Adaptive Rules — 条件別Kelly率。
 * relaxed条件の買い目に対し、マッチしたルールでKelly率を変える。
 * danger_sniper(K1/3) > high_ev_win(K1/4) > relaxed_base(K1/8)
 *
 * ML出力（rank_w, pred_proba_w_cal, predicted_margin等）は predictions.json から取得し、
 * オッズのみ mykeibadb の最新値で上書きして再計算する。
 */

import type { PredictionRace, PredictionEntry, ServerBetRecommendation } from '@/lib/data/predictions-reader';
import type { OddsMap } from './types';
import type { ServerPresetKey, AllocMode } from './bet-logic';
import { rescaleBudget, equalDistribute } from './bet-logic';

// =====================================================================
// パラメータ定義 — Intersection Filter
// =====================================================================

interface IntersectionParams {
  maxRankW: number;       // Winモデル順位上限 (1 = top 1のみ)
  minWinGap: number;      // min win_vb_gap (liveOddsRank - rankW)
  minWinEv: number;       // min win EV (calibrated prob × odds)
  maxMargin: number;      // max predicted_margin (接戦フィルタ)
  maxWinPerRace: number;  // 1レース最大単勝数
  minBet: number;
  betUnit: number;
}

// --- プリセット ---
// ライブ margin 補正: バックテスト最適値 43.4 + 16pt = 59.4
// ライブ予測の predicted_margin はバックテスト(確定データ)より平均+15.3pt高い
// 回帰式: BT_margin = 0.876 × PJ_margin - 8.6
const LIVE_MARGIN_OFFSET = 16;

const ENGINE_PRESETS: Record<ServerPresetKey, IntersectionParams> = {
  adaptive: {
    maxRankW: 1,
    minWinGap: 2,
    minWinEv: 1.3,
    maxMargin: 43.4 + LIVE_MARGIN_OFFSET,
    maxWinPerRace: 1,
    minBet: 100,
    betUnit: 100,
  },
  relaxed: {
    maxRankW: 1,
    minWinGap: 2,
    minWinEv: 1.3,
    maxMargin: 43.4 + LIVE_MARGIN_OFFSET,
    maxWinPerRace: 1,
    minBet: 100,
    betUnit: 100,
  },
  intersection: {
    maxRankW: 1,
    minWinGap: 4,
    minWinEv: 1.3,
    maxMargin: 43.4 + LIVE_MARGIN_OFFSET,
    maxWinPerRace: 1,
    minBet: 100,
    betUnit: 100,
  },
};

// =====================================================================
// 危険馬検出 (Python bet_engine.py detect_danger と同一基準)
// =====================================================================

/** 危険馬: odds<=8 & ARd<53 & P%<15% */
function detectDanger(entries: LiveEntry[]): Set<number> {
  const danger = new Set<number>();
  for (const e of entries) {
    if (e.liveOdds > 0 && e.liveOdds <= 8
        && (e.arDeviation ?? 100) < 53
        && (e.predProbaPRaw ?? 1) < 0.15) {
      danger.add(e.umaban);
    }
  }
  return danger;
}

// =====================================================================
// Adaptive Rules — ルール別Kelly率
// =====================================================================

interface AdaptiveRule {
  name: string;
  description: string;
  requireDanger?: boolean;    // true=危険馬あり必須
  minWinGap: number;
  minWinEv: number;
  kellyFraction: number;      // K1/3=0.33, K1/4=0.25, K1/8=0.125
}

const ADAPTIVE_RULES: AdaptiveRule[] = [
  {
    name: 'danger_sniper',
    description: '危険馬レース狙い撃ち (K1/3)',
    requireDanger: true,
    minWinGap: 4,
    minWinEv: 1.3,
    kellyFraction: 0.33,
  },
  {
    name: 'high_ev_win',
    description: '高EV単勝 (K1/4)',
    minWinGap: 2,
    minWinEv: 1.3,
    kellyFraction: 0.25,
  },
];

/** 馬にマッチする最初のルールを返す */
function matchAdaptiveRule(
  entry: LiveEntry,
  hasDanger: boolean,
): AdaptiveRule | null {
  for (const rule of ADAPTIVE_RULES) {
    if (rule.requireDanger && !hasDanger) continue;
    if (entry.winGap < rule.minWinGap) continue;
    if ((entry.winEv ?? 0) < rule.minWinEv) continue;
    return rule;
  }
  return null;
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
  gap: number;       // liveOddsRank - rankP (表示用)
  winGap: number;    // liveOddsRank - rankW (Intersection Filter用)
  devGap: number;    // z-score(model) - z-score(market) (表示用)
  vbScore: number;   // composite VB score (表示用, 0-10)
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
  adaptiveRule?: string;
}

// =====================================================================
// コア関数
// =====================================================================

/** 金額を unit 単位に丸める (切り捨て) */
function roundToUnit(amount: number, unit: number = 100): number {
  return Math.floor(amount / unit) * unit;
}

/**
 * コンポジットVBスコア (表示用 — フィルタリングには使わない)
 */
function computeVbScore(
  devGap: number,
  gap: number,
  winEv: number | null,
  arDeviation: number | null,
): number {
  let score = 0.0;
  if (devGap >= 1.5) score += 3.0;
  else if (devGap >= 1.0) score += 2.0;
  else if (devGap >= 0.5) score += 1.0;
  if (gap >= 7) score += 3.0;
  else if (gap >= 5) score += 2.0;
  else if (gap >= 3) score += 1.0;
  const ev = winEv ?? 0;
  if (ev >= 2.0) score += 2.0;
  else if (ev >= 1.5) score += 1.5;
  else if (ev >= 1.0) score += 1.0;
  const ard = arDeviation ?? 0;
  if (ard >= 65) score += 2.0;
  else if (ard >= 55) score += 1.5;
  else if (ard >= 50) score += 1.0;
  return score;
}

/** Kelly Criterion: f* = (b*p - q) / b */
function calcKellyFraction(prob: number, odds: number): number {
  const b = odds - 1.0;
  if (b <= 0 || prob <= 0) return 0.0;
  const q = 1.0 - prob;
  const f = (b * prob - q) / b;
  return Math.max(0.0, f);
}

// =====================================================================
// パイプライン
// =====================================================================

/**
 * ライブオッズで購入プラン再計算
 *
 * Intersection Filter: rank_w=1 × winGap × winEv × margin
 * 単勝のみ（複勝は全条件でマイナスROI）
 *
 * adaptive プリセット: relaxed と同じフィルタだが、
 * ルール別Kelly率でベット額を変える。
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

  const isAdaptive = presetKey === 'adaptive';
  const allRecs: LiveRec[] = [];

  for (const race of races) {
    const raceOdds = oddsMap[race.race_id];
    const liveEntries = buildLiveEntries(race.entries, race.race_id, raceOdds);
    if (liveEntries.length === 0) continue;

    // 危険馬検出 (adaptive用)
    const dangerSet = isAdaptive ? detectDanger(liveEntries) : new Set<number>();
    const hasDanger = dangerSet.size > 0;

    const raceRecs: LiveRec[] = [];

    for (const e of liveEntries) {
      // === Intersection Filter ===
      if (e.rankW > params.maxRankW) continue;
      if (e.winGap < params.minWinGap) continue;
      if ((e.winEv ?? 0) < params.minWinEv) continue;
      if ((e.predictedMargin ?? 100) > params.maxMargin) continue;

      // adaptive: ルールマッチング
      let adaptiveRule: string | undefined;
      let kellyCapped = 0;
      if (isAdaptive) {
        const rule = matchAdaptiveRule(e, hasDanger);
        if (rule) {
          adaptiveRule = rule.name;
          // Kelly計算: raw f* × rule.kellyFraction
          const winProb = e.predProbaW ?? ((e.winEv ?? 0) / Math.max(e.liveOdds, 1));
          if (winProb > 0 && e.liveOdds > 1) {
            const rawF = calcKellyFraction(winProb, e.liveOdds);
            kellyCapped = rawF * rule.kellyFraction;
          }
        }
      }

      raceRecs.push({
        raceId: race.race_id,
        entry: e,
        betType: '単勝',
        strength: e.winGap >= 6 ? 'strong' : 'normal',
        winAmount: params.betUnit,
        placeAmount: 0,
        kellyRaw: 0,
        kellyCapped,
        isDanger: dangerSet.has(e.umaban),
        dangerScore: dangerSet.has(e.umaban) ? 1 : 0,
        adaptiveRule,
      });
    }

    // 1レースN単勝制約 (winEv順で優先)
    if (params.maxWinPerRace > 0 && raceRecs.length > params.maxWinPerRace) {
      raceRecs.sort((a, b) => (b.entry.winEv ?? 0) - (a.entry.winEv ?? 0));
      raceRecs.splice(params.maxWinPerRace);
    }

    allRecs.push(...raceRecs);
  }

  // 予算スケーリング
  if (allRecs.length > 0) {
    if (isAdaptive) {
      // adaptive: Kelly率ベースで配分
      // kellyCapped > 0 の比率で予算を按分
      const totalKelly = allRecs.reduce((s, r) => s + Math.max(r.kellyCapped, 0.01), 0);
      for (const r of allRecs) {
        const share = Math.max(r.kellyCapped, 0.01) / totalKelly;
        r.winAmount = Math.max(params.minBet, roundToUnit(budget * share, params.betUnit));
      }
    } else {
      // 均等配分
      const perBet = Math.max(params.minBet, roundToUnit(budget / allRecs.length, params.betUnit));
      for (const r of allRecs) {
        r.winAmount = perBet;
      }
    }
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
    adaptive_rule: r.adaptiveRule,
  }));

  // allocMode に応じた配分
  if (isAdaptive) {
    // adaptive は Kelly率ベース配分済み → そのまま返す
    return serverRecs;
  }
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
  _raceId: string,
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

    // EV再計算 — calibrated確率を使用
    const winProb = e.pred_proba_w_cal ?? e.pred_proba_w;
    const winEv = (winProb != null && liveWinOdds > 0)
      ? winProb * liveWinOdds
      : e.win_ev ?? null;
    const placeEv = (e.pred_proba_p_raw != null && livePlaceMin != null && livePlaceMin > 0)
      ? e.pred_proba_p_raw * livePlaceMin
      : e.place_ev ?? null;

    // Composite VB Score (表示用)
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

/** mean & std (population std, min 1e-8) */
function meanStd(values: number[]): { mean: number; std: number } {
  if (values.length === 0) return { mean: 0, std: 1e-8 };
  const mean = values.reduce((s, v) => s + v, 0) / values.length;
  const variance = values.reduce((s, v) => s + (v - mean) ** 2, 0) / values.length;
  return { mean, std: Math.max(Math.sqrt(variance), 1e-8) };
}
