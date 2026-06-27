/**
 * gap-tansho.ts — 逆張り単（gap単勝）候補の判定 (Session 178・★表示専用★)
 *
 * Python `ml/strategies/gap_tansho_shadow.select_gap_tansho` の TS 忠実移植 (canonical broad)。
 * ★表示専用★: 推奨画面で「自動投票の逆張り単スリーブが今どの馬を拾うか」を可視化するだけ。
 * 実投票には一切影響しない (投票時は orchestrator が predictions から Python 版を直接呼ぶ)。
 *
 * 条件 (committed broad・docs/market_calibration_edge_map.md §8):
 *   クラス∈{未勝利, 条件(1-3勝クラス), 重賞} ∧ rank_w≤3 ∧ gap(=odds_rank-rank_w)≥5
 *   ∧ win_ev≥1.0 (★全オッズ・odds帯フィルタは過学習で棄却したので付けない★)。
 *   新馬/OP/Listed は対象外 (新馬=モデルも盲目・OP=市場シャープ)。
 *
 * ★注意 (Python と同じ既知の限界)★: odds_rank は predictions の値 (= 朝/直前オッズ由来)。
 * grade が空のレース (keibabook ビルダーはクラスを race_name に入れる) は race_name で
 * クラス判定する。重賞は race_name='○○ステークス' で G 判定不可なため拾えない (sleeve も同様)。
 */
/**
 * selectGapTansho が必要とする最小構造型。PredictionRace（/predictions）も
 * ExecuteTab の軽量 race 型（/bankroll・実行時は predictions.json 全文）も構造的にこれを満たす。
 */
export interface GapRaceLike {
  grade?: string;
  race_name?: string;
  entries?: Array<{
    umaban?: number | null;
    horse_name?: string;
    rank_w?: number | null;
    odds_rank?: number | null;
    odds?: number | null;
    win_ev?: number | null;
  }> | null;
}

// committed broad パラメータ (gap_tansho_shadow.DEFAULT_PARAMS と同値・odds帯は付けない)
export const GAP_TANSHO_PARAMS = {
  predRankMax: 3,
  gapMin: 5,
  winEvFloor: 1.0,
} as const;

// 対象クラス (gap_tansho_shadow.EDGE_BUCKETS = 未勝利 / 条件(1-3勝) / 重賞)
const EDGE_BUCKETS = new Set(['miSHOURI', 'jouken', 'juushou']);

/** grade/race_name をエッジ判定クラスに正規化 (Python `_bucket` と同一)。 */
export function gapBucket(gradeOrName: string | undefined | null): string {
  const g = String(gradeOrName ?? '');
  if (g.includes('新馬')) return 'shinba';
  if (g.includes('未勝利')) return 'miSHOURI';
  if (g.includes('クラス')) return 'jouken';
  if (g === 'OP' || g === 'Listed') return 'OP/L';
  if (g.startsWith('G')) return 'juushou';
  return 'other';
}

export interface GapTanshoPick {
  umaban: number;
  horseName: string;
  rankW: number;
  oddsRank: number;
  gap: number;        // odds_rank - rank_w (AI上位なのに人気薄=過小評価の度合い)
  odds: number;
  winEv: number;
  cls: string;        // miSHOURI / jouken / juushou
}

/**
 * 1レースの逆張り単候補を返す (該当なし=[])。Python `select_gap_tansho` と同条件・同ソート。
 * 信号強度 (win_ev) 降順。top_k は付けない (committed broad = 該当馬全頭)。
 */
export function selectGapTansho(race: GapRaceLike): GapTanshoPick[] {
  const bucket = gapBucket(race.grade || race.race_name);
  if (!EDGE_BUCKETS.has(bucket)) return [];
  const picks: GapTanshoPick[] = [];
  for (const e of race.entries ?? []) {
    const rankW = e.rank_w;
    const oddsRank = e.odds_rank;
    const odds = e.odds;
    const winEv = e.win_ev;
    if (e.umaban == null || rankW == null || oddsRank == null
        || odds == null || winEv == null) {
      continue;
    }
    const gap = oddsRank - rankW;
    if (rankW <= GAP_TANSHO_PARAMS.predRankMax
        && gap >= GAP_TANSHO_PARAMS.gapMin
        && winEv >= GAP_TANSHO_PARAMS.winEvFloor) {
      picks.push({
        umaban: e.umaban,
        horseName: e.horse_name ?? '',
        rankW,
        oddsRank,
        gap,
        odds,
        winEv: Math.round(winEv * 100) / 100,
        cls: bucket,
      });
    }
  }
  picks.sort((a, b) => b.winEv - a.winEv);
  return picks;
}

/** クラスの日本語ラベル (バッジ/ツールチップ用)。 */
export function gapClassLabel(cls: string): string {
  return cls === 'miSHOURI' ? '未勝利' : cls === 'jouken' ? '条件' : cls === 'juushou' ? '重賞' : cls;
}
