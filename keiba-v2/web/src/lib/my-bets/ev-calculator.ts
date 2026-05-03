/**
 * EV計算エンジン
 *
 * 各馬の (p1, p2, p3) を構築し、各券種の組合せ確率と EV を計算する。
 *
 * 確率合成方針:
 *   - 各位置 (1着/2着/3着) で全馬合計が1になるよう独立に正規化
 *   - 馬単/三連単等の順序付き券種: P(i→j→k) ∝ p1[i] * p2[j] * p3[k] (i,j,k 全て異なる)
 *     全有効組合せの合計で割って正規化
 *   - 馬連/三連複: 順序付きの全パーミュテーション合計
 *   - ワイド: i,j が 1-2,1-3,2-3 のいずれかに入る確率合計
 *
 * 厳密な確率モデル(Plackett-Luce/Harville)ではなく、独立近似。
 * 印の意味を素直に反映でき、計算高速。
 */

import {
  MARK_PROBS,
  NO_MARK_FALLBACK,
  PositionalProb,
} from './probability-table';
import { ComboOdds, pairKey, orderedPairKey, trioKey, orderedTrioKey } from '../data/db-odds-combo';

// --- 入力型 ---

export interface HorseInput {
  umaban: number;
  mark: string; // '◎','○','▲','△','★','穴',''
  /** ML予測 1着確率（pred_proba_w_cal）。無印馬の主要ソース */
  mlWinProba?: number | null;
  /** ML予測 複勝確率（pred_proba_p）。無印馬の3着内確率近似 */
  mlPlaceProba?: number | null;
  /** 単勝オッズ（参考表示用） */
  winOdds?: number | null;
  /** 複勝オッズ最小・最大（参考表示用） */
  placeOddsMin?: number | null;
  placeOddsMax?: number | null;
}

export interface NormalizedHorse {
  umaban: number;
  mark: string;
  /** 正規化前の素確率 */
  rawProb: PositionalProb;
  /** 正規化後（位置ごとに sum=1） */
  prob: PositionalProb;
}

// --- 確率構築 ---

/**
 * 各馬の素確率を計算（印テーブル or ML予測）
 */
function buildRawProb(horse: HorseInput): PositionalProb {
  if (horse.mark && MARK_PROBS[horse.mark]) {
    return { ...MARK_PROBS[horse.mark] };
  }
  // 無印: ML予測から借用
  const p1 = horse.mlWinProba ?? null;
  const pPlace = horse.mlPlaceProba ?? null;

  if (p1 !== null && pPlace !== null) {
    // 複勝確率 ≈ p1+p2+p3 → 残り(p2+p3)を均等配分
    const remaining = Math.max(0, pPlace - p1);
    const p23 = remaining / 2;
    return { p1, p2: p23, p3: p23 };
  }
  if (p1 !== null) {
    // 1着確率のみ → 2-3着は控えめに同程度
    return { p1, p2: p1 * 0.8, p3: p1 * 0.6 };
  }
  return { ...NO_MARK_FALLBACK };
}

/**
 * 全馬の確率を構築・正規化
 */
export function normalizeHorses(horses: HorseInput[]): NormalizedHorse[] {
  const raw = horses.map((h) => ({
    umaban: h.umaban,
    mark: h.mark,
    rawProb: buildRawProb(h),
  }));

  let sumP1 = 0,
    sumP2 = 0,
    sumP3 = 0;
  for (const r of raw) {
    sumP1 += r.rawProb.p1;
    sumP2 += r.rawProb.p2;
    sumP3 += r.rawProb.p3;
  }
  // ゼロ除算ガード
  sumP1 = sumP1 > 0 ? sumP1 : 1;
  sumP2 = sumP2 > 0 ? sumP2 : 1;
  sumP3 = sumP3 > 0 ? sumP3 : 1;

  return raw.map((r) => ({
    umaban: r.umaban,
    mark: r.mark,
    rawProb: r.rawProb,
    prob: {
      p1: r.rawProb.p1 / sumP1,
      p2: r.rawProb.p2 / sumP2,
      p3: r.rawProb.p3 / sumP3,
    },
  }));
}

// --- 組合せ確率（正規化込み） ---

interface ProbMap {
  [umaban: number]: PositionalProb;
}

function buildProbMap(horses: NormalizedHorse[]): ProbMap {
  const m: ProbMap = {};
  for (const h of horses) m[h.umaban] = h.prob;
  return m;
}

/**
 * 順序付きペア (i→j) の正規化確率
 * P(i 1着 ∧ j 2着) ∝ p1[i] * p2[j], 全 i≠j で正規化
 */
export function umatanProbabilities(horses: NormalizedHorse[]): Map<string, number> {
  const probMap = buildProbMap(horses);
  const umabans = horses.map((h) => h.umaban);
  let total = 0;
  const raw = new Map<string, number>();
  for (const i of umabans) {
    for (const j of umabans) {
      if (i === j) continue;
      const v = probMap[i].p1 * probMap[j].p2;
      raw.set(orderedPairKey(i, j), v);
      total += v;
    }
  }
  if (total <= 0) return raw;
  const out = new Map<string, number>();
  for (const [k, v] of raw) out.set(k, v / total);
  return out;
}

/** 馬連 P({i,j}) = P(i→j) + P(j→i) */
export function umarenProbabilities(horses: NormalizedHorse[]): Map<string, number> {
  const umatan = umatanProbabilities(horses);
  const out = new Map<string, number>();
  for (const [k, v] of umatan) {
    const [a, b] = k.split('-').map(Number);
    const key = pairKey(a, b);
    out.set(key, (out.get(key) ?? 0) + v);
  }
  return out;
}

/**
 * 順序付きトリオ (i→j→k) の正規化確率
 * P(i 1着 ∧ j 2着 ∧ k 3着) ∝ p1[i] * p2[j] * p3[k]
 */
export function sanrentanProbabilities(horses: NormalizedHorse[]): Map<string, number> {
  const probMap = buildProbMap(horses);
  const umabans = horses.map((h) => h.umaban);
  let total = 0;
  const raw = new Map<string, number>();
  for (const i of umabans) {
    for (const j of umabans) {
      if (i === j) continue;
      for (const k of umabans) {
        if (k === i || k === j) continue;
        const v = probMap[i].p1 * probMap[j].p2 * probMap[k].p3;
        raw.set(orderedTrioKey(i, j, k), v);
        total += v;
      }
    }
  }
  if (total <= 0) return raw;
  const out = new Map<string, number>();
  for (const [k, v] of raw) out.set(k, v / total);
  return out;
}

/** 三連複 P({i,j,k}) = 6パーミュテーションの合計 */
export function sanrenpukuProbabilities(horses: NormalizedHorse[]): Map<string, number> {
  const sanrentan = sanrentanProbabilities(horses);
  const out = new Map<string, number>();
  for (const [k, v] of sanrentan) {
    const [a, b, c] = k.split('-').map(Number);
    const key = trioKey(a, b, c);
    out.set(key, (out.get(key) ?? 0) + v);
  }
  return out;
}

/**
 * ワイド P({i,j} 共に3着内)
 * = P(i,jが1-2着) + P(i,jが1-3着) + P(i,jが2-3着) (順序問わず)
 */
export function wideProbabilities(horses: NormalizedHorse[]): Map<string, number> {
  const probMap = buildProbMap(horses);
  const umabans = horses.map((h) => h.umaban);
  let total = 0;
  const raw = new Map<string, number>();
  // 全 ordered triples (i,j,k 異なる) のうち、各 unordered pair {i,j} ⊂ top3 をカウント
  for (const i of umabans) {
    for (const j of umabans) {
      if (i === j) continue;
      for (const k of umabans) {
        if (k === i || k === j) continue;
        const w = probMap[i].p1 * probMap[j].p2 * probMap[k].p3;
        total += w;
        // 3つの unordered pair それぞれに加算
        const pairs: [number, number][] = [
          [i, j],
          [i, k],
          [j, k],
        ];
        for (const [a, b] of pairs) {
          const key = pairKey(a, b);
          raw.set(key, (raw.get(key) ?? 0) + w);
        }
      }
    }
  }
  if (total <= 0) return raw;
  const out = new Map<string, number>();
  for (const [k, v] of raw) out.set(k, v / total);
  return out;
}

// --- EV計算 ---

export type BetType = 'tansho' | 'fukusho' | 'umaren' | 'umatan' | 'wide' | 'sanrenpuku' | 'sanrentan';

export interface BetCandidate {
  betType: BetType;
  /** 馬番リスト（単勝=1, 馬連/馬単/ワイド=2, 三連複/三連単=3） */
  horses: number[];
  /** 推定確率 */
  probability: number;
  /** 採用オッズ */
  odds: number;
  /** EV = probability * odds */
  ev: number;
  /** 人気順位（取得できれば） */
  ninki?: number | null;
  /** 関与する印リスト（戦略フィルタで使用） */
  marks: string[];
}

/**
 * 全候補を生成・EV評価
 *
 * @param horses 正規化済み馬リスト
 * @param odds 全券種オッズ
 * @param horseToMark 馬番→印 マップ
 */
export function evaluateAllCandidates(
  horses: NormalizedHorse[],
  odds: ComboOdds & {
    tansho: Map<number, { odds: number; ninki: number | null }>;
    fukusho: Map<number, { oddsMin: number; oddsMax: number; ninki: number | null }>;
  },
  horseToMark: Record<number, string>
): BetCandidate[] {
  const out: BetCandidate[] = [];
  const probMap = buildProbMap(horses);
  const markFor = (u: number) => horseToMark[u] ?? '';

  // 単勝
  for (const h of horses) {
    const o = odds.tansho.get(h.umaban);
    if (!o) continue;
    const p = h.prob.p1;
    out.push({
      betType: 'tansho',
      horses: [h.umaban],
      probability: p,
      odds: o.odds,
      ev: p * o.odds,
      ninki: o.ninki,
      marks: [markFor(h.umaban)],
    });
  }

  // 複勝（複勝確率 = p1+p2+p3、オッズは最小値で評価=保守的）
  for (const h of horses) {
    const f = odds.fukusho.get(h.umaban);
    if (!f) continue;
    const p = h.prob.p1 + h.prob.p2 + h.prob.p3;
    out.push({
      betType: 'fukusho',
      horses: [h.umaban],
      probability: p,
      odds: f.oddsMin,
      ev: p * f.oddsMin,
      ninki: f.ninki,
      marks: [markFor(h.umaban)],
    });
  }

  // 馬連
  const umarenP = umarenProbabilities(horses);
  for (const [k, p] of umarenP) {
    const o = odds.umaren.get(k);
    if (!o) continue;
    const [a, b] = k.split('-').map(Number);
    out.push({
      betType: 'umaren',
      horses: [a, b],
      probability: p,
      odds: o.odds,
      ev: p * o.odds,
      ninki: o.ninki,
      marks: [markFor(a), markFor(b)],
    });
  }

  // 馬単
  const umatanP = umatanProbabilities(horses);
  for (const [k, p] of umatanP) {
    const o = odds.umatan.get(k);
    if (!o) continue;
    const [a, b] = k.split('-').map(Number);
    out.push({
      betType: 'umatan',
      horses: [a, b],
      probability: p,
      odds: o.odds,
      ev: p * o.odds,
      ninki: o.ninki,
      marks: [markFor(a), markFor(b)],
    });
  }

  // ワイド（オッズは最小値で保守的に）
  const wideP = wideProbabilities(horses);
  for (const [k, p] of wideP) {
    const o = odds.wide.get(k);
    if (!o) continue;
    const [a, b] = k.split('-').map(Number);
    out.push({
      betType: 'wide',
      horses: [a, b],
      probability: p,
      odds: o.oddsMin,
      ev: p * o.oddsMin,
      ninki: o.ninki,
      marks: [markFor(a), markFor(b)],
    });
  }

  // 三連複
  const sanrenpukuP = sanrenpukuProbabilities(horses);
  for (const [k, p] of sanrenpukuP) {
    const o = odds.sanrenpuku.get(k);
    if (!o) continue;
    const [a, b, c] = k.split('-').map(Number);
    out.push({
      betType: 'sanrenpuku',
      horses: [a, b, c],
      probability: p,
      odds: o.odds,
      ev: p * o.odds,
      ninki: o.ninki,
      marks: [markFor(a), markFor(b), markFor(c)],
    });
  }

  // 三連単
  const sanrentanP = sanrentanProbabilities(horses);
  for (const [k, p] of sanrentanP) {
    const o = odds.sanrentan.get(k);
    if (!o) continue;
    const [a, b, c] = k.split('-').map(Number);
    out.push({
      betType: 'sanrentan',
      horses: [a, b, c],
      probability: p,
      odds: o.odds,
      ev: p * o.odds,
      ninki: o.ninki,
      marks: [markFor(a), markFor(b), markFor(c)],
    });
  }

  // probMap参照警告抑制（将来拡張用）
  void probMap;
  return out;
}
