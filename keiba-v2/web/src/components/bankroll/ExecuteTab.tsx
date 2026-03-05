'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Zap, Play, Loader2, CheckCircle2, XCircle,
  ChevronLeft, ChevronRight, Calendar, RefreshCw,
  ArrowRight, TrendingUp, ChevronDown, ChevronUp, Layers,
  ShoppingCart, Check, X, Download, Trophy,
} from 'lucide-react';

// =====================================================================
// 型定義
// =====================================================================

interface RecommendationEntry {
  race_id: string;
  venue: string;
  race_number: number;
  umaban: number;
  horse_name: string;
  odds: number;
  rank_w: number;
  win_vb_gap: number;
  win_ev: number;
  predicted_margin: number | null;
  ar_deviation: number | null;
  pred_proba_w_cal: number | null;
  win_amount: number;
  place_amount: number;
  strength: string;
}

interface PredictionsData {
  date: string;
  model_version: string;
  predict_only: boolean;
  bets_generated_at?: string;
  recommendations?: Record<string, {
    params: Record<string, number>;
    bets: Array<{
      race_id: string;
      venue?: string;
      race_number?: number;
      umaban: number;
      horse_name: string;
      bet_type: string;
      strength: string;
      win_amount: number;
      place_amount: number;
      odds: number;
      gap?: number;
      win_gap?: number;
      dev_gap?: number;
      vb_score?: number;
      predicted_margin?: number;
      win_ev?: number;
      ar_deviation?: number;
      pred_proba_w_cal?: number;
    }>;
    summary: {
      total_bets: number;
      win_bets: number;
      place_bets: number;
      total_amount: number;
    };
  }>;
  races?: Array<{
    race_id: string;
    venue_name: string;
    race_number: number;
    entries: Array<{
      umaban: number;
      horse_name: string;
      odds: number;
      rank_w?: number;
      win_vb_gap?: number;
      win_ev?: number;
      predicted_margin?: number;
      ar_deviation?: number;
      pred_proba_w_cal?: number;
    }>;
  }>;
}

// 購入レコード（API側の PurchaseItem に対応）
interface PurchaseItem {
  id: string;
  race_id: string;
  race_name: string;
  venue: string;
  race_number: number;
  bet_type: string;
  selection: string;  // "馬番-馬名" 形式
  amount: number;
  odds: number | null;
  expected_value: number | null;
  status: 'planned' | 'purchased' | 'result_win' | 'result_lose';
  payout: number;
  confidence: '高' | '中' | '低';
  reason: string;
  created_at: string;
  updated_at: string;
}

interface DailyPurchases {
  date: string;
  budget: number;
  total_planned: number;
  total_purchased: number;
  total_payout: number;
  items: PurchaseItem[];
  updated_at: string;
}

interface OtherPresetData {
  key: string;
  label: string;
  betCount: number;
  totalAmount: number;
  bets: Array<{
    race_id: string;
    venue: string;
    race_number: number;
    umaban: number;
    horse_name: string;
    odds: number;
    win_vb_gap: number;
    win_ev: number;
    predicted_margin: number | null;
    ar_deviation: number | null;
    win_amount: number;
    place_amount: number;
    strength: string;
  }>;
}

// プリセットのラベル定義
const PRESET_LABELS: Record<string, string> = {
  standard: 'Standard (VBスコア)',
  wide: 'Wide (緩め)',
  aggressive: 'Aggressive (攻め)',
  intersection: 'Intersection',
  simple: 'Simple (1位×Gap≥4)',
  simple_ev2: 'Simple EV2 (1位×EV≥2)',
  simple_wide: 'Simple Wide (1位×Gap≥3)',
  relaxed: 'Relaxed (Gap≥3×EV≥1)',
  ev_focus: 'EV重視 (Gap≥1×EV≥1.3)',
};

// =====================================================================
// ヘルパー
// =====================================================================

const formatDateToStr = (date: Date): string => {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
};

const formatDateDisplay = (dateStr: string): string => {
  const parts = dateStr.split('-');
  const year = parseInt(parts[0]);
  const month = parseInt(parts[1]);
  const day = parseInt(parts[2]);
  const date = new Date(year, month - 1, day);
  const weekdays = ['日', '月', '火', '水', '木', '金', '土'];
  return `${month}/${day}(${weekdays[date.getDay()]})`;
};

function getGapBg(gap: number): string {
  if (gap >= 6) return 'bg-red-100 dark:bg-red-900/30';
  if (gap >= 5) return 'bg-orange-100 dark:bg-orange-900/30';
  if (gap >= 4) return 'bg-amber-100 dark:bg-amber-900/30';
  return '';
}

function getEvColor(ev: number): string {
  if (ev >= 2.0) return 'text-amber-600 font-bold';
  if (ev >= 1.5) return 'text-red-600 font-semibold';
  if (ev >= 1.3) return 'text-green-600 font-semibold';
  return 'text-muted-foreground';
}

// =====================================================================
// ExecuteTab コンポーネント
// =====================================================================

export function ExecuteTab() {
  const today = formatDateToStr(new Date());

  // 日付管理
  const [availableDates, setAvailableDates] = useState<string[]>([]);
  const [selectedDate, setSelectedDate] = useState(today);

  // 実行状態
  const [executing, setExecuting] = useState(false);
  const [execLog, setExecLog] = useState<string[]>([]);
  const [execStatus, setExecStatus] = useState<'idle' | 'running' | 'success' | 'error'>('idle');

  // 推奨データ
  const [predictions, setPredictions] = useState<PredictionsData | null>(null);
  const [recommendations, setRecommendations] = useState<RecommendationEntry[]>([]);
  const [nearMisses, setNearMisses] = useState<(RecommendationEntry & { failReason: string })[]>([]);
  const [otherPresets, setOtherPresets] = useState<OtherPresetData[]>([]);
  const [expandedPresets, setExpandedPresets] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);

  // 購入管理
  const [dailyPurchases, setDailyPurchases] = useState<DailyPurchases | null>(null);
  // 推奨ごとの購入金額入力（キー: "race_id-umaban"）
  const [purchaseAmounts, setPurchaseAmounts] = useState<Record<string, number>>({});
  const [savingPurchase, setSavingPurchase] = useState<string | null>(null);

  // バンクロール残高 & 推奨購入額
  const [bankrollBalance, setBankrollBalance] = useState<number | null>(null);
  const [betPct, setBetPct] = useState(2); // 資金の何%をベットするか（デフォルト2%）
  const defaultBetAmount = bankrollBalance !== null
    ? Math.floor((bankrollBalance * betPct / 100) / 100) * 100 // 100円単位に切り下げ
    : 100;

  // FF CSV出力
  const [csvExporting, setCsvExporting] = useState(false);
  const [csvResult, setCsvResult] = useState<{ totalBets: number; winBets: number; totalAmount: number; filePath: string } | null>(null);

  const logRef = useRef<HTMLDivElement>(null);

  // バンクロール残高をロード
  useEffect(() => {
    fetch('/api/bankroll/fund')
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.current_balance != null) {
          setBankrollBalance(data.current_balance);
        }
      })
      .catch(() => {});
    // localStorage からベット%を復元
    const savedPct = localStorage.getItem('keiba_execute_bet_pct');
    if (savedPct) setBetPct(Number(savedPct));
  }, []);

  // 利用可能な予測日付をロード
  useEffect(() => {
    fetch('/api/race-dates')
      .then(r => r.json())
      .then(({ dates }) => {
        if (Array.isArray(dates) && dates.length > 0) {
          setAvailableDates(dates);
          // 当日以前の最新日付をデフォルト
          const todayStr = today;
          const defaultDate = dates.find((d: string) => d <= todayStr) || dates[0];
          setSelectedDate(defaultDate);
        }
      })
      .catch(() => {});
  }, []);

  // 予測データのロード
  const loadPredictions = useCallback(async (date: string) => {
    setLoading(true);
    try {
      const [y, m, d] = date.split('-');
      const res = await fetch(`/api/ml/predictions-raw?date=${y}-${m}-${d}`);
      if (!res.ok) {
        setPredictions(null);
        setRecommendations([]);
        return;
      }
      const data: PredictionsData = await res.json();
      setPredictions(data);

      // intersection プリセットの推奨を抽出
      const intRecs = data.recommendations?.intersection;
      if (intRecs && intRecs.bets.length > 0) {
        const entries: RecommendationEntry[] = intRecs.bets.map((b) => {
          // race情報を races から補完
          const race = data.races?.find(r => r.race_id === b.race_id);
          return {
            race_id: b.race_id,
            venue: b.venue || race?.venue_name || '',
            race_number: b.race_number || race?.race_number || 0,
            umaban: b.umaban,
            horse_name: b.horse_name,
            odds: b.odds,
            rank_w: 1, // intersection は rank_w=1 のみ
            win_vb_gap: b.win_gap ?? b.gap ?? 0,
            win_ev: b.win_ev ?? 0,
            predicted_margin: b.predicted_margin ?? null,
            ar_deviation: b.ar_deviation ?? null,
            pred_proba_w_cal: b.pred_proba_w_cal ?? null,
            win_amount: b.win_amount,
            place_amount: b.place_amount,
            strength: b.strength,
          };
        });
        setRecommendations(entries);
      } else {
        // Python bet_engine の推奨がない場合、races から intersection 条件を自前フィルタ
        const filtered: RecommendationEntry[] = [];
        for (const race of data.races || []) {
          for (const e of race.entries) {
            if (
              e.rank_w === 1 &&
              (e.win_vb_gap ?? 0) >= 4 &&
              (e.win_ev ?? 0) >= 1.3 &&
              (e.predicted_margin ?? 999) <= 60
            ) {
              filtered.push({
                race_id: race.race_id,
                venue: race.venue_name,
                race_number: race.race_number,
                umaban: e.umaban,
                horse_name: e.horse_name,
                odds: e.odds,
                rank_w: 1,
                win_vb_gap: e.win_vb_gap ?? 0,
                win_ev: e.win_ev ?? 0,
                predicted_margin: e.predicted_margin ?? null,
                ar_deviation: e.ar_deviation ?? null,
                pred_proba_w_cal: e.pred_proba_w_cal ?? null,
                win_amount: 0,
                place_amount: 0,
                strength: (e.win_vb_gap ?? 0) >= 6 ? 'strong' : 'normal',
              });
            }
          }
        }
        setRecommendations(filtered);
      }

      // ニアミス: rank_w=1 で 3条件のうち2つ以上満たす馬
      const misses: (RecommendationEntry & { failReason: string })[] = [];
      for (const race of data.races || []) {
        for (const e of race.entries) {
          if (e.rank_w !== 1) continue;
          const wg = e.win_vb_gap ?? 0;
          const ev = e.win_ev ?? 0;
          const pm = e.predicted_margin ?? 999;
          const gapOk = wg >= 4;
          const evOk = ev >= 1.3;
          const mOk = pm <= 60;
          const passCount = [gapOk, evOk, mOk].filter(Boolean).length;
          // 全3条件パスは推奨馬（ニアミスではない）、2条件パスがニアミス
          if (passCount === 2) {
            const fails: string[] = [];
            if (!gapOk) fails.push(`Gap=${wg}<4`);
            if (!evOk) fails.push(`EV=${ev.toFixed(2)}<1.3`);
            if (!mOk) fails.push(`R=${pm.toFixed(0)}>60`);
            misses.push({
              race_id: race.race_id,
              venue: race.venue_name,
              race_number: race.race_number,
              umaban: e.umaban,
              horse_name: e.horse_name,
              odds: e.odds,
              rank_w: 1,
              win_vb_gap: wg,
              win_ev: ev,
              predicted_margin: e.predicted_margin ?? null,
              ar_deviation: e.ar_deviation ?? null,
              pred_proba_w_cal: e.pred_proba_w_cal ?? null,
              win_amount: 0,
              place_amount: 0,
              strength: 'normal',
              failReason: fails.join(', '),
            });
          }
        }
      }
      setNearMisses(misses);

      // 他プリセットの推奨を抽出
      const others: OtherPresetData[] = [];
      if (data.recommendations) {
        for (const [key, preset] of Object.entries(data.recommendations)) {
          if (key === 'intersection') continue; // メイン表示で使用済み
          if (!preset || !preset.bets || preset.bets.length === 0) continue;
          others.push({
            key,
            label: PRESET_LABELS[key] || key,
            betCount: preset.bets.length,
            totalAmount: preset.summary?.total_amount ?? preset.bets.reduce((s, b) => s + (b.win_amount || 0) + (b.place_amount || 0), 0),
            bets: preset.bets.map((b) => {
              const race = data.races?.find(r => r.race_id === b.race_id);
              return {
                race_id: b.race_id,
                venue: b.venue || race?.venue_name || '',
                race_number: b.race_number || race?.race_number || 0,
                umaban: b.umaban,
                horse_name: b.horse_name,
                odds: b.odds,
                win_vb_gap: b.win_gap ?? b.gap ?? 0,
                win_ev: b.win_ev ?? 0,
                predicted_margin: b.predicted_margin ?? null,
                ar_deviation: b.ar_deviation ?? null,
                win_amount: b.win_amount,
                place_amount: b.place_amount,
                strength: b.strength,
              };
            }),
          });
        }
        // ベット数の多い順にソート
        others.sort((a, b) => b.betCount - a.betCount);
      }
      setOtherPresets(others);
    } catch {
      setPredictions(null);
      setRecommendations([]);
      setNearMisses([]);
      setOtherPresets([]);
    } finally {
      setLoading(false);
    }
  }, []);

  // 購入データのロード
  const loadPurchases = useCallback(async (date: string) => {
    try {
      const res = await fetch(`/api/purchases/${date}`);
      if (res.ok) {
        const data: DailyPurchases = await res.json();
        setDailyPurchases(data);
      } else {
        setDailyPurchases(null);
      }
    } catch {
      setDailyPurchases(null);
    }
  }, []);

  // 購入キー（推奨一覧と購入レコードのマッチング用）
  const getPurchaseKey = (raceId: string, umaban: number) => `${raceId}-${umaban}`;

  // 推奨がすでに購入済みかチェック
  const findPurchase = (raceId: string, umaban: number): PurchaseItem | undefined => {
    if (!dailyPurchases) return undefined;
    const selection = `${umaban}`;
    return dailyPurchases.items.find(
      (p) => p.race_id === raceId && p.selection.startsWith(selection + '-')
    );
  };

  // 購入を記録
  const recordPurchase = async (rec: RecommendationEntry) => {
    const key = getPurchaseKey(rec.race_id, rec.umaban);
    setSavingPurchase(key);
    try {
      const amount = purchaseAmounts[key] || defaultBetAmount || rec.win_amount || 100;
      const res = await fetch(`/api/purchases/${selectedDate}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          race_id: rec.race_id,
          race_name: `${rec.venue}${rec.race_number}R`,
          venue: rec.venue,
          race_number: rec.race_number,
          bet_type: '単勝',
          selection: `${rec.umaban}-${rec.horse_name}`,
          amount,
          odds: rec.odds,
          confidence: rec.strength === 'strong' ? '高' : '中',
          reason: `Intersection Filter (Gap+${rec.win_vb_gap}, EV${rec.win_ev.toFixed(2)})`,
          status: 'purchased',
        }),
      });
      if (res.ok) {
        await loadPurchases(selectedDate);
      }
    } catch (err) {
      console.error('Purchase save error:', err);
    } finally {
      setSavingPurchase(null);
    }
  };

  // 購入を取り消し
  const cancelPurchase = async (purchaseId: string) => {
    setSavingPurchase(purchaseId);
    try {
      const res = await fetch(`/api/purchases/${selectedDate}?id=${purchaseId}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        await loadPurchases(selectedDate);
      }
    } catch (err) {
      console.error('Purchase cancel error:', err);
    } finally {
      setSavingPurchase(null);
    }
  };

  // 結果反映
  const [settling, setSettling] = useState(false);
  const [settleResult, setSettleResult] = useState<{ settled: number; wins: number; totalPayout: number; profit: number } | null>(null);

  const settleResults = async () => {
    setSettling(true);
    setSettleResult(null);
    try {
      const res = await fetch(`/api/purchases/${selectedDate}/settle`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setSettleResult({
          settled: data.settled,
          wins: data.wins,
          totalPayout: data.totalPayout,
          profit: data.profit,
        });
        await loadPurchases(selectedDate);
        // バンクロール残高もリフレッシュ
        fetch('/api/bankroll/fund')
          .then(r => r.ok ? r.json() : null)
          .then(d => { if (d?.current_balance != null) setBankrollBalance(d.current_balance); })
          .catch(() => {});
      } else {
        const err = await res.json().catch(() => ({ error: 'Unknown' }));
        alert(`結果反映失敗: ${err.error || res.statusText}`);
      }
    } catch (err) {
      alert(`結果反映エラー: ${err}`);
    } finally {
      setSettling(false);
    }
  };

  // FF CSV出力（TARGET買い目取り込み用）
  const exportFfCsv = async () => {
    // 購入済みの推奨を対象にする（購入データがあればそれを、なければ推奨テーブルの全件を使う）
    const bets: { raceId: string; umaban: number; betType: number; amount: number }[] = [];

    if (dailyPurchases && dailyPurchases.items.length > 0) {
      // 購入済みの馬券からFF CSVを生成
      for (const item of dailyPurchases.items) {
        if (item.status === 'planned' || item.status === 'purchased') {
          const umaban = parseInt(item.selection.split('-')[0]);
          if (umaban >= 1 && umaban <= 18) {
            bets.push({
              raceId: item.race_id,
              umaban,
              betType: item.bet_type === '複勝' ? 1 : 0,
              amount: item.amount,
            });
          }
        }
      }
    } else {
      // 購入記録がない場合は推奨一覧からFF CSVを生成
      for (const rec of recommendations) {
        const key = getPurchaseKey(rec.race_id, rec.umaban);
        const amount = purchaseAmounts[key] || defaultBetAmount || rec.win_amount || 100;
        bets.push({
          raceId: rec.race_id,
          umaban: rec.umaban,
          betType: 0, // 単勝
          amount,
        });
      }
    }

    if (bets.length === 0) {
      alert('出力対象の買い目がありません');
      return;
    }

    setCsvExporting(true);
    setCsvResult(null);
    try {
      const res = await fetch('/api/target-marks/auto-bet', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bets }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: 'Unknown error' }));
        throw new Error(err.error || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setCsvResult({
        totalBets: data.summary.totalBets,
        winBets: data.summary.winBets,
        totalAmount: data.summary.totalAmount,
        filePath: data.summary.filePath,
      });
    } catch (error) {
      alert(`FF CSV出力失敗: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setCsvExporting(false);
    }
  };

  // 日付変更時にリロード
  useEffect(() => {
    if (selectedDate) {
      loadPredictions(selectedDate);
      loadPurchases(selectedDate);
      setCsvResult(null);
    }
  }, [selectedDate, loadPredictions, loadPurchases]);

  // 買い目生成の実行（SSE経由）
  const executeGenerateBets = async () => {
    setExecuting(true);
    setExecLog([]);
    setExecStatus('running');

    try {
      const res = await fetch('/api/admin/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'vb_refresh',
          date: selectedDate,
        }),
      });

      if (!res.ok) {
        setExecStatus('error');
        setExecLog(prev => [...prev, `Error: ${res.status} ${res.statusText}`]);
        setExecuting(false);
        return;
      }

      const reader = res.body?.getReader();
      if (!reader) {
        setExecStatus('error');
        setExecuting(false);
        return;
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const event = JSON.parse(line.slice(6));
              if (event.type === 'log') {
                setExecLog(prev => [...prev, event.message]);
              } else if (event.type === 'complete') {
                setExecStatus('success');
              } else if (event.type === 'error') {
                setExecStatus('error');
                setExecLog(prev => [...prev, `Error: ${event.message}`]);
              }
            } catch {
              // non-JSON line
            }
          }
        }
      }

      // 完了後、推奨データをリロード
      if (execStatus !== 'error') {
        setExecStatus('success');
      }
      setTimeout(() => {
        loadPredictions(selectedDate);
        loadPurchases(selectedDate);
      }, 1000);
    } catch (err) {
      setExecStatus('error');
      setExecLog(prev => [...prev, `Error: ${String(err)}`]);
    } finally {
      setExecuting(false);
    }
  };

  // ログの自動スクロール
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [execLog]);

  // 日付ナビゲーション
  const dateIndex = availableDates.indexOf(selectedDate);
  const goToPrev = () => {
    if (dateIndex >= 0 && dateIndex < availableDates.length - 1) {
      setSelectedDate(availableDates[dateIndex + 1]);
    }
  };
  const goToNext = () => {
    if (dateIndex > 0) {
      setSelectedDate(availableDates[dateIndex - 1]);
    }
  };

  // intersection の summary
  const intSummary = predictions?.recommendations?.intersection?.summary;
  const totalInvest = recommendations.reduce((s, r) => s + r.win_amount + r.place_amount, 0);

  return (
    <div className="space-y-6">
      {/* 日付選択 + 実行ボタン */}
      <Card>
        <CardContent className="py-4">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-2">
              <Button variant="outline" size="icon" onClick={goToPrev}
                disabled={dateIndex < 0 || dateIndex >= availableDates.length - 1}>
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <div className="flex items-center gap-2">
                <Calendar className="h-5 w-5 text-muted-foreground" />
                <select value={selectedDate}
                  onChange={(e) => setSelectedDate(e.target.value)}
                  className="rounded-md border bg-background px-3 py-2 text-lg font-bold min-w-[160px]">
                  {availableDates.map((d) => (
                    <option key={d} value={d}>{formatDateDisplay(d)}</option>
                  ))}
                  {availableDates.length === 0 && (
                    <option value={selectedDate}>{selectedDate}</option>
                  )}
                </select>
              </div>
              <Button variant="outline" size="icon" onClick={goToNext}
                disabled={dateIndex <= 0}>
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>

            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={() => loadPredictions(selectedDate)}
                disabled={loading}>
                <RefreshCw className={`h-4 w-4 mr-1 ${loading ? 'animate-spin' : ''}`} />
                再読み込み
              </Button>
              <Button onClick={executeGenerateBets} disabled={executing}
                className="bg-indigo-600 hover:bg-indigo-700 text-white">
                {executing ? (
                  <><Loader2 className="h-4 w-4 mr-2 animate-spin" />実行中...</>
                ) : (
                  <><Zap className="h-4 w-4 mr-2" />買い目生成</>
                )}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 実行ログ */}
      {execLog.length > 0 && (
        <Card>
          <CardHeader className="py-3">
            <CardTitle className="text-sm flex items-center gap-2">
              {execStatus === 'running' && <Loader2 className="h-4 w-4 animate-spin text-blue-500" />}
              {execStatus === 'success' && <CheckCircle2 className="h-4 w-4 text-green-500" />}
              {execStatus === 'error' && <XCircle className="h-4 w-4 text-red-500" />}
              実行ログ
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <div ref={logRef}
              className="bg-gray-950 text-gray-300 rounded-md p-3 text-xs font-mono max-h-48 overflow-y-auto">
              {execLog.map((line, i) => (
                <div key={i} className={line.startsWith('Error') ? 'text-red-400' : ''}>
                  {line}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* サマリーカード */}
      {predictions && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <Card>
            <CardContent className="pt-4 pb-3">
              <div className="text-xs text-muted-foreground mb-1">モデル</div>
              <div className="text-xl font-bold">v{predictions.model_version}</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 pb-3">
              <div className="text-xs text-muted-foreground mb-1">Intersection推奨</div>
              <div className="text-xl font-bold text-indigo-600">{recommendations.length}件</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 pb-3">
              <div className="text-xs text-muted-foreground mb-1">他プリセット</div>
              <div className="text-xl font-bold text-gray-500">
                {otherPresets.reduce((s, p) => s + p.betCount, 0)}件
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 pb-3">
              <div className="text-xs text-muted-foreground mb-1">購入済</div>
              {dailyPurchases && dailyPurchases.items.length > 0 ? (
                <div>
                  <div className="text-xl font-bold text-green-600">
                    {dailyPurchases.items.length}件
                  </div>
                  <div className="text-xs text-muted-foreground">
                    ¥{dailyPurchases.total_purchased.toLocaleString()}
                  </div>
                </div>
              ) : (
                <div className="text-xl font-bold text-muted-foreground">—</div>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 pb-3">
              <div className="text-xs text-muted-foreground mb-1">生成日時</div>
              <div className="text-sm font-medium">
                {predictions.bets_generated_at
                  ? new Date(predictions.bets_generated_at).toLocaleString('ja-JP', {
                      month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit',
                    })
                  : predictions.predict_only ? '未生成' : '—'}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* バンクロール連動 */}
      {bankrollBalance !== null && (
        <Card className="border-indigo-200 dark:border-indigo-800">
          <CardContent className="py-3">
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div className="flex items-center gap-4">
                <div>
                  <div className="text-xs text-muted-foreground">バンクロール残高</div>
                  <div className="text-lg font-bold">¥{bankrollBalance.toLocaleString()}</div>
                </div>
                <ArrowRight className="h-4 w-4 text-muted-foreground" />
                <div>
                  <div className="text-xs text-muted-foreground">1ベット推奨額（{betPct}%）</div>
                  <div className="text-lg font-bold text-indigo-600">¥{defaultBetAmount.toLocaleString()}</div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">ベット率:</span>
                {[1, 2, 3, 5].map(pct => (
                  <button
                    key={pct}
                    onClick={() => {
                      setBetPct(pct);
                      localStorage.setItem('keiba_execute_bet_pct', String(pct));
                      setPurchaseAmounts({}); // 金額入力をリセット
                    }}
                    className={`px-2.5 py-1 text-xs rounded border transition-colors ${
                      betPct === pct
                        ? 'bg-indigo-600 text-white border-indigo-600'
                        : 'bg-background border-border hover:border-indigo-400'
                    }`}
                  >
                    {pct}%
                  </button>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 推奨一覧テーブル */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-indigo-600" />
              Intersection Filter 推奨
              <Badge variant="outline" className="ml-2 text-xs">
                rank_w=1 / Gap{'\u2265'}4 / EV{'\u2265'}1.3 / R{'\u2264'}60
              </Badge>
            </CardTitle>
            {recommendations.length > 0 && (
              <div className="flex items-center gap-2">
                {csvResult && (
                  <span className="text-xs text-green-600">
                    {csvResult.totalBets}件 / ¥{csvResult.totalAmount.toLocaleString()} → CSV出力済
                  </span>
                )}
                <Button
                  size="sm"
                  variant="outline"
                  onClick={exportFfCsv}
                  disabled={csvExporting}
                  title="TARGET FF CSV出力（買い目取り込みメニューで読込）"
                  className="text-xs"
                >
                  {csvExporting ? (
                    <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                  ) : (
                    <Download className="h-3.5 w-3.5 mr-1" />
                  )}
                  FF CSV出力
                </Button>
              </div>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-center py-8 text-muted-foreground">読み込み中...</div>
          ) : !predictions ? (
            <div className="text-center py-8">
              <p className="text-muted-foreground">予測データがありません</p>
              <p className="text-sm text-muted-foreground mt-2">
                「買い目生成」を実行するか、predict.py を実行してください
              </p>
            </div>
          ) : recommendations.length === 0 ? (
            <div className="py-6">
              <div className="text-center mb-6">
                <p className="text-muted-foreground">この日は全3条件を満たす馬はいません</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Intersection Filter は月平均3.8回 — 0件の日が多いのは正常です
                </p>
              </div>
              {nearMisses.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-muted-foreground mb-3">
                    惜しかった馬（2条件クリア、1条件不足）
                  </h4>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-xs text-muted-foreground">
                        <th className="py-1.5 px-2 text-left">場</th>
                        <th className="py-1.5 px-1 text-center">R</th>
                        <th className="py-1.5 px-2 text-left">馬名</th>
                        <th className="py-1.5 px-1 text-right">Gap</th>
                        <th className="py-1.5 px-1 text-right">EV</th>
                        <th className="py-1.5 px-1 text-right">R(margin)</th>
                        <th className="py-1.5 px-2 text-left">不足条件</th>
                      </tr>
                    </thead>
                    <tbody>
                      {nearMisses.map((nm) => (
                        <tr key={`${nm.race_id}-${nm.umaban}`}
                          className="border-b text-muted-foreground">
                          <td className="py-1.5 px-2">{nm.venue}</td>
                          <td className="py-1.5 px-1 text-center">{nm.race_number}</td>
                          <td className="py-1.5 px-2">{nm.horse_name}</td>
                          <td className="py-1.5 px-1 text-right font-mono">+{nm.win_vb_gap}</td>
                          <td className="py-1.5 px-1 text-right font-mono">{nm.win_ev.toFixed(2)}</td>
                          <td className="py-1.5 px-1 text-right font-mono">
                            {nm.predicted_margin != null ? nm.predicted_margin.toFixed(1) : '—'}
                          </td>
                          <td className="py-1.5 px-2">
                            <Badge variant="outline" className="text-xs text-amber-600 border-amber-300">
                              {nm.failReason}
                            </Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-xs text-muted-foreground">
                    <th className="py-2 px-2 text-left">場</th>
                    <th className="py-2 px-1 text-center">R</th>
                    <th className="py-2 px-1 text-center">馬番</th>
                    <th className="py-2 px-2 text-left">馬名</th>
                    <th className="py-2 px-1 text-center">強度</th>
                    <th className="py-2 px-1 text-right">Gap</th>
                    <th className="py-2 px-1 text-right">EV</th>
                    <th className="py-2 px-1 text-right">AR</th>
                    <th className="py-2 px-1 text-right">ARd</th>
                    <th className="py-2 px-1 text-right">オッズ</th>
                    <th className="py-2 px-1 text-right">金額</th>
                    <th className="py-2 px-2 text-center">購入</th>
                  </tr>
                </thead>
                <tbody>
                  {recommendations.map((rec) => {
                    const key = getPurchaseKey(rec.race_id, rec.umaban);
                    const existing = findPurchase(rec.race_id, rec.umaban);
                    const isSaving = savingPurchase === key || savingPurchase === existing?.id;
                    const defaultAmount = defaultBetAmount || rec.win_amount || 100;
                    const currentAmount = purchaseAmounts[key] ?? defaultAmount;

                    return (
                      <tr key={key}
                        className={`border-b hover:bg-indigo-50 dark:hover:bg-indigo-950/30 ${getGapBg(rec.win_vb_gap)} ${existing ? 'bg-green-50 dark:bg-green-950/20' : ''}`}>
                        <td className="py-2 px-2 font-medium">{rec.venue}</td>
                        <td className="py-2 px-1 text-center">{rec.race_number}</td>
                        <td className="py-2 px-1 text-center">
                          <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-gray-100 dark:bg-gray-800 font-bold text-sm">
                            {rec.umaban}
                          </span>
                        </td>
                        <td className="py-2 px-2 font-medium">{rec.horse_name}</td>
                        <td className="py-2 px-1 text-center">
                          <Badge variant={rec.strength === 'strong' ? 'default' : 'secondary'}
                            className={rec.strength === 'strong' ? 'bg-indigo-600' : ''}>
                            {rec.strength === 'strong' ? 'S' : 'N'}
                          </Badge>
                        </td>
                        <td className="py-2 px-1 text-right font-mono font-bold text-amber-600">
                          +{rec.win_vb_gap}
                        </td>
                        <td className={`py-2 px-1 text-right font-mono ${getEvColor(rec.win_ev)}`}>
                          {rec.win_ev.toFixed(2)}
                        </td>
                        <td className="py-2 px-1 text-right font-mono text-teal-600">
                          {rec.predicted_margin != null ? rec.predicted_margin.toFixed(1) : '—'}
                        </td>
                        <td className="py-2 px-1 text-right font-mono">
                          {rec.ar_deviation != null ? (
                            <span className={rec.ar_deviation >= 60 ? 'text-green-600 font-semibold' :
                              rec.ar_deviation >= 50 ? 'text-blue-600' : ''}>
                              {rec.ar_deviation.toFixed(1)}
                            </span>
                          ) : '—'}
                        </td>
                        <td className="py-2 px-1 text-right font-mono">{rec.odds.toFixed(1)}</td>
                        <td className="py-2 px-1 text-right font-mono font-bold text-red-600">
                          {rec.win_amount > 0 ? `¥${rec.win_amount.toLocaleString()}` : '—'}
                        </td>
                        <td className="py-2 px-2">
                          {existing ? (
                            <div className="flex items-center gap-1">
                              <Badge className="bg-green-600 text-white text-xs whitespace-nowrap">
                                <Check className="h-3 w-3 mr-0.5" />
                                ¥{existing.amount.toLocaleString()}
                              </Badge>
                              <button
                                onClick={() => cancelPurchase(existing.id)}
                                disabled={isSaving}
                                className="p-0.5 rounded hover:bg-red-100 dark:hover:bg-red-900/30 text-red-400 hover:text-red-600 transition-colors"
                                title="購入取消"
                              >
                                <X className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          ) : (
                            <div className="flex items-center gap-1">
                              <input
                                type="number"
                                value={currentAmount}
                                onChange={(e) => setPurchaseAmounts(prev => ({
                                  ...prev,
                                  [key]: parseInt(e.target.value) || 100,
                                }))}
                                className="w-16 rounded border bg-background px-1.5 py-0.5 text-xs text-right font-mono"
                                step={100}
                                min={100}
                              />
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => recordPurchase(rec)}
                                disabled={isSaving}
                                className="h-7 px-2 text-xs border-green-300 text-green-700 hover:bg-green-50 hover:border-green-500 dark:text-green-400 dark:hover:bg-green-950/30"
                              >
                                {isSaving ? (
                                  <Loader2 className="h-3 w-3 animate-spin" />
                                ) : (
                                  <><ShoppingCart className="h-3 w-3 mr-0.5" />購入</>
                                )}
                              </Button>
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
                {totalInvest > 0 && (
                  <tfoot>
                    <tr className="border-t-2 font-bold">
                      <td colSpan={11} className="py-2 px-2 text-right">合計</td>
                      <td className="py-2 px-1 text-right font-mono text-red-600">
                        ¥{totalInvest.toLocaleString()}
                      </td>
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 購入サマリー */}
      {dailyPurchases && dailyPurchases.items.length > 0 && (
        <Card className="border-green-200 dark:border-green-800">
          <CardHeader className="py-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm flex items-center gap-2 text-green-700 dark:text-green-400">
                <ShoppingCart className="h-4 w-4" />
                本日の購入記録
                <Badge className="bg-green-600 text-white text-xs">{dailyPurchases.items.length}件</Badge>
              </CardTitle>
              <div className="flex items-center gap-2">
                {settleResult && (
                  <span className="text-xs">
                    {settleResult.settled > 0 ? (
                      <span className={settleResult.profit >= 0 ? 'text-green-600' : 'text-red-600'}>
                        {settleResult.settled}件確定 / 的中{settleResult.wins} /
                        {settleResult.profit >= 0 ? ' +' : ' '}¥{settleResult.profit.toLocaleString()}
                      </span>
                    ) : (
                      <span className="text-muted-foreground">確定対象なし</span>
                    )}
                  </span>
                )}
                {dailyPurchases.items.some(i => i.status === 'purchased') && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={settleResults}
                    disabled={settling}
                    className="text-xs border-amber-300 text-amber-700 hover:bg-amber-50 hover:border-amber-500 dark:text-amber-400 dark:hover:bg-amber-950/30"
                  >
                    {settling ? (
                      <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                    ) : (
                      <Trophy className="h-3.5 w-3.5 mr-1" />
                    )}
                    結果反映
                  </Button>
                )}
              </div>
            </div>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="grid grid-cols-3 gap-4 mb-3">
              <div>
                <div className="text-xs text-muted-foreground">投資額</div>
                <div className="text-lg font-bold text-red-600">
                  ¥{dailyPurchases.total_purchased.toLocaleString()}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">払戻</div>
                <div className="text-lg font-bold text-green-600">
                  ¥{dailyPurchases.total_payout.toLocaleString()}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">損益</div>
                <div className={`text-lg font-bold ${dailyPurchases.total_payout - dailyPurchases.total_purchased >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {dailyPurchases.total_payout - dailyPurchases.total_purchased >= 0 ? '+' : ''}
                  ¥{(dailyPurchases.total_payout - dailyPurchases.total_purchased).toLocaleString()}
                </div>
              </div>
            </div>
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b text-muted-foreground">
                  <th className="py-1 px-1 text-left">レース</th>
                  <th className="py-1 px-1 text-left">馬券</th>
                  <th className="py-1 px-1 text-right">金額</th>
                  <th className="py-1 px-1 text-right">オッズ</th>
                  <th className="py-1 px-1 text-center">結果</th>
                  <th className="py-1 px-1 text-right">払戻</th>
                </tr>
              </thead>
              <tbody>
                {dailyPurchases.items.map((item) => (
                  <tr key={item.id} className="border-b last:border-0">
                    <td className="py-1 px-1">{item.race_name}</td>
                    <td className="py-1 px-1">{item.bet_type} {item.selection}</td>
                    <td className="py-1 px-1 text-right font-mono">¥{item.amount.toLocaleString()}</td>
                    <td className="py-1 px-1 text-right font-mono">{item.odds?.toFixed(1) ?? '—'}</td>
                    <td className="py-1 px-1 text-center">
                      {item.status === 'result_win' && <Badge className="bg-green-600 text-white text-xs">的中</Badge>}
                      {item.status === 'result_lose' && <Badge variant="secondary" className="text-xs">不的中</Badge>}
                      {item.status === 'purchased' && <Badge variant="outline" className="text-xs">未確定</Badge>}
                      {item.status === 'planned' && <Badge variant="outline" className="text-xs text-gray-400">予定</Badge>}
                    </td>
                    <td className="py-1 px-1 text-right font-mono">
                      {item.payout > 0 ? `¥${item.payout.toLocaleString()}` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {/* ニアミス（推奨があっても表示） */}
      {recommendations.length > 0 && nearMisses.length > 0 && (
        <Card>
          <CardHeader className="py-3">
            <CardTitle className="text-sm text-muted-foreground">
              惜しかった馬（2条件クリア、1条件不足）
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-xs text-muted-foreground">
                  <th className="py-1.5 px-2 text-left">場</th>
                  <th className="py-1.5 px-1 text-center">R</th>
                  <th className="py-1.5 px-2 text-left">馬名</th>
                  <th className="py-1.5 px-1 text-right">Gap</th>
                  <th className="py-1.5 px-1 text-right">EV</th>
                  <th className="py-1.5 px-1 text-right">R(margin)</th>
                  <th className="py-1.5 px-2 text-left">不足条件</th>
                </tr>
              </thead>
              <tbody>
                {nearMisses.map((nm) => (
                  <tr key={`${nm.race_id}-${nm.umaban}`}
                    className="border-b text-muted-foreground">
                    <td className="py-1.5 px-2">{nm.venue}</td>
                    <td className="py-1.5 px-1 text-center">{nm.race_number}</td>
                    <td className="py-1.5 px-2">{nm.horse_name}</td>
                    <td className="py-1.5 px-1 text-right font-mono">+{nm.win_vb_gap}</td>
                    <td className="py-1.5 px-1 text-right font-mono">{nm.win_ev.toFixed(2)}</td>
                    <td className="py-1.5 px-1 text-right font-mono">
                      {nm.predicted_margin != null ? nm.predicted_margin.toFixed(1) : '—'}
                    </td>
                    <td className="py-1.5 px-2">
                      <Badge variant="outline" className="text-xs text-amber-600 border-amber-300">
                        {nm.failReason}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {/* 他プリセット参考情報 */}
      {otherPresets.length > 0 && (
        <Card>
          <CardHeader className="py-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Layers className="h-4 w-4 text-gray-500" />
              参考: 他プリセット推奨
              <Badge variant="outline" className="text-xs">
                {otherPresets.reduce((s, p) => s + p.betCount, 0)}件
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0 space-y-2">
            {otherPresets.map((preset) => {
              const isExpanded = expandedPresets.has(preset.key);
              return (
                <div key={preset.key} className="border rounded-md">
                  <button
                    onClick={() => setExpandedPresets(prev => {
                      const next = new Set(prev);
                      if (next.has(preset.key)) next.delete(preset.key);
                      else next.add(preset.key);
                      return next;
                    })}
                    className="w-full flex items-center justify-between px-3 py-2 text-sm hover:bg-muted/50 transition-colors"
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{preset.label}</span>
                      <Badge variant="secondary" className="text-xs">
                        {preset.betCount}件
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        ¥{preset.totalAmount.toLocaleString()}
                      </span>
                    </div>
                    {isExpanded ? (
                      <ChevronUp className="h-4 w-4 text-muted-foreground" />
                    ) : (
                      <ChevronDown className="h-4 w-4 text-muted-foreground" />
                    )}
                  </button>
                  {isExpanded && (
                    <div className="border-t px-3 pb-2 overflow-x-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="border-b text-muted-foreground">
                            <th className="py-1.5 px-1 text-left">場</th>
                            <th className="py-1.5 px-1 text-center">R</th>
                            <th className="py-1.5 px-1 text-center">番</th>
                            <th className="py-1.5 px-1 text-left">馬名</th>
                            <th className="py-1.5 px-1 text-right">Gap</th>
                            <th className="py-1.5 px-1 text-right">EV</th>
                            <th className="py-1.5 px-1 text-right">ARd</th>
                            <th className="py-1.5 px-1 text-right">オッズ</th>
                            <th className="py-1.5 px-1 text-right">金額</th>
                          </tr>
                        </thead>
                        <tbody>
                          {preset.bets.map((b) => (
                            <tr key={`${b.race_id}-${b.umaban}`} className="border-b last:border-0 hover:bg-muted/30">
                              <td className="py-1 px-1">{b.venue}</td>
                              <td className="py-1 px-1 text-center">{b.race_number}</td>
                              <td className="py-1 px-1 text-center">{b.umaban}</td>
                              <td className="py-1 px-1">{b.horse_name}</td>
                              <td className="py-1 px-1 text-right font-mono">
                                {b.win_vb_gap > 0 ? `+${b.win_vb_gap}` : b.win_vb_gap}
                              </td>
                              <td className={`py-1 px-1 text-right font-mono ${getEvColor(b.win_ev)}`}>
                                {b.win_ev.toFixed(2)}
                              </td>
                              <td className="py-1 px-1 text-right font-mono">
                                {b.ar_deviation != null ? b.ar_deviation.toFixed(1) : '—'}
                              </td>
                              <td className="py-1 px-1 text-right font-mono">{b.odds.toFixed(1)}</td>
                              <td className="py-1 px-1 text-right font-mono text-red-600">
                                ¥{((b.win_amount || 0) + (b.place_amount || 0)).toLocaleString()}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}

      {/* 戦略の説明 */}
      <Card>
        <CardContent className="py-4">
          <div className="text-xs text-muted-foreground space-y-1">
            <p><strong>Intersection Filter</strong> — v7.3バックテスト実証済み (2025-03〜2026-02, 3,364レース)</p>
            <p>ROI 310.7% / 的中率 19.6% / 年間46ベット / 月平均3.8回</p>
            <p>推奨配分: 資金の2%（MaxDD 14%, 年間+340%成長）</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
