'use client';

import { useState, useEffect } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';

interface Pick {
  umaban: number;
  horse_name: string;
  odds: number;
  odds_rank: number;
  rank_w: number;
  rank_p: number;
  ar_deviation: number;
  win_ev: number;
  place_ev: number;
  kb_mark: string;
}

interface Leg {
  leg: number;
  count: number;
  picks: Pick[];
}

interface Strategy {
  label: string;
  legs: Leg[];
  total_tickets: number;
  cost: number;
}

interface RaceInfo {
  leg: number;
  race_id: string;
  venue: string;
  race_number: number;
  race_name: string;
  num_runners: number;
}

interface LegResult {
  leg: number;
  winner_umaban: number;
  winner_name: string;
  winner_odds: number;
  winner_popularity: number;
  has_result: boolean;
}

interface StrategyResult {
  hit: boolean;
  hitLegs: number[];
}

interface Win5Payout {
  kumiban: number[];
  payout: number;
  tickets: number;
}

interface Win5Data {
  date: string;
  races: RaceInfo[];
  strategies: Record<string, Strategy>;
  results?: LegResult[];
  strategy_results?: Record<string, StrategyResult>;
  payout?: Win5Payout;
}

function ardColor(ard: number): string {
  if (ard >= 65) return 'text-red-600 dark:text-red-400 font-bold';
  if (ard >= 60) return 'text-orange-600 dark:text-orange-400 font-semibold';
  if (ard >= 55) return 'text-yellow-600 dark:text-yellow-400';
  if (ard >= 50) return 'text-foreground';
  return 'text-muted-foreground';
}

function evColor(ev: number): string {
  if (ev >= 1.5) return 'text-red-600 dark:text-red-400 font-bold';
  if (ev >= 1.2) return 'text-orange-600 dark:text-orange-400 font-semibold';
  if (ev >= 1.0) return 'text-emerald-600 dark:text-emerald-400';
  return 'text-muted-foreground';
}

function markBadge(mark: string) {
  const colors: Record<string, string> = {
    '\u25CE': 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300 border-red-200 dark:border-red-800',
    '\u25CB': 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 border-blue-200 dark:border-blue-800',
    '\u25B2': 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300 border-green-200 dark:border-green-800',
    '\u25B3': 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300 border-yellow-200 dark:border-yellow-800',
  };
  if (!mark) return null;
  const cls = colors[mark] || 'bg-muted text-muted-foreground border-border';
  return <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold border ${cls}`}>{mark}</span>;
}

function StrategyCard({ name, strategy, races, results, strategyResult }: {
  name: string;
  strategy: Strategy;
  races: RaceInfo[];
  results: LegResult[];
  strategyResult?: StrategyResult;
}) {
  const [open, setOpen] = useState(false);
  const resultMap = new Map(results.map(r => [r.leg, r]));
  const hasResults = results.length > 0;

  return (
    <div className="border rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full px-4 py-3 flex items-center justify-between bg-muted/30 hover:bg-muted/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="text-lg">{name === 'w_floor50_gap' ? '\u2B50' : name.startsWith('wp_gap') ? '\uD83C\uDFAF' : name === 'p_fixed_2' ? '\uD83D\uDCB0' : '\u25C6'}</span>
          <div className="text-left">
            <div className="font-semibold text-sm flex items-center gap-2">
              {strategy.label}
              {strategyResult && (
                strategyResult.hit
                  ? <span className="text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300 font-bold">WIN5 的中!</span>
                  : <span className="text-xs px-2 py-0.5 rounded-full bg-muted text-muted-foreground">{strategyResult.hitLegs.length}/5的中</span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className="text-lg font-bold">{strategy.total_tickets.toLocaleString()}点</div>
            <div className="text-xs text-muted-foreground">&yen;{strategy.cost.toLocaleString()}</div>
          </div>
          <span className={`text-muted-foreground transition-transform ${open ? 'rotate-180' : ''}`}>&darr;</span>
        </div>
      </button>

      {open && (
        <div className="divide-y">
          {strategy.legs.map((leg, i) => {
            const race = races[i];
            const legResult = resultMap.get(leg.leg);
            const legHit = legResult && leg.picks.some(p => p.umaban === legResult.winner_umaban);
            return (
              <div key={i} className="px-4 py-3">
                <div className="flex items-center gap-2 mb-2">
                  <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                    legResult
                      ? legHit
                        ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300'
                        : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
                      : 'bg-primary/10 text-primary'
                  }`}>
                    R{leg.leg}{legResult ? (legHit ? ' \u25CB' : ' \u00D7') : ''}
                  </span>
                  <span className="font-semibold text-sm">
                    {race?.venue}{race?.race_number}R
                  </span>
                  <span className="text-xs text-muted-foreground">{race?.race_name}</span>
                  {legResult && (
                    <span className="text-xs text-muted-foreground">
                      1着: <span className="font-semibold text-foreground">{legResult.winner_umaban} {legResult.winner_name}</span>
                      <span className="text-[10px] ml-1">{legResult.winner_odds.toFixed(1)}倍({legResult.winner_popularity}人)</span>
                    </span>
                  )}
                  <span className="ml-auto text-xs font-medium text-muted-foreground">
                    {leg.count}頭
                  </span>
                </div>

                {leg.picks.length === 0 ? (
                  <div className="text-xs text-muted-foreground italic pl-8">条件外（推奨なし）</div>
                ) : (
                  <table className="w-full text-sm">
                    <tbody>
                      {leg.picks.map((p) => {
                        const isWinner = hasResults && legResult && p.umaban === legResult.winner_umaban;
                        return (
                        <tr key={p.umaban} className={isWinner ? 'bg-emerald-50 dark:bg-emerald-900/20' : 'hover:bg-muted/20'}>
                          <td className="w-8 text-right font-mono font-bold pr-2 py-0.5">{p.umaban}</td>
                          <td className="w-32 truncate py-0.5">{p.horse_name}</td>
                          <td className="w-8 text-center py-0.5">{markBadge(p.kb_mark) ?? <span className="inline-block w-6" />}</td>
                          <td className={`w-12 text-right text-xs py-0.5 ${ardColor(p.ar_deviation)}`}>
                            {p.ar_deviation.toFixed(1)}
                          </td>
                          <td className="w-20 text-right text-xs text-muted-foreground py-0.5">
                            {p.odds.toFixed(1)}倍<span className="text-[10px]">({p.odds_rank}人)</span>
                          </td>
                          <td className={`w-14 text-right text-xs py-0.5 ${evColor(p.win_ev)}`}>
                            W{p.win_ev.toFixed(2)}
                          </td>
                          <td className={`w-14 text-right text-xs py-0.5 ${evColor(p.place_ev)}`}>
                            P{p.place_ev.toFixed(2)}
                          </td>
                          <td className="text-[10px] text-muted-foreground text-right py-0.5">
                            Rw{p.rank_w} Rp{p.rank_p}
                          </td>
                        </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            );
          })}

          {/* フォーメーション表記 */}
          <div className="px-4 py-2 bg-muted/20 text-xs text-muted-foreground">
            <span className="font-medium">フォーメーション: </span>
            {strategy.legs.map((leg, i) => (
              <span key={i}>
                {i > 0 && ' \u00D7 '}
                {leg.picks.map(p => p.umaban).join(',')}
              </span>
            ))}
            <span className="ml-2">= {strategy.total_tickets.toLocaleString()}点</span>
          </div>
        </div>
      )}
    </div>
  );
}

export default function Win5Page() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [data, setData] = useState<Win5Data | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dateInput, setDateInput] = useState(searchParams.get('date') || '');
  const [generating, setGenerating] = useState(false);
  const [genMsg, setGenMsg] = useState<string | null>(null);
  const [fetchKey, setFetchKey] = useState(0);

  const fetchDate = searchParams.get('date') || '';

  useEffect(() => {
    if (!fetchDate) {
      setLoading(false);
      setError('日付を指定してください');
      return;
    }
    setLoading(true);
    setError(null);
    fetch(`/api/win5?date=${fetchDate}`)
      .then(res => {
        if (!res.ok) throw new Error(res.status === 404 ? 'not_found' : 'error');
        return res.json();
      })
      .then(d => { setData(d); setLoading(false); })
      .catch(e => {
        setError(e.message === 'not_found'
          ? `${fetchDate} のWIN5推奨データがありません。\n「生成」ボタンで作成できます。`
          : 'データの読み込みに失敗しました');
        setData(null);
        setLoading(false);
      });
  }, [fetchDate, fetchKey]);

  const handleGo = () => {
    if (dateInput) {
      router.push(`/win5?date=${dateInput}`);
    }
  };

  const handleGenerate = async () => {
    if (!dateInput) return;
    setGenerating(true);
    setGenMsg(null);
    try {
      const res = await fetch('/api/win5/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ date: dateInput }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || 'failed');
      }
      setGenMsg('生成完了');
      // 同じ日付ならfetchKeyで再fetch、違う日付ならURLを変更
      if (fetchDate === dateInput) {
        setFetchKey(k => k + 1);
      } else {
        router.push(`/win5?date=${dateInput}`);
      }
    } catch (e) {
      setGenMsg(`エラー: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setGenerating(false);
    }
  };

  const strategyOrder = ['w_floor50_gap', 'wp_gap_f48', 'wp_gap_f50', 'w_floor48_gap', 'w_floor45_gap', 'p_fixed_2'];

  return (
    <div className="w-full max-w-4xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <span className="text-3xl">5</span>
        <div>
          <h1 className="text-2xl font-bold">WIN5 推奨馬</h1>
          <p className="text-sm text-muted-foreground">可変点数戦略 (backtest ROI 224%)</p>
        </div>
      </div>

      {/* Date Picker */}
      <div className="flex items-center gap-2 mb-6">
        <input
          type="date"
          value={dateInput}
          onChange={e => setDateInput(e.target.value)}
          className="px-3 py-2 border rounded-lg bg-background text-sm"
        />
        <button
          onClick={handleGo}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
        >
          表示
        </button>
        <button
          onClick={handleGenerate}
          disabled={generating || !dateInput}
          className="px-4 py-2 border rounded-lg text-sm font-medium transition-colors hover:bg-muted/50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {generating ? '生成中...' : '生成'}
        </button>
        {genMsg && (
          <span className={`text-xs ${genMsg.startsWith('エラー') ? 'text-red-500' : 'text-emerald-600'}`}>
            {genMsg}
          </span>
        )}
      </div>

      {/* Content */}
      {loading && (
        <div className="text-center py-12 text-muted-foreground">読み込み中...</div>
      )}

      {error && !loading && (
        <div className="text-center py-12">
          <div className="text-muted-foreground whitespace-pre-line">{error}</div>
        </div>
      )}

      {data && !loading && (
        <>
          {/* Race Info */}
          <div className="mb-6 p-4 rounded-xl border bg-muted/20">
            <div className="text-sm font-semibold mb-2">対象レース ({data.date})</div>
            <div className="grid grid-cols-5 gap-2">
              {data.races.map((r) => {
                const res = data.results?.find(lr => lr.leg === r.leg);
                return (
                  <div key={r.leg} className="text-center">
                    <div className="text-xs text-muted-foreground">R{r.leg}</div>
                    <div className="font-semibold text-sm">{r.venue}{r.race_number}R</div>
                    <div className="text-[10px] text-muted-foreground truncate">{r.race_name}</div>
                    {res && (
                      <div className="text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 mt-0.5">
                        {res.winner_umaban} {res.winner_name}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Payout */}
          {data.payout && (
            <div className="mb-6 p-4 rounded-xl border bg-muted/20">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm font-semibold mb-1">WIN5 払戻金</div>
                  <div className="text-xs text-muted-foreground">
                    的中組番: {data.payout.kumiban.map((k, i) => (
                      <span key={i}>{i > 0 && ' - '}<span className="font-mono font-semibold text-foreground">{k}</span></span>
                    ))}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-2xl font-bold text-red-600 dark:text-red-400">
                    &yen;{data.payout.payout.toLocaleString()}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    的中 {data.payout.tickets.toLocaleString()}票
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Strategies */}
          <div className="space-y-3">
            {strategyOrder
              .filter(name => data.strategies[name])
              .map(name => (
                <StrategyCard
                  key={name}
                  name={name}
                  strategy={data.strategies[name]}
                  races={data.races}
                  results={data.results ?? []}
                  strategyResult={data.strategy_results?.[name]}
                />
              ))}
          </div>

          {/* Legend */}
          <div className="mt-6 p-3 rounded-lg border bg-muted/10 text-xs text-muted-foreground space-y-1">
            <div><span className="font-medium">ARd</span>: AR偏差値（レース内相対評価）  <span className="font-medium">W</span>: 単勝EV  <span className="font-medium">P</span>: 複勝EV</div>
            <div><span className="font-medium">Rw</span>: Wモデルランク  <span className="font-medium">Rp</span>: Pモデルランク</div>
            <div>
              <span className="font-medium">gap制御</span>:
              ARd 1位-2位差 &ge;12&rarr;1頭, &ge;6&rarr;2頭, &ge;3&rarr;3頭, 他&rarr;5頭。
              ARdフロア未満の馬はカット。
            </div>
            <div>
              <span className="font-medium">WP合算</span>:
              rank_w + rank_p の合計が小さい順（W/P両モデルで高評価の馬を優先）。的中安定型。
            </div>
          </div>
        </>
      )}
    </div>
  );
}
