'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import type { PredictionsLive, PredictionRace, PredictionEntry, RaceResultsMap } from '@/lib/data/predictions-reader';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

// --- DB Odds types (API response) ---

interface DbOddsHorse {
  umaban: number;
  winOdds: number | null;
  placeOddsMin: number | null;
  placeOddsMax: number | null;
}

interface DbOddsResponse {
  raceId: string;
  source: 'timeseries' | 'final' | 'none';
  snapshotTime: string | null;
  horses: DbOddsHorse[];
}

interface OddsEntry {
  winOdds: number;
  placeOddsMin: number | null;
  placeOddsMax: number | null;
}

type OddsMap = Record<string, Record<number, OddsEntry>>; // raceId -> umaban -> OddsEntry

// --- DB Results types (API response) ---

interface DbResultEntry {
  umaban: number;
  finishPosition: number;
  time: string;
  last3f: number;
  confirmedWinOdds: number;
  confirmedPlaceOddsMin: number | null;
  confirmedPlaceOddsMax: number | null;
  ninki: number;
}

interface DbResultsResponse {
  date: string;
  results: Record<string, DbResultEntry[]>; // raceId → entries
  totalRaces: number;
}

// raceId → umaban → DbResultEntry
type DbResultsMap = Record<string, Record<number, DbResultEntry>>;

// --- ヘルパー ---

function getGapColor(gap: number): string {
  if (gap >= 5) return 'text-red-600 font-bold';
  if (gap >= 4) return 'text-orange-600 font-bold';
  if (gap >= 3) return 'text-amber-600 font-semibold';
  if (gap >= 2) return 'text-blue-600';
  return 'text-gray-500';
}

function getGapBg(gap: number): string {
  if (gap >= 5) return 'bg-red-50 dark:bg-red-900/20';
  if (gap >= 4) return 'bg-orange-50 dark:bg-orange-900/20';
  if (gap >= 3) return 'bg-amber-50 dark:bg-amber-900/20';
  return '';
}

function getMarkColor(mark: string): string {
  if (mark === '◎') return 'text-red-600 font-bold';
  if (mark === '◯' || mark === '○') return 'text-blue-600 font-bold';
  if (mark === '▲') return 'text-green-600 font-bold';
  if (mark === '△') return 'text-orange-500';
  return 'text-gray-400';
}

function getEvColor(ev: number): string {
  if (ev >= 2.0) return 'text-emerald-600 font-bold';
  if (ev >= 1.5) return 'text-green-600 font-bold';
  if (ev >= 1.0) return 'text-green-500 font-semibold';
  if (ev >= 0.8) return 'text-yellow-600';
  return 'text-gray-400';
}

function getRaceLink(race: PredictionRace): string {
  const [y, m, d] = [race.date.slice(0, 4), race.date.slice(5, 7), race.date.slice(8, 10)];
  return `/races-v2/${y}-${m}-${d}/${race.venue_name}/${race.race_id}`;
}

function getTrackBadgeClass(trackType: string): string {
  if (trackType === '芝' || trackType === 'turf') return 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300';
  if (trackType === 'ダ' || trackType === 'dirt') return 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300';
  return 'bg-gray-100 text-gray-600';
}

function getTrackLabel(trackType: string): string {
  if (trackType === '芝' || trackType === 'turf') return '芝';
  if (trackType === 'ダ' || trackType === 'dirt') return 'ダ';
  return '?';
}

function isTurf(trackType: string): boolean {
  return trackType === '芝' || trackType === 'turf';
}

function isDirt(trackType: string): boolean {
  return trackType === 'ダ' || trackType === 'dirt';
}

/**
 * 購入推奨ロジック（バックテスト結果に基づく）
 * 芝: 単勝ROI高い → 単勝推奨
 * ダート: 複勝ROI高い → 複勝推奨
 * 穴馬(odds>=10) + gap>=5: 単勝ROI 130%+ → 芝ダ問わず単勝推奨
 */
function getBuyRecommendation(trackType: string, gap: number, valueRank: number, odds: number | null): { type: '単勝' | '複勝' | '単複' | null; strength: 'strong' | 'normal' } {
  const o = odds ?? 0;

  // 穴馬 + 大幅乖離: 芝ダ問わず単勝（バックテストROI 130%+）
  if (gap >= 5 && o >= 10 && valueRank === 1) {
    return { type: '単勝', strength: 'strong' };
  }

  if (isTurf(trackType)) {
    // 芝: 単勝ROI優位（gap>=4で112.8%, gap>=5で134.3%）
    if (gap >= 5) return { type: '単勝', strength: 'strong' };
    if (gap >= 4) return { type: '単勝', strength: 'normal' };
    return { type: '単勝', strength: 'normal' };
  }

  if (isDirt(trackType)) {
    // ダート: 複勝ROI優位（gap>=4で128.1%, gap>=5で157.6%）
    if (gap >= 5 && o >= 10) return { type: '単複', strength: 'strong' };
    if (gap >= 5) return { type: '複勝', strength: 'strong' };
    return { type: '複勝', strength: 'normal' };
  }

  return { type: null, strength: 'normal' };
}

function getRecBadgeClass(type: string, strength: string): string {
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

function getWinOdds(odds: OddsMap, raceId: string, umaban: number, fallback: number): number | null {
  const raceOdds = odds[raceId];
  if (raceOdds && raceOdds[umaban]?.winOdds > 0) return raceOdds[umaban].winOdds;
  if (fallback > 0) return fallback;
  return null;
}

function getPlaceOddsMin(odds: OddsMap, raceId: string, umaban: number): number | null {
  const entry = odds[raceId]?.[umaban];
  return entry?.placeOddsMin ?? null;
}

/** 単勝EV = P(win) × 単勝オッズ */
function calcWinEv(entry: { pred_proba_wv?: number; pred_proba_v: number }, winOdds: number | null): number | null {
  if (!winOdds || winOdds <= 0) return null;
  const prob = entry.pred_proba_wv ?? entry.pred_proba_v; // fallback to place prob
  return prob * winOdds;
}

/** 複勝EV = P(top3) × 複勝オッズ最低値 */
function calcPlaceEv(probV: number, placeOddsMin: number | undefined | null): number | null {
  if (!placeOddsMin || placeOddsMin <= 0) return null;
  return probV * placeOddsMin;
}

/** 頭向き度 = P(win) / P(top3) */
function calcHeadRatio(probWV: number | undefined, probV: number): number | null {
  if (!probWV || probV <= 0) return null;
  return probWV / probV;
}

/**
 * Kelly Criterion: f* = (b*p - q) / b
 * b = net payout (odds - 1), p = probability, q = 1 - p
 * Returns fractional Kelly (0 if negative = don't bet)
 */
function calcKellyFraction(prob: number, odds: number): number {
  const b = odds - 1;
  if (b <= 0 || prob <= 0) return 0;
  const f = (b * prob - (1 - prob)) / b;
  return Math.max(0, f);
}

/** 推奨買い目の設定定数 */
const BET_CONFIG = {
  defaultBudget: 30000,
  kellyFraction: 0.25,
  minBet: 100,
  betUnit: 100,
  minGap: 3,
  minGapDanger: 2,      // 危険レースは閾値緩和
  dangerThreshold: 5,   // value_rank - odds_rank >= 5 で「危険な人気馬」
  minEvThreshold: 1.0,
} as const;

/** 危険な人気馬情報 */
interface DangerInfo {
  isDanger: boolean;
  dangerScore: number;          // max(rank_v - odds_rank) among top-3 popular
  dangerHorse?: {
    umaban: number;
    horseName: string;
    oddsRank: number;
    rankV: number;
  };
}

/** レースの危険度を判定 */
function getRaceDanger(entries: PredictionEntry[]): DangerInfo {
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
    isDanger: maxDanger >= BET_CONFIG.dangerThreshold,
    dangerScore: maxDanger,
    dangerHorse: maxDanger >= BET_CONFIG.dangerThreshold ? dangerHorse : undefined,
  };
}

/** 降格ローテのパターン詳細をtooltipテキストとして返す */
function getKoukakuDetail(entry: PredictionEntry): string {
  const patterns: string[] = [];
  if (entry.is_koukaku_venue) patterns.push('①会場ランク降格');
  if (entry.is_koukaku_female) patterns.push('②混合→牝限');
  if (entry.is_koukaku_season) patterns.push('③冬春→夏');
  if (entry.is_koukaku_distance) patterns.push('⑤距離短縮');
  if (entry.is_koukaku_turf_to_dirt) patterns.push('⑥芝→ダート');
  if (entry.is_koukaku_handicap) patterns.push('⑦ハンデ戦');
  return `降格ローテ: ${patterns.join(', ')}`;
}

interface BetRecommendation {
  race: PredictionRace;
  entry: PredictionEntry;
  betType: '単勝' | '複勝' | '単複';
  strength: 'strong' | 'normal';
  winEv: number | null;
  placeEv: number | null;
  kellyWin: number;
  kellyPlace: number;
  betAmountWin: number;
  betAmountPlace: number;
  danger?: DangerInfo;   // 危険レースフラグ
}

function getFinishColor(pos: number): string {
  if (pos === 1) return 'text-amber-500 font-bold';
  if (pos === 2) return 'text-gray-500 font-bold';
  if (pos === 3) return 'text-orange-700 font-bold';
  if (pos <= 5) return 'font-semibold';
  return 'text-muted-foreground';
}

function getFinishBg(pos: number): string {
  if (pos === 1) return 'bg-amber-50/60 dark:bg-amber-900/15';
  if (pos <= 3) return 'bg-green-50/40 dark:bg-green-900/10';
  return '';
}

function getPlaceLimit(numRunners: number): number {
  if (numRunners >= 8) return 3;
  if (numRunners >= 5) return 2;
  return 0; // 4頭以下は複勝なし
}

// --- ソート ---

type SortDir = 'asc' | 'desc';
interface SortState { key: string; dir: SortDir }

const ASC_KEYS = new Set(['umaban', 'race', 'rank_a', 'rank_v', 'odds_rank', 'odds', 'finish']);

function SortTh({ children, sortKey, sort, setSort, className = '', title }: {
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

// --- 日付ナビゲーション ---

function getDayOfWeek(dateStr: string): string {
  const date = new Date(dateStr + 'T00:00:00');
  return ['日', '月', '火', '水', '木', '金', '土'][date.getDay()];
}

function getDayColor(dateStr: string): string {
  const day = new Date(dateStr + 'T00:00:00').getDay();
  if (day === 0) return 'text-red-500';
  if (day === 6) return 'text-blue-500';
  return 'text-muted-foreground';
}

interface DateNavProps {
  dates: string[];
  currentDate: string;
  isArchive: boolean;
}

function DateNav({ dates, currentDate, isArchive }: DateNavProps) {
  const router = useRouter();

  if (dates.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2 items-center mb-6">
      <button
        onClick={() => router.push('/predictions')}
        className={`px-3 py-2 rounded border text-sm transition-colors ${
          !isArchive
            ? 'bg-primary text-primary-foreground shadow-md'
            : 'bg-background hover:bg-muted/50'
        }`}
      >
        最新
      </button>
      <span className="text-muted-foreground text-xs mx-1">|</span>
      {dates.map(date => {
        const [, , day] = date.split('-');
        const isActive = isArchive && date === currentDate;
        return (
          <button
            key={date}
            onClick={() => router.push(`/predictions?date=${date}`)}
            className={`px-3 py-2 rounded border text-sm transition-colors flex flex-col items-center min-w-[3.5rem] ${
              isActive
                ? 'bg-primary text-primary-foreground shadow-md'
                : 'bg-background hover:bg-muted/50'
            }`}
          >
            <span className="font-bold leading-none">{parseInt(day)}</span>
            <span className={`text-[10px] mt-0.5 ${isActive ? 'text-primary-foreground/80' : getDayColor(date)}`}>
              {getDayOfWeek(date)}
            </span>
          </button>
        );
      })}
    </div>
  );
}

// --- メインコンポーネント ---

interface PredictionsContentProps {
  data: PredictionsLive;
  availableDates?: string[];
  currentDate?: string;
  isArchive?: boolean;
  results?: RaceResultsMap;
}

export function PredictionsContent({ data, availableDates = [], currentDate = '', isArchive = false, results }: PredictionsContentProps) {
  const [oddsMap, setOddsMap] = useState<OddsMap>({});
  const [oddsSource, setOddsSource] = useState<string>('');
  const [oddsTime, setOddsTime] = useState<string | null>(null);
  const [oddsLoading, setOddsLoading] = useState(true);
  const [dbResults, setDbResults] = useState<DbResultsMap>({});

  // フィルタ state
  const [venueFilter, setVenueFilter] = useState<string>('all');
  const [raceNumFilter, setRaceNumFilter] = useState<number>(0); // 0 = 全て
  const [trackFilter, setTrackFilter] = useState<string>('all'); // 'all' | 'turf' | 'dirt'
  const [minGap, setMinGap] = useState<number>(3);
  const [minEv, setMinEv] = useState<number>(0); // 0 = 全て

  // VBテーブルソート
  const [vbSort, setVbSort] = useState<SortState>({ key: 'gap', dir: 'desc' });
  // 推奨買い目テーブルソート
  const [betSort, setBetSort] = useState<SortState>({ key: 'amount', dir: 'desc' });

  // TARGET馬印2 VB印反映
  const [markSyncing, setMarkSyncing] = useState(false);
  const [markResult, setMarkResult] = useState<{ marks: Record<string, number>; markedHorses: number } | null>(null);

  // 推奨買い目 予算設定（hydration後にlocalStorageから復元）
  const [dailyBudget, setDailyBudget] = useState<number>(BET_CONFIG.defaultBudget);
  useEffect(() => {
    const saved = localStorage.getItem('keiba_daily_budget');
    if (saved) setDailyBudget(Number(saved));
  }, []);
  // 予算変更時にlocalStorageに保存
  const updateBudget = useCallback((value: number) => {
    const v = Math.max(1000, Math.round(value / 1000) * 1000);
    setDailyBudget(v);
    localStorage.setItem('keiba_daily_budget', String(v));
  }, []);

  // TARGET PD CSV 推奨買い目反映
  const [betSyncing, setBetSyncing] = useState(false);
  const [betSyncResult, setBetSyncResult] = useState<{ totalBets: number; winBets: number; placeBets: number; racesWritten: number; totalAmount: number; filePath: string } | null>(null);

  const isToday = useMemo(() => {
    const now = new Date();
    const todayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
    return data.date === todayStr;
  }, [data.date]);

  const raceIds = useMemo(() => data.races.map(r => r.race_id), [data.races]);

  const fetchAllOdds = useCallback(async () => {
    try {
      const ts = Date.now(); // キャッシュバスト用タイムスタンプ
      const results = await Promise.all(
        raceIds.map(id =>
          fetch(`/api/odds/db-latest?raceId=${id}&_t=${ts}`, { cache: 'no-store' })
            .then(r => r.json() as Promise<DbOddsResponse>)
            .catch(() => null)
        )
      );

      const newOdds: OddsMap = {};
      let src = '';
      let time: string | null = null;

      for (const result of results) {
        if (!result || !result.horses) continue;
        const h: Record<number, OddsEntry> = {};
        for (const horse of result.horses) {
          if (horse.winOdds && horse.winOdds > 0) {
            h[horse.umaban] = {
              winOdds: horse.winOdds,
              placeOddsMin: horse.placeOddsMin ?? null,
              placeOddsMax: horse.placeOddsMax ?? null,
            };
          }
        }
        if (Object.keys(h).length > 0) newOdds[result.raceId] = h;
        if (!src && result.source !== 'none') src = result.source;
        if (!time && result.snapshotTime) time = result.snapshotTime;
      }

      setOddsMap(newOdds);
      setOddsSource(src);
      setOddsTime(time);
    } catch {
      // ignore
    } finally {
      setOddsLoading(false);
    }
  }, [raceIds]);

  // DB確定成績をfetch
  const fetchDbResults = useCallback(async () => {
    try {
      const resp = await fetch(`/api/results/db-results?date=${data.date}`);
      const json = await resp.json() as DbResultsResponse;
      if (json.results && json.totalRaces > 0) {
        // array → map (raceId → umaban → entry)
        const map: DbResultsMap = {};
        for (const [raceId, entries] of Object.entries(json.results)) {
          map[raceId] = {};
          for (const e of entries) {
            map[raceId][e.umaban] = e;
          }
        }
        setDbResults(map);
      }
    } catch {
      // ignore
    }
  }, [data.date]);

  useEffect(() => {
    fetchAllOdds();
    fetchDbResults();
    if (isToday) {
      const interval = setInterval(() => { fetchAllOdds(); fetchDbResults(); }, 30000);
      return () => clearInterval(interval);
    }
  }, [fetchAllOdds, fetchDbResults, isToday]);

  const { races, summary } = data;

  // 開催場リスト（フィルタ用）
  const venues = useMemo(() => {
    const set = new Set<string>();
    for (const race of races) set.add(race.venue_name);
    return Array.from(set);
  }, [races]);

  // レース番号リスト（フィルタ用 — 場所フィルタ連動）
  const raceNumbers = useMemo(() => {
    const filtered = venueFilter === 'all' ? races : races.filter(r => r.venue_name === venueFilter);
    const nums = new Set<number>();
    for (const race of filtered) nums.add(race.race_number);
    return Array.from(nums).sort((a, b) => a - b);
  }, [races, venueFilter]);

  // VB候補一覧（全件）
  const allVBEntries = useMemo(() => {
    const entries: Array<{ race: PredictionRace; entry: PredictionEntry }> = [];
    for (const race of races) {
      for (const entry of race.entries) {
        if (entry.is_value_bet) entries.push({ race, entry });
      }
    }
    entries.sort((a, b) => b.entry.vb_gap - a.entry.vb_gap);
    return entries;
  }, [races]);

  // フィルタ適用済みVB一覧
  const filteredVBEntries = useMemo(() => {
    let entries = allVBEntries;

    // Gap閾値
    if (minGap > 3) {
      entries = entries.filter(e => e.entry.vb_gap >= minGap);
    }

    // 場所フィルタ
    if (venueFilter !== 'all') {
      entries = entries.filter(e => e.race.venue_name === venueFilter);
    }

    // 芝/ダートフィルタ
    if (trackFilter !== 'all') {
      entries = entries.filter(e =>
        trackFilter === 'turf' ? isTurf(e.race.track_type) : isDirt(e.race.track_type)
      );
    }

    // レース番号フィルタ
    if (raceNumFilter > 0) {
      entries = entries.filter(e => e.race.race_number === raceNumFilter);
    }

    // EV閾値
    if (minEv > 0) {
      entries = entries.filter(e => {
        const winOdds = getWinOdds(oddsMap, e.race.race_id, e.entry.umaban, e.entry.odds);
        const ev = calcWinEv(e.entry, winOdds);
        return ev !== null && ev >= minEv;
      });
    }

    return entries;
  }, [allVBEntries, venueFilter, trackFilter, raceNumFilter, minGap, minEv, oddsMap]);

  // フィルタ適用済み開催場グループ
  const filteredVenueGroups = useMemo(() => {
    let filtered = races;
    if (venueFilter !== 'all') filtered = filtered.filter(r => r.venue_name === venueFilter);
    if (trackFilter !== 'all') {
      filtered = filtered.filter(r =>
        trackFilter === 'turf' ? isTurf(r.track_type) : isDirt(r.track_type)
      );
    }
    if (raceNumFilter > 0) filtered = filtered.filter(r => r.race_number === raceNumFilter);
    const map = new Map<string, PredictionRace[]>();
    for (const race of filtered) {
      const group = map.get(race.venue_name) || [];
      group.push(race);
      map.set(race.venue_name, group);
    }
    return map;
  }, [races, venueFilter, trackFilter, raceNumFilter]);

  // 統計
  const stats = useMemo(() => {
    let totalVB = 0;
    let totalEntries = 0;
    let evPositiveCount = 0;
    const venueMap = new Map<string, { races: number; vb: number }>();

    for (const race of races) {
      totalEntries += race.entries.length;
      const vbCount = race.entries.filter(e => e.is_value_bet).length;
      totalVB += vbCount;
      const v = venueMap.get(race.venue_name) || { races: 0, vb: 0 };
      v.races++;
      v.vb += vbCount;
      venueMap.set(race.venue_name, v);

      for (const entry of race.entries) {
        const odds = getWinOdds(oddsMap, race.race_id, entry.umaban, entry.odds);
        const ev = calcWinEv(entry, odds);
        if (ev !== null && ev >= 1.0) evPositiveCount++;
      }
    }

    return { totalVB, totalEntries, venueMap, evPositiveCount };
  }, [races, oddsMap]);

  const hasOdds = Object.keys(oddsMap).length > 0;
  const hasDbResults = Object.keys(dbResults).length > 0;
  const hasResults = hasDbResults || (results ? Object.keys(results).length > 0 : false);

  // 着順取得ヘルパー（DB優先 → server-side fallback）
  const getFinishPos = useCallback((raceId: string, umaban: number): number => {
    const dbEntry = dbResults[raceId]?.[umaban];
    if (dbEntry) return dbEntry.finishPosition;
    const jsonEntry = results?.[raceId]?.[umaban];
    return jsonEntry?.finish_position ?? 0;
  }, [dbResults, results]);

  // TARGET馬印2にVB印を一括反映
  const syncVbMarks = useCallback(async () => {
    setMarkSyncing(true);
    setMarkResult(null);
    try {
      const res = await fetch('/api/target-marks/auto-vb', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ date: isArchive ? currentDate : undefined }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: 'Unknown error' }));
        throw new Error(err.error || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setMarkResult({ marks: data.summary.marks, markedHorses: data.summary.markedHorses });
    } catch (error) {
      console.error('[syncVbMarks] Error:', error);
      setMarkResult(null);
      alert(`VB印反映に失敗しました: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setMarkSyncing(false);
    }
  }, [isArchive, currentDate]);

  // 推奨買い目構築（危険レース検出込み）
  const betRecommendations = useMemo<BetRecommendation[]>(() => {
    const recs: BetRecommendation[] = [];
    for (const race of races) {
      // 危険な人気馬の検出
      const danger = getRaceDanger(race.entries);
      const effectiveMinGap = danger.isDanger ? BET_CONFIG.minGapDanger : BET_CONFIG.minGap;

      for (const entry of race.entries) {
        if (entry.vb_gap < effectiveMinGap) continue;

        // EV計算（ライブオッズ優先 → predict.py静的値フォールバック）
        const winOdds = getWinOdds(oddsMap, race.race_id, entry.umaban, entry.odds);
        const placeOddsMin = getPlaceOddsMin(oddsMap, race.race_id, entry.umaban) ?? entry.place_odds_min ?? null;
        const wEv = calcWinEv(entry, winOdds) ?? entry.win_ev ?? null;
        const pEv = calcPlaceEv(entry.pred_proba_v, placeOddsMin) ?? entry.place_ev ?? null;

        const hasWinEv = wEv !== null && wEv > BET_CONFIG.minEvThreshold;
        const hasPlaceEv = pEv !== null && pEv > BET_CONFIG.minEvThreshold;
        if (!hasWinEv && !hasPlaceEv) continue;

        // 買い目タイプ決定（getBuyRecommendation ロジックベース）
        const rec = getBuyRecommendation(race.track_type, entry.vb_gap, entry.rank_v, winOdds);
        if (!rec.type) continue;

        // Kelly計算
        const probWin = entry.pred_proba_wv ?? entry.pred_proba_v;
        const kellyWin = winOdds && winOdds > 0 ? calcKellyFraction(probWin, winOdds) : 0;
        const kellyPlace = placeOddsMin && placeOddsMin > 0 ? calcKellyFraction(entry.pred_proba_v, placeOddsMin) : 0;

        // EV+でKelly>0のみ採用。複勝Kelly=0だがwin Kelly>0の場合は単勝にフォールバック
        let finalType = rec.type;
        let useWin = finalType === '単勝' || finalType === '単複';
        let usePlace = finalType === '複勝' || finalType === '単複';

        if (usePlace && kellyPlace <= 0) {
          if (kellyWin > 0 && hasWinEv) {
            finalType = '単勝';
            useWin = true;
            usePlace = false;
          } else if (!useWin) {
            continue;
          }
        }
        if (useWin && kellyWin <= 0 && !usePlace) continue;

        recs.push({
          race, entry,
          betType: finalType,
          strength: rec.strength,
          winEv: wEv,
          placeEv: pEv,
          kellyWin,
          kellyPlace,
          betAmountWin: 0,
          betAmountPlace: 0,
          danger: danger.isDanger ? danger : undefined,
        });
      }
    }

    // Kelly金額計算（日予算内に収める）
    const budget = dailyBudget;
    let totalRaw = 0;
    for (const r of recs) {
      const useWin = r.betType === '単勝' || r.betType === '単複';
      const usePlace = r.betType === '複勝' || r.betType === '単複';
      if (useWin) totalRaw += r.kellyWin * BET_CONFIG.kellyFraction * budget;
      if (usePlace) totalRaw += r.kellyPlace * BET_CONFIG.kellyFraction * budget;
    }

    const scale = totalRaw > budget ? budget / totalRaw : 1.0;

    for (const r of recs) {
      const useWin = r.betType === '単勝' || r.betType === '単複';
      const usePlace = r.betType === '複勝' || r.betType === '単複';
      if (useWin) {
        const raw = r.kellyWin * BET_CONFIG.kellyFraction * budget * scale;
        r.betAmountWin = Math.max(BET_CONFIG.minBet, Math.round(raw / BET_CONFIG.betUnit) * BET_CONFIG.betUnit);
      }
      if (usePlace) {
        const raw = r.kellyPlace * BET_CONFIG.kellyFraction * budget * scale;
        r.betAmountPlace = Math.max(BET_CONFIG.minBet, Math.round(raw / BET_CONFIG.betUnit) * BET_CONFIG.betUnit);
      }
    }

    // 金額降順
    recs.sort((a, b) => (b.betAmountWin + b.betAmountPlace) - (a.betAmountWin + a.betAmountPlace));
    return recs;
  }, [races, oddsMap, dailyBudget]);

  // 推奨サマリー
  const betSummary = useMemo(() => {
    let winCount = 0, placeCount = 0, winTotal = 0, placeTotal = 0, evSum = 0, evCount = 0;
    const dangerRaceIds = new Set<string>();
    for (const r of betRecommendations) {
      if (r.betAmountWin > 0) { winCount++; winTotal += r.betAmountWin; }
      if (r.betAmountPlace > 0) { placeCount++; placeTotal += r.betAmountPlace; }
      if (r.winEv && r.betAmountWin > 0) { evSum += r.winEv * r.betAmountWin; evCount += r.betAmountWin; }
      if (r.placeEv && r.betAmountPlace > 0) { evSum += r.placeEv * r.betAmountPlace; evCount += r.betAmountPlace; }
      if (r.danger?.isDanger) dangerRaceIds.add(r.race.race_id);
    }
    const avgEv = evCount > 0 ? evSum / evCount : 0;
    const totalAmount = winTotal + placeTotal;
    const expectedReturn = Math.round(evSum);
    return { winCount, placeCount, winTotal, placeTotal, totalAmount, avgEv, expectedReturn, totalBets: betRecommendations.length, dangerRaces: dangerRaceIds.size };
  }, [betRecommendations]);

  // 推奨買い目：フィルタ＆ソート
  const sortedBetRecommendations = useMemo(() => {
    // フィルタ適用（VBテーブルと同じ条件）
    let recs = [...betRecommendations];
    if (venueFilter !== 'all') recs = recs.filter(r => r.race.venue_name === venueFilter);
    if (trackFilter !== 'all') recs = recs.filter(r => trackFilter === 'turf' ? isTurf(r.race.track_type) : isDirt(r.race.track_type));
    if (raceNumFilter > 0) recs = recs.filter(r => r.race.race_number === raceNumFilter);

    // ソート
    const { key, dir } = betSort;
    const mul = dir === 'asc' ? 1 : -1;
    recs.sort((a, b) => {
      let va: number, vb: number;
      switch (key) {
        case 'race': va = a.race.race_number; vb = b.race.race_number; break;
        case 'umaban': va = a.entry.umaban; vb = b.entry.umaban; break;
        case 'winEv': va = a.winEv ?? -1; vb = b.winEv ?? -1; break;
        case 'placeEv': va = a.placeEv ?? -1; vb = b.placeEv ?? -1; break;
        case 'gap': va = a.entry.vb_gap; vb = b.entry.vb_gap; break;
        case 'kelly': {
          const ka = a.betType === '複勝' ? a.kellyPlace : a.kellyWin;
          const kb = b.betType === '複勝' ? b.kellyPlace : b.kellyWin;
          va = ka; vb = kb; break;
        }
        case 'odds': {
          va = getWinOdds(oddsMap, a.race.race_id, a.entry.umaban, a.entry.odds) ?? 9999;
          vb = getWinOdds(oddsMap, b.race.race_id, b.entry.umaban, b.entry.odds) ?? 9999;
          break;
        }
        case 'head': {
          va = calcHeadRatio(a.entry.pred_proba_wv, a.entry.pred_proba_v) ?? -1;
          vb = calcHeadRatio(b.entry.pred_proba_wv, b.entry.pred_proba_v) ?? -1;
          break;
        }
        case 'danger': va = a.danger?.dangerScore ?? 0; vb = b.danger?.dangerScore ?? 0; break;
        default: /* amount */ va = a.betAmountWin + a.betAmountPlace; vb = b.betAmountWin + b.betAmountPlace; break;
      }
      return (va - vb) * mul;
    });
    return recs;
  }, [betRecommendations, betSort, venueFilter, trackFilter, raceNumFilter, oddsMap]);

  // TARGET FF CSVに推奨買い目を書込み（出力前にオッズ最新化）
  const syncBetMarks = useCallback(async () => {
    setBetSyncing(true);
    setBetSyncResult(null);
    try {
      // 最新オッズ取得（EV/Kelly再計算のため）
      await fetchAllOdds();
      // fetchAllOdds後にoddsMapが更新されbetRecommendationsが再計算される
      // 少し待ってstateの反映を確認
      await new Promise(r => setTimeout(r, 500));

      // クライアント側で算出した推奨買い目をAPIに送信
      const bets = sortedBetRecommendations.flatMap(r => {
        const items: { raceId: string; umaban: number; betType: number; amount: number }[] = [];
        if (r.betAmountWin > 0) {
          items.push({ raceId: r.race.race_id, umaban: r.entry.umaban, betType: 0, amount: r.betAmountWin });
        }
        if (r.betAmountPlace > 0) {
          items.push({ raceId: r.race.race_id, umaban: r.entry.umaban, betType: 1, amount: r.betAmountPlace });
        }
        return items;
      });

      if (bets.length === 0) {
        alert('書込み対象の買い目がありません');
        return;
      }

      const res = await fetch('/api/target-marks/auto-bet', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bets }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: 'Unknown error' }));
        throw new Error(err.error || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setBetSyncResult({
        totalBets: data.summary.totalBets,
        winBets: data.summary.winBets,
        placeBets: data.summary.placeBets,
        racesWritten: data.summary.racesWritten,
        totalAmount: data.summary.totalAmount,
        filePath: data.summary.filePath,
      });
    } catch (error) {
      console.error('[syncBetMarks] Error:', error);
      setBetSyncResult(null);
      alert(`TARGET書込み失敗: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setBetSyncing(false);
    }
  }, [sortedBetRecommendations, fetchAllOdds]);

  // VBテーブル ソート適用
  const sortedVBEntries = useMemo(() => {
    const arr = [...filteredVBEntries];
    const { key, dir } = vbSort;
    const mul = dir === 'asc' ? 1 : -1;
    arr.sort((a, b) => {
      let va: number, vb: number;
      switch (key) {
        case 'race': va = a.race.race_number; vb = b.race.race_number; break;
        case 'umaban': va = a.entry.umaban; vb = b.entry.umaban; break;
        case 'rank_v': va = a.entry.rank_v; vb = b.entry.rank_v; break;
        case 'odds_rank': va = a.entry.odds_rank || 999; vb = b.entry.odds_rank || 999; break;
        case 'odds': {
          va = getWinOdds(oddsMap, a.race.race_id, a.entry.umaban, a.entry.odds) ?? 9999;
          vb = getWinOdds(oddsMap, b.race.race_id, b.entry.umaban, b.entry.odds) ?? 9999;
          break;
        }
        case 'ev': {
          va = calcWinEv(a.entry, getWinOdds(oddsMap, a.race.race_id, a.entry.umaban, a.entry.odds)) ?? -1;
          vb = calcWinEv(b.entry, getWinOdds(oddsMap, b.race.race_id, b.entry.umaban, b.entry.odds)) ?? -1;
          break;
        }
        case 'place_ev': {
          const aPlaceMin = a.entry.place_odds_min ?? getPlaceOddsMin(oddsMap, a.race.race_id, a.entry.umaban);
          const bPlaceMin = b.entry.place_odds_min ?? getPlaceOddsMin(oddsMap, b.race.race_id, b.entry.umaban);
          va = calcPlaceEv(a.entry.pred_proba_v, aPlaceMin) ?? -1;
          vb = calcPlaceEv(b.entry.pred_proba_v, bPlaceMin) ?? -1;
          break;
        }
        case 'head_ratio': {
          va = calcHeadRatio(a.entry.pred_proba_wv, a.entry.pred_proba_v) ?? -1;
          vb = calcHeadRatio(b.entry.pred_proba_wv, b.entry.pred_proba_v) ?? -1;
          break;
        }
        case 'prob_a': va = a.entry.pred_proba_a; vb = b.entry.pred_proba_a; break;
        case 'prob_v': va = a.entry.pred_proba_v; vb = b.entry.pred_proba_v; break;
        case 'finish': {
          const pa = getFinishPos(a.race.race_id, a.entry.umaban);
          const pb = getFinishPos(b.race.race_id, b.entry.umaban);
          va = pa > 0 ? pa : 999;
          vb = pb > 0 ? pb : 999;
          break;
        }
        default: /* gap */ va = a.entry.vb_gap; vb = b.entry.vb_gap; break;
      }
      return (va - vb) * mul;
    });
    return arr;
  }, [filteredVBEntries, vbSort, oddsMap, getFinishPos]);

  // ROI計算（フィルタ連動、DB確定オッズ使用）— 全体 + 芝/ダート別
  const roiStats = useMemo(() => {
    if (!hasResults) return null;

    type TrackROI = {
      vbCount: number; winHits: number; placeHits: number;
      winPayout: number; placePayout: number; placeBetCount: number;
      hasAnyPlaceOdds: boolean;
    };
    const initTrack = (): TrackROI => ({ vbCount: 0, winHits: 0, placeHits: 0, winPayout: 0, placePayout: 0, placeBetCount: 0, hasAnyPlaceOdds: false });
    const all = initTrack();
    const turf = initTrack();
    const dirt = initTrack();

    for (const { race, entry } of filteredVBEntries) {
      const pos = getFinishPos(race.race_id, entry.umaban);
      if (pos <= 0) continue;

      const buckets = [all];
      if (isTurf(race.track_type)) buckets.push(turf);
      if (isDirt(race.track_type)) buckets.push(dirt);

      for (const b of buckets) {
        b.vbCount++;
        const placeLimit = getPlaceLimit(race.num_runners);
        const dbEntry = dbResults[race.race_id]?.[entry.umaban];
        const confirmedWinOdds = dbEntry?.confirmedWinOdds ?? (results?.[race.race_id]?.[entry.umaban]?.odds ?? 0);

        if (pos === 1 && confirmedWinOdds > 0) {
          b.winHits++;
          b.winPayout += confirmedWinOdds * 100;
        }

        if (placeLimit > 0) {
          const plOddsMin = dbEntry?.confirmedPlaceOddsMin ?? getPlaceOddsMin(oddsMap, race.race_id, entry.umaban);
          if (plOddsMin && plOddsMin > 0) {
            b.hasAnyPlaceOdds = true;
            b.placeBetCount++;
            if (pos <= placeLimit) {
              b.placeHits++;
              b.placePayout += plOddsMin * 100;
            }
          }
        }
      }
    }

    if (all.vbCount === 0) return null;

    const calcROI = (b: TrackROI) => ({
      vbCount: b.vbCount,
      winHits: b.winHits,
      placeHits: b.placeHits,
      placeBetCount: b.placeBetCount,
      winROI: b.vbCount > 0 ? (b.winPayout / (b.vbCount * 100)) * 100 : 0,
      placeROI: b.placeBetCount > 0 ? (b.placePayout / (b.placeBetCount * 100)) * 100 : 0,
      winProfit: b.winPayout - b.vbCount * 100,
      placeProfit: b.placeBetCount > 0 ? b.placePayout - b.placeBetCount * 100 : 0,
      hasAnyPlaceOdds: b.hasAnyPlaceOdds,
    });

    return { all: calcROI(all), turf: calcROI(turf), dirt: calcROI(dirt) };
  }, [filteredVBEntries, dbResults, results, hasResults, oddsMap, getFinishPos]);

  return (
    <div className="py-6">
      {/* 日付ナビゲーション */}
      {availableDates.length > 0 && (
        <DateNav dates={availableDates} currentDate={currentDate} isArchive={isArchive} />
      )}

      {/* ヘッダー */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold">Value Bet</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {data.date} / Model v{data.model_version} / オッズ: {data.odds_source}
            {data.db_odds_coverage && ` (${data.db_odds_coverage})`}
          </p>
        </div>
        <div className="text-right text-sm text-muted-foreground">
          <div>生成: {new Date(data.created_at).toLocaleString('ja-JP')}</div>
          {hasOdds && (
            <div className="text-xs mt-0.5">
              DBオッズ: {oddsSource === 'timeseries' ? '時系列' : '確定'}
              {oddsTime && ` (${oddsTime})`}
              {isToday && ' 🔄30秒更新'}
            </div>
          )}
          {oddsLoading && <div className="text-xs mt-0.5">オッズ読込中...</div>}
        </div>
      </div>

      {/* サマリーカード */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
        <Card>
          <CardContent className="pt-4 pb-3 text-center">
            <div className="text-3xl font-bold">{summary.total_races}</div>
            <div className="text-xs text-muted-foreground">レース</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-3 text-center">
            <div className="text-3xl font-bold">{summary.total_entries}</div>
            <div className="text-xs text-muted-foreground">出走頭数</div>
          </CardContent>
        </Card>
        <Card className="border-amber-200 dark:border-amber-800">
          <CardContent className="pt-4 pb-3 text-center">
            <div className="text-3xl font-bold text-amber-600">{stats.totalVB}</div>
            <div className="text-xs text-muted-foreground">VB候補 (gap&ge;3)</div>
          </CardContent>
        </Card>
        <Card className="border-emerald-200 dark:border-emerald-800">
          <CardContent className="pt-4 pb-3 text-center">
            <div className={`text-3xl font-bold ${hasOdds ? 'text-emerald-600' : 'text-muted-foreground'}`}>
              {hasOdds ? stats.evPositiveCount : '-'}
            </div>
            <div className="text-xs text-muted-foreground">EV&ge;1.0</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-3 text-center">
            <div className="text-3xl font-bold">{Array.from(stats.venueMap.keys()).join(' / ')}</div>
            <div className="text-xs text-muted-foreground">開催場</div>
          </CardContent>
        </Card>
      </div>

      {/* フィルタバー */}
      <div className="flex flex-wrap items-center gap-4 rounded-lg bg-gray-50 dark:bg-gray-900/50 p-3 mb-6">
        {/* 場所 */}
        <div className="flex items-center gap-1">
          <span className="text-xs text-muted-foreground mr-1">場所:</span>
          {['all', ...venues].map(v => (
            <button
              key={v}
              onClick={() => setVenueFilter(v)}
              className={`px-2.5 py-1 text-xs rounded transition-colors ${
                venueFilter === v
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 border border-gray-200 dark:border-gray-700'
              }`}
            >
              {v === 'all' ? '全て' : v}
            </button>
          ))}
        </div>

        {/* レース番号 */}
        <div className="flex items-center gap-1">
          <span className="text-xs text-muted-foreground mr-1">R:</span>
          <button
            onClick={() => setRaceNumFilter(0)}
            className={`px-2.5 py-1 text-xs rounded transition-colors ${
              raceNumFilter === 0
                ? 'bg-purple-600 text-white shadow-sm'
                : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 border border-gray-200 dark:border-gray-700'
            }`}
          >
            全て
          </button>
          {raceNumbers.map(n => (
            <button
              key={n}
              onClick={() => setRaceNumFilter(n)}
              className={`px-2 py-1 text-xs rounded transition-colors ${
                raceNumFilter === n
                  ? 'bg-purple-600 text-white shadow-sm'
                  : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 border border-gray-200 dark:border-gray-700'
              }`}
            >
              {n}
            </button>
          ))}
        </div>

        {/* 芝/ダート */}
        <div className="flex items-center gap-1">
          <span className="text-xs text-muted-foreground mr-1">馬場:</span>
          {[
            { v: 'all', l: '全て', cls: 'bg-gray-600' },
            { v: 'turf', l: '芝', cls: 'bg-green-600' },
            { v: 'dirt', l: 'ダート', cls: 'bg-amber-600' },
          ].map(({ v, l, cls }) => (
            <button
              key={v}
              onClick={() => setTrackFilter(v)}
              className={`px-2.5 py-1 text-xs rounded transition-colors ${
                trackFilter === v
                  ? `${cls} text-white shadow-sm`
                  : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 border border-gray-200 dark:border-gray-700'
              }`}
            >
              {l}
            </button>
          ))}
        </div>

        {/* Gap */}
        <div className="flex items-center gap-1">
          <span className="text-xs text-muted-foreground mr-1">Gap:</span>
          {[3, 4, 5].map(g => (
            <button
              key={g}
              onClick={() => setMinGap(g)}
              className={`px-2.5 py-1 text-xs rounded transition-colors ${
                minGap === g
                  ? 'bg-orange-600 text-white shadow-sm'
                  : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 border border-gray-200 dark:border-gray-700'
              }`}
            >
              &ge;{g}
            </button>
          ))}
        </div>

        {/* EV */}
        <div className="flex items-center gap-1">
          <span className="text-xs text-muted-foreground mr-1">EV:</span>
          {[
            { v: 0, l: '全て' },
            { v: 0.8, l: '\u22650.8' },
            { v: 1.0, l: '\u22651.0' },
            { v: 1.2, l: '\u22651.2' },
          ].map(({ v, l }) => (
            <button
              key={v}
              onClick={() => setMinEv(v)}
              className={`px-2.5 py-1 text-xs rounded transition-colors ${
                minEv === v
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 border border-gray-200 dark:border-gray-700'
              }`}
            >
              {l}
            </button>
          ))}
        </div>

        {/* 件数表示 */}
        <span className="text-xs text-muted-foreground ml-auto">
          {filteredVBEntries.length !== allVBEntries.length
            ? `${filteredVBEntries.length} / ${allVBEntries.length} 件`
            : `${allVBEntries.length} 件`}
        </span>
      </div>

      {/* ROIサマリーカード（芝/ダート別） */}
      {hasResults && roiStats && (() => {
        const ROIRow = ({ label, s, badgeClass }: { label: string; s: typeof roiStats.all; badgeClass?: string }) => (
          s.vbCount > 0 ? (
            <div className="grid grid-cols-6 gap-2 text-center text-sm items-center py-1.5">
              <div className="text-left">
                {badgeClass ? (
                  <span className={`px-2 py-0.5 rounded text-xs font-bold ${badgeClass}`}>{label}</span>
                ) : (
                  <span className="text-xs font-bold">{label}</span>
                )}
              </div>
              <div>
                <div className="text-lg font-bold">{s.vbCount}</div>
              </div>
              <div>
                <div className="font-bold">{s.winHits}/{s.vbCount}</div>
              </div>
              <div>
                <div className={`font-bold ${s.winROI >= 100 ? 'text-green-600' : 'text-red-500'}`}>
                  {s.winROI.toFixed(1)}%
                </div>
                <div className={`text-[10px] ${s.winProfit >= 0 ? 'text-green-600' : 'text-red-500'}`}>
                  {s.winProfit >= 0 ? '+' : ''}&yen;{Math.round(s.winProfit).toLocaleString()}
                </div>
              </div>
              <div>
                <div className="font-bold">
                  {s.hasAnyPlaceOdds ? `${s.placeHits}/${s.placeBetCount}` : '-'}
                </div>
              </div>
              <div>
                {s.hasAnyPlaceOdds ? (
                  <>
                    <div className={`font-bold ${s.placeROI >= 100 ? 'text-green-600' : 'text-red-500'}`}>
                      {s.placeROI.toFixed(1)}%
                    </div>
                    <div className={`text-[10px] ${s.placeProfit >= 0 ? 'text-green-600' : 'text-red-500'}`}>
                      {s.placeProfit >= 0 ? '+' : ''}&yen;{Math.round(s.placeProfit).toLocaleString()}
                    </div>
                  </>
                ) : <div className="text-muted-foreground">-</div>}
              </div>
            </div>
          ) : null
        );
        return (
          <Card className="mb-6 border-blue-200 dark:border-blue-800">
            <CardContent className="py-4">
              <div className="flex items-center gap-2 mb-3">
                <span className="font-bold text-sm">VB成績サマリー</span>
                <Badge variant="outline" className="text-xs">結果反映済</Badge>
              </div>
              {/* ヘッダー */}
              <div className="grid grid-cols-6 gap-2 text-center text-[10px] text-muted-foreground border-b pb-1 mb-1">
                <div className="text-left">区分</div>
                <div>VB数</div>
                <div>単的中</div>
                <div>単勝ROI</div>
                <div>複的中</div>
                <div>複勝ROI</div>
              </div>
              <ROIRow label="全体" s={roiStats.all} />
              <ROIRow label="芝" s={roiStats.turf} badgeClass="bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300" />
              <ROIRow label="ダート" s={roiStats.dirt} badgeClass="bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300" />
            </CardContent>
          </Card>
        );
      })()}

      {/* 推奨買い目セクション */}
      {betRecommendations.length > 0 && (
        <Card className="mb-8 border-indigo-200 dark:border-indigo-800">
          <CardHeader className="pb-2 bg-gradient-to-r from-indigo-50 to-purple-50 dark:from-indigo-950 dark:to-purple-950">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg flex items-center gap-2">
                推奨買い目 ({sortedBetRecommendations.length !== betRecommendations.length ? `${sortedBetRecommendations.length}/` : ''}{betSummary.totalBets}件)
                <Badge variant="outline" className="text-xs">Stage 1</Badge>
              </CardTitle>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => { setOddsLoading(true); fetchAllOdds(); }}
                  disabled={oddsLoading}
                  className="px-2 py-0.5 text-xs rounded border bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 border-gray-300 dark:border-gray-600 disabled:opacity-50"
                  title="最新オッズを取得してKelly金額を再計算"
                >
                  {oddsLoading ? '取得中...' : '再計算'}
                </button>
                <label className="flex items-center gap-1 text-xs text-muted-foreground">
                  予算
                  <input
                    type="number"
                    value={dailyBudget}
                    onChange={(e) => updateBudget(Number(e.target.value))}
                    step={5000}
                    min={1000}
                    className="w-20 px-1.5 py-0.5 text-xs text-right rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                  />
                </label>
                {betSyncResult && (
                  <span className="text-xs text-green-700 dark:text-green-400">
                    {`${betSyncResult.racesWritten}件 / 単${betSyncResult.winBets} 複${betSyncResult.placeBets} / ¥${betSyncResult.totalAmount.toLocaleString()} → FF CSV出力済`}
                  </span>
                )}
                <button
                  onClick={syncBetMarks}
                  disabled={betSyncing}
                  className="px-3 py-1 text-xs font-medium rounded border bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 border-indigo-300 dark:border-indigo-700 disabled:opacity-50"
                  title="推奨買い目をFF CSV出力（TARGETの買い目取り込みメニューで読込）"
                >
                  {betSyncing ? '出力中...' : 'FF CSV出力'}
                </button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="pt-4">
            {/* サマリー */}
            <div className="grid grid-cols-3 md:grid-cols-6 gap-3 mb-4 text-center text-sm">
              <div className="bg-gray-50 dark:bg-gray-800/50 rounded p-2">
                <div className="text-lg font-bold">&yen;{betSummary.totalAmount.toLocaleString()}</div>
                <div className="text-[10px] text-muted-foreground">投資総額</div>
              </div>
              <div className="bg-red-50 dark:bg-red-900/20 rounded p-2">
                <div className="text-lg font-bold text-red-600">{betSummary.winCount}件</div>
                <div className="text-[10px] text-muted-foreground">単勝 &yen;{betSummary.winTotal.toLocaleString()}</div>
              </div>
              <div className="bg-blue-50 dark:bg-blue-900/20 rounded p-2">
                <div className="text-lg font-bold text-blue-600">{betSummary.placeCount}件</div>
                <div className="text-[10px] text-muted-foreground">複勝 &yen;{betSummary.placeTotal.toLocaleString()}</div>
              </div>
              <div className="bg-emerald-50 dark:bg-emerald-900/20 rounded p-2">
                <div className={`text-lg font-bold ${betSummary.avgEv >= 1.0 ? 'text-emerald-600' : 'text-yellow-600'}`}>
                  {betSummary.avgEv.toFixed(2)}
                </div>
                <div className="text-[10px] text-muted-foreground">加重平均EV</div>
              </div>
              <div className="bg-purple-50 dark:bg-purple-900/20 rounded p-2">
                <div className="text-lg font-bold text-purple-600">&yen;{betSummary.expectedReturn.toLocaleString()}</div>
                <div className="text-[10px] text-muted-foreground">期待回収額</div>
              </div>
              {betSummary.dangerRaces > 0 && (
                <div className="bg-orange-50 dark:bg-orange-900/20 rounded p-2 border border-orange-200 dark:border-orange-800">
                  <div className="text-lg font-bold text-orange-600">{betSummary.dangerRaces}R</div>
                  <div className="text-[10px] text-muted-foreground">危険人気馬</div>
                </div>
              )}
            </div>

            {/* 推奨テーブル */}
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="bg-indigo-50 dark:bg-indigo-900/30 text-xs">
                    <th className="px-2 py-2 text-left border">場</th>
                    <SortTh sortKey="race" sort={betSort} setSort={setBetSort} className="px-2 py-2 text-center border">R</SortTh>
                    <SortTh sortKey="umaban" sort={betSort} setSort={setBetSort} className="px-2 py-2 text-center border">馬番</SortTh>
                    <th className="px-2 py-2 text-left border">馬名</th>
                    <th className="px-2 py-2 text-center border">推奨</th>
                    <SortTh sortKey="winEv" sort={betSort} setSort={setBetSort} className="px-2 py-2 text-center border" title="単勝EV">単EV</SortTh>
                    <SortTh sortKey="placeEv" sort={betSort} setSort={setBetSort} className="px-2 py-2 text-center border" title="複勝EV">複EV</SortTh>
                    <SortTh sortKey="gap" sort={betSort} setSort={setBetSort} className="px-2 py-2 text-center border" title="VB Gap">Gap</SortTh>
                    <SortTh sortKey="kelly" sort={betSort} setSort={setBetSort} className="px-2 py-2 text-center border" title="Kelly基準ベット比率">Kelly</SortTh>
                    <SortTh sortKey="amount" sort={betSort} setSort={setBetSort} className="px-2 py-2 text-center border bg-yellow-50 dark:bg-yellow-900/20" title="推奨金額">金額</SortTh>
                    <SortTh sortKey="odds" sort={betSort} setSort={setBetSort} className="px-2 py-2 text-center border" title="単勝オッズ">オッズ</SortTh>
                    <SortTh sortKey="head" sort={betSort} setSort={setBetSort} className="px-2 py-2 text-center border" title="頭向き度">頭%</SortTh>
                    <SortTh sortKey="danger" sort={betSort} setSort={setBetSort} className="px-2 py-2 text-center border bg-orange-50 dark:bg-orange-900/20" title="危険な人気馬">危険馬</SortTh>
                  </tr>
                </thead>
                <tbody>
                  {sortedBetRecommendations.map((r) => {
                    const winOdds = getWinOdds(oddsMap, r.race.race_id, r.entry.umaban, r.entry.odds);
                    const headRatio = calcHeadRatio(r.entry.pred_proba_wv, r.entry.pred_proba_v);
                    const totalBet = r.betAmountWin + r.betAmountPlace;
                    const mainKelly = r.betType === '複勝' ? r.kellyPlace : r.kellyWin;
                    return (
                      <tr
                        key={`${r.race.race_id}-${r.entry.umaban}`}
                        className={`border-b hover:bg-indigo-50/50 dark:hover:bg-indigo-900/10 ${
                          r.danger?.isDanger
                            ? 'bg-orange-50/40 dark:bg-orange-900/10'
                            : r.strength === 'strong' ? 'bg-indigo-50/30 dark:bg-indigo-900/10' : ''
                        }`}
                      >
                        <td className="px-2 py-1.5 border text-xs">
                          <Link href={getRaceLink(r.race)} target="_blank" className="hover:text-blue-600 hover:underline">
                            {r.race.venue_name}
                          </Link>
                        </td>
                        <td className="px-2 py-1.5 border text-center font-bold">{r.race.race_number}</td>
                        <td className="px-2 py-1.5 border text-center font-mono">{r.entry.umaban}</td>
                        <td className="px-2 py-1.5 border font-bold text-xs">{r.entry.horse_name}</td>
                        <td className="px-2 py-1.5 border text-center">
                          <span className={`px-1.5 py-0.5 rounded text-[10px] ${getRecBadgeClass(r.betType, r.strength)}`}>
                            {r.betType}
                          </span>
                        </td>
                        <td className={`px-2 py-1.5 border text-center font-mono text-xs ${r.winEv && r.winEv >= 1.0 ? getEvColor(r.winEv) : 'text-gray-300'}`}>
                          {r.winEv ? r.winEv.toFixed(2) : '-'}
                        </td>
                        <td className={`px-2 py-1.5 border text-center font-mono text-xs ${r.placeEv && r.placeEv >= 1.0 ? 'text-blue-600 font-bold' : 'text-gray-300'}`}>
                          {r.placeEv ? r.placeEv.toFixed(2) : '-'}
                        </td>
                        <td className={`px-2 py-1.5 border text-center font-mono ${getGapColor(r.entry.vb_gap)}`}>
                          +{r.entry.vb_gap}
                        </td>
                        <td className="px-2 py-1.5 border text-center font-mono text-xs">
                          {(mainKelly * BET_CONFIG.kellyFraction * 100).toFixed(1)}%
                        </td>
                        <td className="px-2 py-1.5 border text-center font-mono font-bold bg-yellow-50/50 dark:bg-yellow-900/10">
                          {r.betAmountWin > 0 && <div className="text-red-600">&yen;{r.betAmountWin.toLocaleString()}</div>}
                          {r.betAmountPlace > 0 && <div className="text-blue-600">&yen;{r.betAmountPlace.toLocaleString()}</div>}
                        </td>
                        <td className="px-2 py-1.5 border text-center font-mono text-xs">
                          {winOdds ? winOdds.toFixed(1) : '-'}
                        </td>
                        <td className={`px-2 py-1.5 border text-center font-mono text-xs ${headRatio && headRatio >= 0.35 ? 'text-red-600 font-bold' : ''}`}>
                          {headRatio ? `${(headRatio * 100).toFixed(0)}` : '-'}
                        </td>
                        <td className="px-2 py-1.5 border text-center text-[10px]">
                          {r.danger?.dangerHorse ? (
                            <span className="text-orange-600 font-bold" title={`${r.danger.dangerHorse.horseName}: 人気${r.danger.dangerHorse.oddsRank}位 → V${r.danger.dangerHorse.rankV}位 (gap ${r.danger.dangerScore})`}>
                              {r.danger.dangerHorse.umaban}{r.danger.dangerHorse.horseName.slice(0, 3)}
                              <span className="text-orange-400 ml-0.5">+{r.danger.dangerScore}</span>
                            </span>
                          ) : '-'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="mt-3 text-[10px] text-muted-foreground">
              Kelly Criterion (1/4 Kelly) / 日予算 &yen;{dailyBudget.toLocaleString()} / 最低 &yen;{BET_CONFIG.minBet} / 危険レースはVB gap&ge;{BET_CONFIG.minGapDanger}に緩和
            </div>
          </CardContent>
        </Card>
      )}
      {betRecommendations.length === 0 && races.length > 0 && (
        <Card className="mb-8 border-gray-200 dark:border-gray-700">
          <CardContent className="py-6 text-center text-muted-foreground">
            <div className="text-lg font-bold mb-1">本日は見送り推奨</div>
            <div className="text-xs">EV &gt; 1.0 かつ VB gap &ge; {BET_CONFIG.minGap}（危険レースは &ge; {BET_CONFIG.minGapDanger}）の条件を満たす馬が見つかりません</div>
          </CardContent>
        </Card>
      )}

      {/* VB候補ハイライト */}
      {filteredVBEntries.length > 0 && (
        <Card className="mb-8 border-amber-200 dark:border-amber-800">
          <CardHeader className="pb-2 bg-gradient-to-r from-amber-50 to-orange-50 dark:from-amber-950 dark:to-orange-950">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg flex items-center gap-2">
                Value Bet 候補 ({filteredVBEntries.length}頭)
              </CardTitle>
              <div className="flex items-center gap-2">
                {markResult && (
                  <span className="text-xs text-green-700 dark:text-green-400">
                    {Object.entries(markResult.marks)
                      .filter(([, v]) => v > 0)
                      .map(([k, v]) => `${k}${v}`)
                      .join(' ')}
                    {' '}反映完了
                  </span>
                )}
                <button
                  onClick={syncVbMarks}
                  disabled={markSyncing}
                  className="px-3 py-1 text-xs font-medium rounded border bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 border-amber-300 dark:border-amber-700 disabled:opacity-50"
                  title="VB候補の印をTARGET馬印2に一括書込み"
                >
                  {markSyncing ? '反映中...' : 'VB印→馬印2'}
                </button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="pt-4">
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="bg-gray-100 dark:bg-gray-800 text-xs">
                    <th className="px-2 py-2 text-left border">場</th>
                    <SortTh sortKey="race" sort={vbSort} setSort={setVbSort} className="px-2 py-2 text-center border">R</SortTh>
                    <th className="px-2 py-2 text-center border" title="芝/ダート">馬場</th>
                    <SortTh sortKey="umaban" sort={vbSort} setSort={setVbSort} className="px-2 py-2 text-center border">馬番</SortTh>
                    <th className="px-2 py-2 text-left border">馬名</th>
                    <th className="px-2 py-2 text-center border" title="バックテスト分析に基づく購入推奨（芝→単勝優位、ダート→複勝優位）">推奨</th>
                    <th className="px-2 py-2 text-center border" title="競馬ブック本紙予想の印">本紙</th>
                    <SortTh sortKey="rank_v" sort={vbSort} setSort={setVbSort} className="px-2 py-2 text-center border" title="Value順位：市場非依存モデル(B)の予測順位">VR</SortTh>
                    <SortTh sortKey="odds_rank" sort={vbSort} setSort={setVbSort} className="px-2 py-2 text-center border" title="オッズ順人気">人気</SortTh>
                    <SortTh sortKey="odds" sort={vbSort} setSort={setVbSort} className="px-2 py-2 text-center border" title="単勝オッズ（DB最新）">オッズ</SortTh>
                    <SortTh sortKey="gap" sort={vbSort} setSort={setVbSort} className="px-2 py-2 text-center border" title="人気 - VR：市場評価とモデル評価の乖離（大きいほど過小評価）">Gap</SortTh>
                    <SortTh sortKey="ev" sort={vbSort} setSort={setVbSort} className="px-2 py-2 text-center border bg-emerald-50 dark:bg-emerald-900/30" title="単勝EV = P(win) × 単勝オッズ（1.0以上がプラス期待値）">単EV</SortTh>
                    <SortTh sortKey="place_ev" sort={vbSort} setSort={setVbSort} className="px-2 py-2 text-center border bg-blue-50 dark:bg-blue-900/30" title="複勝EV = P(top3) × 複勝オッズ最低値">複EV</SortTh>
                    <SortTh sortKey="head_ratio" sort={vbSort} setSort={setVbSort} className="px-2 py-2 text-center border" title="頭向き度 = P(win)/P(top3) — 高いほど勝ち切る力が強い">頭%</SortTh>
                    <SortTh sortKey="prob_v" sort={vbSort} setSort={setVbSort} className="px-2 py-2 text-center border" title="P(top3) 複勝圏予測確率（市場非依存）">V%</SortTh>
                    <th className="px-2 py-2 text-center border" title="競馬ブック調教評価の矢印">調教</th>
                    <th className="px-2 py-2 text-left border" title="競馬ブック短評コメント">短評</th>
                    {hasResults && <SortTh sortKey="finish" sort={vbSort} setSort={setVbSort} className="px-2 py-2 text-center border" title="確定着順">着順</SortTh>}
                    {hasResults && <th className="px-2 py-2 text-center border" title="単勝払い戻し（1着のみ・¥100あたり）">単払</th>}
                    {hasResults && <th className="px-2 py-2 text-center border" title="複勝払い戻し（複勝圏内のみ・¥100あたり）">複払</th>}
                  </tr>
                </thead>
                <tbody>
                  {sortedVBEntries.map(({ race, entry }) => {
                    const winOdds = getWinOdds(oddsMap, race.race_id, entry.umaban, entry.odds);
                    const ev = calcWinEv(entry, winOdds);
                    const placeOddsMin = entry.place_odds_min ?? getPlaceOddsMin(oddsMap, race.race_id, entry.umaban);
                    const placeEv = calcPlaceEv(entry.pred_proba_v, placeOddsMin);
                    const headRatio = calcHeadRatio(entry.pred_proba_wv, entry.pred_proba_v);
                    const finishPos = getFinishPos(race.race_id, entry.umaban);
                    const placeLimit = getPlaceLimit(race.num_runners);
                    const isPlaceHit = finishPos > 0 && placeLimit > 0 && finishPos <= placeLimit;
                    const dbEntry = dbResults[race.race_id]?.[entry.umaban];
                    const rec = getBuyRecommendation(race.track_type, entry.vb_gap, entry.rank_v, winOdds);
                    return (
                      <tr
                        key={`${race.race_id}-${entry.umaban}`}
                        className={`border-b hover:bg-blue-50/50 dark:hover:bg-blue-900/10 ${
                          finishPos === 1 ? 'bg-amber-50/60 dark:bg-amber-900/15' :
                          isPlaceHit ? 'bg-green-50/40 dark:bg-green-900/10' :
                          getGapBg(entry.vb_gap)
                        }`}
                      >
                        <td className="px-2 py-1.5 border text-xs">
                          <Link href={getRaceLink(race)} target="_blank" className="hover:text-blue-600 hover:underline">
                            {race.venue_name}
                          </Link>
                          {(() => { const dg = getRaceDanger(race.entries); return dg.isDanger ? (
                            <span className="ml-0.5 text-[9px] text-orange-500" title={`危険: ${dg.dangerHorse?.horseName} (人気${dg.dangerHorse?.oddsRank}→V${dg.dangerHorse?.rankV})`}>!</span>
                          ) : null; })()}
                        </td>
                        <td className="px-2 py-1.5 border text-center font-bold">
                          <Link href={getRaceLink(race)} target="_blank" className="hover:text-blue-600 hover:underline">
                            {race.race_number}
                          </Link>
                        </td>
                        <td className="px-2 py-1.5 border text-center">
                          <span className={`px-1.5 py-0.5 rounded text-[10px] ${getTrackBadgeClass(race.track_type)}`}>
                            {getTrackLabel(race.track_type)}{race.distance}
                          </span>
                        </td>
                        <td className="px-2 py-1.5 border text-center font-mono">{entry.umaban}</td>
                        <td className="px-2 py-1.5 border font-bold">
                          {entry.horse_name}
                          {(entry.koukaku_rote_count ?? 0) > 0 && (
                            <span className="ml-1 text-[9px] px-1 py-0.5 rounded bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300" title={getKoukakuDetail(entry)}>
                              降格{(entry.koukaku_rote_count ?? 0) > 1 ? `×${entry.koukaku_rote_count}` : ''}
                            </span>
                          )}
                        </td>
                        <td className="px-2 py-1.5 border text-center">
                          {rec.type && (
                            <span className={`px-1.5 py-0.5 rounded text-[10px] ${getRecBadgeClass(rec.type, rec.strength)}`}>
                              {rec.type}
                            </span>
                          )}
                        </td>
                        <td className={`px-2 py-1.5 border text-center ${getMarkColor(entry.kb_mark)}`}>
                          {entry.kb_mark || '-'}
                        </td>
                        <td className="px-2 py-1.5 border text-center font-mono font-bold text-blue-600">{entry.rank_v}</td>
                        <td className="px-2 py-1.5 border text-center font-mono">{entry.odds_rank || '-'}</td>
                        <td className="px-2 py-1.5 border text-center font-mono font-bold">
                          {winOdds ? winOdds.toFixed(1) : '-'}
                        </td>
                        <td className={`px-2 py-1.5 border text-center font-mono ${getGapColor(entry.vb_gap)}`}>
                          +{entry.vb_gap}
                        </td>
                        <td className={`px-2 py-1.5 border text-center font-mono ${ev !== null ? getEvColor(ev) : 'text-gray-300'} bg-emerald-50/50 dark:bg-emerald-900/10`}>
                          {ev !== null ? ev.toFixed(2) : '-'}
                        </td>
                        <td className={`px-2 py-1.5 border text-center font-mono text-xs ${placeEv !== null && placeEv >= 1.0 ? 'text-blue-600 font-bold' : placeEv !== null ? 'text-blue-400' : 'text-gray-300'} bg-blue-50/30 dark:bg-blue-900/10`}>
                          {placeEv !== null ? placeEv.toFixed(2) : '-'}
                        </td>
                        <td className={`px-2 py-1.5 border text-center font-mono text-xs ${headRatio !== null && headRatio >= 0.35 ? 'text-red-600 font-bold' : headRatio !== null ? '' : 'text-gray-300'}`}>
                          {headRatio !== null ? `${(headRatio * 100).toFixed(0)}` : '-'}
                        </td>
                        <td className="px-2 py-1.5 border text-center font-mono text-xs">
                          {(entry.pred_proba_v * 100).toFixed(1)}
                        </td>
                        <td className="px-2 py-1.5 border text-center">{entry.kb_training_arrow}</td>
                        <td className="px-2 py-1.5 border text-xs text-muted-foreground max-w-[200px] truncate">
                          {entry.kb_comment}
                        </td>
                        {hasResults && (
                          <td className={`px-2 py-1.5 border text-center font-mono ${finishPos > 0 ? getFinishColor(finishPos) : 'text-gray-300'}`}>
                            {finishPos > 0 ? `${finishPos}着` : '-'}
                          </td>
                        )}
                        {hasResults && (
                          <td className={`px-2 py-1.5 border text-center font-mono text-xs ${finishPos === 1 && dbEntry?.confirmedWinOdds ? 'text-red-600 font-bold' : 'text-gray-300'}`}>
                            {finishPos === 1 && dbEntry?.confirmedWinOdds
                              ? `¥${Math.round(dbEntry.confirmedWinOdds * 100).toLocaleString()}`
                              : ''}
                          </td>
                        )}
                        {hasResults && (
                          <td className={`px-2 py-1.5 border text-center font-mono text-xs ${isPlaceHit && dbEntry?.confirmedPlaceOddsMin ? 'text-blue-600 font-bold' : 'text-gray-300'}`}>
                            {isPlaceHit && dbEntry?.confirmedPlaceOddsMin
                              ? `¥${Math.round(dbEntry.confirmedPlaceOddsMin * 100).toLocaleString()}`
                              : ''}
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 開催場別レース一覧 */}
      <div className="space-y-8">
        {Array.from(filteredVenueGroups.entries()).map(([venue, venueRaces]) => (
          <div key={venue}>
            <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
              {venue}
              <Badge variant="outline">{venueRaces.length}R</Badge>
              <Badge variant="secondary" className="text-xs">
                VB: {venueRaces.reduce((s, r) => s + r.entries.filter(e => e.is_value_bet).length, 0)}頭
              </Badge>
            </h2>

            <div className="space-y-4">
              {venueRaces.sort((a, b) => a.race_number - b.race_number).map((race) => (
                <RaceCard key={race.race_id} race={race} oddsMap={oddsMap} results={results} dbResults={dbResults} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// --- レースカード ---

function RaceCard({ race, oddsMap, results, dbResults }: { race: PredictionRace; oddsMap: OddsMap; results?: RaceResultsMap; dbResults?: DbResultsMap }) {
  const dbRaceResult = dbResults?.[race.race_id];
  const jsonRaceResult = results?.[race.race_id];
  const hasResults = (dbRaceResult ? Object.keys(dbRaceResult).length > 0 : false) || (jsonRaceResult ? Object.keys(jsonRaceResult).length > 0 : false);
  const vbEntries = race.entries.filter(e => e.is_value_bet);

  const [sort, setSort] = useState<SortState>({ key: 'umaban', dir: 'asc' });

  const sortedEntries = useMemo(() => {
    const arr = [...race.entries];
    const { key, dir } = sort;
    const mul = dir === 'asc' ? 1 : -1;
    arr.sort((a, b) => {
      let va: number, vb: number;
      switch (key) {
        case 'rank_a': va = a.rank_a; vb = b.rank_a; break;
        case 'rank_v': va = a.rank_v; vb = b.rank_v; break;
        case 'odds_rank': va = a.odds_rank || 999; vb = b.odds_rank || 999; break;
        case 'odds': {
          va = getWinOdds(oddsMap, race.race_id, a.umaban, a.odds) ?? 9999;
          vb = getWinOdds(oddsMap, race.race_id, b.umaban, b.odds) ?? 9999;
          break;
        }
        case 'gap': va = a.vb_gap; vb = b.vb_gap; break;
        case 'ev': {
          va = calcWinEv(a, getWinOdds(oddsMap, race.race_id, a.umaban, a.odds)) ?? -1;
          vb = calcWinEv(b, getWinOdds(oddsMap, race.race_id, b.umaban, b.odds)) ?? -1;
          break;
        }
        case 'prob_a': va = a.pred_proba_a; vb = b.pred_proba_a; break;
        case 'prob_v': va = a.pred_proba_v; vb = b.pred_proba_v; break;
        case 'rating': va = a.kb_rating || 0; vb = b.kb_rating || 0; break;
        case 'finish': {
          const pa = dbRaceResult?.[a.umaban]?.finishPosition ?? jsonRaceResult?.[a.umaban]?.finish_position ?? 0;
          const pb = dbRaceResult?.[b.umaban]?.finishPosition ?? jsonRaceResult?.[b.umaban]?.finish_position ?? 0;
          va = pa > 0 ? pa : 999;
          vb = pb > 0 ? pb : 999;
          break;
        }
        default: /* umaban */ va = a.umaban; vb = b.umaban; break;
      }
      return (va - vb) * mul;
    });
    return arr;
  }, [race.entries, sort, oddsMap, race.race_id, dbRaceResult, jsonRaceResult]);

  return (
    <Card className="overflow-hidden">
      <CardHeader className="py-3 px-4 border-b bg-muted/30">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              href={getRaceLink(race)}
              target="_blank"
              className="text-lg font-bold hover:text-blue-600 hover:underline"
            >
              {race.race_number}R
            </Link>
            <Badge className={`text-[10px] ${getTrackBadgeClass(race.track_type)}`}>
              {race.track_type}{race.distance}m
            </Badge>
            <span className="text-sm text-muted-foreground">{race.num_runners}頭</span>
          </div>
          <div className="flex items-center gap-2">
            {vbEntries.length > 0 && (
              <Badge variant="outline" className="text-amber-600 border-amber-300">
                VB {vbEntries.length}頭
              </Badge>
            )}
            <Link
              href={getRaceLink(race)}
              target="_blank"
              className="text-xs text-blue-600 hover:underline"
            >
              詳細 →
            </Link>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-gray-50 dark:bg-gray-800/50 text-xs">
                <SortTh sortKey="umaban" sort={sort} setSort={setSort} className="px-2 py-1.5 text-center border-b w-10">番</SortTh>
                <th className="px-2 py-1.5 text-left border-b min-w-[100px]">馬名</th>
                <th className="px-2 py-1.5 text-center border-b w-10" title="競馬ブック本紙予想の印">紙</th>
                <SortTh sortKey="rank_a" sort={sort} setSort={setSort} className="px-2 py-1.5 text-center border-b w-12" title="Model A（精度モデル）の順位 — 全特徴量使用">A順</SortTh>
                <SortTh sortKey="rank_v" sort={sort} setSort={setSort} className="px-2 py-1.5 text-center border-b w-12" title="Model V（市場非依存モデル）の順位 — オッズ不使用">V順</SortTh>
                <SortTh sortKey="odds_rank" sort={sort} setSort={setSort} className="px-2 py-1.5 text-center border-b w-10" title="オッズ順人気">人</SortTh>
                <SortTh sortKey="odds" sort={sort} setSort={setSort} className="px-2 py-1.5 text-center border-b w-14" title="単勝オッズ（DB最新）">オッズ</SortTh>
                <SortTh sortKey="gap" sort={sort} setSort={setSort} className="px-2 py-1.5 text-center border-b w-12" title="人気 - VR：市場評価とモデル評価の乖離">Gap</SortTh>
                <SortTh sortKey="ev" sort={sort} setSort={setSort} className="px-2 py-1.5 text-center border-b w-14 bg-emerald-50/50 dark:bg-emerald-900/20" title="単勝EV = P(win) × 単勝オッズ（1.0以上がプラス期待値）">単EV</SortTh>
                <SortTh sortKey="prob_a" sort={sort} setSort={setSort} className="px-2 py-1.5 text-center border-b w-14" title="Model A 3着内確率（%） — 全特徴量">A%</SortTh>
                <SortTh sortKey="prob_v" sort={sort} setSort={setSort} className="px-2 py-1.5 text-center border-b w-14" title="Model V 3着内確率（%） — 市場非依存">V%</SortTh>
                <SortTh sortKey="rating" sort={sort} setSort={setSort} className="px-2 py-1.5 text-center border-b w-14" title="競馬ブックレイティング">Rate</SortTh>
                <th className="px-2 py-1.5 text-center border-b w-10" title="競馬ブック調教評価">調</th>
                <th className="px-2 py-1.5 text-left border-b" title="競馬ブック短評">短評</th>
                {hasResults && <SortTh sortKey="finish" sort={sort} setSort={setSort} className="px-2 py-1.5 text-center border-b w-12" title="確定着順">着順</SortTh>}
                {hasResults && <th className="px-2 py-1.5 text-center border-b w-16" title="単勝払い戻し（1着のみ・¥100あたり）">単払</th>}
                {hasResults && <th className="px-2 py-1.5 text-center border-b w-16" title="複勝払い戻し（複勝圏内のみ・¥100あたり）">複払</th>}
              </tr>
            </thead>
            <tbody>
              {sortedEntries.map((entry) => {
                const isVB = entry.is_value_bet;
                const isTopA = entry.rank_a <= 3;
                const winOdds = getWinOdds(oddsMap, race.race_id, entry.umaban, entry.odds);
                const ev = calcWinEv(entry, winOdds);
                const dbEntry = dbRaceResult?.[entry.umaban];
                const jsonEntry = jsonRaceResult?.[entry.umaban];
                const finishPos = dbEntry?.finishPosition ?? jsonEntry?.finish_position ?? 0;
                return (
                  <tr
                    key={entry.umaban}
                    className={`border-b transition-colors ${
                      hasResults && finishPos === 1 ? 'bg-amber-50/60 dark:bg-amber-900/15' :
                      hasResults && finishPos > 0 && finishPos <= 3 ? 'bg-green-50/30 dark:bg-green-900/5' :
                      isVB ? getGapBg(entry.vb_gap) :
                      isTopA ? 'bg-blue-50/30 dark:bg-blue-900/5' : ''
                    } hover:bg-blue-50/50 dark:hover:bg-blue-900/10`}
                  >
                    <td className="px-2 py-1 text-center font-mono text-xs">{entry.umaban}</td>
                    <td className="px-2 py-1 font-bold text-xs">
                      {entry.horse_name}
                      {isVB && <span className="ml-1 text-amber-500 text-[10px]">VB</span>}
                      {isVB && (() => {
                        const rec = getBuyRecommendation(race.track_type, entry.vb_gap, entry.rank_v, winOdds);
                        return rec.type ? (
                          <span className={`ml-1 px-1 py-0.5 rounded text-[9px] ${getRecBadgeClass(rec.type, rec.strength)}`}>
                            {rec.type}
                          </span>
                        ) : null;
                      })()}
                      {(entry.koukaku_rote_count ?? 0) > 0 && (
                        <span className="ml-1 text-[9px] px-1 py-0.5 rounded bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300" title={getKoukakuDetail(entry)}>
                          降格{(entry.koukaku_rote_count ?? 0) > 1 ? `×${entry.koukaku_rote_count}` : ''}
                        </span>
                      )}
                    </td>
                    <td className={`px-2 py-1 text-center ${getMarkColor(entry.kb_mark)}`}>
                      {entry.kb_mark || '-'}
                    </td>
                    <td className={`px-2 py-1 text-center font-mono text-xs ${entry.rank_a <= 3 ? 'font-bold text-blue-600' : ''}`}>
                      {entry.rank_a}
                    </td>
                    <td className={`px-2 py-1 text-center font-mono text-xs ${entry.rank_v <= 3 ? 'font-bold text-purple-600' : ''}`}>
                      {entry.rank_v}
                    </td>
                    <td className="px-2 py-1 text-center font-mono text-xs">{entry.odds_rank || '-'}</td>
                    <td className="px-2 py-1 text-center font-mono text-xs font-bold">
                      {winOdds ? winOdds.toFixed(1) : '-'}
                    </td>
                    <td className={`px-2 py-1 text-center font-mono text-xs ${entry.vb_gap >= 3 ? getGapColor(entry.vb_gap) : 'text-gray-400'}`}>
                      {entry.vb_gap > 0 ? `+${entry.vb_gap}` : entry.vb_gap === 0 ? '0' : entry.vb_gap}
                    </td>
                    <td className={`px-2 py-1 text-center font-mono text-xs ${ev !== null ? getEvColor(ev) : 'text-gray-300'} bg-emerald-50/30 dark:bg-emerald-900/10`}>
                      {ev !== null ? ev.toFixed(2) : '-'}
                    </td>
                    <td className="px-2 py-1 text-center font-mono text-xs">{(entry.pred_proba_a * 100).toFixed(1)}</td>
                    <td className="px-2 py-1 text-center font-mono text-xs">{(entry.pred_proba_v * 100).toFixed(1)}</td>
                    <td className="px-2 py-1 text-center font-mono text-xs">{entry.kb_rating > 0 ? entry.kb_rating.toFixed(1) : '-'}</td>
                    <td className="px-2 py-1 text-center text-xs">{entry.kb_training_arrow}</td>
                    <td className="px-2 py-1 text-xs text-muted-foreground truncate max-w-[180px]">{entry.kb_comment}</td>
                    {hasResults && (
                      <td className={`px-2 py-1 text-center font-mono text-xs ${finishPos > 0 ? getFinishColor(finishPos) : 'text-gray-300'}`}>
                        {finishPos > 0 ? finishPos : '-'}
                      </td>
                    )}
                    {hasResults && (() => {
                      const isWin = finishPos === 1 && dbEntry?.confirmedWinOdds;
                      return (
                        <td className={`px-2 py-1 text-center font-mono text-xs ${isWin ? 'text-red-600 font-bold' : ''}`}>
                          {isWin ? `¥${Math.round(dbEntry!.confirmedWinOdds * 100).toLocaleString()}` : ''}
                        </td>
                      );
                    })()}
                    {hasResults && (() => {
                      const placeLimit = getPlaceLimit(race.num_runners);
                      const isPlaceHit = finishPos > 0 && placeLimit > 0 && finishPos <= placeLimit;
                      const hasPlaceOdds = isPlaceHit && dbEntry?.confirmedPlaceOddsMin;
                      return (
                        <td className={`px-2 py-1 text-center font-mono text-xs ${hasPlaceOdds ? 'text-blue-600 font-bold' : ''}`}>
                          {hasPlaceOdds ? `¥${Math.round(dbEntry!.confirmedPlaceOddsMin! * 100).toLocaleString()}` : ''}
                        </td>
                      );
                    })()}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
