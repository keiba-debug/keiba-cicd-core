'use client';

import { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import {
  ArrowLeft, RefreshCw, Trophy, TrendingUp, BarChart3,
  ArrowUpRight, ArrowDownRight, Minus,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

// ============================================================
// Types
// ============================================================

interface CloseBucket {
  close_wins: number;
  close_seconds: number;
  close_total: number;
  close_win_rate: number;
}

interface RankEntry {
  rank: number;
  code: string;
  name: string;
  total_runs: number;
  wins: number;
  win_rate: number;
  top3_rate: number;
  close_wins: number;
  close_seconds: number;
  close_total: number;
  close_win_rate: number;
  close_by_track: Record<string, CloseBucket>;
  close_by_distance: Record<string, CloseBucket>;
}

interface YearDetail {
  close_total: number;
  close_win_rate: number | null;
  win_rate: number;
  runs: number;
}

interface GrowthEntry {
  code: string;
  name: string;
  total_runs: number;
  close_total: number;
  close_win_rate: number;
  growth_score: number | null;
  years: Record<string, YearDetail>;
}

interface Summary {
  total_jockeys: number;
  qualified_jockeys: number;
  total_close_finishes: number;
  total_races: number;
  overall_close_win_rate: number;
  avg_close_win_rate: number;
  median_close_win_rate: number;
  year_from: string;
  year_to: string;
  min_close_total: number;
  min_year_total: number;
}

interface ConditionData {
  by_track: Record<string, CloseBucket>;
  by_distance: Record<string, CloseBucket>;
}

interface JockeyCloseFinishData {
  created_at: string;
  summary: Summary;
  ranking: RankEntry[];
  growth_trends: GrowthEntry[];
  conditions: ConditionData;
}

// ============================================================
// Helpers
// ============================================================

function pct(v: number | null | undefined, digits = 1): string {
  if (v == null) return '-';
  return `${(v * 100).toFixed(digits)}%`;
}

function closeRateColor(rate: number): string {
  if (rate >= 0.60) return 'text-blue-600 dark:text-blue-400 font-bold';
  if (rate >= 0.55) return 'text-blue-600 dark:text-blue-400';
  if (rate >= 0.50) return 'text-gray-900 dark:text-gray-100';
  if (rate >= 0.45) return 'text-orange-600 dark:text-orange-400';
  return 'text-red-600 dark:text-red-400';
}

function growthBadge(score: number | null) {
  if (score == null) return <Badge variant="secondary">N/A</Badge>;
  if (score >= 0.10)
    return (
      <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
        <ArrowUpRight className="w-3 h-3 mr-0.5" />
        {(score * 100).toFixed(1)}pt
      </Badge>
    );
  if (score >= 0.03)
    return (
      <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
        <ArrowUpRight className="w-3 h-3 mr-0.5" />
        +{(score * 100).toFixed(1)}pt
      </Badge>
    );
  if (score >= -0.03)
    return (
      <Badge variant="secondary">
        <Minus className="w-3 h-3 mr-0.5" />
        {(score * 100).toFixed(1)}pt
      </Badge>
    );
  return (
    <Badge className="bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200">
      <ArrowDownRight className="w-3 h-3 mr-0.5" />
      {(score * 100).toFixed(1)}pt
    </Badge>
  );
}

const DIST_LABELS: Record<string, string> = {
  sprint: 'スプリント (~1400m)',
  mile: 'マイル (1401-1800m)',
  intermediate: '中距離 (1801-2200m)',
  long: '長距離 (2201-2800m)',
  extended: '超長距離 (2801m~)',
};

const DIST_ORDER = ['sprint', 'mile', 'intermediate', 'long', 'extended'];

// ============================================================
// Ranking Tab
// ============================================================

function RankingTab({ ranking, summary }: { ranking: RankEntry[]; summary: Summary }) {
  const [sortKey, setSortKey] = useState<'close_win_rate' | 'close_total' | 'win_rate'>('close_win_rate');
  const [search, setSearch] = useState('');

  const sorted = useMemo(() => {
    let list = ranking;
    if (search) {
      const q = search.toLowerCase();
      list = list.filter((r) => r.name.toLowerCase().includes(q));
    }
    return [...list].sort((a, b) => (b[sortKey] || 0) - (a[sortKey] || 0));
  }, [ranking, sortKey, search]);

  return (
    <div className="space-y-4">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard label="対象騎手" value={summary.qualified_jockeys.toString()} />
        <MetricCard label="接戦レース数" value={summary.total_close_finishes.toLocaleString()} />
        <MetricCard label="全体接戦勝率" value={pct(summary.overall_close_win_rate)} highlight />
        <MetricCard label="中央値" value={pct(summary.median_close_win_rate)} />
      </div>

      {/* Controls */}
      <div className="flex flex-wrap gap-2 items-center">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="騎手名で検索..."
          className="px-3 py-1.5 text-sm border rounded-md bg-white dark:bg-gray-800 w-48"
        />
        <div className="flex gap-1 ml-auto">
          {[
            { key: 'close_win_rate' as const, label: '接戦勝率' },
            { key: 'close_total' as const, label: '接戦数' },
            { key: 'win_rate' as const, label: '通算勝率' },
          ].map((s) => (
            <button
              key={s.key}
              onClick={() => setSortKey(s.key)}
              className={`px-2 py-1 text-xs rounded ${
                sortKey === s.key
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300'
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-slate-50 dark:bg-slate-800">
              <th className="text-right py-2 px-2 w-10">#</th>
              <th className="text-left py-2 px-2">騎手名</th>
              <th className="text-right py-2 px-2">出走数</th>
              <th className="text-right py-2 px-2">勝率</th>
              <th className="text-right py-2 px-2">複勝率</th>
              <th className="text-right py-2 px-2">接戦数</th>
              <th className="text-right py-2 px-2 font-bold">接戦勝率</th>
              <th className="text-right py-2 px-2">芝</th>
              <th className="text-right py-2 px-2">ダート</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((r, i) => (
              <tr
                key={r.code}
                className={`border-b hover:bg-gray-50 dark:hover:bg-gray-800 ${
                  i < 3 ? 'bg-yellow-50/50 dark:bg-yellow-900/10' : ''
                }`}
              >
                <td className="text-right py-1.5 px-2 text-gray-500">{i + 1}</td>
                <td className="py-1.5 px-2 font-medium">{r.name}</td>
                <td className="text-right py-1.5 px-2 tabular-nums">{r.total_runs.toLocaleString()}</td>
                <td className="text-right py-1.5 px-2 tabular-nums">{pct(r.win_rate)}</td>
                <td className="text-right py-1.5 px-2 tabular-nums">{pct(r.top3_rate)}</td>
                <td className="text-right py-1.5 px-2 tabular-nums">{r.close_total}</td>
                <td className={`text-right py-1.5 px-2 tabular-nums ${closeRateColor(r.close_win_rate)}`}>
                  {pct(r.close_win_rate)}
                </td>
                <td className="text-right py-1.5 px-2 tabular-nums text-gray-600 dark:text-gray-400">
                  {r.close_by_track?.turf ? pct(r.close_by_track.turf.close_win_rate) : '-'}
                </td>
                <td className="text-right py-1.5 px-2 tabular-nums text-gray-600 dark:text-gray-400">
                  {r.close_by_track?.dirt ? pct(r.close_by_track.dirt.close_win_rate) : '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ============================================================
// Growth Tab
// ============================================================

function GrowthTab({ trends }: { trends: GrowthEntry[] }) {
  const [sortKey, setSortKey] = useState<'growth' | 'overall' | 'runs'>('growth');
  const [search, setSearch] = useState('');

  const years = useMemo(() => {
    const ys = new Set<string>();
    trends.forEach((t) => Object.keys(t.years).forEach((y) => ys.add(y)));
    return [...ys].sort();
  }, [trends]);

  const sorted = useMemo(() => {
    let list = trends;
    if (search) {
      const q = search.toLowerCase();
      list = list.filter((t) => t.name.toLowerCase().includes(q));
    }
    return [...list].sort((a, b) => {
      if (sortKey === 'growth') {
        const ag = a.growth_score ?? -999;
        const bg = b.growth_score ?? -999;
        return bg - ag;
      }
      if (sortKey === 'overall') return b.close_win_rate - a.close_win_rate;
      return b.total_runs - a.total_runs;
    });
  }, [trends, sortKey, search]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 items-center">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="騎手名で検索..."
          className="px-3 py-1.5 text-sm border rounded-md bg-white dark:bg-gray-800 w-48"
        />
        <div className="flex gap-1 ml-auto">
          {[
            { key: 'growth' as const, label: '成長スコア' },
            { key: 'overall' as const, label: '接戦勝率' },
            { key: 'runs' as const, label: '出走数' },
          ].map((s) => (
            <button
              key={s.key}
              onClick={() => setSortKey(s.key)}
              className={`px-2 py-1 text-xs rounded ${
                sortKey === s.key
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300'
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-slate-50 dark:bg-slate-800">
              <th className="text-left py-2 px-2">騎手名</th>
              <th className="text-right py-2 px-2">出走</th>
              <th className="text-right py-2 px-2">接戦数</th>
              <th className="text-right py-2 px-2">接戦勝率</th>
              <th className="text-center py-2 px-2">成長</th>
              {years.map((y) => (
                <th key={y} className="text-right py-2 px-2 text-xs">
                  {y}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((t) => (
              <tr key={t.code} className="border-b hover:bg-gray-50 dark:hover:bg-gray-800">
                <td className="py-1.5 px-2 font-medium">{t.name}</td>
                <td className="text-right py-1.5 px-2 tabular-nums">
                  {t.total_runs.toLocaleString()}
                </td>
                <td className="text-right py-1.5 px-2 tabular-nums">{t.close_total}</td>
                <td className={`text-right py-1.5 px-2 tabular-nums ${closeRateColor(t.close_win_rate)}`}>
                  {pct(t.close_win_rate)}
                </td>
                <td className="text-center py-1.5 px-2">{growthBadge(t.growth_score)}</td>
                {years.map((y) => {
                  const yd = t.years[y];
                  if (!yd || yd.close_win_rate == null) {
                    return (
                      <td key={y} className="text-right py-1.5 px-2 text-gray-400 text-xs">
                        {yd ? `(${yd.close_total})` : '-'}
                      </td>
                    );
                  }
                  return (
                    <td
                      key={y}
                      className={`text-right py-1.5 px-2 tabular-nums text-xs ${closeRateColor(yd.close_win_rate)}`}
                    >
                      {pct(yd.close_win_rate, 0)}
                      <span className="text-gray-400 ml-0.5">({yd.close_total})</span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-gray-500">
        成長スコア = 直近2年の平均接戦勝率 - それ以前の平均接戦勝率。
        年度内の括弧は接戦数。接戦数5未満はグレーアウト。
      </p>
    </div>
  );
}

// ============================================================
// Conditions Tab
// ============================================================

function ConditionsTab({
  conditions,
  ranking,
}: {
  conditions: ConditionData;
  ranking: RankEntry[];
}) {
  return (
    <div className="space-y-6">
      {/* Track Type */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">芝/ダート別</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            {['turf', 'dirt'].map((track) => {
              const b = conditions.by_track[track];
              if (!b) return null;
              return (
                <div key={track} className="rounded-lg border p-4">
                  <div className="text-sm text-gray-500 mb-1">
                    {track === 'turf' ? '芝' : 'ダート'}
                  </div>
                  <div className={`text-2xl font-bold tabular-nums ${closeRateColor(b.close_win_rate)}`}>
                    {pct(b.close_win_rate)}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    {b.close_wins}勝 / {b.close_total}回
                  </div>
                </div>
              );
            })}
          </div>

          {/* Top 5 per track */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
            {['turf', 'dirt'].map((track) => {
              const top5 = [...ranking]
                .filter((r) => (r.close_by_track?.[track]?.close_total || 0) >= 10)
                .sort(
                  (a, b) =>
                    (b.close_by_track?.[track]?.close_win_rate || 0) -
                    (a.close_by_track?.[track]?.close_win_rate || 0)
                )
                .slice(0, 10);
              return (
                <div key={track}>
                  <h4 className="text-sm font-medium mb-2">
                    {track === 'turf' ? '芝' : 'ダート'} Top 10 (10回以上)
                  </h4>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-xs text-gray-500">
                        <th className="text-left py-1 px-1">#</th>
                        <th className="text-left py-1 px-1">騎手</th>
                        <th className="text-right py-1 px-1">接戦勝率</th>
                        <th className="text-right py-1 px-1">回数</th>
                      </tr>
                    </thead>
                    <tbody>
                      {top5.map((r, i) => {
                        const b = r.close_by_track[track];
                        return (
                          <tr key={r.code} className="border-b">
                            <td className="py-1 px-1 text-gray-500">{i + 1}</td>
                            <td className="py-1 px-1">{r.name}</td>
                            <td className={`text-right py-1 px-1 tabular-nums ${closeRateColor(b.close_win_rate)}`}>
                              {pct(b.close_win_rate)}
                            </td>
                            <td className="text-right py-1 px-1 text-gray-500">{b.close_total}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Distance */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">距離帯別</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
            {DIST_ORDER.map((d) => {
              const b = conditions.by_distance[d];
              if (!b) return null;
              return (
                <div key={d} className="rounded-lg border p-3">
                  <div className="text-xs text-gray-500 mb-1">{DIST_LABELS[d] || d}</div>
                  <div className={`text-xl font-bold tabular-nums ${closeRateColor(b.close_win_rate)}`}>
                    {pct(b.close_win_rate)}
                  </div>
                  <div className="text-xs text-gray-500">{b.close_total}回</div>
                </div>
              );
            })}
          </div>

          {/* Top 5 per distance */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {DIST_ORDER.filter((d) => (conditions.by_distance[d]?.close_total || 0) >= 10).map(
              (dist) => {
                const top5 = [...ranking]
                  .filter((r) => (r.close_by_distance?.[dist]?.close_total || 0) >= 5)
                  .sort(
                    (a, b) =>
                      (b.close_by_distance?.[dist]?.close_win_rate || 0) -
                      (a.close_by_distance?.[dist]?.close_win_rate || 0)
                  )
                  .slice(0, 5);
                return (
                  <div key={dist}>
                    <h4 className="text-sm font-medium mb-2">{DIST_LABELS[dist]} Top 5</h4>
                    <table className="w-full text-sm">
                      <tbody>
                        {top5.map((r, i) => {
                          const b = r.close_by_distance[dist];
                          return (
                            <tr key={r.code} className="border-b">
                              <td className="py-1 text-gray-500 w-6">{i + 1}</td>
                              <td className="py-1">{r.name}</td>
                              <td className={`text-right py-1 tabular-nums ${closeRateColor(b.close_win_rate)}`}>
                                {pct(b.close_win_rate)}
                              </td>
                              <td className="text-right py-1 text-gray-500 text-xs">({b.close_total})</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                );
              }
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// ============================================================
// Metric Card
// ============================================================

function MetricCard({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={`rounded-lg border p-3 ${
        highlight ? 'border-blue-300 bg-blue-50 dark:border-blue-700 dark:bg-blue-950' : 'bg-white dark:bg-gray-900'
      }`}
    >
      <div className="text-xs text-gray-500">{label}</div>
      <div className="mt-1 text-xl font-bold tabular-nums">{value}</div>
    </div>
  );
}

// ============================================================
// Main Page
// ============================================================

export default function JockeyCloseFinishPage() {
  const [data, setData] = useState<JockeyCloseFinishData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/analysis/jockey-close-finish');
      const result = await res.json();
      if (!res.ok) {
        setError(result.message || 'データ取得に失敗');
        return;
      }
      setData(result);
    } catch {
      setError('データ取得に失敗しました');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="p-8 text-center text-gray-500">
        読み込み中...
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="rounded-lg border border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950 p-4">
          <p className="text-red-700 dark:text-red-300">{error}</p>
          <p className="text-sm text-gray-500 mt-2">
            python -m analysis.jockey_close_finish を実行してデータを生成してください。
          </p>
        </div>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="p-4 md:p-6 max-w-7xl mx-auto space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/analysis"
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
          >
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <h1 className="text-xl font-bold">騎手接戦分析</h1>
          <Badge variant="secondary" className="text-xs">
            接戦 = 1着-2着のタイム差 0.1秒以内
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          {data.summary.year_from && (
            <Badge variant="outline" className="text-xs">
              {data.summary.year_from}-{data.summary.year_to}年 / {data.summary.total_races.toLocaleString()}走
            </Badge>
          )}
          <span className="text-xs text-gray-500">
            {new Date(data.created_at).toLocaleDateString('ja-JP')} 生成
          </span>
          <button
            onClick={fetchData}
            className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="ranking">
        <TabsList>
          <TabsTrigger value="ranking" className="gap-1">
            <Trophy className="w-3.5 h-3.5" />
            ランキング
          </TabsTrigger>
          <TabsTrigger value="growth" className="gap-1">
            <TrendingUp className="w-3.5 h-3.5" />
            成長トレンド
          </TabsTrigger>
          <TabsTrigger value="conditions" className="gap-1">
            <BarChart3 className="w-3.5 h-3.5" />
            条件別分析
          </TabsTrigger>
        </TabsList>

        <TabsContent value="ranking">
          <RankingTab ranking={data.ranking} summary={data.summary} />
        </TabsContent>

        <TabsContent value="growth">
          <GrowthTab trends={data.growth_trends} />
        </TabsContent>

        <TabsContent value="conditions">
          <ConditionsTab conditions={data.conditions} ranking={data.ranking} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
