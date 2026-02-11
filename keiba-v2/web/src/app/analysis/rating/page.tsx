'use client';

/**
 * レイティング分析ページ
 * クラス別レイティング統計・レースレベル判定基準を表示
 */

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { RefreshCw, TrendingUp, TrendingDown, Minus, ArrowLeft, Star } from 'lucide-react';
import Link from 'next/link';

// 型定義
interface RatingStats {
  mean: number;
  stdev: number;
  median: number;
  min: number;
  max: number;
}

interface CompetitivenessInfo {
  mean_race_stdev: number;
  mean_top3_diff: number;
  description: string;
}

interface GradeData {
  sample_count: number;
  horse_count: number;
  rating: RatingStats;
  competitiveness: CompetitivenessInfo;
  thresholds: {
    high_level: number;
    low_level: number;
  };
}

interface MaidenSeasonData {
  sample_count: number;
  horse_count: number;
  rating: RatingStats;
}

interface RatingStandardsResponse {
  summary: {
    totalGrades: number;
    totalRaces: number;
    years: string;
  };
  by_grade: Record<string, GradeData>;
  competitiveness_thresholds: {
    stdev: {
      mean: number;
      thresholds: {
        very_competitive: number;
        competitive: number;
        normal: number;
        clear_difference: number;
      };
    };
    top3_diff: {
      mean: number;
      description: string;
    };
  };
  maiden_by_season?: Record<string, MaidenSeasonData>;
  metadata: {
    created_at: string;
    source: string;
    years: string;
    total_races: number;
    description: string;
  };
}

// グレード順序（年齢別グレード対応）
const GRADE_ORDER = [
  'G1_古馬', 'G1_3歳', 'G1_2歳',
  'G2_古馬', 'G2_3歳', 'G2_2歳',
  'G3_古馬', 'G3_3歳', 'G3_2歳',
  // 年齢未分類のフォールバック
  'G1', 'G2', 'G3',
  'OP', '3勝クラス', '2勝クラス', '1勝クラス', '新馬', '未勝利',
];

/** グレード文字列からベースグレード（G1/G2/G3/OP等）を取得 */
function getBaseGrade(grade: string): string {
  const base = grade.split('_')[0];
  return base;
}

function getGradeColor(grade: string): string {
  const base = getBaseGrade(grade);
  switch (base) {
    case 'G1': return 'bg-yellow-100 text-yellow-800 border-yellow-300';
    case 'G2': return 'bg-pink-100 text-pink-800 border-pink-300';
    case 'G3': return 'bg-orange-100 text-orange-800 border-orange-300';
    case 'OP': return 'bg-purple-100 text-purple-800 border-purple-300';
    default: return 'bg-gray-100 text-gray-800 border-gray-300';
  }
}

function getStars(grade: string): number {
  const base = getBaseGrade(grade);
  switch (base) {
    case 'G1': return 5;
    case 'G2': return 4;
    case 'G3': return 4;
    case 'OP': return 3;
    case '3勝クラス': return 3;
    case '2勝クラス': return 2;
    case '1勝クラス': return 2;
    case '新馬': return 1;
    case '未勝利': return 1;
    default: return 1;
  }
}

/** グレード名を表示用にフォーマット（G1_古馬 → "G1 古馬"） */
function formatGradeName(grade: string): string {
  return grade.replace('_', ' ');
}

export default function RatingAnalysisPage() {
  const [data, setData] = useState<RatingStandardsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/admin/rating-standards');
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

  // グレードをソート
  const sortedGrades = data?.by_grade
    ? Object.entries(data.by_grade).sort((a, b) => {
        const indexA = GRADE_ORDER.indexOf(a[0]);
        const indexB = GRADE_ORDER.indexOf(b[0]);
        return (indexA === -1 ? 99 : indexA) - (indexB === -1 ? 99 : indexB);
      })
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
        <span className="text-foreground">レイティング分析</span>
      </nav>

      {/* ヘッダー */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          📈 レイティング分析
        </h1>
        <p className="text-muted-foreground mt-1">
          クラス別レイティング統計・レースレベル判定基準
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
              管理画面 → データ分析 → 「レイティング基準値算出」を実行してください
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
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <Card>
              <CardContent className="pt-6 text-center">
                <div className="text-3xl font-bold text-slate-700">{data.summary.totalGrades}</div>
                <div className="text-sm text-slate-500 mt-1">クラス数</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6 text-center">
                <div className="text-3xl font-bold text-slate-700">{data.summary.totalRaces.toLocaleString()}</div>
                <div className="text-sm text-slate-500 mt-1">総レース数</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6 text-center">
                <div className="text-3xl font-bold text-slate-700">{data.summary.years}</div>
                <div className="text-sm text-slate-500 mt-1">対象期間</div>
              </CardContent>
            </Card>
          </div>

          {/* メタデータ */}
          <div className="text-xs text-muted-foreground flex items-center justify-between">
            <span>
              更新日時: {new Date(data.metadata.created_at).toLocaleString('ja-JP')} | ソース: {data.metadata.source}
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

          {/* クラス別レイティング */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">クラス別レイティング基準</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-slate-50">
                      <th className="text-left py-3 px-4">クラス</th>
                      <th className="text-right py-3 px-4">レース数</th>
                      <th className="text-right py-3 px-4">平均</th>
                      <th className="text-right py-3 px-4">標準偏差</th>
                      <th className="text-center py-3 px-4">レベル判定</th>
                      <th className="text-center py-3 px-4">混戦度</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedGrades.map(([grade, value]) => (
                      <tr key={grade} className="border-b hover:bg-slate-50">
                        <td className="py-3 px-4">
                          <span className={`inline-flex items-center gap-2 px-2 py-1 rounded border text-xs font-medium ${getGradeColor(grade)}`}>
                            {formatGradeName(grade)}
                            <span className="flex">
                              {[...Array(getStars(grade))].map((_, i) => (
                                <Star key={i} className="h-3 w-3 fill-current" />
                              ))}
                            </span>
                          </span>
                        </td>
                        <td className="text-right py-3 px-4">{value.sample_count.toLocaleString()}</td>
                        <td className="text-right py-3 px-4 font-mono font-bold">{value.rating.mean.toFixed(1)}</td>
                        <td className="text-right py-3 px-4 font-mono text-muted-foreground">{value.rating.stdev.toFixed(1)}</td>
                        <td className="text-center py-3 px-4">
                          <span className="text-xs">
                            <span className="text-green-600">高: &gt;{value.thresholds.high_level.toFixed(0)}</span>
                            <span className="mx-1 text-muted-foreground">/</span>
                            <span className="text-red-600">低: &lt;{value.thresholds.low_level.toFixed(0)}</span>
                          </span>
                        </td>
                        <td className="text-center py-3 px-4">
                          <span className={`text-xs px-2 py-1 rounded ${
                            value.competitiveness.mean_race_stdev < 5 
                              ? 'bg-red-100 text-red-700' 
                              : value.competitiveness.mean_race_stdev < 7
                                ? 'bg-yellow-100 text-yellow-700'
                                : 'bg-green-100 text-green-700'
                          }`}>
                            {value.competitiveness.description}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* 詳細カード */}
          <div className="grid md:grid-cols-2 gap-6">
            {sortedGrades.slice(0, 10).map(([grade, value]) => (
              <Card key={grade}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base flex items-center justify-between">
                    <span className={`px-3 py-1 rounded border ${getGradeColor(grade)}`}>
                      {formatGradeName(grade)}
                    </span>
                    <span className="text-sm font-normal text-muted-foreground">
                      {value.sample_count}レース / {value.horse_count}頭
                    </span>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-3 gap-4 text-center">
                    <div>
                      <div className="text-2xl font-bold">{value.rating.mean.toFixed(1)}</div>
                      <div className="text-xs text-muted-foreground">平均</div>
                    </div>
                    <div>
                      <div className="text-2xl font-bold text-muted-foreground">{value.rating.stdev.toFixed(1)}</div>
                      <div className="text-xs text-muted-foreground">標準偏差</div>
                    </div>
                    <div>
                      <div className="text-2xl font-bold">{value.rating.median.toFixed(1)}</div>
                      <div className="text-xs text-muted-foreground">中央値</div>
                    </div>
                  </div>
                  <div className="mt-4 pt-4 border-t">
                    <div className="flex justify-between text-xs">
                      <span>レンジ: {value.rating.min.toFixed(0)} - {value.rating.max.toFixed(0)}</span>
                      <span>上位差: {value.competitiveness.mean_top3_diff.toFixed(1)}pt</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* 混戦度判定基準 */}
          {data.competitiveness_thresholds?.stdev && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">混戦度判定基準</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground mb-4">
                  レース内のレイティング標準偏差から混戦度を判定します。標準偏差が小さいほど実力が拮抗しています。
                </p>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="bg-red-50 p-4 rounded-lg text-center">
                    <div className="font-bold text-red-700">非常に混戦</div>
                    <div className="text-sm text-red-600 mt-1">
                      &lt; {data.competitiveness_thresholds.stdev.thresholds.very_competitive.toFixed(1)}
                    </div>
                  </div>
                  <div className="bg-yellow-50 p-4 rounded-lg text-center">
                    <div className="font-bold text-yellow-700">やや混戦</div>
                    <div className="text-sm text-yellow-600 mt-1">
                      &lt; {data.competitiveness_thresholds.stdev.thresholds.competitive.toFixed(1)}
                    </div>
                  </div>
                  <div className="bg-gray-50 p-4 rounded-lg text-center">
                    <div className="font-bold text-gray-700">標準的</div>
                    <div className="text-sm text-gray-600 mt-1">
                      ≈ {data.competitiveness_thresholds.stdev.thresholds.normal.toFixed(1)}
                    </div>
                  </div>
                  <div className="bg-green-50 p-4 rounded-lg text-center">
                    <div className="font-bold text-green-700">力差明確</div>
                    <div className="text-sm text-green-600 mt-1">
                      &gt; {data.competitiveness_thresholds.stdev.thresholds.clear_difference.toFixed(1)}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* 未勝利戦シーズン別分析 */}
          {data.maiden_by_season && Object.keys(data.maiden_by_season).length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  🌱 未勝利戦シーズン別レイティング
                </CardTitle>
                <p className="text-sm text-muted-foreground">
                  2歳・3歳未勝利戦の月別レイティング推移（成長による変化を確認）
                </p>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left py-3 px-4">シーズン</th>
                        <th className="text-center py-3 px-4">コース</th>
                        <th className="text-right py-3 px-4">レース数</th>
                        <th className="text-right py-3 px-4">平均</th>
                        <th className="text-right py-3 px-4">標準偏差</th>
                        <th className="text-right py-3 px-4">中央値</th>
                        <th className="text-right py-3 px-4">レンジ</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(data.maiden_by_season).map(([key, value]) => {
                        const parts = key.split('_');
                        const season = parts.slice(0, 2).join('_');
                        const track = parts[2] || '';
                        const isShiba = track === '芝';
                        
                        return (
                          <tr key={key} className="border-b hover:bg-muted/50">
                            <td className="py-3 px-4 font-medium">{season.replace('_', ' ')}</td>
                            <td className="text-center py-3 px-4">
                              <span className={`px-2 py-1 rounded text-xs ${
                                isShiba ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'
                              }`}>
                                {track || '不明'}
                              </span>
                            </td>
                            <td className="text-right py-3 px-4 text-muted-foreground">
                              {value.sample_count.toLocaleString()}
                            </td>
                            <td className="text-right py-3 px-4 font-mono font-bold">
                              {value.rating.mean.toFixed(1)}
                            </td>
                            <td className="text-right py-3 px-4 font-mono text-muted-foreground">
                              {value.rating.stdev.toFixed(1)}
                            </td>
                            <td className="text-right py-3 px-4 font-mono">
                              {value.rating.median.toFixed(1)}
                            </td>
                            <td className="text-right py-3 px-4 font-mono text-muted-foreground text-xs">
                              {value.rating.min.toFixed(0)}-{value.rating.max.toFixed(0)}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                <div className="mt-4 p-4 bg-muted/50 rounded-lg">
                  <h4 className="font-medium mb-2">分析の視点</h4>
                  <ul className="text-sm text-muted-foreground space-y-1">
                    <li>• 2歳6-8月 → 2歳9-12月 → 3歳1-3月... と進むにつれてレイティング平均が上昇するか確認</li>
                    <li>• 成長期の若駒は後半戦ほど能力が向上する傾向があるか</li>
                    <li>• 芝とダートで成長曲線に違いがあるか</li>
                  </ul>
                </div>
              </CardContent>
            </Card>
          )}

          {/* 解説 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">活用方法</CardTitle>
            </CardHeader>
            <CardContent className="text-sm space-y-3 text-muted-foreground">
              <div>
                <strong className="text-foreground">1. レースレベル判定</strong>
                <p>該当レースの平均レイティングをクラス基準値と比較し、高いか低いかを判断します。</p>
              </div>
              <div>
                <strong className="text-foreground">2. 混戦度判定</strong>
                <p>レイティングのばらつき（標準偏差）から、実力が拮抗しているか力差があるかを判断します。</p>
              </div>
              <div>
                <strong className="text-foreground">3. 予想への活用</strong>
                <ul className="list-disc list-inside ml-2 mt-1">
                  <li>混戦 → 人気馬が信頼しづらい、荒れる可能性</li>
                  <li>力差明確 → 上位馬が堅い、堅い決着の可能性</li>
                  <li>レベル高 → 他クラスとの比較で有利</li>
                </ul>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
