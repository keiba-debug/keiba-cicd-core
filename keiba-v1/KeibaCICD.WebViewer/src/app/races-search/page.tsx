'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

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
  raceTrend: string;
  rpci: number | null;
}

// ── 定数 ──

const VENUES = ['東京', '中山', '阪神', '京都', '中京', '小倉', '札幌', '函館', '福島', '新潟'] as const;
const YEARS = [2026, 2025, 2024, 2023] as const;
const GRADE_OPTIONS = ['G1', 'G2', 'G3', 'OP', 'L', '3勝', '2勝', '1勝', '未勝利', '新馬'] as const;

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

const TREND_BADGE: Record<string, { label: string; className: string }> = {
  sprint_finish: { label: '瞬発', className: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300' },
  long_sprint: { label: 'ロンスパ', className: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300' },
  even_pace: { label: '平均', className: 'bg-gray-100 text-gray-600 dark:bg-gray-700/30 dark:text-gray-300' },
  front_loaded: { label: 'H前傾', className: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300' },
  front_loaded_strong: { label: 'H後傾', className: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300' },
};

const BABA_COLORS: Record<string, string> = {
  '良': 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
  '稍重': 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300',
  '重': 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300',
  '不良': 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
};

// ── レース名からグレードプレフィックスを除去 ──

function stripGradePrefix(name: string): string {
  return name
    .replace(/^Ｇ[１２３]\s*/, '')
    .replace(/^G[123]\s*/, '')
    .replace(/^Ｌ\s*/, '')
    .trim();
}

// ── チェックボックストグルヘルパー ──

function toggleItem<T>(arr: T[], item: T): T[] {
  return arr.includes(item) ? arr.filter((v) => v !== item) : [...arr, item];
}

// ── ページコンポーネント ──

export default function RaceSearchPage() {
  // 検索条件
  const [query, setQuery] = useState('');
  const [venues, setVenues] = useState<string[]>([]);
  const [track, setTrack] = useState('');
  const [distanceMin, setDistanceMin] = useState('');
  const [distanceMax, setDistanceMax] = useState('');
  const [years, setYears] = useState<number[]>([]);
  const [grades, setGrades] = useState<string[]>([]);

  // 結果
  const [results, setResults] = useState<RaceSearchEntry[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [filteredCount, setFilteredCount] = useState(0);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  // フィルタ表示
  const [showFilters, setShowFilters] = useState(false);

  const handleSearch = async () => {
    setIsSearching(true);
    setHasSearched(true);

    const params = new URLSearchParams();
    if (query.trim()) params.set('q', query.trim());
    if (venues.length) params.set('venues', venues.join(','));
    if (track) params.set('track', track);
    if (distanceMin) params.set('distanceMin', distanceMin);
    if (distanceMax) params.set('distanceMax', distanceMax);
    if (years.length) params.set('years', years.join(','));
    if (grades.length) params.set('grades', grades.join(','));

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
    setYears([]);
    setGrades([]);
  };

  const hasActiveFilters = venues.length > 0 || track || distanceMin || distanceMax || years.length > 0 || grades.length > 0;

  return (
    <div className="container py-6 max-w-5xl">
      <h1 className="text-2xl font-bold mb-6">レース検索</h1>

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
      </div>

      {/* フィルタ切替 */}
      <div className="mb-4">
        <button
          onClick={() => setShowFilters(!showFilters)}
          className="text-sm text-muted-foreground hover:text-foreground flex items-center gap-1"
        >
          <span>{showFilters ? '▼' : '▶'}</span>
          <span>絞り込み条件</span>
          {hasActiveFilters && (
            <Badge variant="secondary" className="ml-1 text-[10px]">
              {[venues.length, track ? 1 : 0, distanceMin || distanceMax ? 1 : 0, years.length, grades.length]
                .reduce((a, b) => a + b, 0)}
              件
            </Badge>
          )}
        </button>
      </div>

      {/* フィルタパネル */}
      {showFilters && (
        <div className="border rounded-lg p-4 mb-6 space-y-4 bg-muted/30">
          {/* 競馬場 */}
          <div>
            <label className="text-sm font-medium mb-1 block">競馬場</label>
            <div className="flex flex-wrap gap-1.5">
              {VENUES.map((v) => (
                <button
                  key={v}
                  onClick={() => setVenues(toggleItem(venues, v))}
                  className={cn(
                    'px-2.5 py-1 text-xs rounded-md border transition-colors',
                    venues.includes(v)
                      ? 'bg-primary text-primary-foreground border-primary'
                      : 'bg-background hover:bg-muted border-border',
                  )}
                >
                  {v}
                </button>
              ))}
            </div>
          </div>

          {/* トラック */}
          <div>
            <label className="text-sm font-medium mb-1 block">トラック</label>
            <div className="flex gap-1.5">
              {['', '芝', 'ダ'].map((t) => (
                <button
                  key={t}
                  onClick={() => setTrack(t)}
                  className={cn(
                    'px-3 py-1 text-xs rounded-md border transition-colors',
                    track === t
                      ? 'bg-primary text-primary-foreground border-primary'
                      : 'bg-background hover:bg-muted border-border',
                  )}
                >
                  {t || '全て'}
                </button>
              ))}
            </div>
          </div>

          {/* 距離 */}
          <div>
            <label className="text-sm font-medium mb-1 block">距離</label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                value={distanceMin}
                onChange={(e) => setDistanceMin(e.target.value)}
                placeholder="下限"
                className="w-24 px-3 py-1 text-sm border rounded-md dark:bg-gray-900 dark:border-gray-700"
              />
              <span className="text-sm text-muted-foreground">~</span>
              <input
                type="number"
                value={distanceMax}
                onChange={(e) => setDistanceMax(e.target.value)}
                placeholder="上限"
                className="w-24 px-3 py-1 text-sm border rounded-md dark:bg-gray-900 dark:border-gray-700"
              />
              <span className="text-xs text-muted-foreground">m</span>
            </div>
          </div>

          {/* 年度 */}
          <div>
            <label className="text-sm font-medium mb-1 block">年度</label>
            <div className="flex flex-wrap gap-1.5">
              {YEARS.map((y) => (
                <button
                  key={y}
                  onClick={() => setYears(toggleItem(years, y))}
                  className={cn(
                    'px-2.5 py-1 text-xs rounded-md border transition-colors',
                    years.includes(y)
                      ? 'bg-primary text-primary-foreground border-primary'
                      : 'bg-background hover:bg-muted border-border',
                  )}
                >
                  {y}
                </button>
              ))}
            </div>
          </div>

          {/* グレード */}
          <div>
            <label className="text-sm font-medium mb-1 block">グレード</label>
            <div className="flex flex-wrap gap-1.5">
              {GRADE_OPTIONS.map((g) => (
                <button
                  key={g}
                  onClick={() => setGrades(toggleItem(grades, g))}
                  className={cn(
                    'px-2.5 py-1 text-xs rounded-md border transition-colors',
                    grades.includes(g)
                      ? 'bg-primary text-primary-foreground border-primary'
                      : 'bg-background hover:bg-muted border-border',
                  )}
                >
                  {g}
                </button>
              ))}
            </div>
          </div>

          {/* リセット */}
          {hasActiveFilters && (
            <Button variant="ghost" size="sm" onClick={handleReset} className="text-xs">
              条件をリセット
            </Button>
          )}
        </div>
      )}

      {/* 検索結果 */}
      {hasSearched && (
        <div>
          <p className="text-sm text-muted-foreground mb-4">
            {filteredCount > 100
              ? `${filteredCount}件中 上位100件を表示（全${totalCount.toLocaleString()}件中）`
              : `${filteredCount}件の結果（全${totalCount.toLocaleString()}件中）`}
          </p>

          {results.length > 0 ? (
            <div className="space-y-3">
              {results.map((race) => (
                <RaceCard key={race.raceId} race={race} />
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground py-8 text-center">
              該当するレースが見つかりませんでした
            </p>
          )}
        </div>
      )}

      {!hasSearched && (
        <p className="text-muted-foreground py-8 text-center">
          レース名を入力するか、絞り込み条件を設定して検索してください
        </p>
      )}
    </div>
  );
}

// ── レースカード ──

function RaceCard({ race }: { race: RaceSearchEntry }) {
  const href = `/races-v2/${race.date}/${encodeURIComponent(race.venue)}/${race.raceId}`;
  const displayName = stripGradePrefix(race.raceName);
  const trend = TREND_BADGE[race.raceTrend];
  const babaColor = BABA_COLORS[race.trackCondition];
  const gradeColor = GRADE_COLORS[race.grade];

  return (
    <Link href={href} target="_blank" rel="noopener noreferrer">
      <div className="border rounded-lg p-4 hover:bg-muted/50 transition-colors cursor-pointer">
        {/* 1行目: グレード + レース名 + 日付 */}
        <div className="flex items-start justify-between gap-2 mb-1.5">
          <div className="flex items-center gap-2 min-w-0">
            {race.grade && gradeColor && (
              <span className={cn('px-1.5 py-0.5 rounded text-[11px] font-bold shrink-0', gradeColor)}>
                {race.grade}
              </span>
            )}
            <span className="font-semibold truncate">{displayName || `${race.raceNumber}R`}</span>
          </div>
          <span className="text-sm text-muted-foreground shrink-0">{race.date}</span>
        </div>

        {/* 2行目: 競馬場 + コース + 馬場 + 頭数 */}
        <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
          <span>{race.venue}</span>
          <span>{race.track}{race.distance}m</span>
          {race.trackCondition && babaColor && (
            <span className={cn('px-1.5 py-0.5 rounded text-[10px] font-medium', babaColor)}>
              {race.trackCondition}
            </span>
          )}
          {race.entryCount > 0 && <span>{race.entryCount}頭</span>}
        </div>

        {/* 3行目: 勝ち馬 + RPCI + 傾向 */}
        <div className="flex items-center gap-2 text-sm">
          {race.winnerName && (
            <span className="text-yellow-600 dark:text-yellow-400 font-medium">
              {race.winnerName}
            </span>
          )}
          {race.rpci != null && (
            <span className="text-muted-foreground text-xs">
              RPCI {race.rpci}
            </span>
          )}
          {trend && (
            <span className={cn('px-1.5 py-0.5 rounded text-[10px] font-medium', trend.className)}>
              {trend.label}
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}
