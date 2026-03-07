/**
 * IDM分析ページ
 * クラス別 JRDB IDM 統計（全馬 / 勝ち馬基準）
 */

import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import { getIDMStandards, type IDMGradeStandard } from '@/lib/data/idm-standards-reader';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

// ── 定数 ──

const GRADE_ORDER = [
  'G1_古馬', 'G1_3歳', 'G1_2歳',
  'G2_古馬', 'G2_3歳', 'G2_2歳',
  'G3_古馬', 'G3_3歳', 'G3_2歳',
  'Listed_古馬', 'Listed_3歳', 'Listed_2歳',
  'OP_古馬', 'OP_3歳', 'OP_2歳',
  'G1', 'G2', 'G3', 'Listed', 'OP',
  '3勝クラス', '2勝クラス', '1勝クラス', '新馬', '未勝利',
];

function getGradeColor(grade: string): string {
  const base = grade.split('_')[0];
  switch (base) {
    case 'G1': return 'bg-yellow-100 text-yellow-800 border-yellow-300';
    case 'G2': return 'bg-pink-100 text-pink-800 border-pink-300';
    case 'G3': return 'bg-orange-100 text-orange-800 border-orange-300';
    case 'Listed': return 'bg-blue-100 text-blue-800 border-blue-300';
    case 'OP': return 'bg-purple-100 text-purple-800 border-purple-300';
    default: return 'bg-gray-100 text-gray-800 border-gray-300';
  }
}

function formatGradeName(grade: string): string {
  return grade.replace('_', ' ');
}

// ── ビジュアルバー ──

function IdmBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-3 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      <span className="text-xs font-mono w-8 text-right">{value.toFixed(0)}</span>
    </div>
  );
}

// ── ページ ──

export default function IDMAnalysisPage() {
  const standards = getIDMStandards();

  if (!standards) {
    return (
      <div className="container py-6 max-w-6xl">
        <nav className="flex items-center space-x-2 text-sm text-muted-foreground mb-6">
          <Link href="/" className="hover:underline flex items-center gap-1">
            <ArrowLeft className="h-4 w-4" />
            トップ
          </Link>
          <span>/</span>
          <span className="text-foreground">IDM分析</span>
        </nav>
        <Card className="bg-amber-50 border-amber-200">
          <CardContent className="py-6">
            <p className="font-medium text-amber-800">データがありません</p>
            <p className="text-sm mt-1 text-amber-700">
              python -m analysis.idm_standards を実行してください
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const { metadata, by_grade } = standards;

  // ソート
  const sortedGrades = Object.entries(by_grade).sort((a, b) => {
    const ia = GRADE_ORDER.indexOf(a[0]);
    const ib = GRADE_ORDER.indexOf(b[0]);
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
  });

  // 勝ち馬IDM最大値（バー表示用）
  const maxWinnerIdm = Math.max(
    ...sortedGrades.map(([, v]) => v.winner?.mean ?? 0)
  );

  return (
    <div className="container py-6 max-w-6xl">
      {/* パンくず */}
      <nav className="flex items-center space-x-2 text-sm text-muted-foreground mb-6">
        <Link href="/" className="hover:underline flex items-center gap-1">
          <ArrowLeft className="h-4 w-4" />
          トップ
        </Link>
        <span>/</span>
        <span className="text-foreground">IDM分析</span>
      </nav>

      {/* ヘッダー */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold">IDM分析 — クラス別 JRDB IDM 基準</h1>
        <p className="text-muted-foreground mt-1">
          各クラスの全馬平均IDMと勝ち馬平均IDMの比較
        </p>
      </div>

      {/* サマリー */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <Card>
          <CardContent className="pt-6 text-center">
            <div className="text-3xl font-bold">{sortedGrades.length}</div>
            <div className="text-sm text-muted-foreground mt-1">クラス数</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6 text-center">
            <div className="text-3xl font-bold">{metadata.total_races.toLocaleString()}</div>
            <div className="text-sm text-muted-foreground mt-1">総レース数</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6 text-center">
            <div className="text-3xl font-bold">{metadata.global_mean_idm.toFixed(1)}</div>
            <div className="text-sm text-muted-foreground mt-1">全体平均IDM</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6 text-center">
            <div className="text-3xl font-bold text-amber-600">{metadata.global_winner_mean_idm.toFixed(1)}</div>
            <div className="text-sm text-muted-foreground mt-1">勝ち馬平均IDM</div>
          </CardContent>
        </Card>
      </div>

      {/* メタデータ */}
      <div className="text-xs text-muted-foreground mb-6">
        更新: {new Date(metadata.created_at).toLocaleString('ja-JP')} |
        対象: {metadata.years} |
        ソース: {metadata.source}
      </div>

      {/* メインテーブル */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-lg">クラス別 IDM基準値</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-slate-50 dark:bg-slate-900">
                  <th className="text-left py-3 px-3">クラス</th>
                  <th className="text-right py-3 px-3">レース数</th>
                  <th className="text-right py-3 px-3">全馬平均</th>
                  <th className="text-right py-3 px-3">全馬σ</th>
                  <th className="text-right py-3 px-3 text-amber-700 dark:text-amber-400 font-bold">勝ち馬平均</th>
                  <th className="text-right py-3 px-3">勝ち馬σ</th>
                  <th className="text-right py-3 px-3">差</th>
                  <th className="py-3 px-3 w-40">勝ち馬IDM</th>
                </tr>
              </thead>
              <tbody>
                {sortedGrades.map(([grade, data]) => {
                  const winMean = data.winner?.mean ?? 0;
                  const allMean = data.all.mean;
                  const diff = winMean - allMean;
                  return (
                    <tr key={grade} className="border-b hover:bg-slate-50 dark:hover:bg-slate-900/50">
                      <td className="py-2.5 px-3">
                        <span className={`inline-block px-2 py-0.5 rounded border text-xs font-medium ${getGradeColor(grade)}`}>
                          {formatGradeName(grade)}
                        </span>
                        {data.fallback_to && (
                          <span className="ml-1 text-[10px] text-muted-foreground">(pool)</span>
                        )}
                      </td>
                      <td className="text-right py-2.5 px-3 text-muted-foreground">{data.sample_count.toLocaleString()}</td>
                      <td className="text-right py-2.5 px-3 font-mono">{allMean.toFixed(1)}</td>
                      <td className="text-right py-2.5 px-3 font-mono text-muted-foreground">{data.all.stdev.toFixed(1)}</td>
                      <td className="text-right py-2.5 px-3 font-mono font-bold text-amber-700 dark:text-amber-400">
                        {data.winner ? winMean.toFixed(1) : '-'}
                      </td>
                      <td className="text-right py-2.5 px-3 font-mono text-muted-foreground">
                        {data.winner ? data.winner.stdev.toFixed(1) : '-'}
                      </td>
                      <td className="text-right py-2.5 px-3 font-mono text-xs text-green-600">
                        {data.winner ? `+${diff.toFixed(1)}` : '-'}
                      </td>
                      <td className="py-2.5 px-3">
                        {data.winner && <IdmBar value={winMean} max={maxWinnerIdm} color="#f59e0b" />}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* 詳細カード（上位10グレード） */}
      <div className="grid md:grid-cols-2 gap-4 mb-6">
        {sortedGrades.slice(0, 10).map(([grade, data]) => (
          <Card key={grade}>
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center justify-between">
                <span className={`px-3 py-1 rounded border ${getGradeColor(grade)}`}>
                  {formatGradeName(grade)}
                </span>
                <span className="text-sm font-normal text-muted-foreground">
                  {data.sample_count}R / {data.horse_count}頭
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4">
                {/* 全馬 */}
                <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-3">
                  <div className="text-xs text-muted-foreground mb-1">全馬</div>
                  <div className="text-2xl font-bold">{data.all.mean.toFixed(1)}</div>
                  <div className="text-xs text-muted-foreground mt-1">
                    σ={data.all.stdev.toFixed(1)} / 中央値={data.all.median}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {data.all.min} ~ {data.all.max}
                  </div>
                </div>
                {/* 勝ち馬 */}
                <div className="bg-amber-50 dark:bg-amber-900/20 rounded-lg p-3">
                  <div className="text-xs text-amber-700 dark:text-amber-400 mb-1">勝ち馬</div>
                  {data.winner ? (
                    <>
                      <div className="text-2xl font-bold text-amber-700 dark:text-amber-400">
                        {data.winner.mean.toFixed(1)}
                      </div>
                      <div className="text-xs text-muted-foreground mt-1">
                        σ={data.winner.stdev.toFixed(1)} / 中央値={data.winner.median}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {data.winner.min} ~ {data.winner.max}
                      </div>
                    </>
                  ) : (
                    <div className="text-muted-foreground">-</div>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* 重賞 個別レース基準 */}
      {standards.by_race_name && Object.keys(standards.by_race_name).length > 0 && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-lg">重賞レース別 勝ち馬IDM基準</CardTitle>
            <p className="text-sm text-muted-foreground">
              同一レース名の過去3-4年の勝ち馬IDM平均（IDM比較チャートの基準線に使用）
            </p>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-slate-50 dark:bg-slate-900">
                    <th className="text-left py-2.5 px-3">レース名</th>
                    <th className="text-center py-2.5 px-2">G</th>
                    <th className="text-right py-2.5 px-2">回数</th>
                    <th className="text-right py-2.5 px-3 text-amber-700 dark:text-amber-400 font-bold">勝馬平均</th>
                    <th className="text-right py-2.5 px-2">min</th>
                    <th className="text-right py-2.5 px-2">max</th>
                    <th className="text-left py-2.5 px-3">年別勝馬IDM</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(standards.by_race_name)
                    .filter(([, d]) => d.winner_mean != null)
                    .sort((a, b) => (b[1].winner_mean ?? 0) - (a[1].winner_mean ?? 0))
                    .map(([name, d]) => (
                      <tr key={name} className="border-b hover:bg-slate-50 dark:hover:bg-slate-900/50">
                        <td className="py-2 px-3 font-medium text-xs">{name}</td>
                        <td className="text-center py-2 px-2">
                          <span className={`px-1.5 py-0.5 rounded border text-[10px] font-bold ${getGradeColor(d.grade)}`}>
                            {d.grade}
                          </span>
                        </td>
                        <td className="text-right py-2 px-2 text-muted-foreground">{d.count}</td>
                        <td className="text-right py-2 px-3 font-mono font-bold text-amber-700 dark:text-amber-400">
                          {d.winner_mean?.toFixed(1)}
                        </td>
                        <td className="text-right py-2 px-2 font-mono text-xs text-muted-foreground">
                          {d.winner_min}
                        </td>
                        <td className="text-right py-2 px-2 font-mono text-xs text-muted-foreground">
                          {d.winner_max}
                        </td>
                        <td className="py-2 px-3 text-xs">
                          {d.yearly_winners?.map((yw, i) => (
                            <span key={i} className="inline-block mr-2">
                              <span className="text-muted-foreground">{yw.year.slice(2)}:</span>
                              <span className="font-mono font-bold ml-0.5">{yw.winner_idm}</span>
                            </span>
                          ))}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 活用方法 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">活用方法</CardTitle>
        </CardHeader>
        <CardContent className="text-sm space-y-3 text-muted-foreground">
          <div>
            <strong className="text-foreground">1. 勝ち馬基準IDM</strong>
            <p>
              IDM比較チャートの橙色ラインに表示。このラインを超えていれば、
              同クラスの過去勝ち馬と同等以上の能力を持つ可能性がある。
            </p>
          </div>
          <div>
            <strong className="text-foreground">2. 全馬平均との差</strong>
            <p>
              勝ち馬平均と全馬平均の差（+10〜+18pt）が大きいクラスほど、
              IDMの高い馬が実際に勝ちやすい（能力差が結果に反映されやすい）。
            </p>
          </div>
          <div>
            <strong className="text-foreground">3. クラス間比較</strong>
            <p>
              例: 1勝クラスの勝ち馬平均IDM ≈ 52 vs OP古馬の全馬平均IDM ≈ 49。
              下位クラスで高IDMを出した馬は昇級後も通用する可能性が高い。
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
