'use client';

/**
 * AIコメント印(ABC)成績 (/analysis/comment-marks)
 *
 * AIコメント印 = markSet4 = comment_llm 人気薄ピックアップ(Ａ高/Ｂ中/Ｃ低)。
 * - 純粋集計: グレード別(Ａ/Ｂ/Ｃ)の勝率・複勝率・単勝回収率、月別walk-forward
 * - ML組み合わせ: グレード × モデル勝率順位(rank_w<=3) / 単勝EV(win_ev>=1) クロス
 *
 * 表示専用。予想ロジック・買い目には一切触れない。
 * データ: /api/analysis/comment-marks → analysis/comment_mark_performance.json
 */

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { ArrowLeft, RefreshCw, Tag, Info, AlertTriangle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

interface Stat {
  n: number;
  wins: number;
  places: number;
  win_rate: number | null;
  place_rate: number | null;
  roi: number | null;
  roi_ex_tail: number | null;
  tail_cut: number;
  place_roi: number | null;
  place_n_priced: number;
}
interface OverallRow extends Stat {
  grade: string;
  label: string;
}
interface MonthlyRow extends Stat {
  month: string;
}
interface CrossCell {
  grade: string;
  label: string;
  yes: Stat;
  no: Stat;
}
interface Cross {
  name: string;
  cells: CrossCell[];
}
interface Payload {
  meta: {
    date_from: string;
    date_to: string;
    n_days: number;
    n_picks: number;
    n_finished: number;
    avg_pop: number | null;
    generated_at: string;
    note?: string;
  };
  overall: OverallRow[];
  monthly_by_grade: Record<string, MonthlyRow[]>;
  cross: Cross[];
}

// ROI: 100%超で緑、90-100黄、それ未満赤（回収率は控除ぶん100が基準）
function roiColor(v: number | null): string {
  if (v == null) return 'text-muted-foreground';
  if (v >= 120) return 'text-green-700 dark:text-green-400 font-bold';
  if (v >= 100) return 'text-emerald-600 dark:text-emerald-400 font-semibold';
  if (v >= 85) return 'text-amber-600 dark:text-amber-400';
  return 'text-red-600 dark:text-red-400';
}

// グレードのバッジ色
function gradeBadge(g: string): string {
  if (g === 'Ａ') return 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300';
  if (g === 'Ｂ') return 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300';
  if (g === 'Ｃ') return 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400';
  return 'bg-primary/10 text-primary';
}

const fmtPct = (v: number | null) => (v == null ? '—' : `${v.toFixed(1)}%`);
const fmtRoi = (v: number | null) => (v == null ? '—' : `${v.toFixed(0)}%`);

export default function CommentMarksPage() {
  const [data, setData] = useState<Payload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/analysis/comment-marks');
      const result = await res.json();
      if (!res.ok) {
        setError(result.message || 'データ取得に失敗しました');
        setData(null);
        return;
      }
      setData(result);
    } catch {
      setError('データ取得に失敗しました');
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const months = data ? data.monthly_by_grade['計']?.map((m) => m.month) ?? [] : [];

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
      {/* パンくず */}
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Link href="/" className="hover:underline flex items-center gap-1">
          <ArrowLeft className="h-4 w-4" />
          トップ
        </Link>
        <span>/</span>
        <span className="text-foreground">AIコメント印(ABC)成績</span>
      </div>

      {/* タイトル */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Tag className="h-6 w-6 text-primary" />
            AIコメント印(ABC)成績
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            AIコメント印（
            <span className="font-medium">markSet4 = comment_llm 人気薄ピックアップ</span>
            ・Ａ高/Ｂ中/Ｃ低）の的中率・回収率と、ML予測との組み合わせ集計（表示専用）
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchData} className="gap-1.5 shrink-0">
          <RefreshCw className="h-4 w-4" />
          更新
        </Button>
      </div>

      {/* 説明＋免責 */}
      <Card className="bg-muted/40">
        <CardContent className="p-4 space-y-2 text-sm">
          <div className="flex gap-2">
            <Info className="h-4 w-4 mt-0.5 shrink-0 text-primary" />
            <p>
              <span className="font-semibold">複勝率</span> が信頼できる主指標（リーク検証済みで
              市場超過 +4.7pt・z=5.58）。<span className="font-semibold">単勝回収率</span> =
              確定オッズ×100円均等賭けの試算で、
              <span className="font-semibold text-amber-700 dark:text-amber-400">
                高配当の尻尾依存＝高分散・参考値
              </span>
              （上位5本を除くと全体75%＝損益分岐割れ）。
              <span className="font-semibold">ML組み合わせ</span> は各印を
              rank_w・win_evで絞ると成績が改善するかを見る（現状は改善せず＝印そのものが主エッジ）。
            </p>
          </div>
          <div className="flex gap-2 text-xs text-muted-foreground">
            <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0 text-amber-500" />
            <p>
              <span className="font-semibold">免責</span>:
              picksは <span className="font-medium">lookaheadリーク監査・修正済み</span>
              （<code className="text-[11px]">comment_llm/docs/06_LEAK_AUDIT.md</code>・過去走結合の
              時点フィルタ欠落を修正、本集計は修正後コードで再生成したクリーン版）。
              ただし全て in-sample（2026上期）で、<span className="font-medium">単勝ROIは尻尾依存＝再現性なし</span>。
              信頼できるのは複勝の的中率edge（控えめ・複勝ROI下限は88%で黒字未達）。
              グレードＡはn≈200と小さく月次変動大。最終確証は out-of-sample（前向き）待ち。
            </p>
          </div>
        </CardContent>
      </Card>

      {loading ? (
        <div className="flex items-center justify-center py-16 gap-3">
          <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
          <span className="text-muted-foreground">読み込み中...</span>
        </div>
      ) : error ? (
        <Card className="bg-amber-50 dark:bg-amber-950/30 border-amber-200">
          <CardContent className="p-6 text-center">
            <p className="text-amber-800 dark:text-amber-200 font-medium mb-2">{error}</p>
          </CardContent>
        </Card>
      ) : data ? (
        <>
          {/* 集計レンジ */}
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <Badge variant="secondary">
              期間 {data.meta.date_from} 〜 {data.meta.date_to}
            </Badge>
            <Badge variant="secondary">{data.meta.n_days}開催日</Badge>
            <Badge variant="secondary">着確定 {data.meta.n_finished}頭</Badge>
            <Badge variant="secondary">母集団平均人気 {data.meta.avg_pop ?? '—'}番</Badge>
            <span className="ml-auto">
              生成 {data.meta.generated_at?.slice(0, 16).replace('T', ' ')}
            </span>
          </div>

          <Tabs defaultValue="pure">
            <TabsList>
              <TabsTrigger value="pure">純粋集計</TabsTrigger>
              <TabsTrigger value="ml">ML組み合わせ</TabsTrigger>
            </TabsList>

            {/* 純粋集計 */}
            <TabsContent value="pure" className="mt-4 space-y-4">
              {/* グレード別 通算 */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">グレード別 通算</CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b text-xs text-muted-foreground">
                          <th className="px-3 py-2 text-left">評価</th>
                          <th className="px-3 py-2 text-right">頭数</th>
                          <th className="px-3 py-2 text-right">1着</th>
                          <th className="px-3 py-2 text-right">勝率</th>
                          <th className="px-3 py-2 text-right">複勝率</th>
                          <th className="px-3 py-2 text-right">単勝回収</th>
                          <th className="px-3 py-2 text-right" title="的中の高配当上位5本を除いた単勝回収率。尻尾依存の度合いが分かる">
                            単回収<span className="text-[10px]">(尾除)</span>
                          </th>
                          <th className="px-3 py-2 text-right" title="複勝回収率(下限)。place_odds_minで3着内成立分を試算。監査と同じ保守値">
                            複勝回収<span className="text-[10px]">(下限)</span>
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.overall.map((r) => (
                          <tr
                            key={r.grade}
                            className={`border-b ${r.grade === '計' ? 'bg-muted/40 font-medium' : ''}`}
                          >
                            <td className="px-3 py-2">
                              <Badge className={gradeBadge(r.grade)}>{r.label}</Badge>
                            </td>
                            <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">
                              {r.n}
                            </td>
                            <td className="px-3 py-2 text-right tabular-nums">{r.wins}</td>
                            <td className="px-3 py-2 text-right tabular-nums">{fmtPct(r.win_rate)}</td>
                            <td className="px-3 py-2 text-right tabular-nums">{fmtPct(r.place_rate)}</td>
                            <td className={`px-3 py-2 text-right tabular-nums ${roiColor(r.roi)}`}>
                              {fmtRoi(r.roi)}
                            </td>
                            <td className={`px-3 py-2 text-right tabular-nums ${roiColor(r.roi_ex_tail)}`}>
                              {fmtRoi(r.roi_ex_tail)}
                            </td>
                            <td className={`px-3 py-2 text-right tabular-nums ${roiColor(r.place_roi)}`}>
                              {fmtRoi(r.place_roi)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="px-3 py-2 text-[11px] text-muted-foreground">
                    <span className="font-medium">単回収(尾除)</span> = 的中の高配当上位5本を除いた単勝回収率。
                    素の単勝回収から大きく落ちる＝<span className="text-amber-700 dark:text-amber-400">尻尾依存で高分散</span>。
                    <span className="font-medium ml-2">複勝回収(下限)</span> = place_odds_min ベースの保守試算（黒字化の乗り物候補）。
                  </p>
                </CardContent>
              </Card>

              {/* 月別 walk-forward */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">月別 単勝回収率（walk-forward）</CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b text-xs text-muted-foreground">
                          <th className="px-3 py-2 text-left">評価</th>
                          {months.map((m) => (
                            <th key={m} className="px-3 py-2 text-right whitespace-nowrap">
                              {m.slice(5)}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {['Ａ', 'Ｂ', 'Ｃ', '計'].map((g) => {
                          const series = data.monthly_by_grade[g] ?? [];
                          const byMonth = new Map(series.map((s) => [s.month, s]));
                          return (
                            <tr
                              key={g}
                              className={`border-b ${g === '計' ? 'bg-muted/40 font-medium' : ''}`}
                            >
                              <td className="px-3 py-2">
                                <Badge className={gradeBadge(g)}>{g}</Badge>
                              </td>
                              {months.map((m) => {
                                const s = byMonth.get(m);
                                return (
                                  <td
                                    key={m}
                                    className={`px-3 py-2 text-right tabular-nums ${roiColor(s?.roi ?? null)}`}
                                    title={s ? `n=${s.n} 勝率${fmtPct(s.win_rate)}` : ''}
                                  >
                                    {s && s.n > 0 ? fmtRoi(s.roi) : '—'}
                                    {s && s.n > 0 && (
                                      <span className="block text-[10px] text-muted-foreground/70 font-normal">
                                        n{s.n}
                                      </span>
                                    )}
                                  </td>
                                );
                              })}
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                  <p className="px-3 py-2 text-[11px] text-muted-foreground">
                    セルは単勝回収率・下段は母数n。100%超＝緑、100%割れ＝赤。ホバーで勝率。
                  </p>
                </CardContent>
              </Card>
            </TabsContent>

            {/* ML組み合わせ */}
            <TabsContent value="ml" className="mt-4 space-y-4">
              {data.cross.map((cx) => (
                <Card key={cx.name}>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">グレード × {cx.name}</CardTitle>
                  </CardHeader>
                  <CardContent className="p-0">
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b text-xs text-muted-foreground">
                            <th className="px-3 py-2 text-left" rowSpan={2}>
                              評価
                            </th>
                            <th
                              className="px-3 py-1 text-center border-l bg-emerald-50/50 dark:bg-emerald-950/20"
                              colSpan={4}
                            >
                              該当あり（条件で絞る）
                            </th>
                            <th className="px-3 py-1 text-center border-l" colSpan={4}>
                              該当なし
                            </th>
                          </tr>
                          <tr className="border-b text-xs text-muted-foreground">
                            <th className="px-2 py-1 text-right border-l">n</th>
                            <th className="px-2 py-1 text-right">勝率</th>
                            <th className="px-2 py-1 text-right">複勝</th>
                            <th className="px-2 py-1 text-right">回収</th>
                            <th className="px-2 py-1 text-right border-l">n</th>
                            <th className="px-2 py-1 text-right">勝率</th>
                            <th className="px-2 py-1 text-right">複勝</th>
                            <th className="px-2 py-1 text-right">回収</th>
                          </tr>
                        </thead>
                        <tbody>
                          {cx.cells.map((c) => (
                            <tr
                              key={c.grade}
                              className={`border-b ${c.grade === '計' ? 'bg-muted/40 font-medium' : ''}`}
                            >
                              <td className="px-3 py-2">
                                <Badge className={gradeBadge(c.grade)}>{c.label}</Badge>
                              </td>
                              <td className="px-2 py-2 text-right tabular-nums text-muted-foreground border-l bg-emerald-50/30 dark:bg-emerald-950/10">
                                {c.yes.n}
                              </td>
                              <td className="px-2 py-2 text-right tabular-nums bg-emerald-50/30 dark:bg-emerald-950/10">
                                {fmtPct(c.yes.win_rate)}
                              </td>
                              <td className="px-2 py-2 text-right tabular-nums bg-emerald-50/30 dark:bg-emerald-950/10">
                                {fmtPct(c.yes.place_rate)}
                              </td>
                              <td
                                className={`px-2 py-2 text-right tabular-nums bg-emerald-50/30 dark:bg-emerald-950/10 ${roiColor(c.yes.roi)}`}
                              >
                                {fmtRoi(c.yes.roi)}
                              </td>
                              <td className="px-2 py-2 text-right tabular-nums text-muted-foreground border-l">
                                {c.no.n}
                              </td>
                              <td className="px-2 py-2 text-right tabular-nums">
                                {fmtPct(c.no.win_rate)}
                              </td>
                              <td className="px-2 py-2 text-right tabular-nums">
                                {fmtPct(c.no.place_rate)}
                              </td>
                              <td className={`px-2 py-2 text-right tabular-nums ${roiColor(c.no.roi)}`}>
                                {fmtRoi(c.no.roi)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              ))}
              <Card className="bg-muted/40">
                <CardContent className="p-4 text-xs text-muted-foreground flex gap-2">
                  <Info className="h-3.5 w-3.5 mt-0.5 shrink-0 text-primary" />
                  <p>
                    「該当あり」の回収が「該当なし」を上回れば、その条件で絞る意味がある。
                    現状の集計では rank_w や win_ev で絞ると回収がむしろ下がる傾向（人気側に寄る・
                    longshot過大評価を拾う）＝ 印そのものが主エッジ。
                  </p>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </>
      ) : null}
    </div>
  );
}
