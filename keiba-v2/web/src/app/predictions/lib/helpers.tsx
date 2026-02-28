import type { PredictionRace, PredictionEntry } from '@/lib/data/predictions-reader';
import type { OddsMap, DangerInfo, SortDir, SortState } from './types';

// --- ★スコア（おいしさ）---

/** winGap + rating から★スコアを算出 (3=★★★, 2=★★, 1=★, 0=条件外) */
export function getStarScore(winGap: number, rating: number): number {
  if (rating < 56.6) return 0;
  if (winGap >= 7) return 3;
  if (winGap >= 6) return 2;
  if (winGap >= 5) return 1;
  return 0;
}

/** ★スコアの表示文字列 */
export function getStarDisplay(score: number): string {
  if (score >= 3) return '\u2605\u2605\u2605';
  if (score === 2) return '\u2605\u2605';
  if (score === 1) return '\u2605';
  return '-';
}

/** ★スコアの色クラス */
export function getStarColor(score: number): string {
  if (score >= 3) return 'text-amber-500 font-bold';
  if (score === 2) return 'text-indigo-500 font-bold';
  if (score === 1) return 'text-gray-400';
  return 'text-gray-300';
}

/** AR (Aura Rating) の色クラス (>=68 green, 58-68 normal, 56.6-58 yellow, <56.6 gray) */
export function getArColor(rating: number | null | undefined): string {
  if (rating == null) return 'text-gray-300';
  if (rating >= 68) return 'text-green-600 font-bold';
  if (rating >= 58) return '';
  if (rating >= 56.6) return 'text-yellow-600';
  return 'text-gray-400';
}

/** @deprecated Use getArColor instead */
export const getRatingColor = getArColor;

/** ARd (AR偏差値) の色クラス */
export function getArdColor(ard: number | null | undefined): string {
  if (ard == null) return 'text-gray-400';
  if (ard >= 60) return 'text-green-600 font-bold';
  if (ard >= 50) return 'text-blue-600 font-bold';
  if (ard >= 45) return 'text-yellow-600';
  return 'text-gray-400';
}

/** グレードバッジの色クラス */
export function getGradeBadgeClass(grade: string | undefined): string {
  if (!grade) return 'border-gray-300 text-gray-600 dark:border-gray-600 dark:text-gray-400';
  if (grade === 'G1' || grade === 'GI') return 'bg-amber-100 text-amber-800 border-amber-400 dark:bg-amber-900/40 dark:text-amber-300 dark:border-amber-700 font-bold';
  if (/^G[23]$|^G[II]{2,3}$/.test(grade)) return 'bg-purple-100 text-purple-800 border-purple-300 dark:bg-purple-900/40 dark:text-purple-300 dark:border-purple-700';
  if (grade === 'L' || grade === '(L)' || grade === 'Listed') return 'bg-blue-100 text-blue-800 border-blue-300 dark:bg-blue-900/40 dark:text-blue-300 dark:border-blue-700';
  if (grade === 'OP' || grade === 'オープン' || grade === 'OPEN') return 'bg-green-100 text-green-800 border-green-300 dark:bg-green-900/40 dark:text-green-300 dark:border-green-700';
  // 条件戦 (3勝, 2勝, 1勝, 未勝利, 新馬)
  return 'border-gray-300 text-gray-500 dark:border-gray-600 dark:text-gray-400';
}

// --- 色・スタイル ---

export function getGapColor(gap: number): string {
  if (gap >= 5) return 'text-red-600 font-bold';
  if (gap >= 4) return 'text-orange-600 font-bold';
  if (gap >= 3) return 'text-amber-600 font-semibold';
  if (gap >= 2) return 'text-blue-600';
  return 'text-gray-500';
}

export function getGapBg(gap: number): string {
  if (gap >= 5) return 'bg-red-50 dark:bg-red-900/20';
  if (gap >= 4) return 'bg-orange-50 dark:bg-orange-900/20';
  if (gap >= 3) return 'bg-amber-50 dark:bg-amber-900/20';
  return '';
}

export function getMarkColor(mark: string): string {
  if (mark === '◎') return 'text-red-600 font-bold';
  if (mark === '◯' || mark === '○') return 'text-blue-600 font-bold';
  if (mark === '▲') return 'text-green-600 font-bold';
  if (mark === '△') return 'text-orange-500';
  return 'text-gray-400';
}

export function getEvColor(ev: number | null | undefined): string {
  if (ev == null) return 'text-gray-400';
  if (ev >= 2.0) return 'text-amber-600 font-bold';
  if (ev >= 1.5) return 'text-red-500 font-bold';
  if (ev >= 1.2) return 'text-green-600 font-bold';
  if (ev >= 1.0) return 'text-green-500 font-semibold';
  if (ev >= 0.8) return 'text-yellow-600';
  return 'text-gray-400';
}

export function getFinishColor(pos: number): string {
  if (pos === 1) return 'text-amber-500 font-bold';
  if (pos === 2) return 'text-gray-500 font-bold';
  if (pos === 3) return 'text-orange-700 font-bold';
  if (pos <= 5) return 'font-semibold';
  return 'text-muted-foreground';
}

export function getFinishBg(pos: number): string {
  if (pos === 1) return 'bg-amber-50/60 dark:bg-amber-900/15';
  if (pos <= 3) return 'bg-green-50/40 dark:bg-green-900/10';
  return '';
}

export function getTrackBadgeClass(trackType: string): string {
  if (trackType === '芝' || trackType === 'turf') return 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300';
  if (trackType === 'ダ' || trackType === 'dirt') return 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300';
  if (trackType === '障' || trackType === 'obstacle') return 'bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300';
  return 'bg-gray-100 text-gray-600';
}

export function getTrackLabel(trackType: string): string {
  if (trackType === '芝' || trackType === 'turf') return '芝';
  if (trackType === 'ダ' || trackType === 'dirt') return 'ダ';
  if (trackType === '障' || trackType === 'obstacle') return '障';
  return '?';
}

export function getRecBadgeClass(type: string, strength: string): string {
  if (type === '単勝') {
    return strength === 'strong'
      ? 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300 font-bold'
      : 'bg-red-50 text-red-600 dark:bg-red-900/20 dark:text-red-400';
  }
  if (type === '複勝') {
    return strength === 'strong'
      ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300 font-bold'
      : 'bg-blue-50 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400';
  }
  if (type === '単複') {
    return 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300 font-bold';
  }
  return '';
}

// --- トラック判定 ---

export function isTurf(trackType: string): boolean {
  return trackType === '芝' || trackType === 'turf';
}

export function isDirt(trackType: string): boolean {
  return trackType === 'ダ' || trackType === 'dirt';
}

// --- リンク ---

export function getRaceLink(race: PredictionRace): string {
  const [y, m, d] = [race.date.slice(0, 4), race.date.slice(5, 7), race.date.slice(8, 10)];
  return `/races-v2/${y}-${m}-${d}/${race.venue_name}/${race.race_id}`;
}

// --- オッズ・EV計算 ---

export function getWinOdds(odds: OddsMap, raceId: string, umaban: number, fallback: number): number | null {
  const raceOdds = odds[raceId];
  if (raceOdds && raceOdds[umaban]?.winOdds > 0) return raceOdds[umaban].winOdds;
  if (fallback > 0) return fallback;
  return null;
}

export function getPlaceOddsMin(odds: OddsMap, raceId: string, umaban: number): number | null {
  const entry = odds[raceId]?.[umaban];
  return entry?.placeOddsMin ?? null;
}

export function calcWinEv(entry: { pred_proba_wv_cal?: number; pred_proba_wv?: number; pred_proba_v: number }, winOdds: number | null): number | null {
  if (!winOdds || winOdds <= 0) return null;
  // Use calibrated probability (IsotonicRegression) for EV calculation — matches Python's logic
  const prob = entry.pred_proba_wv_cal ?? entry.pred_proba_wv ?? entry.pred_proba_v;
  return prob * winOdds;
}

export function calcPlaceEv(probV: number, placeOddsMin: number | undefined | null): number | null {
  if (!placeOddsMin || placeOddsMin <= 0) return null;
  return probV * placeOddsMin;
}

/**
 * バックテスト実績確率による補正 Win EV
 * 個別モデルP(win)ではなく、gap別の実績的中率 × 個別オッズ
 */
export function calcCorrectedWinEv(gap: number, winOdds: number | null, empiricalWinRate: number): number | null {
  if (!winOdds || winOdds <= 0) return null;
  return empiricalWinRate * winOdds;
}

/**
 * バックテスト実績確率による補正 Place EV
 * 個別モデルP(top3)ではなく、gap別の実績的中率 × 個別複勝オッズ
 */
export function calcCorrectedPlaceEv(gap: number, placeOddsMin: number | undefined | null, empiricalPlaceRate: number): number | null {
  if (!placeOddsMin || placeOddsMin <= 0) return null;
  return empiricalPlaceRate * placeOddsMin;
}

export function calcHeadRatio(probWV: number | undefined, probV: number): number | null {
  if (!probWV || probV <= 0) return null;
  return probWV / probV;
}

export function getPlaceLimit(numRunners: number): number {
  if (numRunners >= 8) return 3;
  if (numRunners >= 5) return 2;
  return 0;
}

// --- 降格ローテ ---

export function getKoukakuDetail(entry: PredictionEntry): string {
  const patterns: string[] = [];
  if (entry.is_koukaku_venue) patterns.push('①会場ランク降格');
  if (entry.is_koukaku_female) patterns.push('②混合→牝限');
  if (entry.is_koukaku_season) patterns.push('③冬春→夏');
  if (entry.is_koukaku_distance) patterns.push('⑤距離短縮');
  if (entry.is_koukaku_turf_to_dirt) patterns.push('⑥芝→ダート');
  if (entry.is_koukaku_handicap) patterns.push('⑦ハンデ戦');
  return `降格ローテ: ${patterns.join(', ')}`;
}

// --- 危険な人気馬 ---

/** 危険馬検出: odds<=8 & ARd<53 & V%<15% (v5.33) */
export function getRaceDanger(entries: PredictionEntry[]): DangerInfo {
  let dangerHorse: DangerInfo['dangerHorse'] = undefined;

  for (const e of entries) {
    const odds = e.odds || 0;
    const ard = e.ar_deviation ?? 999;
    const predV = e.pred_proba_v ?? 0;
    if (odds > 0 && odds <= 8.0 && ard < 53 && predV < 0.15) {
      dangerHorse = {
        umaban: e.umaban,
        horseName: e.horse_name,
        oddsRank: e.odds_rank,
        odds,
      };
      break; // 1頭見つかればOK
    }
  }

  return {
    isDanger: !!dangerHorse,
    dangerHorse,
  };
}

// --- コメントNLP ---

/** 厩舎談話NLPスコアの色 */
export function getCommentColor(score: number): string {
  if (score >= 2) return 'text-green-600 font-bold';
  if (score >= 1) return 'text-green-500';
  if (score <= -2) return 'text-red-600 font-bold';
  if (score <= -1) return 'text-red-500';
  return 'text-gray-400';
}

/** コメントNLPスコアのツールチップ */
export function getCommentTooltip(entry: PredictionEntry): string {
  const parts: string[] = [];
  if (entry.comment_has_stable) {
    parts.push(`仕上: ${entry.comment_stable_condition ?? 0}`);
    parts.push(`自信: ${entry.comment_stable_confidence ?? 0}`);
    if (entry.comment_stable_mark) parts.push(`印: ${['', '△', '', '○', '◎'][entry.comment_stable_mark] ?? entry.comment_stable_mark}`);
  }
  if (entry.comment_memo_condition) parts.push(`メモ仕上: ${entry.comment_memo_condition}`);
  if (entry.comment_memo_trouble_score) parts.push(`メモ特記: ${entry.comment_memo_trouble_score}`);
  return parts.length > 0 ? parts.join(' / ') : 'コメントデータなし';
}

// --- 日付 ---

export function getDayOfWeek(dateStr: string): string {
  const date = new Date(dateStr + 'T00:00:00');
  return ['日', '月', '火', '水', '木', '金', '土'][date.getDay()];
}

export function getDayColor(dateStr: string): string {
  const day = new Date(dateStr + 'T00:00:00').getDay();
  if (day === 0) return 'text-red-500';
  if (day === 6) return 'text-blue-500';
  return 'text-muted-foreground';
}

// --- ソート ---

export const ASC_KEYS = new Set(['umaban', 'race', 'race_number', 'rank_a', 'rank_v', 'odds_rank', 'odds', 'finish', 'verdict']);

export function SortTh({ children, sortKey, sort, setSort, className = '', title }: {
  children: React.ReactNode;
  sortKey: string;
  sort: SortState;
  setSort: (s: SortState) => void;
  className?: string;
  title?: string;
}) {
  const active = sort.key === sortKey;
  const defDir: SortDir = ASC_KEYS.has(sortKey) ? 'asc' : 'desc';
  return (
    <th
      className={`${className} cursor-pointer select-none hover:bg-gray-200/60 dark:hover:bg-gray-600/40`}
      title={title}
      onClick={() => setSort(active ? { key: sortKey, dir: sort.dir === 'asc' ? 'desc' : 'asc' } : { key: sortKey, dir: defDir })}
    >
      <span className="inline-flex items-center gap-0.5 justify-center">
        {children}
        {active && <span className="text-blue-500 text-[9px]">{sort.dir === 'asc' ? '▲' : '▼'}</span>}
      </span>
    </th>
  );
}
