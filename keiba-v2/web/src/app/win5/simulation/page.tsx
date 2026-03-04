'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';

// ============================================================
// Types
// ============================================================
interface PlanData {
  name: string;
  played: number;
  skipped: number;
  hits: number;
  hit_rate: number;
  avg_tickets: number;
  total_cost: number;
  total_payout: number;
  roi: number;
  final_pl: number;
  peak: number;
  max_dd: number;
  max_dd_from: string;
  max_dd_to: string;
  max_losing_streak: number;
  cum_pls: number[];
}

interface WeeklyData {
  date: string;
  cost: number;
  payout: number;
  pl: number;
  cum_pl: number;
  hit: boolean;
  a_hit: boolean;
  b_hit: boolean;
  c_hit: boolean;
  d_hit: boolean;
  b_skip: boolean;
  a_cost: number;
  b_cost: number;
  c_cost: number;
  d_cost: number;
  a_payout: number;
  b_payout: number;
  c_payout: number;
  d_payout: number;
}

interface ComboData {
  total_cost: number;
  total_payout: number;
  roi: number;
  final_pl: number;
  peak: number;
  max_dd: number;
  max_dd_from: string;
  max_dd_to: string;
  max_losing_streak: number;
  hit_count: number;
  cum_pls: number[];
  weekly: WeeklyData[];
  annual_cost: number;
  annual_payout: number;
  annual_pl: number;
  bankroll_req: number;
}

interface SimData {
  period: { start: string; end: string };
  matched_weeks: number;
  plans: Record<string, PlanData>;
  combos: Record<string, ComboData>;
}

// ============================================================
// Helpers
// ============================================================
function fmtDate(d: string) {
  // "20250302" → "2025/03/02"
  return `${d.slice(0, 4)}/${d.slice(4, 6)}/${d.slice(6, 8)}`;
}

function fmtYen(v: number) {
  return `¥${v.toLocaleString()}`;
}

function fmtPl(v: number) {
  const sign = v >= 0 ? '+' : '';
  return `${sign}${fmtYen(v)}`;
}

function roiColor(roi: number) {
  if (roi >= 150) return 'text-red-600 dark:text-red-400 font-bold';
  if (roi >= 100) return 'text-emerald-600 dark:text-emerald-400 font-semibold';
  return 'text-muted-foreground';
}

function plColor(v: number) {
  if (v > 0) return 'text-emerald-600 dark:text-emerald-400';
  if (v < 0) return 'text-red-600 dark:text-red-400';
  return '';
}

// ============================================================
// Chart Component (CSS-based bar chart)
// ============================================================
function CumPlChart({ data, label }: { data: WeeklyData[]; label: string }) {
  if (!data.length) return null;
  const pls = data.map(d => d.cum_pl);
  const maxVal = Math.max(...pls, 0);
  const minVal = Math.min(...pls, 0);
  const range = maxVal - minVal || 1;
  const zeroPos = ((maxVal) / range) * 100;

  return (
    <div className="mt-6">
      <h3 className="text-sm font-semibold mb-3">{label} 累計損益チャート</h3>
      <div className="relative border rounded-lg p-4 bg-muted/10 overflow-x-auto">
        <div className="flex items-end gap-[2px] h-40 min-w-[600px]">
          {data.map((w, i) => {
            const height = Math.abs(w.cum_pl) / range * 100;
            const isPositive = w.cum_pl >= 0;
            return (
              <div
                key={i}
                className="flex-1 relative group"
                style={{ minWidth: '4px' }}
              >
                <div
                  className="absolute left-0 right-0"
                  style={{
                    bottom: isPositive ? `${zeroPos}%` : `${zeroPos - height}%`,
                    height: `${height}%`,
                  }}
                >
                  <div
                    className={`w-full h-full rounded-sm ${
                      w.hit
                        ? 'bg-yellow-400 dark:bg-yellow-500'
                        : isPositive
                        ? 'bg-emerald-400/80 dark:bg-emerald-500/80'
                        : 'bg-red-400/80 dark:bg-red-500/80'
                    }`}
                  />
                </div>
                {/* Tooltip */}
                <div className="hidden group-hover:block absolute bottom-full left-1/2 -translate-x-1/2 mb-1 z-10
                  bg-background border rounded-lg shadow-lg p-2 text-xs whitespace-nowrap">
                  <div className="font-semibold">{fmtDate(w.date)}</div>
                  <div className={plColor(w.cum_pl)}>{fmtPl(w.cum_pl)}</div>
                  {w.hit && <div className="text-yellow-600 font-bold">的中!</div>}
                </div>
              </div>
            );
          })}
        </div>
        {/* Zero line */}
        <div
          className="absolute left-4 right-4 border-t border-dashed border-muted-foreground/40"
          style={{ bottom: `calc(${zeroPos}% + 1rem)` }}
        />
        {/* Labels */}
        <div className="flex justify-between text-[10px] text-muted-foreground mt-1 min-w-[600px]">
          <span>{fmtDate(data[0].date)}</span>
          <span>{fmtDate(data[data.length - 1].date)}</span>
        </div>
      </div>
      <div className="flex gap-4 mt-2 text-xs text-muted-foreground">
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 bg-emerald-400 rounded-sm inline-block" /> プラス
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 bg-red-400 rounded-sm inline-block" /> マイナス
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 bg-yellow-400 rounded-sm inline-block" /> 的中週
        </span>
      </div>
    </div>
  );
}

// ============================================================
// Main Page
// ============================================================
export default function Win5SimulationPage() {
  const [data, setData] = useState<SimData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeCombo, setActiveCombo] = useState<string>('A+B');
  const [showWeekly, setShowWeekly] = useState(false);

  useEffect(() => {
    fetch('/api/win5/simulation')
      .then(res => {
        if (!res.ok) throw new Error('not_found');
        return res.json();
      })
      .then(d => { setData(d); setLoading(false); })
      .catch(() => {
        setError('シミュレーション結果がありません。python -m ml.win5_combo_sim を実行してください。');
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="w-full max-w-5xl mx-auto px-4 py-12 text-center text-muted-foreground">
        読み込み中...
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="w-full max-w-5xl mx-auto px-4 py-12 text-center text-muted-foreground">
        {error}
      </div>
    );
  }

  const combo = data.combos[activeCombo];
  const plans = data.plans;

  return (
    <div className="w-full max-w-5xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <span className="text-3xl">5</span>
          <div>
            <h1 className="text-2xl font-bold">WIN5 シミュレーション結果</h1>
            <p className="text-sm text-muted-foreground">
              v7.3モデル バックテスト {fmtDate(data.period.start)}〜{fmtDate(data.period.end)} ({data.matched_weeks}週)
            </p>
          </div>
        </div>
        <Link
          href="/win5"
          className="px-4 py-2 border rounded-lg text-sm font-medium hover:bg-muted/50 transition-colors"
        >
          推奨馬に戻る
        </Link>
      </div>

      {/* Plan Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        {(['A', 'B', 'C', 'D'] as const).map(key => {
          const p = plans[key];
          if (!p) return null;
          return (
            <div key={key} className="border rounded-xl p-4">
              <div className="text-sm font-semibold mb-2">{p.name}</div>
              <div className="grid grid-cols-2 gap-y-1 text-sm">
                <span className="text-muted-foreground">ROI</span>
                <span className={`text-right ${roiColor(p.roi)}`}>{p.roi}%</span>
                <span className="text-muted-foreground">的中</span>
                <span className="text-right">{p.hits}回 ({p.hit_rate}%)</span>
                <span className="text-muted-foreground">平均点</span>
                <span className="text-right">{p.avg_tickets}点</span>
                <span className="text-muted-foreground">最終損益</span>
                <span className={`text-right ${plColor(p.final_pl)}`}>{fmtPl(p.final_pl)}</span>
                <span className="text-muted-foreground">最大DD</span>
                <span className="text-right text-red-500">{fmtYen(p.max_dd)}</span>
                <span className="text-muted-foreground">最大連敗</span>
                <span className="text-right">{p.max_losing_streak}週</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Combo Tabs */}
      <div className="flex gap-2 mb-4 flex-wrap">
        {Object.keys(data.combos).map(name => (
          <button
            key={name}
            onClick={() => setActiveCombo(name)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeCombo === name
                ? 'bg-primary text-primary-foreground shadow-md'
                : 'border hover:bg-muted/50'
            }`}
          >
            {name} 併用
          </button>
        ))}
      </div>

      {/* Combo Summary */}
      <div className="border rounded-xl p-5 mb-6">
        <div className="flex items-center gap-3 mb-4">
          <h2 className="text-lg font-bold">{activeCombo} 併用プラン</h2>
          <span className={`text-2xl font-bold ${roiColor(combo.roi)}`}>
            ROI {combo.roi}%
          </span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <div className="text-xs text-muted-foreground">累計投資</div>
            <div className="text-lg font-bold">{fmtYen(combo.total_cost)}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">累計払戻</div>
            <div className="text-lg font-bold">{fmtYen(combo.total_payout)}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">最終損益</div>
            <div className={`text-lg font-bold ${plColor(combo.final_pl)}`}>
              {fmtPl(combo.final_pl)}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">的中回数</div>
            <div className="text-lg font-bold">{combo.hit_count}回</div>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4 pt-4 border-t">
          <div>
            <div className="text-xs text-muted-foreground">最高到達点</div>
            <div className="text-sm font-semibold text-emerald-600 dark:text-emerald-400">
              {fmtPl(combo.peak)}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">最大ドローダウン</div>
            <div className="text-sm font-semibold text-red-600 dark:text-red-400">
              {fmtYen(combo.max_dd)}
            </div>
            <div className="text-[10px] text-muted-foreground">
              {fmtDate(combo.max_dd_from)}〜{fmtDate(combo.max_dd_to)}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">最大連敗</div>
            <div className="text-sm font-semibold">{combo.max_losing_streak}週</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">推奨バンクロール</div>
            <div className="text-sm font-semibold">{fmtYen(combo.bankroll_req)}</div>
            <div className="text-[10px] text-muted-foreground">最大DD×1.5</div>
          </div>
        </div>

        {/* Annual */}
        <div className="mt-4 pt-4 border-t">
          <div className="text-xs text-muted-foreground mb-2">年間換算 (52週)</div>
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <span className="text-muted-foreground">年間投資: </span>
              <span className="font-semibold">{fmtYen(combo.annual_cost)}</span>
            </div>
            <div>
              <span className="text-muted-foreground">年間払戻: </span>
              <span className="font-semibold">{fmtYen(combo.annual_payout)}</span>
            </div>
            <div>
              <span className="text-muted-foreground">年間損益: </span>
              <span className={`font-bold ${plColor(combo.annual_pl)}`}>
                {fmtPl(combo.annual_pl)}
              </span>
              <span className="text-xs text-muted-foreground ml-1">
                (月{fmtPl(Math.round(combo.annual_pl / 12))})
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Chart */}
      <CumPlChart data={combo.weekly} label={activeCombo} />

      {/* Hit Details */}
      <div className="mt-6">
        <h3 className="text-sm font-semibold mb-3">的中詳細</h3>
        <div className="border rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-muted/30 text-xs text-muted-foreground">
                <th className="px-3 py-2 text-left">日付</th>
                <th className="px-3 py-2 text-right">投資</th>
                <th className="px-3 py-2 text-right">払戻</th>
                <th className="px-3 py-2 text-right">損益</th>
                <th className="px-3 py-2 text-center">的中プラン</th>
              </tr>
            </thead>
            <tbody>
              {combo.weekly.filter(w => w.hit).map(w => {
                const plans_hit: string[] = [];
                if (w.a_hit) plans_hit.push('A');
                if (w.b_hit) plans_hit.push('B');
                if (w.c_hit) plans_hit.push('C');
                if (w.d_hit) plans_hit.push('D');
                const profit = w.payout - w.cost;
                return (
                  <tr key={w.date} className="border-t hover:bg-muted/20">
                    <td className="px-3 py-2 font-mono">{fmtDate(w.date)}</td>
                    <td className="px-3 py-2 text-right">{fmtYen(w.cost)}</td>
                    <td className="px-3 py-2 text-right font-semibold">{fmtYen(w.payout)}</td>
                    <td className={`px-3 py-2 text-right font-semibold ${plColor(profit)}`}>
                      {fmtPl(profit)}
                    </td>
                    <td className="px-3 py-2 text-center">
                      {plans_hit.map(p => (
                        <span
                          key={p}
                          className={`inline-block px-2 py-0.5 rounded-full text-xs font-bold mr-1 ${
                            p === 'A' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300' :
                            p === 'B' ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300' :
                            p === 'D' ? 'bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-300' :
                            'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300'
                          }`}
                        >
                          {p}
                        </span>
                      ))}
                      {plans_hit.length >= 2 && (
                        <span className="text-yellow-600 dark:text-yellow-400 text-xs font-bold ml-1">W的中</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Weekly Detail Toggle */}
      <div className="mt-6">
        <button
          onClick={() => setShowWeekly(!showWeekly)}
          className="text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          {showWeekly ? '週次詳細を閉じる ▲' : '週次詳細を表示 ▼'}
        </button>

        {showWeekly && (() => {
          const planKeys = activeCombo.split('+') as ('A' | 'B' | 'C' | 'D')[];
          const costKey = (k: string) => `${k.toLowerCase()}_cost` as keyof WeeklyData;
          const payKey = (k: string) => `${k.toLowerCase()}_payout` as keyof WeeklyData;
          return (
            <div className="mt-3 border rounded-xl overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-muted/30 text-muted-foreground">
                    <th className="px-2 py-1.5 text-left">日付</th>
                    {planKeys.map(k => (
                      <React.Fragment key={k}>
                        <th className="px-2 py-1.5 text-right">{k}投資</th>
                        <th className="px-2 py-1.5 text-right">{k}払戻</th>
                      </React.Fragment>
                    ))}
                    <th className="px-2 py-1.5 text-right">週損益</th>
                    <th className="px-2 py-1.5 text-right">累計損益</th>
                  </tr>
                </thead>
                <tbody>
                  {combo.weekly.map(w => (
                    <tr
                      key={w.date}
                      className={`border-t ${
                        w.hit ? 'bg-yellow-50 dark:bg-yellow-900/10' : 'hover:bg-muted/20'
                      }`}
                    >
                      <td className="px-2 py-1 font-mono">{fmtDate(w.date)}</td>
                      {planKeys.map(k => {
                        const cost = (w[costKey(k)] as number) || 0;
                        const pay = (w[payKey(k)] as number) || 0;
                        const isSkip = k === 'B' && w.b_skip;
                        return (
                          <React.Fragment key={k}>
                            <td className="px-2 py-1 text-right">
                              {isSkip ? <span className="text-muted-foreground italic">SKIP</span> : fmtYen(cost)}
                            </td>
                            <td className="px-2 py-1 text-right">
                              {pay > 0 ? (
                                <span className="font-bold text-emerald-600 dark:text-emerald-400">{fmtYen(pay)}</span>
                              ) : '-'}
                            </td>
                          </React.Fragment>
                        );
                      })}
                      <td className={`px-2 py-1 text-right font-semibold ${plColor(w.pl)}`}>
                        {fmtPl(w.pl)}
                      </td>
                      <td className={`px-2 py-1 text-right font-semibold ${plColor(w.cum_pl)}`}>
                        {fmtPl(w.cum_pl)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        })()}
      </div>

      {/* Legend */}
      <div className="mt-6 p-3 rounded-lg border bg-muted/10 text-xs text-muted-foreground space-y-1">
        <div>
          <span className="font-medium">Plan A</span>: w_top2 — rank_w上位2頭を毎週購入 (32点=3,200円)
        </div>
        <div>
          <span className="font-medium">Plan B</span>: w_ard1st_55_tiered — ARd1位&ge;55の週のみ参加、ARd値でtiered可変
        </div>
        <div>
          <span className="font-medium">Plan C</span>: union_top2 — rank_w上位2頭 &cup; rank_p上位2頭の和集合
        </div>
        <div>
          <span className="font-medium">Plan D</span>: w2_ar1_p1 — rank_w上位2頭 &cup; AR偏差値1位 &cup; rank_p1位
        </div>
        <div>
          <span className="font-medium">推奨バンクロール</span>: 最大ドローダウンの1.5倍。この金額を準備してから開始すること。
        </div>
      </div>
    </div>
  );
}
