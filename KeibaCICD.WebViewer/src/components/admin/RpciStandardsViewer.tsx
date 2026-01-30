'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { ChevronDown, ChevronUp, RefreshCw, TrendingUp, TrendingDown, Minus } from 'lucide-react';

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

// コース名をパース（例: Tokyo_Turf_2000m -> 東京 芝 2000m）
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

export function RpciStandardsViewer() {
  const [data, setData] = useState<RpciStandardsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(false);
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
    if (isOpen && !data) {
      fetchData();
    }
  }, [isOpen, data]);

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
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <Card className="border-muted">
        <CollapsibleTrigger asChild>
          <CardHeader className="pb-3 cursor-pointer hover:bg-muted/50 transition-colors">
            <CardTitle className="text-lg flex items-center justify-between">
              <span className="flex items-center gap-2">
                📈 RPCI分析結果
                <span className="text-xs font-normal text-muted-foreground">
                  （コース別傾向・類似コース）
                </span>
              </span>
              {isOpen ? (
                <ChevronUp className="h-5 w-5 text-muted-foreground" />
              ) : (
                <ChevronDown className="h-5 w-5 text-muted-foreground" />
              )}
            </CardTitle>
          </CardHeader>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <CardContent>
            {loading && (
              <div className="flex items-center justify-center py-8">
                <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
                <span className="ml-2 text-muted-foreground">読み込み中...</span>
              </div>
            )}

            {error && (
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-amber-800">
                <p className="font-medium">データがありません</p>
                <p className="text-sm mt-1">{error}</p>
                <button
                  onClick={fetchData}
                  className="mt-2 text-sm underline hover:no-underline"
                >
                  再読み込み
                </button>
              </div>
            )}

            {data && (
              <div className="space-y-4">
                {/* サマリー */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div className="bg-slate-50 rounded-lg p-3 text-center">
                    <div className="text-2xl font-bold text-slate-700">{data.summary.totalCourses}</div>
                    <div className="text-xs text-slate-500">コース数</div>
                  </div>
                  <div className="bg-slate-50 rounded-lg p-3 text-center">
                    <div className="text-2xl font-bold text-slate-700">{data.summary.totalSamples.toLocaleString()}</div>
                    <div className="text-xs text-slate-500">総レース数</div>
                  </div>
                  <div className="bg-slate-50 rounded-lg p-3 text-center">
                    <div className="text-2xl font-bold text-slate-700">{data.summary.distanceGroups}</div>
                    <div className="text-xs text-slate-500">距離グループ</div>
                  </div>
                  <div className="bg-slate-50 rounded-lg p-3 text-center">
                    <div className="text-2xl font-bold text-slate-700">{Math.round(data.summary.similarPairs)}</div>
                    <div className="text-xs text-slate-500">類似ペア</div>
                  </div>
                </div>

                {/* 更新日時 */}
                <div className="text-xs text-muted-foreground flex items-center justify-between">
                  <span>
                    更新: {new Date(data.metadata.created_at).toLocaleString('ja-JP')}
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
                    className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                      activeTab === 'distance'
                        ? 'border-blue-500 text-blue-600'
                        : 'border-transparent text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    距離グループ別
                  </button>
                  <button
                    onClick={() => setActiveTab('course')}
                    className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                      activeTab === 'course'
                        ? 'border-blue-500 text-blue-600'
                        : 'border-transparent text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    コース別
                  </button>
                  <button
                    onClick={() => setActiveTab('similar')}
                    className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
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
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b bg-slate-50">
                          <th className="text-left py-2 px-3">カテゴリ</th>
                          <th className="text-right py-2 px-3">件数</th>
                          <th className="text-right py-2 px-3">RPCI平均</th>
                          <th className="text-center py-2 px-3">傾向</th>
                          <th className="text-right py-2 px-3">瞬発閾値</th>
                          <th className="text-right py-2 px-3">持続閾値</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(data.by_distance_group)
                          .sort((a, b) => b[1].rpci.mean - a[1].rpci.mean)
                          .map(([key, value]) => {
                            const trend = getRpciTrend(value.rpci.mean);
                            return (
                              <tr key={key} className="border-b hover:bg-slate-50">
                                <td className="py-2 px-3 font-medium">{formatDistanceGroup(key)}</td>
                                <td className="text-right py-2 px-3">{value.sample_count.toLocaleString()}</td>
                                <td className="text-right py-2 px-3 font-mono">{value.rpci.mean.toFixed(2)}</td>
                                <td className="text-center py-2 px-3">
                                  <span className={`flex items-center justify-center gap-1 ${trend.color}`}>
                                    {trend.icon}
                                    <span className="text-xs">{trend.label}</span>
                                  </span>
                                </td>
                                <td className="text-right py-2 px-3 font-mono text-blue-600">&gt;{value.thresholds.instantaneous.toFixed(1)}</td>
                                <td className="text-right py-2 px-3 font-mono text-red-600">&lt;{value.thresholds.sustained.toFixed(1)}</td>
                              </tr>
                            );
                          })}
                      </tbody>
                    </table>
                  </div>
                )}

                {/* コース別タブ */}
                {activeTab === 'course' && (
                  <div className="space-y-3">
                    <input
                      type="text"
                      placeholder="コース名で検索（例: 東京芝2000）"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full px-3 py-2 border rounded-lg text-sm"
                    />
                    <div className="overflow-x-auto max-h-96">
                      <table className="w-full text-sm">
                        <thead className="sticky top-0 bg-white">
                          <tr className="border-b bg-slate-50">
                            <th className="text-left py-2 px-3">コース</th>
                            <th className="text-right py-2 px-3">件数</th>
                            <th className="text-right py-2 px-3">RPCI</th>
                            <th className="text-center py-2 px-3">傾向</th>
                            <th className="text-right py-2 px-3">標準偏差</th>
                          </tr>
                        </thead>
                        <tbody>
                          {filteredCourses.map(([key, value]) => {
                            const trend = getRpciTrend(value.rpci.mean);
                            return (
                              <tr key={key} className="border-b hover:bg-slate-50">
                                <td className="py-2 px-3 font-medium">{formatCourseName(key)}</td>
                                <td className="text-right py-2 px-3">{value.sample_count}</td>
                                <td className="text-right py-2 px-3 font-mono font-bold">{value.rpci.mean.toFixed(2)}</td>
                                <td className="text-center py-2 px-3">
                                  <span className={`flex items-center justify-center gap-1 ${trend.color}`}>
                                    {trend.icon}
                                  </span>
                                </td>
                                <td className="text-right py-2 px-3 font-mono text-muted-foreground">{value.rpci.stdev.toFixed(2)}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                      {filteredCourses.length === 0 && (
                        <div className="py-8 text-center text-muted-foreground">
                          該当するコースがありません
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* 類似コースタブ */}
                {activeTab === 'similar' && (
                  <div className="space-y-3">
                    <div className="text-xs text-muted-foreground mb-2">
                      RPCI差が0.8以下のコースを「類似」と判定しています
                    </div>
                    <div className="max-h-96 overflow-y-auto space-y-2">
                      {Object.entries(data.similar_courses)
                        .filter(([_, similar]) => similar.length > 0)
                        .sort((a, b) => b[1].length - a[1].length)
                        .map(([course, similarCourses]) => {
                          const courseData = data.courses[course];
                          return (
                            <div key={course} className="bg-slate-50 rounded-lg p-3">
                              <div className="font-medium flex items-center gap-2">
                                {formatCourseName(course)}
                                <span className="text-xs font-mono text-muted-foreground">
                                  RPCI: {courseData?.rpci.mean.toFixed(2)}
                                </span>
                              </div>
                              <div className="mt-1 flex flex-wrap gap-2">
                                {similarCourses.map((similar) => {
                                  const similarData = data.courses[similar];
                                  const diff = similarData && courseData
                                    ? Math.abs(similarData.rpci.mean - courseData.rpci.mean)
                                    : 0;
                                  return (
                                    <span
                                      key={similar}
                                      className="inline-flex items-center gap-1 bg-white px-2 py-1 rounded text-xs border"
                                    >
                                      {formatCourseName(similar)}
                                      <span className="text-muted-foreground">
                                        (差: {diff.toFixed(2)})
                                      </span>
                                    </span>
                                  );
                                })}
                              </div>
                            </div>
                          );
                        })}
                    </div>
                    {Object.values(data.similar_courses).every(arr => arr.length === 0) && (
                      <div className="py-8 text-center text-muted-foreground">
                        類似コースのデータがありません
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  );
}
