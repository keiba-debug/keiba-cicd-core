'use client';

/**
 * 券種選択タブ (Session 140 / bettype-selection-roadmap Phase 3)
 *
 * 軸◎から「どの券種を買うか / 降りるか」を決めた結果を表示する決定ビュー。
 * Phase2 (💵券種効率) が全プランの効率を並べる判断支援なら、 こちらは選択ロジック
 * (bettype_selection.py) が出した結論 (✅選んだ券種 / ✖降りた券種 + 判断理由)。
 *
 * ★誤誘導防止 (シズネ Session 138 置き土産・選択ロジックの核心制約):
 *   vs単 は「広げる相対妙味」であって期待値の符号ではない。 控除率があるため市場オッズでは
 *   通常ほぼ全プランで EV<1.0 (期待値マイナス) が常態。 「単より高」≠「儲かる」。
 *   fund 判断は EV 絶対水準のみで、 vs単 は参考表示。 「広げ得 ≠ 儲かる」。
 *
 * ★これは候補 (candidate) であって確定ではない: 生成時オッズに基づくスナップショット。
 *   実際の投票は締切前の最新オッズで再計算されうる (ふくだ哲学「最後の判断=最新オッズが正」)。
 *
 * データは /api/odds/bettype-selection (Python が書いた JSON artifact) を読むだけ。
 */
import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type {
  RaceSelectionResult,
  SelectedPlan,
  SkippedPlan,
} from '@/lib/data/betting-selection-reader';

interface Props {
  raceId: string;
}

const BET_TYPE_GROUP: Record<string, { label: string; color: string }> = {
  tansho: { label: '単勝', color: 'text-gray-700 dark:text-gray-300' },
  fukusho: { label: '複勝', color: 'text-gray-700 dark:text-gray-300' },
  umaren: { label: '馬連', color: 'text-blue-700 dark:text-blue-400' },
  wide: { label: 'ワイド', color: 'text-teal-700 dark:text-teal-400' },
  umatan: { label: '馬単', color: 'text-indigo-700 dark:text-indigo-400' },
  sanrenpuku: { label: '三連複', color: 'text-purple-700 dark:text-purple-400' },
  sanrentan: { label: '三連単', color: 'text-rose-700 dark:text-rose-400' },
};

const STRATEGY_LABEL: Record<string, string> = {
  concentrate: '集中（保守）',
  ev_floor: 'EV足切り',
  spread_if_worth: '妙味あれば広げる',
  hole_seeker: '穴軸（妙味軸）',
  skip_all: '全見送り',
};

const TASTE_LABEL: Record<string, string> = {
  popularity_gap_max: '人気乖離最大',
  ev_min: '合成妙味優先',
};

function fmtOdds(v: number | null): string {
  return v === null || v === undefined ? '—' : v.toFixed(1);
}
function fmtEv(v: number | null): string {
  return v === null || v === undefined ? '—' : v.toFixed(2);
}
function fmtPct(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

/** 期待リターン (EV) の色: 1.0 以上=緑(期待プラス), 0.9-1.0=黄, 未満=灰(期待マイナス) */
function evColor(ev: number | null): string {
  if (ev === null || ev === undefined) return 'text-gray-400';
  if (ev >= 1.0) return 'text-green-600 dark:text-green-400 font-bold';
  if (ev >= 0.9) return 'text-amber-600 dark:text-amber-400';
  return 'text-gray-500 dark:text-gray-400';
}

/** vs単バッジ: 期待値の符号ではなく「広げる相対妙味」のみを表す (色は中立) */
function VsTanshoBadge({
  betType,
  vsTansho,
  syntheticOdds,
}: {
  betType: string;
  vsTansho: 'lt' | 'gt' | null;
  syntheticOdds: number | null;
}) {
  if (betType === 'tansho') {
    return <Badge variant="outline" className="text-[10px]">基準</Badge>;
  }
  if (betType === 'fukusho' || vsTansho === null || syntheticOdds === null) {
    return <span className="text-gray-300">—</span>;
  }
  if (vsTansho === 'lt') {
    return (
      <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300 text-[10px] whitespace-nowrap">
        合成&lt;単
      </Badge>
    );
  }
  return (
    <Badge className="bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300 text-[10px] whitespace-nowrap">
      単より高
    </Badge>
  );
}

function freshnessLabel(generatedAt: string | null): { text: string; stale: boolean } | null {
  if (!generatedAt) return null;
  const t = Date.parse(generatedAt);
  if (Number.isNaN(t)) return null;
  const mins = Math.round((Date.now() - t) / 60000);
  const stale = mins >= 180;
  if (mins < 1) return { text: 'たった今生成', stale: false };
  if (mins < 60) return { text: `${mins}分前のオッズで選択`, stale };
  const h = Math.floor(mins / 60);
  return { text: `${h}時間${mins % 60}分前のオッズで選択`, stale };
}

function strategyLabel(strategy: string): string {
  return STRATEGY_LABEL[strategy] ?? strategy;
}

export default function BetTypeSelectionTab({ raceId }: Props) {
  const [data, setData] = useState<RaceSelectionResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<{ msg: string; hint?: string } | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    // setState は effect 本体で同期呼びせず、 内側 async に閉じる
    // (react-hooks/set-state-in-effect を踏まない & cascading render 回避)。
    const run = async () => {
      setLoading(true);
      setErr(null);
      try {
        const r = await fetch(`/api/odds/bettype-selection?raceId=${raceId}`, {
          signal: controller.signal,
        });
        const j = await r.json();
        if (controller.signal.aborted) return;
        if (!r.ok) {
          setErr({ msg: j.error ?? '取得失敗', hint: j.hint });
          setData(null);
        } else {
          setData(j as RaceSelectionResult);
        }
      } catch (e) {
        if ((e as { name?: string })?.name === 'AbortError') return;
        setErr({ msg: '取得失敗' });
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    };
    run();
    return () => controller.abort();
  }, [raceId]);

  if (loading) {
    return <div className="py-10 text-center text-gray-400">読み込み中...</div>;
  }
  if (err) {
    return (
      <div className="py-10 text-center text-gray-500 space-y-2">
        <div>券種選択データがありません（{err.msg}）</div>
        {err.hint && (
          <code className="block text-xs bg-muted/60 rounded px-3 py-2 mx-auto max-w-md">
            {err.hint}
          </code>
        )}
      </div>
    );
  }
  if (!data) {
    return <div className="py-10 text-center text-gray-400">データなし</div>;
  }

  const sel = data.selection;
  const fresh = freshnessLabel(data.generated_at);
  const axisName = (sel.axis_name || '').trim() || `馬${sel.axis_umaban}`;
  const isSkipAll = sel.strategy === 'skip_all';
  const comboSelected = sel.selected_plans.filter(
    (p) => p.bet_type !== 'tansho' && p.bet_type !== 'fukusho',
  );

  return (
    <div className="space-y-4">
      {/* ヘッダー: 軸◎ + 戦略 + 鮮度 */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex flex-wrap items-center gap-2">
            <span>🎫 券種選択</span>
            <Badge variant="outline" className="font-normal">
              軸◎ {sel.axis_umaban}番 {axisName}
            </Badge>
            <span className="text-sm text-gray-500">単 {fmtOdds(sel.axis_odds)}倍</span>
            <Badge className="bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">
              戦略: {strategyLabel(data.selection_strategy)}
            </Badge>
            <span className="text-[11px] text-gray-500">EV足切り {data.ev_floor.toFixed(2)}</span>
            {data.taste && (
              <Badge variant="outline" className="text-[10px]">
                妙味軸: {TASTE_LABEL[data.taste] ?? data.taste}
              </Badge>
            )}
            {sel.specialist && (
              <Badge className="bg-fuchsia-100 text-fuchsia-700 dark:bg-fuchsia-900/40 dark:text-fuchsia-300">
                🌪 {sel.specialist}
              </Badge>
            )}
            {fresh && (
              <span className={`text-[11px] ml-auto ${fresh.stale ? 'text-orange-500' : 'text-gray-400'}`}>
                {fresh.stale ? '⚠ ' : ''}
                {fresh.text}
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-xs">
          {/* 判断 (decision_reason) */}
          <div className="rounded-md border border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-900/40 px-3 py-2">
            <span className="font-bold text-slate-700 dark:text-slate-200">判断: </span>
            <span className="text-slate-600 dark:text-slate-300">{sel.decision_reason}</span>
          </div>

          {/* ★誤誘導防止バナー (シズネ 🔴) */}
          <div className="rounded-md border border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/20 px-3 py-2 text-[11px] text-amber-800 dark:text-amber-300">
            <strong>vs単</strong> は「広げる<strong>相対</strong>妙味」（合成オッズが単より高いか）で、
            <strong>期待値の符号ではありません</strong>。控除率があるため通常ほぼ全プランで
            <strong> 期待リターン &lt; 1.0（期待値マイナス）</strong>が常態。
            <strong>「広げ得 ≠ 儲かる」</strong>。fund 判断は<strong>期待リターン（EV絶対水準）</strong>のみで、
            vs単は参考です。
          </div>

          {/* candidate 注記 (ふくだ哲学・シズネ乖離論点) */}
          <p className="text-[11px] text-gray-500 dark:text-gray-400">
            これは<strong>候補</strong>（生成時オッズに基づくスナップショット）。実際の投票は締切前の
            <strong>最新オッズで再計算されうる</strong>（「最後の判断＝最新オッズが正」）。日次・レース上限は
            別途 config のハードキャップ（per_race / per_day）で守られます。
          </p>
        </CardContent>
      </Card>

      {/* ✅ 買う券種 (selected_plans) */}
      <Card>
        <CardContent className="pt-4">
          <div className="mb-2 flex items-center gap-2">
            <span className="text-sm font-bold text-green-700 dark:text-green-400">
              ✅ 買う券種（{sel.selected_plans.length} 件）
            </span>
            {!isSkipAll && comboSelected.length === 0 && (
              <span className="text-[11px] text-gray-500">複合券種なし → 軸◎に集中</span>
            )}
          </div>

          {sel.selected_plans.length === 0 ? (
            <div className="py-6 text-center text-gray-500 text-sm">
              {isSkipAll ? '全見送り（fund 対象なし）' : 'fund 対象なし'}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-gray-500 text-xs">
                    <th className="px-2 py-1.5 text-left">券種</th>
                    <th className="px-2 py-1.5 text-left">買い目</th>
                    <th className="px-2 py-1.5 text-right">点</th>
                    <th className="px-2 py-1.5 text-right">的中率</th>
                    <th className="px-2 py-1.5 text-right">合成オッズ</th>
                    <th className="px-2 py-1.5 text-right">期待リターン</th>
                    <th className="px-2 py-1.5 text-center">vs 単</th>
                  </tr>
                </thead>
                <tbody>
                  {sel.selected_plans.map((p: SelectedPlan, i) => {
                    const grp = BET_TYPE_GROUP[p.bet_type];
                    return (
                      <tr key={i} className="border-b border-gray-100 dark:border-gray-800 align-top">
                        <td className={`px-2 py-1.5 whitespace-nowrap ${grp?.color ?? ''}`}>
                          {grp?.label ?? p.bet_type}
                        </td>
                        <td className="px-2 py-1.5">
                          <div>{p.label}</div>
                          <div className="text-[10px] text-gray-500 dark:text-gray-400 mt-0.5">
                            {p.select_reason}
                          </div>
                        </td>
                        <td className="px-2 py-1.5 text-right tabular-nums text-gray-500">
                          {p.legs.length}
                        </td>
                        <td className="px-2 py-1.5 text-right tabular-nums">{fmtPct(p.hit_prob)}</td>
                        <td className="px-2 py-1.5 text-right tabular-nums font-medium">
                          {fmtOdds(p.synthetic_odds)}
                        </td>
                        <td className={`px-2 py-1.5 text-right tabular-nums ${evColor(p.expected_return)}`}>
                          {fmtEv(p.expected_return)}
                        </td>
                        <td className="px-2 py-1.5 text-center">
                          <VsTanshoBadge
                            betType={p.bet_type}
                            vsTansho={p.vs_tansho}
                            syntheticOdds={p.synthetic_odds}
                          />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ✖ 降りた券種 (skipped_plans) */}
      {sel.skipped_plans.length > 0 && (
        <Card>
          <CardContent className="pt-4">
            <div className="mb-2 text-sm font-bold text-gray-500 dark:text-gray-400">
              ✖ 降りた券種（{sel.skipped_plans.length} 件）
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-gray-500 text-xs">
                    <th className="px-2 py-1.5 text-left">券種</th>
                    <th className="px-2 py-1.5 text-left">買い目</th>
                    <th className="px-2 py-1.5 text-right">期待リターン</th>
                    <th className="px-2 py-1.5 text-center">vs 単</th>
                    <th className="px-2 py-1.5 text-left">理由</th>
                  </tr>
                </thead>
                <tbody>
                  {sel.skipped_plans.map((p: SkippedPlan, i) => {
                    const grp = BET_TYPE_GROUP[p.bet_type];
                    return (
                      <tr
                        key={i}
                        className="border-b border-gray-100 dark:border-gray-800 opacity-70 align-top"
                      >
                        <td className={`px-2 py-1.5 whitespace-nowrap ${grp?.color ?? ''}`}>
                          {grp?.label ?? p.bet_type}
                        </td>
                        <td className="px-2 py-1.5">{p.label}</td>
                        <td className={`px-2 py-1.5 text-right tabular-nums ${evColor(p.expected_return)}`}>
                          {fmtEv(p.expected_return)}
                        </td>
                        <td className="px-2 py-1.5 text-center">
                          <VsTanshoBadge
                            betType={p.bet_type}
                            vsTansho={p.vs_tansho}
                            syntheticOdds={null}
                          />
                        </td>
                        <td className="px-2 py-1.5 text-[11px] text-gray-500 dark:text-gray-400">
                          {p.skip_reason}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 注記 + warnings (常時表示) */}
      <div className="space-y-1 text-[11px] text-gray-500 dark:text-gray-400 px-1">
        <p>
          戦略 <strong>{strategyLabel(data.selection_strategy)}</strong> での選択結果。
          別戦略で見たい場合は CLI で再生成（
          <code className="text-[10px]">
            --strategy concentrate | ev_floor | spread_if_worth | hole_seeker
          </code>
          ）。
        </p>
        {sel.warnings.map((w, i) => (
          <p key={i} className="text-orange-500">⚠ {w}</p>
        ))}
      </div>
    </div>
  );
}
