import type { PredictionRace, PredictionEntry } from '@/lib/data/predictions-reader';
import type { OddsMap, DangerInfo, SortDir, SortState } from './types';

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

export function getEvColor(ev: number): string {
  if (ev >= 2.0) return 'text-emerald-600 font-bold';
  if (ev >= 1.5) return 'text-green-600 font-bold';
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
  return 'bg-gray-100 text-gray-600';
}

export function getTrackLabel(trackType: string): string {
  if (trackType === '芝' || trackType === 'turf') return '芝';
  if (trackType === 'ダ' || trackType === 'dirt') return 'ダ';
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

export function calcWinEv(entry: { pred_proba_wv?: number; pred_proba_v: number }, winOdds: number | null): number | null {
  if (!winOdds || winOdds <= 0) return null;
  const prob = entry.pred_proba_wv ?? entry.pred_proba_v;
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

export function getRaceDanger(entries: PredictionEntry[], dangerThreshold: number): DangerInfo {
  let maxDanger = 0;
  let dangerHorse: DangerInfo['dangerHorse'] = undefined;

  for (const e of entries) {
    if (e.odds_rank > 0 && e.odds_rank <= 3) {
      const dg = e.rank_v - e.odds_rank;
      if (dg > maxDanger) {
        maxDanger = dg;
        dangerHorse = {
          umaban: e.umaban,
          horseName: e.horse_name,
          oddsRank: e.odds_rank,
          rankV: e.rank_v,
        };
      }
    }
  }

  return {
    isDanger: maxDanger >= dangerThreshold,
    dangerScore: maxDanger,
    dangerHorse: maxDanger >= dangerThreshold ? dangerHorse : undefined,
  };
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
