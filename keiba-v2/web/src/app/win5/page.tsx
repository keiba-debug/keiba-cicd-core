'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import Link from 'next/link';

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

function buildFormationText(strategy: Strategy, races: RaceInfo[]): string {
  const lines = [`${strategy.label} (${strategy.total_tickets.toLocaleString()}点 / ¥${strategy.cost.toLocaleString()})`];
  strategy.legs.forEach((leg, i) => {
    const race = races[i];
    const nums = leg.picks.map(p => p.umaban).join(',');
    lines.push(`Leg${leg.leg} ${race?.venue}${race?.race_number}R: ${nums || '(なし)'}`);
  });
  const formation = strategy.legs.map(leg => leg.picks.map(p => p.umaban).join(',')).join(' × ');
  lines.push(`Formation: ${formation} = ${strategy.total_tickets.toLocaleString()}点`);
  return lines.join('\n');
}

function StrategyCard({ name, strategy, races, results, strategyResult }: {
  name: string;
  strategy: Strategy;
  races: RaceInfo[];
  results: LegResult[];
  strategyResult?: StrategyResult;
}) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    const text = buildFormationText(strategy, races);
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  const resultMap = new Map(results.map(r => [r.leg, r]));
  const hasResults = results.length > 0;

  return (
    <div className="border rounded-xl overflow-hidden">
      <div
        onClick={() => setOpen(!open)}
        className="w-full px-4 py-3 flex items-center justify-between bg-muted/30 hover:bg-muted/50 transition-colors cursor-pointer"
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setOpen(!open); } }}
      >
        <div className="flex items-center gap-3">
          <span className="text-lg">{name === 'w_top2' ? 'W2' : name === 'w_top5' ? 'W5' : name === 'w_adaptive' ? 'WA' : name === 'w_floor50_gap' ? '\u2B50' : name === 'w2_ar1_p1' ? 'D' : name === 'p_fixed_2' ? 'P2' : '\u25C6'}</span>
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
        <div className="flex items-center gap-3">
          <button
            onClick={(e) => { e.stopPropagation(); handleCopy(e); }}
            className="p-1.5 rounded-md hover:bg-muted/60 transition-colors text-muted-foreground hover:text-foreground"
            title="フォーメーションをコピー"
          >
            {copied ? (
              <svg className="w-4 h-4 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            ) : (
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <rect x="9" y="9" width="13" height="13" rx="2" strokeWidth={2} />
                <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" strokeWidth={2} />
              </svg>
            )}
          </button>
          <div className="text-right">
            <div className="text-lg font-bold">{strategy.total_tickets.toLocaleString()}点</div>
            <div className="text-xs text-muted-foreground">&yen;{strategy.cost.toLocaleString()}</div>
          </div>
          <span className={`text-muted-foreground transition-transform ${open ? 'rotate-180' : ''}`}>&darr;</span>
        </div>
      </div>

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

/** YYYY-MM-DD → "2026年2月22日(日)" */
function formatDateDisplay(dateStr: string): string {
  const [y, m, d] = dateStr.split('-').map(Number);
  const dow = ['日', '月', '火', '水', '木', '金', '土'][new Date(y, m - 1, d).getDay()];
  return `${y}年${m}月${d}日(${dow})`;
}

export default function Win5Page() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [data, setData] = useState<Win5Data | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [genMsg, setGenMsg] = useState<string | null>(null);
  const [fetchKey, setFetchKey] = useState(0);
  const [availDates, setAvailDates] = useState<string[]>([]);
  const [pendingDates, setPendingDates] = useState<string[]>([]);

  const fetchDate = searchParams.get('date') || '';

  // Load available WIN5 dates
  useEffect(() => {
    fetch('/api/win5/dates')
      .then(res => res.json())
      .then(d => {
        setAvailDates(d.dates || []);
        setPendingDates(d.pendingDates || []);
      })
      .catch(() => {});
  }, [fetchKey]);

  // 全日付を統合（新しい順）: pendingDates + availDates を日付降順でマージ
  const allDates = useMemo(
    () => [...new Set([...pendingDates, ...availDates])].sort().reverse(),
    [pendingDates, availDates]
  );
  const pendingSet = useMemo(() => new Set(pendingDates), [pendingDates]);

  useEffect(() => {
    // No date param but we have available dates → navigate to latest
    if (!fetchDate && allDates.length > 0) {
      router.replace(`/win5?date=${allDates[0]}`);
      return;
    }
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
  }, [fetchDate, fetchKey, allDates, router]);

  const currentIndex = allDates.indexOf(fetchDate);
  const isLatest = currentIndex === 0;
  const isOldest = currentIndex >= allDates.length - 1;
  const isPending = pendingSet.has(fetchDate);

  const goToPrev = useCallback(() => {
    if (currentIndex < 0 || currentIndex >= allDates.length - 1) return;
    router.push(`/win5?date=${allDates[currentIndex + 1]}`);
  }, [currentIndex, allDates, router]);

  const goToNext = useCallback(() => {
    if (currentIndex <= 0) return;
    router.push(`/win5?date=${allDates[currentIndex - 1]}`);
  }, [currentIndex, allDates, router]);

  const onSelectChange = (value: string) => {
    router.push(`/win5?date=${value}`);
  };

  const handleGenerate = async () => {
    if (!fetchDate) return;
    setGenerating(true);
    setGenMsg(null);
    try {
      const res = await fetch('/api/win5/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ date: fetchDate }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || 'failed');
      }
      setGenMsg('生成完了');
      setFetchKey(k => k + 1);
    } catch (e) {
      setGenMsg(`エラー: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setGenerating(false);
    }
  };

  const strategyOrder = ['w_top2', 'w_top5', 'w_adaptive', 'w_floor50_gap', 'w2_ar1_p1', 'p_fixed_2'];

  return (
    <div className="w-full max-w-4xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <span className="text-3xl">5</span>
          <div>
            <h1 className="text-2xl font-bold">写輪眼 — WIN5 推奨馬</h1>
            <p className="text-sm text-muted-foreground">v7.3.1 W Top5 ROI 200% / W Top2 ROI 126%</p>
          </div>
        </div>
        <Link
          href="/win5/simulation"
          className="px-4 py-2 border rounded-lg text-sm font-medium hover:bg-muted/50 transition-colors"
        >
          シミュレーション結果
        </Link>
      </div>

      {/* Date Navigation (ValueBet style) */}
      <div className="flex items-center gap-2 mb-6">
        <button
          onClick={goToPrev}
          disabled={currentIndex < 0 || isOldest}
          className="p-2 border rounded-lg hover:bg-muted/50 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          title="前の開催日"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <div className="flex items-center gap-2">
          <svg className="w-5 h-5 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2" strokeWidth={2} />
            <line x1="16" y1="2" x2="16" y2="6" strokeWidth={2} />
            <line x1="8" y1="2" x2="8" y2="6" strokeWidth={2} />
            <line x1="3" y1="10" x2="21" y2="10" strokeWidth={2} />
          </svg>
          <select
            value={fetchDate}
            onChange={(e) => onSelectChange(e.target.value)}
            className="rounded-md border bg-background px-3 py-2 text-lg font-bold min-w-[220px]"
          >
            {allDates.length === 0 && fetchDate && (
              <option value={fetchDate}>{formatDateDisplay(fetchDate)}</option>
            )}
            {allDates.map(date => (
              <option key={date} value={date}>
                {formatDateDisplay(date)}{pendingSet.has(date) ? ' [未生成]' : ''}
              </option>
            ))}
          </select>
        </div>
        <button
          onClick={goToNext}
          disabled={isLatest || currentIndex < 0}
          className="p-2 border rounded-lg hover:bg-muted/50 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          title="次の開催日"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>
        <button
          onClick={handleGenerate}
          disabled={generating || !fetchDate}
          className="px-4 py-2 border rounded-lg text-sm font-medium transition-colors hover:bg-muted/50 disabled:opacity-40 disabled:cursor-not-allowed ml-2"
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
          <div className="text-muted-foreground whitespace-pre-line mb-4">{error}</div>
          {isPending && (
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="px-6 py-3 bg-primary text-primary-foreground rounded-lg font-semibold hover:bg-primary/90 transition-colors disabled:opacity-40"
            >
              {generating ? '生成中...' : `${fetchDate} のWIN5推奨を生成`}
            </button>
          )}
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
              <span className="font-medium">W Top2</span>: rank_w上位2頭×5R=32点(3,200円)。低予算で高ROI。
              <span className="font-medium">W Top5</span>: rank_w上位5頭×5R=3,125点(312,500円)。高的中率。
            </div>
            <div>
              <span className="font-medium">gap制御</span>:
              ARd 1位-2位差 &ge;12&rarr;1頭, &ge;6&rarr;2頭, &ge;3&rarr;3頭, 他&rarr;5頭。
              ARdフロア未満の馬はカット。
            </div>
          </div>
        </>
      )}
    </div>
  );
}
