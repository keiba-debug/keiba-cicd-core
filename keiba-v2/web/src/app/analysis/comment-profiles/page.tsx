'use client';

/**
 * 発信者コメント分析 (/analysis/comment-profiles)
 *
 * 既存「調教分析」(/analysis/trainer-patterns) の定性コンパニオン。
 * - A. 情報量ランキング (_quant_{role}.json) … 全件表示・gap降順・ソート・色分け
 * - B. 発信者プロファイル ({role}_{name}.json) … 存在する発信者のみ詳細、無ければプレースホルダ
 *
 * 表示専用。予想ロジック・買い目には一切触れない。
 */

import { useState, useEffect, useMemo, useCallback } from 'react';
import Link from 'next/link';
import {
  ArrowLeft,
  RefreshCw,
  MessageSquare,
  Info,
  AlertTriangle,
  CheckCircle2,
  ChevronUp,
  ChevronDown,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

type Role = 'trainer' | 'jockey';

interface QuantRow {
  name: string;
  n_strong: number;
  n_other: number;
  strong_place: number;
  other_place: number;
  strong_resid: number;
  other_resid: number;
  gap_pt: number;
  z: number;
  strong_rate_of_all: number;
}

interface Dossier {
  name: string;
  role: string;
  quant: { n: number; n_finished: number; place_rate: number };
  profile: {
    strong_bias: number;
    baseline_tone: string;
    specificity: string;
    characteristic_phrases: string[];
    caution_phrases: { phrase: string; why: string }[];
    trust_signals: { phrase: string; why: string }[];
    info_value: string;
    persona: string;
  };
}

type SortKey = keyof Pick<
  QuantRow,
  'gap_pt' | 'z' | 'strong_place' | 'strong_resid' | 'other_resid' | 'n_strong'
>;

// gap_pt(pt) の色分け: 正で大きいほど緑、0付近グレー、負で赤
function gapColor(g: number): string {
  if (g >= 10) return 'text-green-700 dark:text-green-400 font-bold';
  if (g >= 5) return 'text-emerald-600 dark:text-emerald-400 font-semibold';
  if (g >= 2) return 'text-emerald-500 dark:text-emerald-400';
  if (g <= -5) return 'text-red-600 dark:text-red-400 font-semibold';
  if (g <= -2) return 'text-red-500 dark:text-red-400';
  return 'text-muted-foreground';
}

function residColor(r: number): string {
  if (r >= 3) return 'text-emerald-600 dark:text-emerald-400';
  if (r <= -3) return 'text-red-500 dark:text-red-400';
  return 'text-muted-foreground';
}

function infoValueBadge(v: string) {
  if (v === '高') return 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300';
  if (v === '低') return 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400';
  return 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300';
}

export default function CommentProfilesPage() {
  const [role, setRole] = useState<Role>('trainer');
  const [rows, setRows] = useState<QuantRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [sortKey, setSortKey] = useState<SortKey>('gap_pt');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  const [selected, setSelected] = useState<QuantRow | null>(null);
  const [dossier, setDossier] = useState<Dossier | null>(null);
  const [dossierState, setDossierState] = useState<'idle' | 'loading' | 'loaded' | 'missing'>('idle');

  const fetchRows = useCallback(async (r: Role) => {
    setLoading(true);
    setError(null);
    setSelected(null);
    setDossier(null);
    setDossierState('idle');
    try {
      const res = await fetch(`/api/analysis/comment-profiles?role=${r}`);
      const result = await res.json();
      if (!res.ok) {
        setError(result.message || 'データ取得に失敗しました');
        setRows([]);
        return;
      }
      setRows(Array.isArray(result.rows) ? result.rows : []);
    } catch {
      setError('データ取得に失敗しました');
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRows(role);
  }, [role, fetchRows]);

  // gap_pt 降順の固定ランク (再ソートしても順位は gap 基準で安定)
  const gapRank = useMemo(() => {
    const m = new Map<string, number>();
    [...rows]
      .sort((a, b) => b.gap_pt - a.gap_pt)
      .forEach((r, i) => m.set(r.name, i + 1));
    return m;
  }, [rows]);

  const sortedRows = useMemo(() => {
    const sign = sortDir === 'desc' ? -1 : 1;
    return [...rows].sort((a, b) => sign * (a[sortKey] - b[sortKey]));
  }, [rows, sortKey, sortDir]);

  const toggleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'));
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const selectRow = async (row: QuantRow) => {
    setSelected(row);
    setDossier(null);
    setDossierState('loading');
    try {
      const res = await fetch(
        `/api/analysis/comment-profiles/dossier?role=${role}&name=${encodeURIComponent(row.name)}`
      );
      if (!res.ok) {
        setDossierState('missing');
        return;
      }
      const data = await res.json();
      setDossier(data);
      setDossierState('loaded');
    } catch {
      setDossierState('missing');
    }
  };

  const SortHeader = ({ k, label, cls }: { k: SortKey; label: string; cls?: string }) => (
    <th
      className={`px-2 py-2 cursor-pointer select-none hover:text-foreground whitespace-nowrap ${cls ?? 'text-right'}`}
      onClick={() => toggleSort(k)}
    >
      <span className="inline-flex items-center gap-0.5">
        {label}
        {sortKey === k &&
          (sortDir === 'desc' ? (
            <ChevronDown className="h-3 w-3" />
          ) : (
            <ChevronUp className="h-3 w-3" />
          ))}
      </span>
    </th>
  );

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
      {/* パンくず */}
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Link href="/" className="hover:underline flex items-center gap-1">
          <ArrowLeft className="h-4 w-4" />
          トップ
        </Link>
        <span>/</span>
        <span className="text-foreground">発信者コメント分析</span>
      </div>

      {/* タイトル */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <MessageSquare className="h-6 w-6 text-primary" />
            発信者コメント分析
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            競馬ブックの厩舎・騎手コメントを発信者ごとに分析（
            <Link href="/analysis/trainer-patterns" className="underline hover:text-foreground">
              調教分析
            </Link>
            の定性コンパニオン・表示専用）
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => fetchRows(role)} className="gap-1.5 shrink-0">
          <RefreshCw className="h-4 w-4" />
          更新
        </Button>
      </div>

      {/* 指標説明＋免責 */}
      <Card className="bg-muted/40">
        <CardContent className="p-4 space-y-2 text-sm">
          <div className="flex gap-2">
            <Info className="h-4 w-4 mt-0.5 shrink-0 text-primary" />
            <p>
              <span className="font-semibold">gap</span> =
              強気コメント時の複勝圏率が「その人気で期待される水準」をどれだけ上回るか（pt）。
              大きいほど強気が結果に連動＝<span className="text-emerald-600 dark:text-emerald-400 font-medium">信頼できる発信者</span>、
              0付近/負は結果と無関係な<span className="text-red-500 dark:text-red-400 font-medium">“オオカミ少年”</span>。
              人気で補正済み・リーク安全。<span className="font-semibold">z</span> は gap の簡易有意性で
              |z|≥2 が統計的に確からしい両端。
            </p>
          </div>
          <div className="flex gap-2 text-xs text-muted-foreground">
            <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0 text-amber-500" />
            <p>
              <span className="font-semibold">免責</span>:
              現状サンプルは約6ヶ月・in-sample。発信者約190名の多重比較のため偶然 |z|＞2 が数名出る。
              信頼できるのは両端の極値と分布傾向で、中位の個別順位は今後の複数シーズン検証待ち。
            </p>
          </div>
        </CardContent>
      </Card>

      {/* タブ */}
      <Tabs value={role} onValueChange={(v) => setRole(v as Role)}>
        <TabsList>
          <TabsTrigger value="trainer">調教師</TabsTrigger>
          <TabsTrigger value="jockey">騎手</TabsTrigger>
        </TabsList>

        <TabsContent value={role} className="mt-4">
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
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {/* ランキング表 */}
              <div className="lg:col-span-2">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base flex items-center gap-2">
                      情報量ランキング
                      <Badge variant="secondary">{rows.length}名</Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="p-0">
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b text-xs text-muted-foreground">
                            <th className="px-2 py-2 text-right w-10">#</th>
                            <th className="px-2 py-2 text-left">発信者</th>
                            <SortHeader k="gap_pt" label="gap(pt)" />
                            <SortHeader k="z" label="z" />
                            <SortHeader k="strong_place" label="強気複勝%" />
                            <SortHeader k="strong_resid" label="強気上振(pt)" />
                            <SortHeader k="other_resid" label="他上振(pt)" />
                            <SortHeader k="n_strong" label="強気n" />
                          </tr>
                        </thead>
                        <tbody>
                          {sortedRows.map((r) => {
                            const isSel = selected?.name === r.name;
                            const strongZ = Math.abs(r.z) >= 2;
                            return (
                              <tr
                                key={r.name}
                                onClick={() => selectRow(r)}
                                className={`border-b cursor-pointer transition-colors hover:bg-muted/50 ${
                                  isSel ? 'bg-primary/10' : ''
                                }`}
                              >
                                <td className="px-2 py-1.5 text-right text-muted-foreground tabular-nums">
                                  {gapRank.get(r.name)}
                                </td>
                                <td className="px-2 py-1.5 font-medium">{r.name}</td>
                                <td className={`px-2 py-1.5 text-right tabular-nums ${gapColor(r.gap_pt)}`}>
                                  {r.gap_pt > 0 ? '+' : ''}
                                  {r.gap_pt.toFixed(1)}
                                </td>
                                <td className="px-2 py-1.5 text-right tabular-nums">
                                  {strongZ ? (
                                    <span
                                      className={`font-bold ${
                                        r.z > 0
                                          ? 'text-emerald-600 dark:text-emerald-400'
                                          : 'text-red-500 dark:text-red-400'
                                      }`}
                                    >
                                      {r.z.toFixed(2)}
                                    </span>
                                  ) : (
                                    <span className="text-muted-foreground">{r.z.toFixed(2)}</span>
                                  )}
                                </td>
                                <td className="px-2 py-1.5 text-right tabular-nums">
                                  {r.strong_place.toFixed(0)}%
                                </td>
                                <td className={`px-2 py-1.5 text-right tabular-nums ${residColor(r.strong_resid)}`}>
                                  {r.strong_resid > 0 ? '+' : ''}
                                  {r.strong_resid.toFixed(1)}
                                </td>
                                <td className={`px-2 py-1.5 text-right tabular-nums ${residColor(r.other_resid)}`}>
                                  {r.other_resid > 0 ? '+' : ''}
                                  {r.other_resid.toFixed(1)}
                                </td>
                                <td className="px-2 py-1.5 text-right tabular-nums text-muted-foreground">
                                  {r.n_strong}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* ドシエ詳細 */}
              <div className="lg:col-span-1">
                <div className="lg:sticky lg:top-4">
                  {!selected ? (
                    <Card className="border-dashed">
                      <CardContent className="p-6 text-center text-sm text-muted-foreground">
                        発信者名をクリックすると詳細プロファイルを表示します
                      </CardContent>
                    </Card>
                  ) : (
                    <DossierPanel
                      row={selected}
                      gapRank={gapRank.get(selected.name)}
                      dossier={dossier}
                      state={dossierState}
                    />
                  )}
                </div>
              </div>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function DossierPanel({
  row,
  gapRank,
  dossier,
  state,
}: {
  row: QuantRow;
  gapRank?: number;
  dossier: Dossier | null;
  state: 'idle' | 'loading' | 'loaded' | 'missing';
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center justify-between gap-2">
          <span>{row.name}</span>
          {gapRank && <Badge variant="outline">gap #{gapRank}</Badge>}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        {/* 定量サマリ (常に表示) */}
        <div className="grid grid-cols-3 gap-2 text-center">
          <div className="rounded-md bg-muted/50 p-2">
            <div className={`text-lg font-bold tabular-nums ${gapColor(row.gap_pt)}`}>
              {row.gap_pt > 0 ? '+' : ''}
              {row.gap_pt.toFixed(1)}
            </div>
            <div className="text-[10px] text-muted-foreground">gap (pt)</div>
          </div>
          <div className="rounded-md bg-muted/50 p-2">
            <div className="text-lg font-bold tabular-nums">{row.z.toFixed(2)}</div>
            <div className="text-[10px] text-muted-foreground">z</div>
          </div>
          <div className="rounded-md bg-muted/50 p-2">
            <div className="text-lg font-bold tabular-nums">{row.strong_place.toFixed(0)}%</div>
            <div className="text-[10px] text-muted-foreground">強気複勝率</div>
          </div>
        </div>
        <div className="text-xs text-muted-foreground">
          強気 {row.n_strong}件 / その他 {row.n_other}件 ・ 強気率 {row.strong_rate_of_all.toFixed(0)}%
        </div>

        {/* プロファイル (B) */}
        {state === 'loading' && (
          <div className="flex items-center gap-2 text-muted-foreground py-4">
            <RefreshCw className="h-4 w-4 animate-spin" />
            プロファイル読込中...
          </div>
        )}

        {state === 'missing' && (
          <div className="rounded-md border border-dashed p-4 text-center text-xs text-muted-foreground">
            LLMプロファイル未生成
            <div className="mt-1 text-[10px]">
              定量サマリのみ表示しています
            </div>
          </div>
        )}

        {state === 'loaded' && dossier && (
          <div className="space-y-3 border-t pt-3">
            {/* ペルソナ + 各属性 */}
            <div>
              <div className="font-semibold text-base">{dossier.profile.persona}</div>
              <div className="flex flex-wrap gap-1.5 mt-1.5">
                <Badge variant="secondary">トーン: {dossier.profile.baseline_tone}</Badge>
                <Badge variant="secondary">具体性: {dossier.profile.specificity}</Badge>
                <Badge className={infoValueBadge(dossier.profile.info_value)}>
                  情報価値: {dossier.profile.info_value}
                </Badge>
              </div>
              <div className="mt-2 flex items-center gap-1.5 text-xs">
                <span className="text-muted-foreground">強気度</span>
                <span className="font-mono">
                  {'●'.repeat(Math.max(0, Math.min(5, dossier.profile.strong_bias)))}
                  <span className="text-muted-foreground/40">
                    {'○'.repeat(Math.max(0, 5 - dossier.profile.strong_bias))}
                  </span>
                </span>
                <span className="text-muted-foreground">{dossier.profile.strong_bias}/5</span>
              </div>
            </div>

            {/* 口ぐせ */}
            {dossier.profile.characteristic_phrases?.length > 0 && (
              <div>
                <div className="text-xs font-semibold text-muted-foreground mb-1">口ぐせ</div>
                <div className="flex flex-wrap gap-1">
                  {dossier.profile.characteristic_phrases.map((p, i) => (
                    <Badge key={i} variant="outline" className="font-normal">
                      {p}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {/* 信頼シグナル */}
            {dossier.profile.trust_signals?.length > 0 && (
              <div>
                <div className="text-xs font-semibold text-emerald-700 dark:text-emerald-400 mb-1 flex items-center gap-1">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  信頼サイン
                </div>
                <ul className="space-y-1">
                  {dossier.profile.trust_signals.map((s, i) => (
                    <li key={i} className="text-xs">
                      <span className="font-medium">「{s.phrase}」</span>
                      <span className="text-muted-foreground"> — {s.why}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* 要注意フレーズ */}
            {dossier.profile.caution_phrases?.length > 0 && (
              <div>
                <div className="text-xs font-semibold text-amber-700 dark:text-amber-400 mb-1 flex items-center gap-1">
                  <AlertTriangle className="h-3.5 w-3.5" />
                  要注意フレーズ
                </div>
                <ul className="space-y-1">
                  {dossier.profile.caution_phrases.map((s, i) => (
                    <li key={i} className="text-xs">
                      <span className="font-medium">「{s.phrase}」</span>
                      <span className="text-muted-foreground"> — {s.why}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {dossier.quant && (
              <div className="text-[10px] text-muted-foreground border-t pt-2">
                全コメント {dossier.quant.n}件 / 結果確定 {dossier.quant.n_finished}件 ・ 全体複勝率{' '}
                {dossier.quant.place_rate?.toFixed(1)}%
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
