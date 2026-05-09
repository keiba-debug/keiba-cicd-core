/**
 * /analysis/specialists/niigata-1000m
 *
 * vega-niigata1000 (千直スペシャリストモデル) の解説 + Phase 1+2 検証データ。
 * 2タブ構成: コース事典 / Phase 1+2 データ。
 *
 * URL クエリ ?tab=data でデータタブ初期表示。
 */

import Link from 'next/link';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import {
  loadNiigataPhase12Bundle,
  type Phase3Metrics,
} from '@/lib/data/niigata1000-stats';

export const dynamic = 'force-dynamic';

interface PageParams {
  searchParams: Promise<{ tab?: string }>;
}

// =====================================================
// 共通フォーマッタ
// =====================================================

function pct(v: number, digits = 1): string {
  return `${(v * 100).toFixed(digits)}%`;
}

function roi(v: number): string {
  return `${(v * 100).toFixed(0)}%`;
}

// =====================================================
// コース事典タブ用データ (Phase 1+2 ハイライト)
// =====================================================

const FRAME_STATS = [
  { frame: 1, top3Rate: 5.2, winRoi: 30, n: 135 },
  { frame: 2, top3Rate: 9.6, winRoi: 41, n: 135 },
  { frame: 3, top3Rate: 11.8, winRoi: 52, n: 135 },
  { frame: 4, top3Rate: 13.4, winRoi: 58, n: 135 },
  { frame: 5, top3Rate: 16.0, winRoi: 71, n: 135 },
  { frame: 6, top3Rate: 22.4, winRoi: 95, n: 135 },
  { frame: 7, top3Rate: 28.5, winRoi: 79, n: 135 },
  { frame: 8, top3Rate: 36.6, winRoi: 142, n: 135 },
];

const TRACK_FRAME_STATS = [
  { cond: '良',     frame: '7-8枠', top3Rate: 32.4, n: 84 },
  { cond: '稍重以上', frame: '7-8枠', top3Rate: 48.8, n: 51 },
  { cond: '良',     frame: '1-3枠', top3Rate: 8.6,  n: 84 },
  { cond: '稍重以上', frame: '1-3枠', top3Rate: 5.2,  n: 51 },
];

const STRONG_TRAINERS = [
  { name: '斎藤誠',    rate: 35.3, n: 17 },
  { name: '嘉藤貴行',  rate: 29.4, n: 17 },
  { name: '菊沢隆徳',  rate: 29.2, n: 24 },
];

const STRONG_JOCKEYS = [
  { name: '鮫島克駿', rate: 35.0, n: 20 },
  { name: '荻野極',   rate: 29.0, n: 31 },
  { name: '丹内祐次', rate: 28.3, n: 60 },
];

const STRONG_SIRES: { name: string; rate: number; n: number; roi?: number }[] = [
  { name: 'ビッグアーサー',     rate: 25.0, n: 32, roi: 132 },
  { name: 'ダイワメジャー',     rate: 23.5, n: 17, roi: 95 },
  { name: 'スクリーンヒーロー', rate: 22.2, n: 18, roi: 110 },
  { name: 'ロードカナロア',     rate: 27.6, n: 47, roi: 179 },
];

const STRONG_PROFILE = [
  { metric: '過去5走 前半通過順位', strong: '4.60', overall: '5.95', insight: '先行型' },
  { metric: '年齢',                  strong: '3.82', overall: '4.12', insight: '若駒' },
  { metric: '通算出走数',            strong: '11.91', overall: '13.29', insight: '経験浅め' },
];

const VALUE_BETS = [
  { label: '前走4-5着馬',                detail: '巻き返し穴',   roi: 99.5 },
  { label: '中5-8週ローテ',              detail: '休み明けでもなく詰め込みでもない', roi: 78 },
  { label: '永島まなみ騎乗',             detail: '若手×千直適性',                  roi: 376 },
  { label: '菊沢隆徳厩舎',               detail: 'コンビ補正の代表',                roi: 289 },
  { label: '過去千直3着内率<33%の経験馬', detail: '"見限られた"穴',                  roi: 158 },
  { label: 'キンカメ系×牝馬',            detail: '血統相性',                        roi: 176 },
];

const REJECT_RULES = [
  '千直3戦以上で全敗（top3=0）',
  '8歳以上 × 前走6着以下',
  'サンデー系牡馬古馬で短距離未経験',
];

function frameColor(frame: number): string {
  if (frame >= 7) return '#3b82f6';
  if (frame >= 6) return '#22d3ee';
  if (frame >= 4) return '#9ca3af';
  return '#f97316';
}

function rateColor(rate: number, max = 50): string {
  const t = Math.min(1, rate / max);
  if (t > 0.6) return '#3b82f6';
  if (t > 0.3) return '#22d3ee';
  return '#cbd5e1';
}

// =====================================================
// コース事典タブ
// =====================================================

function EncyclopediaContent() {
  return (
    <div className="space-y-8">
      {/* 1. 枠順 */}
      <section className="rounded-2xl border bg-white p-5">
        <h2 className="text-lg font-bold mb-1">① 枠順バイアス（最重要）</h2>
        <p className="text-xs text-gray-500 mb-4">
          ホッケースティック型: 1枠5.2% から 8枠36.6%まで7倍差。外枠ほど「外ラチ沿い」を最短距離で走り抜ける構造。
        </p>
        <div className="space-y-1.5">
          {FRAME_STATS.map((f) => {
            const w = (f.top3Rate / 40) * 100;
            return (
              <div key={f.frame} className="flex items-center gap-3">
                <span className="w-12 text-xs font-bold text-right">{f.frame}枠</span>
                <div className="flex-1 h-6 bg-gray-50 rounded relative overflow-hidden">
                  <div
                    className="h-full rounded transition-all"
                    style={{ width: `${w}%`, backgroundColor: frameColor(f.frame) }}
                  />
                  <div className="absolute inset-0 flex items-center px-2">
                    <span className="text-[11px] font-mono font-bold mix-blend-difference text-white">
                      {f.top3Rate.toFixed(1)}%
                    </span>
                    <span className="text-[10px] text-gray-500 ml-auto">単勝ROI {f.winRoi}%</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
        <p className="text-[11px] text-gray-400 mt-3">出典: Phase 1 §1 全体集計 (n=135R)</p>
      </section>

      {/* 2. 馬場 × 枠 */}
      <section className="rounded-2xl border bg-white p-5">
        <h2 className="text-lg font-bold mb-1">② 馬場悪化で更に極端化</h2>
        <p className="text-xs text-gray-500 mb-4">稍重以上では7-8枠が48.8%まで上がる一方、内枠は5%台に沈む。</p>
        <div className="grid grid-cols-2 gap-3">
          {TRACK_FRAME_STATS.map((s, i) => (
            <div key={i} className="rounded-xl border bg-gradient-to-br from-gray-50 to-white p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold">{s.cond} × {s.frame}</span>
                <span className="text-[10px] text-gray-400">n={s.n}</span>
              </div>
              <div className="flex items-end gap-2">
                <span className="text-3xl font-bold" style={{ color: rateColor(s.top3Rate) }}>
                  {s.top3Rate.toFixed(1)}%
                </span>
                <span className="text-xs text-gray-500 mb-1">3着内率</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* 3. 強馬製造元 */}
      <section className="rounded-2xl border bg-white p-5">
        <h2 className="text-lg font-bold mb-1">③ 強馬製造元（Phase 2）</h2>
        <p className="text-xs text-gray-500 mb-4">「強馬」= 千直で複数勝利または高ROIをマークした馬。</p>
        <div className="grid md:grid-cols-3 gap-4">
          {[
            { title: '厩舎', items: STRONG_TRAINERS, color: '#7c3aed' },
            { title: '騎手', items: STRONG_JOCKEYS, color: '#2563eb' },
            { title: '父',   items: STRONG_SIRES,   color: '#059669' },
          ].map((group) => (
            <div key={group.title} className="space-y-2">
              <div className="text-xs font-bold uppercase tracking-wider" style={{ color: group.color }}>
                {group.title} TOP{group.items.length}
              </div>
              {group.items.map((item, i) => {
                const itemRoi = (item as { roi?: number }).roi;
                return (
                  <div key={i} className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2">
                    <div>
                      <div className="text-sm font-bold">{item.name}</div>
                      <div className="text-[10px] text-gray-400">n={item.n}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-bold" style={{ color: group.color }}>{item.rate.toFixed(1)}%</div>
                      {itemRoi !== undefined && (
                        <div className="text-[10px] text-gray-500">ROI {itemRoi}%</div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </section>

      {/* 4. typical profile */}
      <section className="rounded-2xl border bg-white p-5">
        <h2 className="text-lg font-bold mb-1">④ 強馬の typical profile</h2>
        <p className="text-xs text-gray-500 mb-4">「若くて、先行型で、経験浅い馬」が強馬になりやすい。</p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-xs text-gray-500">
                <th className="text-left py-2 px-3">指標</th>
                <th className="text-right py-2 px-3">強馬平均</th>
                <th className="text-right py-2 px-3">全体平均</th>
                <th className="text-left py-2 px-3">解釈</th>
              </tr>
            </thead>
            <tbody>
              {STRONG_PROFILE.map((p, i) => (
                <tr key={i} className="border-b last:border-b-0">
                  <td className="py-2 px-3 text-gray-700">{p.metric}</td>
                  <td className="py-2 px-3 text-right font-mono font-bold text-blue-700">{p.strong}</td>
                  <td className="py-2 px-3 text-right font-mono text-gray-500">{p.overall}</td>
                  <td className="py-2 px-3 text-xs text-gray-600">{p.insight}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* 5. アタリ穴 */}
      <section className="rounded-2xl border bg-white p-5">
        <h2 className="text-lg font-bold mb-1">⑤ アタリ穴（ROI高条件）</h2>
        <p className="text-xs text-gray-500 mb-4">見落とされがちだが、サンプル裏付けのある穴パターン。</p>
        <div className="grid md:grid-cols-2 gap-2">
          {VALUE_BETS.map((v, i) => (
            <div key={i} className="flex items-center justify-between rounded-lg border bg-amber-50 px-3 py-2.5">
              <div>
                <div className="text-sm font-bold text-amber-900">{v.label}</div>
                <div className="text-[11px] text-amber-700">{v.detail}</div>
              </div>
              <div className="text-right">
                <div className="text-sm font-bold text-amber-900">ROI {v.roi}%</div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* 6. ルールエンジン全体像 */}
      <section className="rounded-2xl border-2 border-indigo-200 bg-indigo-50/40 p-5">
        <h2 className="text-lg font-bold mb-1">⑥ vega-niigata1000 ルールエンジン v0.2</h2>
        <p className="text-xs text-gray-600 mb-4">
          polaris予測値に <b>logit空間で加算</b> する補正レイヤー。各レースの千直エントリーに自動適用される。
        </p>
        <div className="grid md:grid-cols-2 gap-3">
          {[
            { step: 'A', title: '環境補正', desc: '馬場/年代/フルゲート/レース種別 — 後続STEPの分岐条件' },
            { step: 'B', title: '枠順バイアス', desc: '8枠 +0.50 / 7枠後期 +0.50 / 1-2枠は B\' 救済へ' },
            { step: 'C-1', title: '血統', desc: 'ロードカナロア +0.30, ビッグアーサー +0.25, ...' },
            { step: 'C-2', title: '過去走脚質', desc: '前半通過≤4.0 / 上がり3F≤33.5 で先行+末脚ボーナス' },
            { step: 'C-3', title: '属性', desc: '3歳牝馬 +0.10 / 7歳以上 -0.10' },
            { step: 'D', title: '関係者', desc: '菊沢×菊沢 +0.40 / 強騎手・強厩舎の閾値ボーナス' },
            { step: 'E', title: 'ローテ', desc: '前走短距離 +0.10 / 前走4-5着 +0.20 / 中5-8週 +0.10' },
            { step: 'F', title: '警戒/除外', desc: '3条件のいずれか該当で is_rejected = true' },
          ].map((s, i) => (
            <div key={i} className="rounded-xl border bg-white p-3">
              <div className="flex items-baseline gap-2">
                <span className="text-xs font-bold px-1.5 py-0.5 rounded bg-indigo-600 text-white">{s.step}</span>
                <span className="text-sm font-bold">{s.title}</span>
              </div>
              <p className="text-xs text-gray-600 mt-1">{s.desc}</p>
            </div>
          ))}
        </div>
        <div className="mt-4 rounded-lg bg-white border border-indigo-200 px-4 py-3">
          <div className="text-xs font-bold text-indigo-900 mb-1">⚠️ 除外条件 (STEP F)</div>
          <ul className="text-xs text-gray-700 space-y-0.5">
            {REJECT_RULES.map((r, i) => (<li key={i}>・{r}</li>))}
          </ul>
        </div>
      </section>

      {/* 7. 留意点 */}
      <section className="rounded-2xl border bg-yellow-50/60 p-5">
        <h2 className="text-sm font-bold text-yellow-900 mb-2">⚠️ 留意点</h2>
        <ul className="text-xs text-yellow-900 space-y-1.5 list-disc list-inside">
          <li>サンプル規模 135R は小さい。年代非定常性（2023年以降に枠順×脚質の傾向変化）あり。</li>
          <li>「先行有利」は誤解。結果脚質「テン速 × 末脚遅」は3着内3.4%で壊滅。<b>上がり3F最速</b>が王道（Q1: 3着内41%, ROI 160%）。</li>
          <li>OOS 2024-2025 (46R) で v0.2 ルール: 上位1点 勝率 37.0% / 単勝ROI 140.2%。Bayesian shrinkage v0.4 でも超えられず手動 v0.2 が production 採用。</li>
        </ul>
      </section>
    </div>
  );
}

// =====================================================
// Phase 1+2 データタブ
// =====================================================

function Phase3Summary({ metrics }: { metrics: Phase3Metrics | null }) {
  if (!metrics) {
    return (
      <div className="rounded-2xl border bg-white p-5 text-sm text-gray-500">
        Phase 3 バックテスト結果が見つかりません。
      </div>
    );
  }
  const po = metrics.polaris_only;
  const pr = metrics.polaris_rule;
  const ra = metrics.rejected_analysis;

  const cards = [
    { label: 'top1 勝率', polaris: pct(po.top1_win_rate), rule: pct(pr.top1_win_rate), delta: pr.top1_win_rate - po.top1_win_rate, better: pr.top1_win_rate > po.top1_win_rate },
    { label: 'top1 単勝ROI', polaris: roi(po.top1_roi), rule: roi(pr.top1_roi), delta: pr.top1_roi - po.top1_roi, better: pr.top1_roi > po.top1_roi },
    { label: 'top3 ヒット率', polaris: pct(po.top3_hit_rate), rule: pct(pr.top3_hit_rate), delta: pr.top3_hit_rate - po.top3_hit_rate, better: pr.top3_hit_rate > po.top3_hit_rate },
    { label: 'top3 単勝ROI (3頭買い)', polaris: roi(po.top3_roi), rule: roi(pr.top3_roi), delta: pr.top3_roi - po.top3_roi, better: pr.top3_roi > po.top3_roi },
  ];

  return (
    <section className="rounded-2xl border-2 border-emerald-200 bg-gradient-to-br from-emerald-50/60 to-white p-5">
      <h2 className="text-lg font-bold mb-1">Phase 3 バックテスト: polaris単独 vs polaris+rule</h2>
      <p className="text-xs text-gray-500 mb-4">
        135R, 2020-2025 (in-sample)。Top1 推奨で勝率 +{((pr.top1_win_rate - po.top1_win_rate) * 100).toFixed(1)}pt の改善。
      </p>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {cards.map((c) => (
          <div key={c.label} className="rounded-xl bg-white border p-3.5">
            <div className="text-[10px] text-gray-500 uppercase tracking-wider">{c.label}</div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-bold" style={{ color: c.better ? '#059669' : '#dc2626' }}>
                {c.rule}
              </span>
              <span className="text-xs text-gray-400 font-mono">vs {c.polaris}</span>
            </div>
            <div className={`text-[11px] font-bold mt-1 ${c.better ? 'text-emerald-700' : 'text-red-600'}`}>
              {c.delta >= 0 ? '+' : ''}{(c.delta * 100).toFixed(1)}pt
            </div>
          </div>
        ))}
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3">
        <div className="rounded-xl bg-white border p-3.5">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider">STEP F 除外推奨馬の3着内率</div>
          <div className="mt-2 text-2xl font-bold text-amber-700">{pct(ra.rejected_top3_rate)}</div>
          <div className="text-[11px] text-gray-500">n={ra.n_rejected} 頭</div>
        </div>
        <div className="rounded-xl bg-white border p-3.5">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider">非除外馬の3着内率</div>
          <div className="mt-2 text-2xl font-bold text-blue-700">{pct(ra.non_rejected_top3_rate)}</div>
          <div className="text-[11px] text-gray-500">n={ra.n_non_rejected} 頭 → 除外機能有効 (-7.7pt)</div>
        </div>
      </div>
    </section>
  );
}

function DataDashboardContent({ data }: { data: ReturnType<typeof loadNiigataPhase12Bundle> }) {
  const frameMaxTop3 = Math.max(...data.frameOverall.map((r) => r.top3Rate), 0.01);
  const frameMaxRoi = Math.max(...data.frameOverall.map((r) => r.winRoi), 0.01);

  const sireSorted = [...data.sireRanking].sort((a, b) => b.top3Rate - a.top3Rate).slice(0, 12);
  const jockeyTop = [...data.jockeyTop3].sort((a, b) => b.top3Rate - a.top3Rate).slice(0, 10);
  const trainerTop = [...data.trainerTop3].sort((a, b) => b.top3Rate - a.top3Rate).slice(0, 10);

  return (
    <div className="space-y-8">
      <Phase3Summary metrics={data.phase3Metrics} />

      {/* 枠順 */}
      <section className="rounded-2xl border bg-white p-5">
        <h2 className="text-lg font-bold mb-1">① 枠順別 集計</h2>
        <p className="text-xs text-gray-500 mb-1">ホッケースティック型: 1枠→8枠で 3着内率が7倍差。</p>
        <p className="text-[10px] text-gray-400 mb-4">出典: 01_frame_overall.csv (n=2230 走 / 135R)</p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-xs text-gray-500">
                <th className="text-center py-2 px-2 w-12">枠</th>
                <th className="text-right py-2 px-2">n</th>
                <th className="text-right py-2 px-2">勝</th>
                <th className="text-right py-2 px-2">3着内</th>
                <th className="text-right py-2 px-2 w-20">勝率</th>
                <th className="text-right py-2 px-2 w-24">3着内率</th>
                <th className="py-2 px-2 w-1/3">3着内率 (95% CI)</th>
                <th className="text-right py-2 px-2 w-20">単勝ROI</th>
                <th className="py-2 px-2 w-1/4">ROIバー</th>
              </tr>
            </thead>
            <tbody>
              {data.frameOverall.map((r) => {
                const tw = frameMaxTop3 > 0 ? Math.min(100, (r.top3Rate / frameMaxTop3) * 100) : 0;
                const rw = frameMaxRoi > 0 ? Math.min(100, (r.winRoi / frameMaxRoi) * 100) : 0;
                return (
                  <tr key={r.wakuban} className="border-b last:border-b-0 hover:bg-gray-50">
                    <td className="text-center py-2 font-bold">{r.wakuban}</td>
                    <td className="text-right font-mono text-xs">{r.n}</td>
                    <td className="text-right font-mono text-xs">{r.wins}</td>
                    <td className="text-right font-mono text-xs">{r.top3}</td>
                    <td className="text-right font-mono text-xs">{pct(r.winRate)}</td>
                    <td className="text-right font-mono text-sm font-bold" style={{ color: r.wakuban >= 7 ? '#1d4ed8' : r.wakuban >= 6 ? '#0e7490' : '#6b7280' }}>
                      {pct(r.top3Rate)}
                    </td>
                    <td className="px-2">
                      <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div className="h-full rounded-full" style={{ width: `${tw}%`, backgroundColor: r.wakuban >= 7 ? '#3b82f6' : '#9ca3af' }} />
                      </div>
                      <div className="text-[9px] text-gray-400 mt-0.5">[{pct(r.top3RateLo, 0)} ~ {pct(r.top3RateHi, 0)}]</div>
                    </td>
                    <td className={`text-right font-mono text-sm font-bold ${r.winRoi >= 1 ? 'text-emerald-700' : 'text-gray-500'}`}>{roi(r.winRoi)}</td>
                    <td className="px-2">
                      <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div className="h-full rounded-full" style={{ width: `${rw}%`, backgroundColor: r.winRoi >= 1 ? '#10b981' : '#cbd5e1' }} />
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* 結果脚質 */}
      <section className="rounded-2xl border bg-white p-5">
        <h2 className="text-lg font-bold mb-1">② 結果脚質 集計</h2>
        <p className="text-xs text-gray-500 mb-1">「テン速&末脚速」(強馬) が圧倒的、「テン速&末脚遅」(逃げ・先行) は壊滅。</p>
        <p className="text-[10px] text-gray-400 mb-4">出典: 02_running_style_overall.csv</p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-xs text-gray-500">
                <th className="text-left py-2 px-3">脚質</th>
                <th className="text-right py-2 px-2">n</th>
                <th className="text-right py-2 px-2">勝</th>
                <th className="text-right py-2 px-2">3着内</th>
                <th className="text-right py-2 px-2">勝率</th>
                <th className="text-right py-2 px-2">3着内率</th>
                <th className="text-right py-2 px-2">単勝ROI</th>
              </tr>
            </thead>
            <tbody>
              {data.runningStyle.map((r) => (
                <tr key={r.runningStyle} className="border-b last:border-b-0">
                  <td className="py-2 px-3">{r.runningStyle}</td>
                  <td className="text-right font-mono text-xs">{r.n}</td>
                  <td className="text-right font-mono text-xs">{r.wins}</td>
                  <td className="text-right font-mono text-xs">{r.top3}</td>
                  <td className="text-right font-mono text-xs">{pct(r.winRate)}</td>
                  <td className="text-right font-mono text-sm font-bold">{pct(r.top3Rate)}</td>
                  <td className={`text-right font-mono text-sm font-bold ${r.winRoi >= 1 ? 'text-emerald-700' : 'text-gray-500'}`}>{roi(r.winRoi)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* 枠×脚質 */}
      <section className="rounded-2xl border bg-white p-5">
        <h2 className="text-lg font-bold mb-1">③ 枠 × 脚質 ヒートマップ</h2>
        <p className="text-xs text-gray-500 mb-4">6-8枠 × 強馬の組み合わせは 3着内率61% / ROI 139%。1-5枠は強馬でも 43%止まり。</p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-xs text-gray-500">
                <th className="text-left py-2 px-3 w-32">枠</th>
                <th className="text-left py-2 px-3">脚質</th>
                <th className="text-right py-2 px-2">n</th>
                <th className="text-right py-2 px-2">3着内</th>
                <th className="text-right py-2 px-2">3着内率</th>
                <th className="text-right py-2 px-2">単勝ROI</th>
              </tr>
            </thead>
            <tbody>
              {data.frameXStyle.map((r, i) => (
                <tr key={i} className="border-b last:border-b-0">
                  <td className="py-2 px-3 font-bold text-xs">{r.frameGrp}</td>
                  <td className="py-2 px-3 text-xs">{r.runningStyle}</td>
                  <td className="text-right font-mono text-xs">{r.n}</td>
                  <td className="text-right font-mono text-xs">{r.top3}</td>
                  <td className="text-right font-mono font-bold" style={{ color: r.top3Rate >= 0.4 ? '#1d4ed8' : r.top3Rate >= 0.2 ? '#0e7490' : r.top3Rate >= 0.05 ? '#6b7280' : '#dc2626' }}>
                    {pct(r.top3Rate)}
                  </td>
                  <td className={`text-right font-mono text-sm font-bold ${r.winRoi >= 1 ? 'text-emerald-700' : 'text-gray-500'}`}>{roi(r.winRoi)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* 父馬 */}
      <section className="rounded-2xl border bg-white p-5">
        <h2 className="text-lg font-bold mb-1">④ 父馬ランキング (3着内率 TOP12)</h2>
        <p className="text-xs text-gray-500 mb-4">ロードカナロアは ROI 179% で稼ぎ頭。ビッグアーサーは強馬率 25% でハマる血統。</p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-xs text-gray-500">
                <th className="text-left py-2 px-3">父</th>
                <th className="text-right py-2 px-2">n</th>
                <th className="text-right py-2 px-2">勝</th>
                <th className="text-right py-2 px-2">3着内</th>
                <th className="text-right py-2 px-2">3着内率</th>
                <th className="text-right py-2 px-2">強馬率</th>
                <th className="text-right py-2 px-2">単勝ROI</th>
              </tr>
            </thead>
            <tbody>
              {sireSorted.map((r) => (
                <tr key={r.sireName} className="border-b last:border-b-0">
                  <td className="py-2 px-3 font-bold">{r.sireName}</td>
                  <td className="text-right font-mono text-xs">{r.n}</td>
                  <td className="text-right font-mono text-xs">{r.wins}</td>
                  <td className="text-right font-mono text-xs">{r.top3}</td>
                  <td className="text-right font-mono text-sm font-bold text-blue-700">{pct(r.top3Rate)}</td>
                  <td className="text-right font-mono text-xs">{pct(r.strongRate)}</td>
                  <td className={`text-right font-mono text-sm font-bold ${r.winRoi >= 1 ? 'text-emerald-700' : 'text-gray-500'}`}>{roi(r.winRoi)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* 騎手・厩舎 */}
      {[
        { title: '⑤ 騎手ランキング (3着内率 TOP10)', subtitle: '鮫島克駿 50%、丹内祐次 35% (n=60)。永島まなみは ROI 376% (Phase 1 §7-2)。', src: '07_jockey_top3.csv (n>=15)', items: jockeyTop },
        { title: '⑥ 厩舎ランキング (3着内率 TOP10)', subtitle: '斎藤誠 35.3%、嘉藤貴行 29.4%。菊沢隆徳厩舎は Phase 1 で ROI 289%。', src: '07_trainer_top3.csv (n>=15)', items: trainerTop },
      ].map((sec) => (
        <section key={sec.title} className="rounded-2xl border bg-white p-5">
          <h2 className="text-lg font-bold mb-1">{sec.title}</h2>
          <p className="text-xs text-gray-500 mb-1">{sec.subtitle}</p>
          <p className="text-[10px] text-gray-400 mb-4">{sec.src}</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-xs text-gray-500">
                  <th className="text-left py-2 px-3">名前</th>
                  <th className="text-right py-2 px-2">n</th>
                  <th className="text-right py-2 px-2">勝</th>
                  <th className="text-right py-2 px-2">3着内</th>
                  <th className="text-right py-2 px-2">3着内率</th>
                  <th className="text-right py-2 px-2">強馬率</th>
                  <th className="text-right py-2 px-2">単勝ROI</th>
                </tr>
              </thead>
              <tbody>
                {sec.items.map((r) => (
                  <tr key={r.name} className="border-b last:border-b-0">
                    <td className="py-2 px-3 font-bold">{r.name}</td>
                    <td className="text-right font-mono text-xs">{r.n}</td>
                    <td className="text-right font-mono text-xs">{r.wins}</td>
                    <td className="text-right font-mono text-xs">{r.top3}</td>
                    <td className="text-right font-mono text-sm font-bold text-blue-700">{pct(r.top3Rate)}</td>
                    <td className="text-right font-mono text-xs">{pct(r.strongRate)}</td>
                    <td className={`text-right font-mono text-sm font-bold ${r.winRoi >= 1 ? 'text-emerald-700' : 'text-gray-500'}`}>{roi(r.winRoi)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}

      {/* Phase 2 強馬指標 */}
      <section className="rounded-2xl border bg-white p-5">
        <h2 className="text-lg font-bold mb-1">⑦ Phase 2 強馬予測指標 (Q1〜Q4 比較)</h2>
        <p className="text-xs text-gray-500 mb-4">過去走指標を四分位で区切り、Q1（最良）と Q4（最悪）の3着内率/ROI 差を計算。</p>
        <div className="grid md:grid-cols-2 gap-4">
          {[
            { title: '前半通過順位平均 (5走)', subtitle: 'Q1=最先行型 / Q4=後方型', data: data.p2CornerFirst },
            { title: '上がり3F ベスト (5走)', subtitle: 'Q1=末脚最速 / Q4=末脚最遅', data: data.p2Last3fMin },
            { title: '短距離 上がり3F 平均', subtitle: 'Q1=短距離適性高 / Q4=低', data: data.p2ShortL3f },
          ].map((g) => (
            <div key={g.title} className="rounded-xl border bg-gray-50 p-4">
              <div className="text-sm font-bold mb-1">{g.title}</div>
              <div className="text-[10px] text-gray-500 mb-3">{g.subtitle}</div>
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b text-gray-500">
                    <th className="text-left py-1.5">区分</th>
                    <th className="text-right py-1.5">n</th>
                    <th className="text-right py-1.5">3着内率</th>
                    <th className="text-right py-1.5">ROI</th>
                  </tr>
                </thead>
                <tbody>
                  {g.data.map((r) => (
                    <tr key={r.quartile} className="border-b last:border-b-0">
                      <td className="py-1.5 text-[11px]">{r.quartile}</td>
                      <td className="text-right font-mono text-[11px]">{r.n}</td>
                      <td className="text-right font-mono font-bold">{pct(r.top3Rate)}</td>
                      <td className={`text-right font-mono font-bold ${r.winRoi >= 1 ? 'text-emerald-700' : 'text-gray-500'}`}>{roi(r.winRoi)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

// =====================================================
// メインページ
// =====================================================

export default async function Page({ searchParams }: PageParams) {
  const params = await searchParams;
  const initialTab = params?.tab === 'data' ? 'data' : 'encyclopedia';
  const data = loadNiigataPhase12Bundle();

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      {/* パンくず */}
      <nav className="text-xs text-gray-500">
        <span>分析</span>
        <span className="mx-1">›</span>
        <span>スペシャリスト</span>
        <span className="mx-1">›</span>
        <span className="text-gray-700">🌪 千直 (vega-niigata1000)</span>
      </nav>

      {/* ヘロー (固定、タブ切替でも残る) */}
      <header className="rounded-2xl border-2 border-blue-200 overflow-hidden">
        <div className="px-6 py-5 bg-gradient-to-br from-blue-50 to-indigo-50">
          <div className="flex items-start justify-between flex-wrap gap-2">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-700">
                  Specialist Model
                </span>
                <span className="text-xs font-bold px-2 py-0.5 rounded bg-blue-600 text-white">千直</span>
              </div>
              <h1 className="text-2xl font-bold mt-1">新潟 芝1000m 直線</h1>
              <p className="text-sm text-gray-600 mt-1">
                JRAで唯一の直線1000m。アイビスサマーダッシュ(G3)が象徴。
                外枠＝ラチ走り抜けが王道、稍重以上で更に極端化。
              </p>
            </div>
            <div className="flex flex-wrap gap-1.5 self-end">
              <span className="text-[11px] px-2 py-0.5 rounded-full bg-white border border-blue-200 text-blue-700">外枠最強</span>
              <span className="text-[11px] px-2 py-0.5 rounded-full bg-white border border-blue-200 text-blue-700">上がり3F最速</span>
              <span className="text-[11px] px-2 py-0.5 rounded-full bg-white border border-blue-200 text-blue-700">vega-niigata1000</span>
            </div>
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-gray-100">
          {[
            { label: '直線距離',   value: '1000m',  sub: 'JRA唯一' },
            { label: '形状',       value: '完全直線', sub: 'カーブなし' },
            { label: '分析サンプル', value: '135R',  sub: '2020-2025' },
            { label: 'モデル',     value: 'vega-niigata1000', sub: 'polaris+rule v0.2' },
          ].map((s, i) => (
            <div key={i} className="bg-white px-4 py-3 text-center">
              <div className="text-[10px] text-gray-400 uppercase tracking-wider">{s.label}</div>
              <div className="text-lg font-bold mt-0.5 text-blue-700">{s.value}</div>
              <div className="text-[10px] text-gray-500">{s.sub}</div>
            </div>
          ))}
        </div>
      </header>

      {/* タブ */}
      <Tabs defaultValue={initialTab} className="w-full">
        <TabsList className="grid w-full md:inline-grid md:grid-cols-2 md:w-auto">
          <TabsTrigger value="encyclopedia">📚 コース事典 / モデル解説</TabsTrigger>
          <TabsTrigger value="data">📊 Phase 1+2 データ ({data.frameOverall.length > 0 ? '全データ' : '読込中'})</TabsTrigger>
        </TabsList>
        <TabsContent value="encyclopedia" className="mt-6">
          <EncyclopediaContent />
        </TabsContent>
        <TabsContent value="data" className="mt-6">
          <DataDashboardContent data={data} />
        </TabsContent>
      </Tabs>

      <footer className="text-center text-xs text-gray-400 pt-4 border-t">
        分析: Phase 1+2 (135R, 2020-2025) ・ 設計書: vega_niigata1000_rule_engine.md v0.2
      </footer>
    </div>
  );
}
