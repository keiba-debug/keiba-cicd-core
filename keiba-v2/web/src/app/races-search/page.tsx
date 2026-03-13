'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { RACE_TREND_V2_LABELS, RACE_TREND_V2_COLORS, type RaceTrendV2Type } from '@/lib/data/rpci-utils';

// ── 型定義 ──

interface RaceSearchEntry {
  raceId: string;
  date: string;
  venue: string;
  raceNumber: number;
  raceName: string;
  grade: string;
  track: string;
  distance: number;
  trackCondition: string;
  entryCount: number;
  winnerName: string;
  winnerTime: string;
  winnerLast3f: number | null;
  weather: string;
  paceType: string;
  rpci: number | null;
  raceTrendV2?: string;
}

// ── 定数 ──

const VENUES = ['東京', '中山', '阪神', '京都', '中京', '小倉', '札幌', '函館', '福島', '新潟'] as const;
const GRADE_OPTIONS = ['G1', 'G2', 'G3', 'OP', 'L', '3勝', '2勝', '1勝', '未勝利', '新馬'] as const;

const DATE_PRESETS = [
  { label: '直近1ヶ月', months: 1 },
  { label: '3ヶ月', months: 3 },
  { label: '6ヶ月', months: 6 },
  { label: '1年', months: 12 },
] as const;

function monthsAgo(n: number): string {
  const d = new Date();
  d.setMonth(d.getMonth() - n);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}
function currentMonth(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}
const DISTANCE_PRESETS = [1200, 1400, 1600, 1800, 2000, 2200, 2400, 3000] as const;
const BABA_OPTIONS = ['良', '稍重', '重', '不良'] as const;

const GRADE_COLORS: Record<string, string> = {
  G1: 'bg-red-500 text-white',
  G2: 'bg-blue-500 text-white',
  G3: 'bg-green-600 text-white',
  OP: 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300',
  L: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
  '3勝': 'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
  '2勝': 'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
  '1勝': 'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
  '未勝利': 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400',
  '新馬': 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400',
};

const PACE_BADGE: Record<string, { label: string; className: string }> = {
  sprint: { label: '瞬発', className: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300' },
  average: { label: '平均', className: 'bg-gray-100 text-gray-600 dark:bg-gray-700/30 dark:text-gray-300' },
  stamina: { label: '持続', className: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300' },
};

const WEATHER_ICON: Record<string, string> = {
  '晴': '☀',
  '曇': '☁',
  '雨': '🌧',
  '小雨': '🌦',
  '雪': '❄',
};

const BABA_COLORS: Record<string, string> = {
  '良': 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
  '稍重': 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300',
  '重': 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300',
  '不良': 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
};

function stripGradePrefix(name: string): string {
  return name
    .replace(/^Ｇ[１２３]\s*/, '')
    .replace(/^G[123]\s*/, '')
    .replace(/^Ｌ\s*/, '')
    .trim();
}

function toggleItem<T>(arr: T[], item: T): T[] {
  return arr.includes(item) ? arr.filter((v) => v !== item) : [...arr, item];
}

// ── フィルタチップ ──

function Chip({
  label,
  active,
  onClick,
  colorClass,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  colorClass?: string;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'px-2 py-0.5 text-xs rounded border transition-colors',
        active
          ? colorClass || 'bg-primary text-primary-foreground border-primary'
          : 'bg-background hover:bg-muted border-border text-foreground',
      )}
    >
      {label}
    </button>
  );
}

// ── ページコンポーネント ──

export default function RaceSearchPage() {
  const [query, setQuery] = useState('');
  const [venues, setVenues] = useState<string[]>([]);
  const [track, setTrack] = useState('');
  const [distanceMin, setDistanceMin] = useState('');
  const [distanceMax, setDistanceMax] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [grades, setGrades] = useState<string[]>([]);
  const [babas, setBabas] = useState<string[]>([]);

  const [results, setResults] = useState<RaceSearchEntry[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [filteredCount, setFilteredCount] = useState(0);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  const handleSearch = async () => {
    setIsSearching(true);
    setHasSearched(true);

    const params = new URLSearchParams();
    if (query.trim()) params.set('q', query.trim());
    if (venues.length) params.set('venues', venues.join(','));
    if (track) params.set('track', track);
    if (distanceMin) params.set('distanceMin', distanceMin);
    if (distanceMax) params.set('distanceMax', distanceMax);
    if (dateFrom) params.set('dateFrom', dateFrom);
    if (dateTo) params.set('dateTo', dateTo);
    if (grades.length) params.set('grades', grades.join(','));
    if (babas.length) params.set('babas', babas.join(','));

    try {
      const res = await fetch(`/api/races/search?${params.toString()}`);
      const data = await res.json();
      setResults(data.races || []);
      setTotalCount(data.totalCount || 0);
      setFilteredCount(data.filteredCount || 0);
    } catch (error) {
      console.error('Search error:', error);
      setResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  const handleReset = () => {
    setQuery('');
    setVenues([]);
    setTrack('');
    setDistanceMin('');
    setDistanceMax('');
    setDateFrom('');
    setDateTo('');
    setGrades([]);
    setBabas([]);
  };

  const setDistancePreset = (d: number) => {
    setDistanceMin(String(d));
    setDistanceMax(String(d));
  };

  const hasActiveFilters =
    venues.length > 0 || track || distanceMin || distanceMax || dateFrom || dateTo || grades.length > 0 || babas.length > 0;

  return (
    <div className="container py-6 max-w-6xl">
      <h1 className="text-2xl font-bold mb-4">レース検索</h1>

      {/* 検索バー */}
      <div className="flex gap-2 mb-4">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          placeholder="レース名を入力..."
          className="flex-1 px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary dark:bg-gray-900 dark:border-gray-700"
        />
        <Button onClick={handleSearch} disabled={isSearching}>
          {isSearching ? '検索中...' : '検索'}
        </Button>
        {hasActiveFilters && (
          <Button variant="ghost" size="sm" onClick={handleReset} className="text-xs text-muted-foreground">
            リセット
          </Button>
        )}
      </div>

      {/* フィルタパネル（常時表示・コンパクト） */}
      <div className="border rounded-lg p-3 mb-5 space-y-2.5 bg-muted/20 text-sm">
        {/* 競馬場 + トラック */}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-muted-foreground font-medium w-12 shrink-0">競馬場</span>
            <div className="flex flex-wrap gap-1">
              {VENUES.map((v) => (
                <Chip key={v} label={v} active={venues.includes(v)} onClick={() => setVenues(toggleItem(venues, v))} />
              ))}
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-muted-foreground font-medium shrink-0">トラック</span>
            <div className="flex gap-1">
              {['芝', 'ダ'].map((t) => (
                <Chip key={t} label={t} active={track === t} onClick={() => setTrack(track === t ? '' : t)} />
              ))}
            </div>
          </div>
        </div>

        {/* 距離 */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-muted-foreground font-medium w-12 shrink-0">距離</span>
          <div className="flex flex-wrap gap-1">
            {DISTANCE_PRESETS.map((d) => (
              <Chip
                key={d}
                label={`${d}`}
                active={distanceMin === String(d) && distanceMax === String(d)}
                onClick={() => {
                  if (distanceMin === String(d) && distanceMax === String(d)) {
                    setDistanceMin('');
                    setDistanceMax('');
                  } else {
                    setDistancePreset(d);
                  }
                }}
              />
            ))}
          </div>
          <div className="flex items-center gap-1.5 ml-1">
            <input
              type="number"
              value={distanceMin}
              onChange={(e) => setDistanceMin(e.target.value)}
              placeholder="下限"
              className="w-20 px-2 py-0.5 text-xs border rounded dark:bg-gray-900 dark:border-gray-700"
            />
            <span className="text-xs text-muted-foreground">~</span>
            <input
              type="number"
              value={distanceMax}
              onChange={(e) => setDistanceMax(e.target.value)}
              placeholder="上限"
              className="w-20 px-2 py-0.5 text-xs border rounded dark:bg-gray-900 dark:border-gray-700"
            />
            <span className="text-xs text-muted-foreground">m</span>
          </div>
        </div>

        {/* グレード + 馬場 + 年度 */}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-muted-foreground font-medium w-12 shrink-0">グレード</span>
            <div className="flex flex-wrap gap-1">
              {GRADE_OPTIONS.map((g) => (
                <Chip key={g} label={g} active={grades.includes(g)} onClick={() => setGrades(toggleItem(grades, g))} />
              ))}
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-muted-foreground font-medium shrink-0">馬場</span>
            <div className="flex gap-1">
              {BABA_OPTIONS.map((b) => (
                <Chip key={b} label={b} active={babas.includes(b)} onClick={() => setBabas(toggleItem(babas, b))} />
              ))}
            </div>
          </div>
        </div>

        {/* 期間 */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-muted-foreground font-medium w-12 shrink-0">期間</span>
          <div className="flex flex-wrap gap-1">
            {DATE_PRESETS.map((p) => {
              const from = monthsAgo(p.months);
              const to = currentMonth();
              const active = dateFrom === from && dateTo === to;
              return (
                <Chip
                  key={p.label}
                  label={p.label}
                  active={active}
                  onClick={() => {
                    if (active) { setDateFrom(''); setDateTo(''); }
                    else { setDateFrom(from); setDateTo(to); }
                  }}
                />
              );
            })}
          </div>
          <div className="flex items-center gap-1.5 ml-1">
            <input
              type="month"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="px-2 py-0.5 text-xs border rounded dark:bg-gray-900 dark:border-gray-700"
            />
            <span className="text-xs text-muted-foreground">~</span>
            <input
              type="month"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="px-2 py-0.5 text-xs border rounded dark:bg-gray-900 dark:border-gray-700"
            />
          </div>
        </div>
      </div>

      {/* 検索結果 */}
      {hasSearched ? (
        <div>
          <p className="text-xs text-muted-foreground mb-3">
            {filteredCount > 100
              ? `${filteredCount}件中 上位100件を表示（全${totalCount.toLocaleString()}件中）`
              : `${filteredCount}件の結果（全${totalCount.toLocaleString()}件中）`}
          </p>

          {results.length > 0 ? (
            <div className="border rounded-lg overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-muted/50 text-xs text-muted-foreground">
                  <tr>
                    <th className="text-left px-3 py-2 font-medium">日付</th>
                    <th className="text-left px-3 py-2 font-medium">場R</th>
                    <th className="text-left px-3 py-2 font-medium">グレード</th>
                    <th className="text-left px-3 py-2 font-medium">レース名</th>
                    <th className="text-left px-3 py-2 font-medium">コース</th>
                    <th className="text-left px-3 py-2 font-medium">馬場</th>
                    <th className="text-left px-3 py-2 font-medium">頭</th>
                    <th className="text-left px-3 py-2 font-medium">勝ち馬</th>
                    <th className="text-left px-3 py-2 font-medium">タイム</th>
                    <th className="text-left px-3 py-2 font-medium">上り</th>
                    <th className="text-left px-3 py-2 font-medium">ペース型</th>
                    <th className="text-right px-3 py-2 font-medium">CQ</th>
                    <th className="text-right px-3 py-2 font-medium">含水</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {results.map((race) => (
                    <RaceRow key={`${race.raceId}-${race.date}`} race={race} />
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-muted-foreground py-8 text-center">該当するレースが見つかりませんでした</p>
          )}
        </div>
      ) : (
        <p className="text-muted-foreground py-8 text-center text-sm">
          レース名を入力するか、絞り込み条件を設定して検索してください
        </p>
      )}
    </div>
  );
}

// ── テーブル行 ──

function RaceRow({ race }: { race: RaceSearchEntry }) {
  const href = `/races-v2/${race.date}/${encodeURIComponent(race.venue)}/${race.raceId}`;
  const displayName = stripGradePrefix(race.raceName);
  const pace = PACE_BADGE[race.paceType];
  const babaColor = BABA_COLORS[race.trackCondition];
  const gradeColor = GRADE_COLORS[race.grade];
  const weatherIcon = WEATHER_ICON[race.weather];

  const trend =
    race.raceTrendV2 && RACE_TREND_V2_LABELS[race.raceTrendV2 as RaceTrendV2Type]
      ? { label: RACE_TREND_V2_LABELS[race.raceTrendV2 as RaceTrendV2Type], className: RACE_TREND_V2_COLORS[race.raceTrendV2 as RaceTrendV2Type] }
      : pace
        ? { label: pace.label, className: pace.className }
        : null;

  return (
      <tr
        className="hover:bg-muted/40 transition-colors cursor-pointer"
        onClick={() => window.open(href, '_blank', 'noopener,noreferrer')}
      >
        <td className="px-3 py-2 text-xs text-muted-foreground whitespace-nowrap">{race.date}</td>
        <td className="px-3 py-2 text-xs whitespace-nowrap">
          {race.venue}{race.raceNumber}R
        </td>
        <td className="px-3 py-2">
          {race.grade && gradeColor && (
            <span className={cn('px-1.5 py-0.5 rounded text-[10px] font-bold', gradeColor)}>{race.grade}</span>
          )}
        </td>
        <td className="px-3 py-2 font-medium max-w-[200px] truncate">
          {displayName || `${race.raceNumber}R`}
        </td>
        <td className="px-3 py-2 text-xs whitespace-nowrap">
          {race.track}{race.distance}m
        </td>
        <td className="px-3 py-2 text-xs">
          <div className="flex items-center gap-1">
            {race.trackCondition && babaColor && (
              <span className={cn('px-1 py-0.5 rounded text-[10px] font-medium', babaColor)}>
                {race.trackCondition}
              </span>
            )}
            {weatherIcon && <span className="text-xs">{weatherIcon}</span>}
          </div>
        </td>
        <td className="px-3 py-2 text-xs text-muted-foreground">{race.entryCount > 0 ? race.entryCount : ''}</td>
        <td className="px-3 py-2 text-xs text-yellow-600 dark:text-yellow-400 font-medium whitespace-nowrap">
          {race.winnerName}
        </td>
        <td className="px-3 py-2 text-xs text-muted-foreground whitespace-nowrap">{race.winnerTime}</td>
        <td className="px-3 py-2 text-xs text-muted-foreground">
          {race.winnerLast3f != null ? race.winnerLast3f : ''}
        </td>
        <td className="px-3 py-2">
          {trend && (
            <span className={cn('px-1.5 py-0.5 rounded text-[10px] font-medium', trend.className)}>
              {trend.label}
            </span>
          )}
        </td>
        <td className="px-3 py-2 text-xs text-right text-muted-foreground font-mono">
          {race.cushionValue != null ? race.cushionValue.toFixed(1) : ''}
        </td>
        <td className="px-3 py-2 text-xs text-right text-muted-foreground font-mono">
          {race.moistureRate != null ? race.moistureRate.toFixed(1) : ''}
        </td>
      </tr>
  );
}
