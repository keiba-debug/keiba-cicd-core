'use client';

/**
 * RPCI分析ページ
 * コース別のレース特性（瞬発戦/持続戦）傾向を表示
 */

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { RefreshCw, TrendingUp, TrendingDown, Minus, ArrowLeft } from 'lucide-react';
import Link from 'next/link';
import { RpciGauge, RpciBar, StatCard } from '@/components/ui/visualization';

// 型定義
interface RpciStats {
  mean: number;
  stdev: number;
  median: number;
  min: number;
  max: number;
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

interface RpciStandardsResponse {
  summary: {
    totalCourses: number;
    totalSamples: number;
    distanceGroups: number;
    similarPairs: number;
  };
  by_distance_group: Record<string, CourseData>;
  courses: Record<string, CourseData>;
  similar_courses: Record<string, string[]>;
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
function getRpciTrend(rpci: number): { label: string; color: string; icon: React.ReactNode } {
  if (rpci >= 51) {
    return { label: 'スロー（瞬発戦）', color: 'text-blue-600', icon: <TrendingUp className="h-4 w-4" /> };
  } else if (rpci <= 48) {
    return { label: 'ハイ（持続戦）', color: 'text-red-600', icon: <TrendingDown className="h-4 w-4" /> };
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

export default function RpciAnalysisPage() {
  const [data, setData] = useState<RpciStandardsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'distance' | 'course' | 'similar'>('distance');
  const [searchQuery, setSearchQuery] = useState('');

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
  const filteredCourses = data?.courses
    ? Object.entries(data.courses)
        .filter(([key]) => 
          searchQuery === '' || 
          formatCourseName(key).includes(searchQuery) ||
          key.toLowerCase().includes(searchQuery.toLowerCase())
        )
        .sort((a, b) => b[1].rpci.mean - a[1].rpci.mean)
    : [];

  return (
    <div className="container py-6 max-w-6xl">
      {/* パンくずリスト */}
      <nav className="flex items-center space-x-2 text-sm text-muted-foreground mb-6">
        <Link href="/" className="hover:underline flex items-center gap-1">
          <ArrowLeft className="h-4 w-4" />
          トップ
        </Link>
        <span>/</span>
        <span className="text-foreground">RPCI分析（レース特性）</span>
      </nav>

      {/* ヘッダー */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          📈 RPCI分析（レース特性）
        </h1>
        <p className="text-muted-foreground mt-1">
          コース別の瞬発戦/持続戦傾向を分析。RPCI = (前3F / 後3F) × 50
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
          <div className="flex border-b">
            <button
              onClick={() => setActiveTab('distance')}
              className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'distance'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              距離グループ別
            </button>
            <button
              onClick={() => setActiveTab('course')}
              className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'course'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              コース別
            </button>
            <button
              onClick={() => setActiveTab('similar')}
              className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'similar'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              類似コース
            </button>
          </div>

          {/* 距離グループ別タブ */}
          {activeTab === 'distance' && (
            <div className="space-y-6">
              {/* ゲージグリッド表示 */}
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                {Object.entries(data.by_distance_group)
                  .sort((a, b) => b[1].rpci.mean - a[1].rpci.mean)
                  .map(([key, value]) => (
                    <Card key={key} className="hover:shadow-md transition-shadow">
                      <CardContent className="pt-4 pb-3 flex flex-col items-center">
                        <div className="text-xs font-medium text-muted-foreground mb-2">
                          {formatDistanceGroup(key)}
                        </div>
                        <RpciGauge value={value.rpci.mean} size="sm" />
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
                          <th className="text-center py-3 px-4">傾向</th>
                          <th className="text-right py-3 px-4">瞬発閾値</th>
                          <th className="text-right py-3 px-4">持続閾値</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(data.by_distance_group)
                          .sort((a, b) => b[1].rpci.mean - a[1].rpci.mean)
                          .map(([key, value]) => {
                            const trend = getRpciTrend(value.rpci.mean);
                            return (
                              <tr key={key} className="border-b hover:bg-slate-50 dark:hover:bg-slate-800/50">
                                <td className="py-3 px-4 font-medium">{formatDistanceGroup(key)}</td>
                                <td className="text-right py-3 px-4">{value.sample_count.toLocaleString()}</td>
                                <td className="py-3 px-4">
                                  <div className="flex justify-center">
                                    <RpciGauge value={value.rpci.mean} size="sm" showLabel={false} />
                                  </div>
                                </td>
                                <td className="text-center py-3 px-4">
                                  <span className={`flex items-center justify-center gap-1 ${trend.color}`}>
                                    {trend.icon}
                                    <span className="text-xs">{trend.label}</span>
                                  </span>
                                </td>
                                <td className="text-right py-3 px-4 font-mono text-blue-600">&gt;{value.thresholds.instantaneous.toFixed(1)}</td>
                                <td className="text-right py-3 px-4 font-mono text-red-600">&lt;{value.thresholds.sustained.toFixed(1)}</td>
                              </tr>
                            );
                          })}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {/* コース別タブ */}
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
                <input
                  type="text"
                  placeholder="コース名で検索（例: 東京芝2000）"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full px-4 py-2 border rounded-lg text-sm dark:bg-gray-800 dark:border-gray-700"
                />
                
                {/* バーグラフ表示 */}
                <div className="max-h-[600px] overflow-y-auto space-y-1">
                  {filteredCourses.map(([key, value], index) => (
                    <RpciBar
                      key={key}
                      value={value.rpci.mean}
                      label={formatCourseName(key)}
                      rank={searchQuery === '' ? index + 1 : undefined}
                      sampleCount={value.sample_count}
                      animate={true}
                      delay={index * 30}
                    />
                  ))}
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
                    <span>瞬発戦（RPCI &gt; 50）</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-4 h-4 rounded bg-gray-400"></span>
                    <span>平均的</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-4 h-4 rounded bg-red-500"></span>
                    <span>持続戦（RPCI &lt; 50）</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* 類似コースタブ */}
          {activeTab === 'similar' && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">類似コース分析</CardTitle>
                <p className="text-sm text-muted-foreground">
                  RPCI差が0.8以下のコースを「類似」と判定しています
                </p>
              </CardHeader>
              <CardContent>
                <div className="max-h-[600px] overflow-y-auto space-y-3">
                  {Object.entries(data.similar_courses)
                    .filter(([_, similar]) => similar.length > 0)
                    .sort((a, b) => b[1].length - a[1].length)
                    .map(([course, similarCourses]) => {
                      const courseData = data.courses[course];
                      return (
                        <div key={course} className="bg-slate-50 rounded-lg p-4">
                          <div className="font-medium flex items-center gap-2">
                            {formatCourseName(course)}
                            <span className="text-xs font-mono text-muted-foreground">
                              RPCI: {courseData?.rpci.mean.toFixed(2)}
                            </span>
                          </div>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {similarCourses.map((similar) => {
                              const similarData = data.courses[similar];
                              const diff = similarData && courseData
                                ? Math.abs(similarData.rpci.mean - courseData.rpci.mean)
                                : 0;
                              return (
                                <span
                                  key={similar}
                                  className="inline-flex items-center gap-1 bg-white px-3 py-1.5 rounded text-sm border"
                                >
                                  {formatCourseName(similar)}
                                  <span className="text-muted-foreground text-xs">
                                    (差: {diff.toFixed(2)})
                                  </span>
                                </span>
                              );
                            })}
                          </div>
                        </div>
                      );
                    })}
                  {Object.values(data.similar_courses).every(arr => arr.length === 0) && (
                    <div className="py-8 text-center text-muted-foreground">
                      類似コースのデータがありません
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          {/* 解説 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">RPCIとは</CardTitle>
            </CardHeader>
            <CardContent className="text-sm space-y-2 text-muted-foreground">
              <p>
                <strong>RPCI (Race Pace Change Index)</strong> = (前半3Fタイム / 後半3Fタイム) × 50
              </p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li><span className="text-blue-600 font-medium">RPCI &gt; 50</span>: スローペース（前半遅い）→ 瞬発戦傾向</li>
                <li><span className="text-red-600 font-medium">RPCI &lt; 50</span>: ハイペース（前半速い）→ 持続戦傾向</li>
                <li><span className="text-gray-600 font-medium">RPCI ≈ 50</span>: 平均的なペース</li>
              </ul>
              <p className="mt-3">
                瞬発戦では上がり3Fの切れ味が重要、持続戦では持久力とスタミナが重要になります。
              </p>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
