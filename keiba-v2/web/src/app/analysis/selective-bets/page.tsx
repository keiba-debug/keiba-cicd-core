'use client';

/**
 * Selective 候補表示ダッシュボード
 *
 * Session 122 Phase 4 で発見した「重賞のみ rank_p==1 単勝」戦略 (BT ROI 203%) の
 * 当日の候補馬を一覧表示する。 手動購入の参考用。
 *
 * データソース: data3/races/YYYY/MM/DD/selective_bets.json
 *   生成: python -m ml.strategies.selective --date YYYY-MM-DD
 */

import { useState, useEffect, useMemo } from 'react';
import useSWR from 'swr';
import Link from 'next/link';
import { ArrowLeft, Target, TrendingUp, AlertCircle, Calendar, ExternalLink } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface SelectiveBet {
  race_id: string;
  race_number: number | null;
  venue_name: string | null;
  grade: string;
  track_type: string | null;
  distance: number | null;
  num_runners: number | null;
  umaban: number;
  horse_name: string;
  odds: number;
  rank_p: number | null;
  pred_proba_p_raw: number | null;
  win_ev: number | null;
  confidence: number | null;
  odds_rank: number | null;
  vb_gap: number | null;
  source?: 'grade_top_p' | 'emerging_w_not_top2'; // v2.0
  rank_w?: number | null;                          // v2.0
}

// Sel_v3 戦略タグを判定 (重賞 v1.0 のみ)。 1勝クラス (emerging_w_not_top2) は別表示
function deriveStrategyTags(bet: SelectiveBet): { name: string; label: string; bt_roi: string; color: string }[] {
  // 1勝クラス出自は固有戦略タグ
  if (bet.source === 'emerging_w_not_top2') {
    return [
      { name: 'emerging_w', label: '1勝穴(rank_w + not_top2)', bt_roi: '+115.7%', color: 'bg-fuchsia-600' },
    ];
  }
  const tags: { name: string; label: string; bt_roi: string; color: string }[] = [
    { name: 'baseline', label: 'Selective', bt_roi: '+203%', color: 'bg-rose-600' },
  ];
  if (bet.odds_rank != null && bet.odds_rank !== 1) {
    tags.push({ name: 'not_fav1', label: 'not_fav1', bt_roi: '+247%', color: 'bg-orange-600' });
  }
  if (bet.odds_rank != null && bet.odds_rank > 2) {
    tags.push({ name: 'not_top2', label: 'not_top2', bt_roi: '+263%', color: 'bg-amber-600' });
  }
  if (bet.vb_gap != null && bet.vb_gap >= 3) {
    tags.push({ name: 'gap3', label: 'gap≥3', bt_roi: '+320%', color: 'bg-emerald-600' });
  }
  if (bet.vb_gap != null && bet.vb_gap >= 4) {
    tags.push({ name: 'gap4', label: 'gap≥4', bt_roi: '+381%', color: 'bg-emerald-700' });
  }
  return tags;
}

interface SelectiveResponse {
  strategy: string;
  version?: string;
  description?: string;
  generated_at?: string;
  date: string;
  n_bets: number;
  n_grade_top_p?: number;
  n_emerging_w_not_top2?: number;
  bets: SelectiveBet[];
  exists: boolean;
}

const fetcher = (url: string) => fetch(url).then((r) => r.json());

function todayStr(): string {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

function gradeStyle(grade: string): string {
  if (grade === 'G1') return 'bg-rose-600 text-white border-rose-600';
  if (grade === 'G2') return 'bg-amber-500 text-white border-amber-500';
  if (grade === 'G3') return 'bg-blue-600 text-white border-blue-600';
  if (grade === 'Listed') return 'bg-violet-600 text-white border-violet-600';
  if (grade === '1勝クラス') return 'bg-fuchsia-200 dark:bg-fuchsia-900 text-fuchsia-800 dark:text-fuchsia-100 border-fuchsia-300';
  return 'bg-slate-300 text-slate-800';
}

function sourceLabel(src?: string): { tag: string; tip: string } {
  if (src === 'emerging_w_not_top2') {
    return { tag: '💎', tip: '1勝クラス rank_w==1 && odds_rank>2 (BT ROI 115.7%)' };
  }
  return { tag: '🏆', tip: '重賞 rank_p==1 (BT ROI 203%)' };
}

function evStyle(ev: number | null): string {
  if (ev === null) return 'text-slate-400';
  if (ev >= 1.3) return 'text-emerald-700 dark:text-emerald-400 font-bold';
  if (ev >= 1.1) return 'text-emerald-600 dark:text-emerald-500';
  if (ev >= 0.9) return 'text-slate-700 dark:text-slate-300';
  return 'text-rose-500';
}

export default function SelectiveBetsPage() {
  const [date, setDate] = useState<string>(todayStr());

  const { data, error, isLoading } = useSWR<SelectiveResponse>(
    `/api/selective-bets?date=${date}`,
    fetcher,
  );

  const hasBets = !!data && data.n_bets > 0;

  // shift キーで前日/翌日 (簡易ナビ)
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (!(e.target instanceof HTMLElement) || ['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) return;
      const d = new Date(date + 'T00:00:00');
      if (e.key === 'ArrowLeft') {
        d.setDate(d.getDate() - 1);
        setDate(d.toISOString().slice(0, 10));
      } else if (e.key === 'ArrowRight') {
        d.setDate(d.getDate() + 1);
        setDate(d.toISOString().slice(0, 10));
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [date]);

  return (
    <div className="container mx-auto p-4 space-y-4 max-w-5xl">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <Link
            href="/analysis/polaris-segments"
            className="flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100"
          >
            <ArrowLeft className="w-4 h-4" />
            polaris 分析
          </Link>
          <h1 className="text-xl font-bold flex items-center gap-2">
            <Target className="w-5 h-5 text-rose-500" />
            Selective 候補 <span className="text-xs text-slate-400">v2.0</span>
          </h1>
          <Badge variant="outline" className="text-xs">🏆 重賞 ROI 203%</Badge>
          <Badge variant="outline" className="text-xs">💎 1勝穴 ROI 115.7%</Badge>
        </div>

        <div className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-slate-400" />
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="border rounded px-3 py-1 text-sm bg-white dark:bg-slate-800 dark:border-slate-700"
          />
          <span className="text-xs text-slate-400">←→キーで前後日</span>
        </div>
      </div>

      <Card>
        <CardContent className="py-3 text-sm text-slate-600 dark:text-slate-400 space-y-1">
          <p>
            <strong className="text-slate-800 dark:text-slate-200">🏆 重賞 (v1.0)</strong>:
            G1/G2/G3/Listed のみ <code>rank_p==1</code> 単勝買い。
            BT (2025-05〜2026-03 / 166 bets) で
            <strong className="text-emerald-700 dark:text-emerald-400"> ROI +203%</strong>。
          </p>
          <p>
            <strong className="text-slate-800 dark:text-slate-200">💎 1勝クラス (v2.0 NEW)</strong>:
            1勝クラスで <code>rank_w==1 && odds_rank&gt;2</code> (3番人気以下) 単勝買い。
            BT 同期間 (92 bets) で
            <strong className="text-emerald-700 dark:text-emerald-400"> ROI +115.7%</strong>。
          </p>
          <p className="mt-2 text-xs">
            生成: <code>python -m ml.strategies.selective --date {date}</code>
          </p>
        </CardContent>
      </Card>

      {isLoading && (
        <Card><CardContent className="py-8 text-center text-slate-400">読込中...</CardContent></Card>
      )}

      {error && (
        <Card><CardContent className="py-6 text-rose-600">エラー: {String(error)}</CardContent></Card>
      )}

      {data && !data.exists && (
        <Card>
          <CardContent className="py-8 text-center text-slate-500">
            <AlertCircle className="w-8 h-8 mx-auto mb-2 text-slate-400" />
            <p>この日の selective_bets.json はまだ生成されていません。</p>
            <p className="text-xs mt-2 font-mono">
              python -m ml.strategies.selective --date {date}
            </p>
          </CardContent>
        </Card>
      )}

      {data && data.exists && !hasBets && (
        <Card>
          <CardContent className="py-8 text-center text-slate-500">
            <p>この日は対象レースなし</p>
            <p className="text-xs mt-2 text-slate-400">
              (Selective は 重賞 + 1勝クラス が対象)
            </p>
          </CardContent>
        </Card>
      )}

      {hasBets && (
        <>
          <div className="text-sm text-slate-500">
            <strong className="text-slate-800 dark:text-slate-200">{data.n_bets}件</strong>の候補 ・
            投資合計: <strong>¥{(data.n_bets * 100).toLocaleString()}</strong> (各100円)
            {(data.n_grade_top_p != null || data.n_emerging_w_not_top2 != null) && (
              <span className="ml-2 text-xs">
                (🏆 重賞 {data.n_grade_top_p ?? 0} 件 / 💎 1勝穴 {data.n_emerging_w_not_top2 ?? 0} 件)
              </span>
            )}
            {data.generated_at && (
              <span className="text-xs ml-2 text-slate-400">
                (生成: {data.generated_at})
              </span>
            )}
          </div>

          {data.bets.map((bet) => (
            <Card key={bet.race_id} className="hover:shadow-md transition-shadow">
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center justify-between flex-wrap gap-2">
                  <span className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 rounded text-xs font-bold border ${gradeStyle(bet.grade)}`}>
                      {bet.grade}
                    </span>
                    <span className="font-mono">{bet.venue_name || '?'} {bet.race_number}R</span>
                    <span className="text-xs text-slate-500">
                      {bet.track_type === 'turf' ? '芝' : bet.track_type === 'dirt' ? 'ダ' : bet.track_type}
                      {bet.distance && ` ${bet.distance}m`}
                      {bet.num_runners && ` / ${bet.num_runners}頭`}
                    </span>
                  </span>
                  <Link
                    href={`/odds-race/${bet.race_id}`}
                    className="text-xs text-slate-500 hover:text-slate-900 dark:hover:text-slate-100 flex items-center gap-1"
                  >
                    オッズ画面 <ExternalLink className="w-3 h-3" />
                  </Link>
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
                  <div>
                    <div className="text-xs text-slate-500">買い目</div>
                    <div className="font-bold text-lg">
                      <span className="inline-block w-7 h-7 rounded-full bg-slate-200 dark:bg-slate-700 text-center mr-2 leading-7">
                        {bet.umaban}
                      </span>
                      {bet.horse_name}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-500">単勝オッズ</div>
                    <div className="font-bold text-lg tabular-nums">{bet.odds.toFixed(1)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-500">単勝EV</div>
                    <div className={`font-bold text-lg tabular-nums ${evStyle(bet.win_ev)}`}>
                      {bet.win_ev !== null ? bet.win_ev.toFixed(2) : '—'}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-500">複勝確率</div>
                    <div className="font-bold text-lg tabular-nums">
                      {bet.pred_proba_p_raw !== null ? `${(bet.pred_proba_p_raw * 100).toFixed(0)}%` : '—'}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-500">race信頼度</div>
                    <div className="font-bold text-lg tabular-nums">
                      {bet.confidence !== null ? bet.confidence.toFixed(1) : '—'}
                    </div>
                  </div>
                </div>
                <div className="mt-3 flex items-center justify-between gap-2 text-xs">
                  <div className="flex items-center gap-2 text-slate-500">
                    <TrendingUp className="w-3 h-3 text-emerald-500" />
                    100円 → 想定戻り ¥{Math.round(bet.odds * 100).toLocaleString()}
                  </div>
                  <div className="flex items-center gap-1 flex-wrap">
                    <span className="text-xs text-slate-400">戦略マッチ:</span>
                    {deriveStrategyTags(bet).map((tag) => (
                      <Badge
                        key={tag.name}
                        className={`text-[10px] ${tag.color} text-white`}
                        title={`Sel_v3 ${tag.label}: BT ROI ${tag.bt_roi}`}
                      >
                        {tag.label} ({tag.bt_roi})
                      </Badge>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}

          <p className="text-xs text-slate-400 text-center pt-4 pb-8">
            ※これは予測モデルの出力に基づく参考情報です。 実際の購入は自己責任で。
          </p>
        </>
      )}
    </div>
  );
}
