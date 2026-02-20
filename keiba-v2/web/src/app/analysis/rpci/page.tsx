'use client';

/**
 * RPCI分析ページ
 * コース別のレース特性（瞬発戦/持続戦）傾向を表示
 * v2: 馬場別比較 / 頭数別補正 / 年度重み付け対応
 */

import React, { useState, useEffect, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { RefreshCw, TrendingUp, TrendingDown, Minus, ArrowLeft, ArrowUpRight, ArrowDownRight } from 'lucide-react';
import Link from 'next/link';
import { RpciGauge, RpciBar, StatCard } from '@/components/ui/visualization';
import { cn } from '@/lib/utils';

// 型定義
interface RpciStats {
  mean: number;
  stdev: number;
  median: number;
  min: number;
  max: number;
  weighted_mean?: number;
}

interface RpciThresholds {
  instantaneous: number;
  sustained: number;
}

interface CourseData {
  sample_count: number;
  rpci: RpciStats;
  thresholds: RpciThresholds;
}

interface RunnerAdjustment {
  rpci_offset: number;
  rpci_mean: number;
  sample_count: number;
}

interface TrendDistEntry {
  count: number;
  pct: number;
}

interface Lap33CourseData {
  mean: number;
  stdev: number;
  median: number;
  sample_count: number;
}

type TabKey = 'distance' | 'course' | 'trend' | 'lap33' | 'baba' | 'runners' | 'similar';

interface RpciStandardsResponse {
  summary: {
    totalCourses: number;
    totalSamples: number;
    distanceGroups: number;
    similarPairs: number;
    lap33Courses: number;
  };
  by_distance_group: Record<string, CourseData>;
  courses: Record<string, CourseData>;
  similar_courses: Record<string, string[]>;
  by_distance_group_baba: Record<string, CourseData>;
  runner_adjustments: Record<string, Record<string, RunnerAdjustment>>;
  race_trend_distribution: Record<string, Record<string, TrendDistEntry>>;
  course_lap33_average: Record<string, Lap33CourseData>;
  race_trend_v2_distribution: Record<string, Record<string, TrendDistEntry>>;
  metadata: {
    created_at: string;
    source: string;
    years?: string;
    years_list?: number[];
    description: string;
    calculation: string;
  };
}

// RPCI傾向を判定
// RPCI = last_3f / (first_3f + last_3f) * 100
// 高RPCI → 後半遅い → ハイペース → 持続戦
// 低RPCI → 後半速い → スロー → 瞬発戦
function getRpciTrend(rpci: number): { label: string; color: string; icon: React.ReactNode } {
  if (rpci >= 51) {
    return { label: 'ハイ（持続戦）', color: 'text-red-600', icon: <TrendingDown className="h-4 w-4" /> };
  } else if (rpci <= 48) {
    return { label: 'スロー（瞬発戦）', color: 'text-blue-600', icon: <TrendingUp className="h-4 w-4" /> };
  }
  return { label: '平均的', color: 'text-gray-600', icon: <Minus className="h-4 w-4" /> };
}

// コース名をパース
function formatCourseName(courseKey: string): string {
  const trackMap: Record<string, string> = {
    'Tokyo': '東京', 'Nakayama': '中山', 'Hanshin': '阪神', 'Kyoto': '京都',
    'Chukyo': '中京', 'Niigata': '新潟', 'Sapporo': '札幌', 'Hakodate': '函館',
    'Kokura': '小倉', 'Fukushima': '福島'
  };
  const surfaceMap: Record<string, string> = {
    'Turf': '芝', 'Dirt': 'ダ'
  };

  const parts = courseKey.split('_');
  if (parts.length >= 3) {
    const track = trackMap[parts[0]] || parts[0];
    const surface = surfaceMap[parts[1]] || parts[1];
    const distance = parts.slice(2).join('');
    return `${track}${surface}${distance}`;
  }
  return courseKey;
}

// 距離グループ名をフォーマット
function formatDistanceGroup(groupKey: string): string {
  const surfaceMap: Record<string, string> = {
    'Turf': '芝', 'Dirt': 'ダート'
  };
  const parts = groupKey.split('_');
  if (parts.length >= 2) {
    const surface = surfaceMap[parts[0]] || parts[0];
    const distance = parts.slice(1).join(' ');
    return `${surface} ${distance}`;
  }
  return groupKey;
}

// コースキーをパース
function parseCourseKey(courseKey: string): { venue: string; surface: string; distance: number } | null {
  const parts = courseKey.split('_');
  if (parts.length < 3) return null;
  const distance = parseInt(parts.slice(2).join('').replace('m', ''), 10);
  if (isNaN(distance)) return null;
  return { venue: parts[0], surface: parts[1], distance };
}

// 距離帯を判定
function getDistanceRange(distance: number): string {
  if (distance <= 1200) return '1200';
  if (distance <= 1600) return '1400-1600';
  if (distance <= 2200) return '1800-2200';
  return '2400';
}

const VENUE_LIST = [
  { key: 'Tokyo', label: '東京' }, { key: 'Nakayama', label: '中山' },
  { key: 'Hanshin', label: '阪神' }, { key: 'Kyoto', label: '京都' },
  { key: 'Chukyo', label: '中京' }, { key: 'Niigata', label: '新潟' },
  { key: 'Sapporo', label: '札幌' }, { key: 'Hakodate', label: '函館' },
  { key: 'Kokura', label: '小倉' }, { key: 'Fukushima', label: '福島' },
] as const;

// オフセット値の色クラス
function getOffsetColor(offset: number): string {
  if (offset >= 1.0) return 'text-blue-600';
  if (offset >= 0.3) return 'text-blue-400';
  if (offset <= -0.5) return 'text-red-600';
  if (offset <= -0.2) return 'text-red-400';
  return 'text-gray-500';
}

// 差分の符号付き表示
function formatDiff(diff: number): string {
  if (diff > 0) return `+${diff.toFixed(2)}`;
  return diff.toFixed(2);
}

// 5段階傾向の定義
const TREND_KEYS = ['sprint_finish', 'long_sprint', 'even_pace', 'front_loaded', 'front_loaded_strong'] as const;
const TREND_LABELS: Record<string, string> = {
  sprint_finish: '瞬発',
  long_sprint: 'ロンスパ',
  even_pace: '平均',
  front_loaded: 'H前傾',
  front_loaded_strong: 'H後傾',
};
const TREND_COLORS: Record<string, string> = {
  sprint_finish: 'bg-blue-500',
  long_sprint: 'bg-indigo-500',
  even_pace: 'bg-gray-400',
  front_loaded: 'bg-red-500',
  front_loaded_strong: 'bg-orange-500',
};
const TREND_TEXT_COLORS: Record<string, string> = {
  sprint_finish: 'text-blue-600',
  long_sprint: 'text-indigo-600',
  even_pace: 'text-gray-600',
  front_loaded: 'text-red-600',
  front_loaded_strong: 'text-orange-600',
};
const TREND_BADGE_COLORS: Record<string, string> = {
  sprint_finish: 'bg-blue-100 text-blue-700',
  long_sprint: 'bg-indigo-100 text-indigo-700',
  even_pace: 'bg-gray-100 text-gray-700',
  front_loaded: 'bg-red-100 text-red-700',
  front_loaded_strong: 'bg-orange-100 text-orange-700',
};

// v2 7分類定義
const TREND_V2_KEYS = ['sprint', 'sprint_mild', 'even', 'long_sprint', 'sustained_hp', 'sustained_strong', 'sustained_doroashi'] as const;
const TREND_V2_LABELS: Record<string, string> = {
  sprint: '瞬発', sprint_mild: '軽瞬発', long_sprint: 'ロンスパ',
  even: '平均', sustained_hp: '持続HP', sustained_strong: '持続強L3', sustained_doroashi: '持続道悪',
};
const TREND_V2_COLORS: Record<string, string> = {
  sprint: 'bg-blue-500', sprint_mild: 'bg-sky-400',
  even: 'bg-gray-400',
  long_sprint: 'bg-orange-400', sustained_hp: 'bg-orange-600', sustained_strong: 'bg-red-500', sustained_doroashi: 'bg-rose-700',
};
const TREND_V2_BADGE_COLORS: Record<string, string> = {
  sprint: 'bg-blue-100 text-blue-700', sprint_mild: 'bg-sky-100 text-sky-700',
  even: 'bg-gray-100 text-gray-700',
  long_sprint: 'bg-orange-100 text-orange-700', sustained_hp: 'bg-orange-100 text-orange-800',
  sustained_strong: 'bg-red-100 text-red-700', sustained_doroashi: 'bg-rose-100 text-rose-700',
};

// lap33の色クラス
function getLap33Color(lap33: number): string {
  if (lap33 >= 1.5) return 'text-blue-600 dark:text-blue-400';
  if (lap33 >= 0.5) return 'text-blue-500 dark:text-blue-400';
  if (lap33 >= 0) return 'text-sky-500 dark:text-sky-400';
  if (lap33 >= -0.5) return 'text-orange-500 dark:text-orange-400';
  if (lap33 >= -1.5) return 'text-red-500 dark:text-red-400';
  return 'text-red-600 dark:text-red-400';
}

function getLap33Bg(lap33: number): string {
  if (lap33 >= 1.0) return 'bg-blue-50 dark:bg-blue-950/30';
  if (lap33 >= 0.3) return 'bg-sky-50 dark:bg-sky-950/20';
  if (lap33 <= -1.0) return 'bg-red-50 dark:bg-red-950/30';
  if (lap33 <= -0.3) return 'bg-orange-50 dark:bg-orange-950/20';
  return '';
}

function getLap33Label(lap33: number): string {
  if (lap33 >= 1.5) return '強瞬発';
  if (lap33 >= 0.5) return '瞬発寄り';
  if (lap33 >= 0) return 'やや瞬発';
  if (lap33 >= -0.5) return 'やや持続';
  if (lap33 >= -1.5) return '持続寄り';
  return '強持続';
}

// 最多傾向を取得
function getDominantTrend(dist: Record<string, TrendDistEntry>): { key: string; pct: number } | null {
  let maxKey = '';
  let maxPct = 0;
  for (const [key, entry] of Object.entries(dist)) {
    if (entry.pct > maxPct) {
      maxPct = entry.pct;
      maxKey = key;
    }
  }
  return maxKey ? { key: maxKey, pct: maxPct } : null;
}

export default function RpciAnalysisPage() {
  const [data, setData] = useState<RpciStandardsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>('distance');
  const [searchQuery, setSearchQuery] = useState('');
  const [surfaceFilter, setSurfaceFilter] = useState<'all' | 'Turf' | 'Dirt'>('all');
  const [distanceFilter, setDistanceFilter] = useState<string>('all');
  const [venueFilter, setVenueFilter] = useState<string>('all');

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/admin/rpci-standards');
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || errorData.error || 'データ取得に失敗');
      }
      const result = await response.json();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'エラーが発生しました');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // コースをフィルタリング
  const filteredCourses = useMemo(() => {
    if (!data?.courses) return [];
    return Object.entries(data.courses)
      .filter(([key]) => {
        if (searchQuery !== '') {
          const matches = formatCourseName(key).includes(searchQuery) ||
            key.toLowerCase().includes(searchQuery.toLowerCase());
          if (!matches) return false;
        }
        const parsed = parseCourseKey(key);
        if (!parsed) return false;
        if (surfaceFilter !== 'all' && parsed.surface !== surfaceFilter) return false;
        if (distanceFilter !== 'all' && getDistanceRange(parsed.distance) !== distanceFilter) return false;
        if (venueFilter !== 'all' && parsed.venue !== venueFilter) return false;
        return true;
      })
      .sort((a, b) => {
        const meanA = a[1].rpci.weighted_mean ?? a[1].rpci.mean;
        const meanB = b[1].rpci.weighted_mean ?? b[1].rpci.mean;
        return meanB - meanA;
      });
  }, [data, searchQuery, surfaceFilter, distanceFilter, venueFilter]);

  // フィルタされた類似コース
  const filteredSimilarCourses = useMemo(() => {
    if (!data?.similar_courses) return [];
    const hasFilter = surfaceFilter !== 'all' || distanceFilter !== 'all' || venueFilter !== 'all';
    return Object.entries(data.similar_courses)
      .filter(([course, similar]) => {
        if (similar.length === 0) return false;
        if (!hasFilter) return true;
        const parsed = parseCourseKey(course);
        if (!parsed) return false;
        if (surfaceFilter !== 'all' && parsed.surface !== surfaceFilter) return false;
        if (distanceFilter !== 'all' && getDistanceRange(parsed.distance) !== distanceFilter) return false;
        if (venueFilter !== 'all' && parsed.venue !== venueFilter) return false;
        return true;
      })
      .sort((a, b) => b[1].length - a[1].length);
  }, [data, surfaceFilter, distanceFilter, venueFilter]);

  // 馬場別比較データ（距離グループ単位）
  const babaComparison = useMemo(() => {
    if (!data?.by_distance_group_baba || !data?.by_distance_group) return [];
    const groups = Object.keys(data.by_distance_group);
    return groups
      .filter(g => {
        if (surfaceFilter !== 'all') {
          return g.startsWith(surfaceFilter);
        }
        return true;
      })
      .map(groupKey => {
        const overall = data.by_distance_group[groupKey];
        const goodKey = `${groupKey}_良`;
        const heavyKey = `${groupKey}_稍重以上`;
        const good = data.by_distance_group_baba[goodKey];
        const heavy = data.by_distance_group_baba[heavyKey];
        return {
          groupKey,
          overall,
          good,
          heavy,
          diff: good && heavy ? heavy.rpci.mean - good.rpci.mean : null,
        };
      })
      .sort((a, b) => {
        // 芝→ダートの順、距離昇順
        const surfA = a.groupKey.startsWith('Turf') ? 0 : 1;
        const surfB = b.groupKey.startsWith('Turf') ? 0 : 1;
        if (surfA !== surfB) return surfA - surfB;
        return a.groupKey.localeCompare(b.groupKey);
      });
  }, [data, surfaceFilter]);

  // 頭数別補正データ
  const runnerAdjData = useMemo(() => {
    if (!data?.runner_adjustments) return [];
    return Object.entries(data.runner_adjustments)
      .filter(([key]) => {
        if (surfaceFilter !== 'all') {
          return key.startsWith(surfaceFilter);
        }
        return true;
      })
      .sort((a, b) => {
        const surfA = a[0].startsWith('Turf') ? 0 : 1;
        const surfB = b[0].startsWith('Turf') ? 0 : 1;
        if (surfA !== surfB) return surfA - surfB;
        return a[0].localeCompare(b[0]);
      });
  }, [data, surfaceFilter]);

  // 傾向分布データ（フィルタ適用済み）
  const filteredTrendDist = useMemo(() => {
    if (!data?.race_trend_distribution) return [];
    return Object.entries(data.race_trend_distribution)
      .filter(([key]) => {
        const parsed = parseCourseKey(key);
        if (!parsed) return false;
        if (surfaceFilter !== 'all' && parsed.surface !== surfaceFilter) return false;
        if (distanceFilter !== 'all' && getDistanceRange(parsed.distance) !== distanceFilter) return false;
        if (venueFilter !== 'all' && parsed.venue !== venueFilter) return false;
        return true;
      })
      .sort((a, b) => {
        // 瞬発戦%降順でソート
        const pctA = a[1]?.sprint_finish?.pct ?? 0;
        const pctB = b[1]?.sprint_finish?.pct ?? 0;
        return pctB - pctA;
      });
  }, [data, surfaceFilter, distanceFilter, venueFilter]);

  // 33ラップコース別データ（フィルタ適用済み）
  const filteredLap33 = useMemo(() => {
    if (!data?.course_lap33_average) return [];
    return Object.entries(data.course_lap33_average)
      .filter(([key]) => {
        const parsed = parseCourseKey(key);
        if (!parsed) return false;
        if (surfaceFilter !== 'all' && parsed.surface !== surfaceFilter) return false;
        if (distanceFilter !== 'all' && getDistanceRange(parsed.distance) !== distanceFilter) return false;
        if (venueFilter !== 'all' && parsed.venue !== venueFilter) return false;
        return true;
      })
      .sort((a, b) => b[1].mean - a[1].mean); // 瞬発寄り→持続寄り
  }, [data, surfaceFilter, distanceFilter, venueFilter]);

  // v2傾向分布データ（フィルタ適用済み）
  const filteredTrendV2Dist = useMemo(() => {
    if (!data?.race_trend_v2_distribution) return [];
    return Object.entries(data.race_trend_v2_distribution)
      .filter(([key]) => {
        const parsed = parseCourseKey(key);
        if (!parsed) return false;
        if (surfaceFilter !== 'all' && parsed.surface !== surfaceFilter) return false;
        if (distanceFilter !== 'all' && getDistanceRange(parsed.distance) !== distanceFilter) return false;
        if (venueFilter !== 'all' && parsed.venue !== venueFilter) return false;
        return true;
      })
      .sort((a, b) => {
        const pctA = (a[1]?.sprint?.pct ?? 0) + (a[1]?.sprint_mild?.pct ?? 0);
        const pctB = (b[1]?.sprint?.pct ?? 0) + (b[1]?.sprint_mild?.pct ?? 0);
        return pctB - pctA;
      });
  }, [data, surfaceFilter, distanceFilter, venueFilter]);

  const hasActiveFilter = surfaceFilter !== 'all' || distanceFilter !== 'all' || venueFilter !== 'all';
  const btnClass = (active: boolean) => cn(
    'px-3 py-1 text-xs rounded-full border transition-colors',
    active
      ? 'bg-blue-500 text-white border-blue-500'
      : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50 dark:bg-gray-800 dark:text-gray-300 dark:border-gray-600'
  );
  const resetFilters = () => { setSurfaceFilter('all'); setDistanceFilter('all'); setVenueFilter('all'); };

  const renderFilters = (matchCount?: number) => (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-muted-foreground w-16 shrink-0">芝/ダート</span>
        {(['all', 'Turf', 'Dirt'] as const).map((v) => (
          <button key={v} onClick={() => setSurfaceFilter(v)} className={btnClass(surfaceFilter === v)}>
            {v === 'all' ? '全て' : v === 'Turf' ? '芝' : 'ダート'}
          </button>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-muted-foreground w-16 shrink-0">距離帯</span>
        {[{ k: 'all', l: '全て' }, { k: '1200', l: '~1200m' }, { k: '1400-1600', l: '1400-1600m' }, { k: '1800-2200', l: '1800-2200m' }, { k: '2400', l: '2400m+' }].map(({ k, l }) => (
          <button key={k} onClick={() => setDistanceFilter(k)} className={btnClass(distanceFilter === k)}>
            {l}
          </button>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-muted-foreground w-16 shrink-0">競馬場</span>
        <button onClick={() => setVenueFilter('all')} className={btnClass(venueFilter === 'all')}>全て</button>
        {VENUE_LIST.map(({ key, label }) => (
          <button key={key} onClick={() => setVenueFilter(key)} className={btnClass(venueFilter === key)}>
            {label}
          </button>
        ))}
      </div>
      {hasActiveFilter && (
        <div className="flex items-center gap-2 pt-1">
          <button onClick={resetFilters} className="text-xs text-blue-600 hover:underline dark:text-blue-400">
            フィルタをリセット
          </button>
          {matchCount !== undefined && (
            <span className="text-xs text-muted-foreground">({matchCount}件)</span>
          )}
        </div>
      )}
    </div>
  );

  // 芝/ダートのみフィルタ（馬場別・頭数別タブ用）
  const renderSurfaceFilter = () => (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs font-medium text-muted-foreground w-16 shrink-0">芝/ダート</span>
      {(['all', 'Turf', 'Dirt'] as const).map((v) => (
        <button key={v} onClick={() => setSurfaceFilter(v)} className={btnClass(surfaceFilter === v)}>
          {v === 'all' ? '全て' : v === 'Turf' ? '芝' : 'ダート'}
        </button>
      ))}
    </div>
  );

  const TABS: { key: TabKey; label: string }[] = [
    { key: 'distance', label: '距離グループ別' },
    { key: 'course', label: 'コース別' },
    { key: 'lap33', label: '33ラップ' },
    { key: 'trend', label: '傾向分布' },
    { key: 'baba', label: '馬場別比較' },
    { key: 'runners', label: '頭数別補正' },
    { key: 'similar', label: '類似コース' },
  ];

  return (
    <div className="container py-6 max-w-6xl">
      {/* パンくずリスト */}
      <nav className="flex items-center space-x-2 text-sm text-muted-foreground mb-6">
        <Link href="/" className="hover:underline flex items-center gap-1">
          <ArrowLeft className="h-4 w-4" />
          トップ
        </Link>
        <span>/</span>
        <span className="text-foreground">レースペース分析</span>
      </nav>

      {/* ヘッダー */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          レースペース分析
        </h1>
        <p className="text-muted-foreground mt-1">
          コース別のレースペース傾向（RPCI・33ラップ・傾向分類）を分析
        </p>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-16">
          <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
          <span className="ml-3 text-muted-foreground">読み込み中...</span>
        </div>
      )}

      {error && (
        <Card className="bg-amber-50 border-amber-200">
          <CardContent className="py-6">
            <p className="font-medium text-amber-800">データがありません</p>
            <p className="text-sm mt-1 text-amber-700">{error}</p>
            <p className="text-sm mt-2 text-amber-600">
              管理画面 → データ分析 → 「レース特性基準値算出」を実行してください
            </p>
            <button
              onClick={fetchData}
              className="mt-3 text-sm underline hover:no-underline text-amber-800"
            >
              再読み込み
            </button>
          </CardContent>
        </Card>
      )}

      {data && (
        <div className="space-y-6">
          {/* サマリーカード */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard
              label="コース数"
              value={data.summary.totalCourses}
              icon="🏇"
            />
            <StatCard
              label="総レース数"
              value={data.summary.totalSamples.toLocaleString()}
              icon="🏁"
            />
            <StatCard
              label="距離グループ"
              value={data.summary.distanceGroups}
              icon="📏"
            />
            <StatCard
              label="類似コースペア"
              value={Math.round(data.summary.similarPairs)}
              icon="🔗"
            />
          </div>

          {/* メタデータ */}
          <div className="text-xs text-muted-foreground flex items-center justify-between">
            <span>
              対象期間: <strong className="text-foreground">{data.metadata.years || '不明'}</strong> |
              更新: {new Date(data.metadata.created_at).toLocaleString('ja-JP')} |
              ソース: {data.metadata.source}
            </span>
            <button
              onClick={fetchData}
              className="flex items-center gap-1 hover:text-foreground transition-colors"
              disabled={loading}
            >
              <RefreshCw className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} />
              再読み込み
            </button>
          </div>

          {/* タブ */}
          <div className="flex border-b overflow-x-auto">
            {TABS.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                  activeTab === key
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-muted-foreground hover:text-foreground'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {/* ===== 距離グループ別タブ ===== */}
          {activeTab === 'distance' && (
            <div className="space-y-6">
              {/* ゲージグリッド表示 */}
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                {Object.entries(data.by_distance_group)
                  .sort((a, b) => (b[1].rpci.weighted_mean ?? b[1].rpci.mean) - (a[1].rpci.weighted_mean ?? a[1].rpci.mean))
                  .map(([key, value]) => (
                    <Card key={key} className="hover:shadow-md transition-shadow">
                      <CardContent className="pt-4 pb-3 flex flex-col items-center">
                        <div className="text-xs font-medium text-muted-foreground mb-2">
                          {formatDistanceGroup(key)}
                        </div>
                        <RpciGauge value={value.rpci.weighted_mean ?? value.rpci.mean} size="sm" />
                        <div className="text-[10px] text-muted-foreground mt-1">
                          {value.sample_count.toLocaleString()}件
                        </div>
                      </CardContent>
                    </Card>
                  ))}
              </div>

              {/* 詳細テーブル */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">芝/ダート × 距離グループ別 RPCI</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b bg-slate-50 dark:bg-slate-800">
                          <th className="text-left py-3 px-4">カテゴリ</th>
                          <th className="text-right py-3 px-4">件数</th>
                          <th className="text-center py-3 px-4">RPCI</th>
                          <th className="text-right py-3 px-4">重み付</th>
                          <th className="text-center py-3 px-4">傾向</th>
                          <th className="text-right py-3 px-4">瞬発閾値</th>
                          <th className="text-right py-3 px-4">持続閾値</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(data.by_distance_group)
                          .sort((a, b) => (b[1].rpci.weighted_mean ?? b[1].rpci.mean) - (a[1].rpci.weighted_mean ?? a[1].rpci.mean))
                          .map(([key, value]) => {
                            const wm = value.rpci.weighted_mean;
                            const rpci = wm ?? value.rpci.mean;
                            const trend = getRpciTrend(rpci);
                            const diff = wm != null ? wm - value.rpci.mean : null;
                            return (
                              <tr key={key} className="border-b hover:bg-slate-50 dark:hover:bg-slate-800/50">
                                <td className="py-3 px-4 font-medium">{formatDistanceGroup(key)}</td>
                                <td className="text-right py-3 px-4">{value.sample_count.toLocaleString()}</td>
                                <td className="py-3 px-4">
                                  <div className="flex justify-center">
                                    <RpciGauge value={rpci} size="sm" showLabel={false} />
                                  </div>
                                </td>
                                <td className="text-right py-3 px-4 font-mono text-xs">
                                  {wm != null ? (
                                    <span title={`全体平均: ${value.rpci.mean.toFixed(2)}`}>
                                      {wm.toFixed(2)}
                                      {diff != null && Math.abs(diff) >= 0.01 && (
                                        <span className={diff > 0 ? 'text-blue-500 ml-1' : 'text-red-500 ml-1'}>
                                          ({formatDiff(diff)})
                                        </span>
                                      )}
                                    </span>
                                  ) : (
                                    <span className="text-muted-foreground">-</span>
                                  )}
                                </td>
                                <td className="text-center py-3 px-4">
                                  <span className={`flex items-center justify-center gap-1 ${trend.color}`}>
                                    {trend.icon}
                                    <span className="text-xs">{trend.label}</span>
                                  </span>
                                </td>
                                <td className="text-right py-3 px-4 font-mono text-blue-600">&lt;{value.thresholds.instantaneous.toFixed(1)}</td>
                                <td className="text-right py-3 px-4 font-mono text-red-600">&gt;{value.thresholds.sustained.toFixed(1)}</td>
                              </tr>
                            );
                          })}
                      </tbody>
                    </table>
                  </div>
                  <p className="text-[10px] text-muted-foreground mt-2">
                    重み付: 直近2年×2倍の重み付け平均。カッコ内は全体平均との差。
                  </p>
                </CardContent>
              </Card>
            </div>
          )}

          {/* ===== コース別タブ ===== */}
          {activeTab === 'course' && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center justify-between">
                  <span>コース別 RPCI ランキング</span>
                  <span className="text-xs font-normal text-muted-foreground">
                    {filteredCourses.length}コース
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {renderFilters(filteredCourses.length)}

                <input
                  type="text"
                  placeholder="コース名で検索（例: 東京芝2000）"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full px-4 py-2 border rounded-lg text-sm dark:bg-gray-800 dark:border-gray-700"
                />

                {/* バーグラフ表示 */}
                <div className="max-h-[600px] overflow-y-auto space-y-1">
                  {filteredCourses.map(([key, value], index) => {
                    const trendDist = data.race_trend_distribution?.[key];
                    const dominant = trendDist ? getDominantTrend(trendDist) : null;
                    return (
                      <div key={key} className="flex items-center gap-2">
                        <div className="flex-1">
                          <RpciBar
                            value={value.rpci.weighted_mean ?? value.rpci.mean}
                            label={formatCourseName(key)}
                            rank={searchQuery === '' ? index + 1 : undefined}
                            sampleCount={value.sample_count}
                            animate={true}
                            delay={index * 30}
                          />
                        </div>
                        {dominant && (
                          <span className={cn(
                            'text-[10px] font-medium rounded px-1.5 py-0.5 whitespace-nowrap shrink-0',
                            TREND_BADGE_COLORS[dominant.key] || 'bg-gray-100 text-gray-700'
                          )}>
                            {TREND_LABELS[dominant.key]} {dominant.pct.toFixed(0)}%
                          </span>
                        )}
                      </div>
                    );
                  })}
                  {filteredCourses.length === 0 && (
                    <div className="py-8 text-center text-muted-foreground">
                      該当するコースがありません
                    </div>
                  )}
                </div>

                {/* 凡例 */}
                <div className="flex flex-wrap gap-4 text-xs text-muted-foreground border-t pt-4">
                  <div className="flex items-center gap-2">
                    <span className="w-4 h-4 rounded bg-blue-500"></span>
                    <span>瞬発戦（RPCI &lt; 50）</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-4 h-4 rounded bg-gray-400"></span>
                    <span>平均的</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-4 h-4 rounded bg-red-500"></span>
                    <span>持続戦（RPCI &gt; 50）</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* ===== 33ラップタブ ===== */}
          {activeTab === 'lap33' && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center justify-between">
                  <span>コース別 33ラップ平均</span>
                  <span className="text-xs font-normal text-muted-foreground">
                    {filteredLap33.length}コース
                  </span>
                </CardTitle>
                <p className="text-sm text-muted-foreground">
                  33ラップ = (残り6F〜3F区間タイム) − (残り3F〜ゴールタイム)。プラス=瞬発力勝負、マイナス=持続力勝負。
                </p>
              </CardHeader>
              <CardContent className="space-y-4">
                {renderFilters(filteredLap33.length)}

                {/* テーブル */}
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-slate-50 dark:bg-slate-800">
                        <th className="text-left py-3 px-4">コース</th>
                        <th className="text-right py-3 px-4">33ラップ</th>
                        <th className="text-right py-3 px-3">stdev</th>
                        <th className="text-right py-3 px-3">中央値</th>
                        <th className="text-right py-3 px-3">件数</th>
                        <th className="text-center py-3 px-4">タイプ</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredLap33.map(([key, value]) => (
                        <tr key={key} className={cn('border-b hover:bg-slate-50 dark:hover:bg-slate-800/50', getLap33Bg(value.mean))}>
                          <td className="py-3 px-4 font-medium">{formatCourseName(key)}</td>
                          <td className={cn('text-right py-3 px-4 font-mono font-bold', getLap33Color(value.mean))}>
                            {value.mean >= 0 ? '+' : ''}{value.mean.toFixed(2)}
                          </td>
                          <td className="text-right py-3 px-3 font-mono text-xs text-muted-foreground">
                            {value.stdev.toFixed(2)}
                          </td>
                          <td className={cn('text-right py-3 px-3 font-mono text-xs', getLap33Color(value.median))}>
                            {value.median >= 0 ? '+' : ''}{value.median.toFixed(2)}
                          </td>
                          <td className="text-right py-3 px-3 text-muted-foreground">
                            {value.sample_count}
                          </td>
                          <td className="text-center py-3 px-4">
                            <span className={cn(
                              'text-xs font-medium rounded-full px-2 py-0.5',
                              value.mean >= 0.5 ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300'
                                : value.mean <= -0.5 ? 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'
                                : 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
                            )}>
                              {getLap33Label(value.mean)}
                            </span>
                          </td>
                        </tr>
                      ))}
                      {filteredLap33.length === 0 && (
                        <tr>
                          <td colSpan={6} className="py-8 text-center text-muted-foreground">
                            該当するコースがありません
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                {/* 凡例 */}
                <div className="flex flex-wrap gap-4 text-xs text-muted-foreground border-t pt-4">
                  <div className="flex items-center gap-2">
                    <span className="w-4 h-4 rounded bg-blue-500"></span>
                    <span>瞬発力勝負 (+0.5以上)</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-4 h-4 rounded bg-gray-400"></span>
                    <span>中間域</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-4 h-4 rounded bg-red-500"></span>
                    <span>持続力勝負 (-0.5以下)</span>
                  </div>
                </div>

                {/* 解説 */}
                <div className="text-xs text-muted-foreground border-t pt-3 space-y-1">
                  <p><strong>33ラップ</strong> = (残り6F〜3F区間の1Fあたりタイム) − (残り3F〜Goalの1Fあたりタイム)</p>
                  <p><span className="text-blue-600 font-medium">プラス</span>: 後半で加速 → 瞬発力が問われるコース。<span className="text-red-600 font-medium">マイナス</span>: 後半で減速 → 持久力・スタミナが重要。</p>
                  <p>stdevが大きいコースは展開によるブレが大きく、レースごとの傾向が安定しない。</p>
                </div>
              </CardContent>
            </Card>
          )}

          {/* ===== 傾向分布タブ ===== */}
          {activeTab === 'trend' && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center justify-between">
                  <span>コース別 レース傾向分布（v2 7分類）</span>
                  <span className="text-xs font-normal text-muted-foreground">
                    {(filteredTrendV2Dist.length > 0 ? filteredTrendV2Dist : filteredTrendDist).length}コース
                  </span>
                </CardTitle>
                <p className="text-sm text-muted-foreground">
                  各コースで過去レースがどの傾向タイプに分類されたかの割合（L3F閾値 + RPCI + 33ラップの3シグナル統合判定）
                </p>
              </CardHeader>
              <CardContent className="space-y-4">
                {renderFilters((filteredTrendV2Dist.length > 0 ? filteredTrendV2Dist : filteredTrendDist).length)}

                {/* v2凡例 */}
                {filteredTrendV2Dist.length > 0 ? (
                  <div className="flex flex-wrap gap-3 text-xs">
                    {TREND_V2_KEYS.map((key) => (
                      <div key={key} className="flex items-center gap-1.5">
                        <span className={cn('w-3 h-3 rounded-sm', TREND_V2_COLORS[key])}></span>
                        <span>{TREND_V2_LABELS[key]}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="flex flex-wrap gap-3 text-xs">
                    {TREND_KEYS.map((key) => (
                      <div key={key} className="flex items-center gap-1.5">
                        <span className={cn('w-3 h-3 rounded-sm', TREND_COLORS[key])}></span>
                        <span>{TREND_LABELS[key]}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* スタックドバー一覧 */}
                <div className="max-h-[600px] overflow-y-auto space-y-1.5">
                  {filteredTrendV2Dist.length > 0 ? (
                    /* v2 7分類 */
                    filteredTrendV2Dist.map(([courseKey, dist]) => {
                      const totalCount = Object.values(dist).reduce((s, e) => s + e.count, 0);
                      return (
                        <div key={courseKey} className="flex items-center gap-3">
                          <div className="w-28 shrink-0 text-xs font-medium truncate" title={courseKey}>
                            {formatCourseName(courseKey)}
                          </div>
                          <div className="flex-1 flex h-5 rounded overflow-hidden bg-gray-100 dark:bg-gray-800">
                            {TREND_V2_KEYS.map((tKey) => {
                              const entry = dist[tKey];
                              if (!entry || entry.pct === 0) return null;
                              return (
                                <div
                                  key={tKey}
                                  className={cn('h-full transition-all', TREND_V2_COLORS[tKey])}
                                  style={{ width: `${entry.pct}%` }}
                                  title={`${TREND_V2_LABELS[tKey]}: ${entry.count}件 (${entry.pct.toFixed(1)}%)`}
                                />
                              );
                            })}
                          </div>
                          <div className="w-10 shrink-0 text-[10px] text-muted-foreground text-right">
                            {totalCount}件
                          </div>
                        </div>
                      );
                    })
                  ) : (
                    /* v1 5分類フォールバック */
                    filteredTrendDist.map(([courseKey, dist]) => {
                      const totalCount = Object.values(dist).reduce((s, e) => s + e.count, 0);
                      return (
                        <div key={courseKey} className="flex items-center gap-3">
                          <div className="w-28 shrink-0 text-xs font-medium truncate" title={courseKey}>
                            {formatCourseName(courseKey)}
                          </div>
                          <div className="flex-1 flex h-5 rounded overflow-hidden bg-gray-100 dark:bg-gray-800">
                            {TREND_KEYS.map((tKey) => {
                              const entry = dist[tKey];
                              if (!entry || entry.pct === 0) return null;
                              return (
                                <div
                                  key={tKey}
                                  className={cn('h-full transition-all', TREND_COLORS[tKey])}
                                  style={{ width: `${entry.pct}%` }}
                                  title={`${TREND_LABELS[tKey]}: ${entry.count}件 (${entry.pct}%)`}
                                />
                              );
                            })}
                          </div>
                          <div className="w-10 shrink-0 text-[10px] text-muted-foreground text-right">
                            {totalCount}件
                          </div>
                        </div>
                      );
                    })
                  )}
                  {filteredTrendV2Dist.length === 0 && filteredTrendDist.length === 0 && (
                    <div className="py-8 text-center text-muted-foreground">
                      傾向分布データがありません。管理画面で「レース特性基準値算出」を再実行してください。
                    </div>
                  )}
                </div>

                {/* 注釈 */}
                <div className="text-xs text-muted-foreground border-t pt-3 space-y-1">
                  {filteredTrendV2Dist.length > 0 ? (
                    <>
                      <p><strong>瞬発:</strong> L3F閾値クリア + RPCI確認 / <strong>軽瞬発:</strong> RPCIのみ瞬発シグナル / <strong>ロンスパ:</strong> L4加速 + 中盤緩み</p>
                      <p><strong>平均:</strong> 全指標が中間域 / <strong>持続HP:</strong> RPCI低 + L3遅い / <strong>持続強L3:</strong> RPCI低 + L3速い / <strong>持続道悪:</strong> 道悪 + 持続シグナル</p>
                    </>
                  ) : (
                    <>
                      <p><strong>瞬発:</strong> RPCI≧51, L3で一気加速 / <strong>ロンスパ:</strong> RPCI≧50, 残4Fから持続加速</p>
                      <p><strong>平均:</strong> 48&lt;RPCI&lt;51 / <strong>H前傾:</strong> RPCI≦48, L3遅め / <strong>H後傾:</strong> RPCI≦48, L3速い</p>
                    </>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          {/* ===== 馬場別比較タブ ===== */}
          {activeTab === 'baba' && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">馬場状態別 RPCI 比較</CardTitle>
                <p className="text-sm text-muted-foreground">
                  良馬場 vs 稍重以上でRPCI傾向がどう変わるか。芝は稍重でペースが速まり（RPCI↓）、ダートは逆傾向。
                </p>
              </CardHeader>
              <CardContent className="space-y-4">
                {renderSurfaceFilter()}

                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-slate-50 dark:bg-slate-800">
                        <th className="text-left py-3 px-4">距離グループ</th>
                        <th className="text-right py-3 px-3">
                          <span className="text-green-600">良</span> RPCI
                        </th>
                        <th className="text-right py-3 px-2">n</th>
                        <th className="text-right py-3 px-3">
                          <span className="text-amber-600">稍重+</span> RPCI
                        </th>
                        <th className="text-right py-3 px-2">n</th>
                        <th className="text-center py-3 px-3">差</th>
                        <th className="text-center py-3 px-4">影響</th>
                      </tr>
                    </thead>
                    <tbody>
                      {babaComparison.map(({ groupKey, good, heavy, diff }) => {
                        const isTurf = groupKey.startsWith('Turf');
                        return (
                          <tr key={groupKey} className="border-b hover:bg-slate-50 dark:hover:bg-slate-800/50">
                            <td className="py-3 px-4 font-medium">{formatDistanceGroup(groupKey)}</td>
                            <td className="text-right py-3 px-3 font-mono">
                              {good ? (
                                <span className="text-green-700 dark:text-green-400">{good.rpci.mean.toFixed(2)}</span>
                              ) : '-'}
                            </td>
                            <td className="text-right py-3 px-2 text-xs text-muted-foreground">
                              {good ? good.sample_count.toLocaleString() : '-'}
                            </td>
                            <td className="text-right py-3 px-3 font-mono">
                              {heavy ? (
                                <span className="text-amber-700 dark:text-amber-400">{heavy.rpci.mean.toFixed(2)}</span>
                              ) : '-'}
                            </td>
                            <td className="text-right py-3 px-2 text-xs text-muted-foreground">
                              {heavy ? heavy.sample_count.toLocaleString() : '-'}
                            </td>
                            <td className="text-center py-3 px-3">
                              {diff != null ? (
                                <span className={cn(
                                  'font-mono font-medium text-sm',
                                  diff > 0 ? 'text-blue-600' : diff < 0 ? 'text-red-600' : 'text-gray-500'
                                )}>
                                  {formatDiff(diff)}
                                </span>
                              ) : '-'}
                            </td>
                            <td className="text-center py-3 px-4">
                              {diff != null && (
                                <span className="flex items-center justify-center gap-1 text-xs">
                                  {isTurf ? (
                                    diff < -0.3 ? (
                                      <><ArrowDownRight className="h-3.5 w-3.5 text-red-500" /><span className="text-red-600">ペース速化</span></>
                                    ) : diff > 0.3 ? (
                                      <><ArrowUpRight className="h-3.5 w-3.5 text-blue-500" /><span className="text-blue-600">スロー化</span></>
                                    ) : (
                                      <span className="text-muted-foreground">変化小</span>
                                    )
                                  ) : (
                                    diff > 0.1 ? (
                                      <><ArrowUpRight className="h-3.5 w-3.5 text-blue-500" /><span className="text-blue-600">スロー化</span></>
                                    ) : diff < -0.1 ? (
                                      <><ArrowDownRight className="h-3.5 w-3.5 text-red-500" /><span className="text-red-600">ペース速化</span></>
                                    ) : (
                                      <span className="text-muted-foreground">変化小</span>
                                    )
                                  )}
                                </span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                <div className="text-xs text-muted-foreground space-y-1 border-t pt-3">
                  <p><strong>読み方:</strong> 差 = 稍重以上RPCI - 良RPCI。負の値 = 稍重でペースが速くなる。</p>
                  <p>芝は馬場が悪化すると瞬発力が出にくくなり、持続戦寄りになる傾向。ダートは脚抜きが良くなり、ややスロー寄り。</p>
                </div>
              </CardContent>
            </Card>
          )}

          {/* ===== 頭数別補正タブ ===== */}
          {activeTab === 'runners' && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">頭数別 RPCI 補正</CardTitle>
                <p className="text-sm text-muted-foreground">
                  出走頭数によるRPCIオフセット。少頭数はスロー傾向（+）、多頭数はハイペース傾向（-）。
                </p>
              </CardHeader>
              <CardContent className="space-y-4">
                {renderSurfaceFilter()}

                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-slate-50 dark:bg-slate-800">
                        <th className="text-left py-3 px-4">距離グループ</th>
                        <th className="text-center py-3 px-3" colSpan={2}>
                          <span className="text-blue-600">少頭数(~8)</span>
                        </th>
                        <th className="text-center py-3 px-3" colSpan={2}>
                          <span className="text-gray-600">中頭数(9-13)</span>
                        </th>
                        <th className="text-center py-3 px-3" colSpan={2}>
                          <span className="text-red-600">多頭数(14~)</span>
                        </th>
                      </tr>
                      <tr className="border-b bg-slate-50/50 dark:bg-slate-800/50 text-xs text-muted-foreground">
                        <th></th>
                        <th className="py-1 px-2 text-right">offset</th>
                        <th className="py-1 px-2 text-right">n</th>
                        <th className="py-1 px-2 text-right">offset</th>
                        <th className="py-1 px-2 text-right">n</th>
                        <th className="py-1 px-2 text-right">offset</th>
                        <th className="py-1 px-2 text-right">n</th>
                      </tr>
                    </thead>
                    <tbody>
                      {runnerAdjData.map(([groupKey, bands]) => {
                        const small = bands['少頭数(~8)'];
                        const mid = bands['中頭数(9-13)'];
                        const large = bands['多頭数(14~)'];
                        return (
                          <tr key={groupKey} className="border-b hover:bg-slate-50 dark:hover:bg-slate-800/50">
                            <td className="py-3 px-4 font-medium">{formatDistanceGroup(groupKey)}</td>
                            {/* 少頭数 */}
                            <td className="text-right py-3 px-2">
                              {small ? (
                                <span className={cn('font-mono font-medium', getOffsetColor(small.rpci_offset))}>
                                  {formatDiff(small.rpci_offset)}
                                </span>
                              ) : <span className="text-muted-foreground">-</span>}
                            </td>
                            <td className="text-right py-3 px-2 text-xs text-muted-foreground">
                              {small ? small.sample_count : '-'}
                            </td>
                            {/* 中頭数 */}
                            <td className="text-right py-3 px-2">
                              {mid ? (
                                <span className={cn('font-mono font-medium', getOffsetColor(mid.rpci_offset))}>
                                  {formatDiff(mid.rpci_offset)}
                                </span>
                              ) : <span className="text-muted-foreground">-</span>}
                            </td>
                            <td className="text-right py-3 px-2 text-xs text-muted-foreground">
                              {mid ? mid.sample_count : '-'}
                            </td>
                            {/* 多頭数 */}
                            <td className="text-right py-3 px-2">
                              {large ? (
                                <span className={cn('font-mono font-medium', getOffsetColor(large.rpci_offset))}>
                                  {formatDiff(large.rpci_offset)}
                                </span>
                              ) : <span className="text-muted-foreground">-</span>}
                            </td>
                            <td className="text-right py-3 px-2 text-xs text-muted-foreground">
                              {large ? large.sample_count : '-'}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                <div className="text-xs text-muted-foreground space-y-1 border-t pt-3">
                  <p><strong>offset:</strong> 当該頭数帯のRPCI平均 - 距離グループ全体のRPCI平均</p>
                  <p>正の値（<span className="text-blue-600">青</span>）= スロー傾向 → 瞬発力が問われやすい。負の値（<span className="text-red-600">赤</span>）= ハイペース傾向 → 持久力が問われやすい。</p>
                </div>
              </CardContent>
            </Card>
          )}

          {/* ===== 類似コースタブ ===== */}
          {activeTab === 'similar' && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">類似コース分析</CardTitle>
                <p className="text-sm text-muted-foreground">
                  RPCI差が0.5以下のコースを「類似」と判定しています
                </p>
              </CardHeader>
              <CardContent className="space-y-4">
                {renderFilters(filteredSimilarCourses.length)}

                <div className="max-h-[600px] overflow-y-auto space-y-3">
                  {filteredSimilarCourses
                    .map(([course, similarCourses]) => {
                      const courseData = data.courses[course];
                      const rpci = courseData?.rpci.weighted_mean ?? courseData?.rpci.mean ?? 50;
                      const courseTrend = getRpciTrend(rpci);
                      return (
                        <div key={course} className="bg-slate-50 dark:bg-slate-800 rounded-lg p-4">
                          <div className="font-medium flex items-center gap-2">
                            {formatCourseName(course)}
                            <span className="text-xs font-mono text-muted-foreground">
                              RPCI: {rpci.toFixed(2)}
                            </span>
                            <span className={cn('flex items-center gap-1 text-xs', courseTrend.color)}>
                              {courseTrend.icon}
                              {courseTrend.label}
                            </span>
                          </div>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {similarCourses.map((similar) => {
                              const similarData = data.courses[similar];
                              const similarRpci = similarData?.rpci.weighted_mean ?? similarData?.rpci.mean ?? 50;
                              const diff = Math.abs(similarRpci - rpci);
                              const similarTrend = getRpciTrend(similarRpci);
                              return (
                                <span
                                  key={similar}
                                  className="inline-flex items-center gap-1 bg-white dark:bg-slate-700 px-3 py-1.5 rounded text-sm border dark:border-slate-600"
                                >
                                  {formatCourseName(similar)}
                                  <span className="text-muted-foreground text-xs">
                                    (差: {diff.toFixed(2)})
                                  </span>
                                  <span className={cn('ml-0.5', similarTrend.color)}>
                                    {similarTrend.icon}
                                  </span>
                                </span>
                              );
                            })}
                          </div>
                        </div>
                      );
                    })}
                  {filteredSimilarCourses.length === 0 && (
                    <div className="py-8 text-center text-muted-foreground">
                      {hasActiveFilter ? '該当する類似コースがありません' : '類似コースのデータがありません'}
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          {/* 解説 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">用語解説</CardTitle>
            </CardHeader>
            <CardContent className="text-sm space-y-2 text-muted-foreground">
              {/* RPCI */}
              <div className="space-y-1">
                <p className="font-medium text-foreground">RPCI (Race Pace Change Index)</p>
                <p>後半3Fタイム / (前半3F + 後半3F) × 100</p>
                <ul className="list-disc list-inside space-y-1 ml-2">
                  <li><span className="text-red-600 font-medium">RPCI &gt; 50</span>: ハイペース（前傾）→ 持続戦傾向</li>
                  <li><span className="text-blue-600 font-medium">RPCI &lt; 50</span>: スローペース（後傾）→ 瞬発戦傾向</li>
                  <li><span className="text-gray-600 font-medium">RPCI ≈ 50</span>: 平均的なペース</li>
                </ul>
              </div>

              {/* 33ラップ */}
              <div className="mt-3 border-t pt-3 space-y-1">
                <p className="font-medium text-foreground">33ラップ</p>
                <p>(残り6F〜3F区間の1Fあたりタイム) − (残り3F〜Goalの1Fあたりタイム)</p>
                <ul className="list-disc list-inside space-y-1 ml-2">
                  <li><span className="text-blue-600 font-medium">プラス (+1.0以上)</span>: 後半加速 → 瞬発力が問われるレース</li>
                  <li><span className="text-red-600 font-medium">マイナス (-1.0以下)</span>: 後半減速 → 持久力・スタミナ勝負</li>
                  <li><span className="text-gray-600 font-medium">0付近</span>: 前後半でペース変化が小さい</li>
                </ul>
                <p className="mt-1">RPCIが前後半3Fの比率なのに対し、33ラップは中盤と終盤の加速度を直接測定。RPCIでは見えないロングスパートや持続力の質を捉えます。</p>
              </div>

              {/* v2 7分類 */}
              <div className="mt-3 border-t pt-3 space-y-1">
                <p className="font-medium text-foreground">v2 7段階レース傾向分類</p>
                <p>L3F閾値 + RPCI + 33ラップの3シグナルを統合し、7タイプに分類:</p>
                <ul className="list-none space-y-1.5 ml-2 mt-2">
                  <li className="flex items-start gap-2">
                    <span className="bg-blue-100 text-blue-700 text-xs font-medium rounded px-1.5 py-0.5 shrink-0">瞬発</span>
                    <span>L3F閾値クリア + RPCI瞬発。最後3Fで一気加速する切れ味勝負。</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="bg-sky-100 text-sky-700 text-xs font-medium rounded px-1.5 py-0.5 shrink-0">軽瞬発</span>
                    <span>RPCIのみ瞬発シグナル。やや瞬発寄りだが明確な切れ味は出にくい。</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="bg-indigo-100 text-indigo-700 text-xs font-medium rounded px-1.5 py-0.5 shrink-0">ロンスパ</span>
                    <span>残4F目から持続的に加速。L4ギャップ大 + 中盤緩みのロングスパート戦。</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="bg-gray-100 text-gray-700 text-xs font-medium rounded px-1.5 py-0.5 shrink-0">平均</span>
                    <span>全指標が中間域。展開によって瞬発にも持続にも振れる。</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="bg-red-100 text-red-700 text-xs font-medium rounded px-1.5 py-0.5 shrink-0">持続HP</span>
                    <span>RPCI低 + L3遅い。前半で消耗し後半失速するハイペース持続戦。</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="bg-orange-100 text-orange-700 text-xs font-medium rounded px-1.5 py-0.5 shrink-0">持続強L3</span>
                    <span>RPCI低 + L3速い。ハイペースでも上がりが速い、強い持続力の競馬。</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="bg-amber-100 text-amber-700 text-xs font-medium rounded px-1.5 py-0.5 shrink-0">持続道悪</span>
                    <span>道悪 + 持続シグナル。重馬場など脚元が悪い条件での持続戦。</span>
                  </li>
                </ul>
              </div>

              {/* 分析ツール */}
              <div className="mt-3 border-t pt-3 space-y-1">
                <p className="font-medium text-foreground">分析ツール</p>
                <ul className="list-disc list-inside space-y-1 ml-2">
                  <li><strong>馬場別比較:</strong> 良馬場 vs 稍重以上でRPCI傾向を分離分析</li>
                  <li><strong>頭数別補正:</strong> 少頭数→スロー傾向、多頭数→ハイペース傾向のオフセット値</li>
                  <li><strong>年度重み付け:</strong> 直近2年を×2倍で重み付けし、最新傾向を反映</li>
                </ul>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
