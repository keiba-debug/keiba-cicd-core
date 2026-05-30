'use client';

/**
 * 券種効率タブ (Session 138 / bettype-selection-roadmap Phase 2)
 *
 * ハーヴィル確率 × 市場オッズ で各券種プランの (的中確率, 合成オッズ, 期待リターン) を一覧化。
 * 「合成オッズ < 単オッズ = 広げる相対妙味が薄い」を可視化する判断支援ビュー。
 *
 * ★誤誘導防止 (シズネ Session 138 レビュー 🔴): vs単 は「広げる相対妙味」の比較であって
 *   期待値の絶対水準ではない。 控除率があるため市場オッズでは通常ほぼ全プランで EV<1.0
 *   (期待値マイナス) が常態。 「単より高」≠「儲かる」。 fund 判断には EV 絶対水準を使うこと。
 *
 * データは /api/odds/bettype-efficiency (Python が書いた JSON artifact) を読むだけ。
 */
import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { RaceEfficiency, EfficiencyPlan } from '@/lib/data/bettype-efficiency-reader';

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
  if (ev === null) return 'text-gray-400';
  if (ev >= 1.0) return 'text-green-600 dark:text-green-400 font-bold';
  if (ev >= 0.9) return 'text-amber-600 dark:text-amber-400';
  return 'text-gray-500 dark:text-gray-400';
}

/** vs単バッジ: 期待値の符号ではなく「広げる相対妙味」のみを表す (色は中立) */
function VsTanshoBadge({ plan }: { plan: EfficiencyPlan }) {
  if (plan.bet_type === 'tansho') {
    return <Badge variant="outline" className="text-[10px]">基準</Badge>;
  }
  if (plan.bet_type === 'fukusho' || plan.vs_tansho === null || plan.synthetic_odds === null) {
    return <span className="text-gray-300">—</span>;
  }
  if (plan.vs_tansho === 'lt') {
    // 合成 < 単: 広げると1点あたり実効オッズが単より低い (相対妙味薄)
    return (
      <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300 text-[10px] whitespace-nowrap">
        合成&lt;単
      </Badge>
    );
  }
  // 合成 > 単: 単より実効オッズは高い (が EV プラスとは限らない → 中立の青)
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
  if (mins < 60) return { text: `${mins}分前のオッズ`, stale };
  const h = Math.floor(mins / 60);
  return { text: `${h}時間${mins % 60}分前のオッズ`, stale };
}

export default function BetTypeEfficiencyTab({ raceId }: Props) {
  const [data, setData] = useState<RaceEfficiency | null>(null);
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<{ msg: string; hint?: string } | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setErr(null);
    fetch(`/api/odds/bettype-efficiency?raceId=${raceId}`, { signal: controller.signal })
      .then(async (r) => {
        const j = await r.json();
        if (controller.signal.aborted) return;
        if (!r.ok) {
          setErr({ msg: j.error ?? '取得失敗', hint: j.hint });
          setData(null);
        } else {
          setData(j.race as RaceEfficiency);
          setGeneratedAt(j.generated_at ?? null);
        }
      })
      .catch((e) => {
        if (e?.name === 'AbortError') return;
        setErr({ msg: '取得失敗' });
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [raceId]);

  if (loading) {
    return <div className="py-10 text-center text-gray-400">読み込み中...</div>;
  }
  if (err) {
    return (
      <div className="py-10 text-center text-gray-500 space-y-2">
        <div>券種効率データがありません（{err.msg}）</div>
        {err.hint && (
          <code className="block text-xs bg-muted/60 rounded px-3 py-2 mx-auto max-w-md">
            {err.hint}
          </code>
        )}
      </div>
    );
  }
  if (!data || data.strengths.length === 0) {
    return <div className="py-10 text-center text-gray-400">軸馬データが不完全です</div>;
  }

  const fresh = freshnessLabel(generatedAt);

  return (
    <div className="space-y-4">
      {/* 軸◎ + 相手 + 重み */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex flex-wrap items-center gap-2">
            <span>💵 券種効率</span>
            <Badge variant="outline" className="font-normal">
              軸◎ {data.axis_umaban}番 {data.axis_name}
            </Badge>
            <span className="text-sm text-gray-500">単 {fmtOdds(data.axis_odds)}倍</span>
            {data.specialist && (
              <Badge className="bg-fuchsia-100 text-fuchsia-700 dark:bg-fuchsia-900/40 dark:text-fuchsia-300">
                🌪 {data.specialist}
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
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-gray-600 dark:text-gray-400">
            <span>相手: {data.partners.map((p) => `${p}番`).join(' / ') || '—'}</span>
            <span>強さ重み W:P:ADR = {data.weights.join(' : ')}（等重み・未最適化）</span>
          </div>
          <p className="text-[11px] text-gray-500 dark:text-gray-400">
            軸◎ = 強さ総合（W/P/ADR）の最上位。
            <strong>オッズ妙味（人気との乖離）は考慮していない</strong>
            ため、しばしば人気馬になる。穴狙いは軸を手動指定（<code>--axis</code>）。
          </p>

          {/* 強さ判定テーブル */}
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b text-gray-500">
                  <th className="px-1.5 py-1 text-left">強さ順</th>
                  <th className="px-1.5 py-1 text-left">馬</th>
                  <th className="px-1.5 py-1 text-right">総合</th>
                  <th className="px-1.5 py-1 text-right">rW</th>
                  <th className="px-1.5 py-1 text-right">rP</th>
                  <th className="px-1.5 py-1 text-right">rADR</th>
                  <th className="px-1.5 py-1 text-right">勝率</th>
                </tr>
              </thead>
              <tbody>
                {data.strengths.slice(0, 6).map((s) => (
                  <tr
                    key={s.umaban}
                    className={
                      s.umaban === data.axis_umaban
                        ? 'bg-amber-50 dark:bg-amber-950/20 font-medium'
                        : ''
                    }
                  >
                    <td className="px-1.5 py-1">{s.rank_composite}</td>
                    <td className="px-1.5 py-1">
                      {s.umaban} {s.horse_name}
                      {s.p_source === 'specialist' && (
                        <span className="ml-1 text-fuchsia-500" title="specialist 補正の top3 確率を使用">★</span>
                      )}
                    </td>
                    <td className="px-1.5 py-1 text-right tabular-nums">
                      {s.composite >= 0 ? '+' : ''}
                      {s.composite.toFixed(2)}
                    </td>
                    <td className="px-1.5 py-1 text-right text-gray-500">{s.rank_w ?? '—'}</td>
                    <td className="px-1.5 py-1 text-right text-gray-500">{s.rank_p ?? '—'}</td>
                    <td className="px-1.5 py-1 text-right text-gray-500">{s.rank_adr ?? '—'}</td>
                    <td className="px-1.5 py-1 text-right tabular-nums">{fmtPct(s.win_prob)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* プラン効率テーブル */}
      <Card>
        <CardContent className="pt-4">
          {/* ★誤誘導防止バナー (シズネ 🔴) */}
          <div className="mb-3 rounded-md border border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/20 px-3 py-2 text-[11px] text-amber-800 dark:text-amber-300">
            <strong>vs単</strong> は「広げる<strong>相対</strong>妙味」（合成オッズが単オッズより高いか）の比較で、
            <strong>期待値の符号ではありません</strong>。控除率があるため通常ほぼ全プランで
            <strong> 期待リターン &lt; 1.0（期待値マイナス）</strong>が常態です。
            「単より高」＝儲かる、ではありません。買うかどうかは<strong>期待リターン</strong>で判断を。
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-gray-500 text-xs">
                  <th className="px-2 py-1.5 text-left">プラン</th>
                  <th className="px-2 py-1.5 text-right">点</th>
                  <th className="px-2 py-1.5 text-right">的中率</th>
                  <th className="px-2 py-1.5 text-right">合成オッズ</th>
                  <th className="px-2 py-1.5 text-right">期待リターン</th>
                  <th className="px-2 py-1.5 text-center">vs 単</th>
                </tr>
              </thead>
              <tbody>
                {data.plans.map((p, i) => {
                  const grp = BET_TYPE_GROUP[p.bet_type];
                  const noOdds = p.coverage <= 0.0 || p.synthetic_odds === null;
                  return (
                    <tr
                      key={i}
                      className={`border-b border-gray-100 dark:border-gray-800 ${
                        noOdds ? 'opacity-40' : ''
                      }`}
                    >
                      <td className={`px-2 py-1.5 ${grp?.color ?? ''}`}>
                        {p.label}
                        {p.bet_type === 'wide' && (
                          <span
                            className="ml-1 text-[10px] text-teal-500"
                            title="ワイドは複数点が同時的中しうる。合成オッズは保守的なので、判断は期待リターンで"
                          >
                            ※EV
                          </span>
                        )}
                        {!noOdds && p.coverage < 0.999 && (
                          <span className="ml-1 text-[10px] text-orange-500">
                            (cov{Math.round(p.coverage * 100)}%)
                          </span>
                        )}
                        {noOdds && (
                          <span className="ml-1 text-[10px] text-gray-400">(オッズ無)</span>
                        )}
                      </td>
                      <td className="px-2 py-1.5 text-right tabular-nums text-gray-500">
                        {p.n_points}
                      </td>
                      <td className="px-2 py-1.5 text-right tabular-nums">{fmtPct(p.hit_prob)}</td>
                      <td className="px-2 py-1.5 text-right tabular-nums font-medium">
                        {fmtOdds(p.synthetic_odds)}
                      </td>
                      <td className={`px-2 py-1.5 text-right tabular-nums ${evColor(p.expected_return)}`}>
                        {fmtEv(p.expected_return)}
                      </td>
                      <td className="px-2 py-1.5 text-center">
                        <VsTanshoBadge plan={p} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* 注記 */}
          <div className="mt-3 space-y-1 text-[11px] text-gray-500 dark:text-gray-400">
            <p>
              <strong>合成オッズ</strong> = 1/Σ(1/各点オッズ)（均等払戻基準の実効倍率）。
              <strong>期待リターン</strong> = 合成オッズ × 期待的中点数
              （<span className="text-green-600 dark:text-green-400">1.0超＝期待値プラス</span> /
              1.0未満＝マイナス）。
            </p>
            <p>
              <span className="text-amber-600 dark:text-amber-400">合成&lt;単</span>
              ＝広げると1点あたり実効オッズが単勝より低い（広げる相対妙味が薄い）。
              <span className="text-sky-600 dark:text-sky-400 ml-1">単より高</span>
              ＝単より実効オッズは高い（ただしEVプラスとは限らない）。
            </p>
            <p>
              ※ ワイドは複数点が同時的中しうるため合成オッズは保守的。実効値は
              <strong>期待リターン</strong>で判断（多重的中込みで正確）。
            </p>
            {data.warnings.map((w, i) => (
              <p key={i} className="text-orange-500">⚠ {w}</p>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
