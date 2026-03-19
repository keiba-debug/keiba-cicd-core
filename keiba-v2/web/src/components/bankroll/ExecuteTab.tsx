'use client';

import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Zap, Play, Loader2, CheckCircle2, XCircle,
  ChevronLeft, ChevronRight, Calendar, RefreshCw,
  ArrowRight, TrendingUp, ChevronDown, ChevronUp, Layers,
  Download, Bookmark, BookmarkCheck,
} from 'lucide-react';
import type { MultiLegRecommendation, PredictionRace } from '@/lib/data/predictions-reader';
import { MultiLegRecommendations } from '@/app/predictions/components/multi-leg-recommendations';

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
  track_type?: string;
  bet_type?: string;
  place_ev?: number | null;
  vb_score?: number | null;
  wide_pair?: number[] | null;
  wide_source?: string | null;  // '障害' | '激戦'
  kelly_amount?: number | null;
  kelly_capped?: number | null; // adaptive Kelly fraction (0.33/0.25/0.125)
  adaptive_rule?: string | null; // 'danger_sniper' | 'high_ev_win' | 'relaxed_base'
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
      place_ev?: number | null;
      ar_deviation?: number;
      pred_proba_w_cal?: number;
      wide_pair?: number[] | null;
      wide_source?: string | null;
      track_type?: string;
      kelly_win_frac?: number;
      kelly_amount?: number;
      kelly_capped?: number;
      market_signal?: string;
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
    track_type?: string;
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
  finish_positions?: Record<string, Record<number, number>>; // race_id -> {umaban: finish_position}
  multi_leg_recommendations?: MultiLegRecommendation[];
  sanrentan_formation?: MultiLegRecommendation[];
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
    track_type?: string;
    bet_type?: string;
    place_ev?: number | null;
    vb_score?: number | null;
  }>;
}

// プリセットのラベル定義
const PRESET_LABELS: Record<string, string> = {
  standard: 'Standard (VBスコア)',
  wide: 'Wide (緩め)',
  aggressive: 'Aggressive (攻め)',
  adaptive: '螺旋丸 (傾斜Kelly)',
  intersection: 'Intersection',
  relaxed: 'Relaxed (Gap≥3×EV≥1)',
  simple: 'Simple (1位×Gap≥4)',
  simple_ev2: 'Simple EV2 (1位×EV≥2)',
  simple_wide: 'Simple Wide (1位×Gap≥3)',
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

  // プリセット切替
  const [activePreset, setActivePreset] = useState<string>('adaptive');
  const [allPresetsMap, setAllPresetsMap] = useState<Record<string, RecommendationEntry[]>>({});

  // レース番号フィルタ（0=全レース）
  const [raceRangeMin, setRaceRangeMin] = useState(0);
  const [raceRangeMax, setRaceRangeMax] = useState(0);

  // バンクロール残高 & 推奨購入額
  const [bankrollBalance, setBankrollBalance] = useState<number | null>(null);
  const [betPct, setBetPct] = useState(2); // 資金の何%をベットするか（デフォルト2%）
  const defaultBetAmount = bankrollBalance !== null
    ? Math.floor((bankrollBalance * betPct / 100) / 100) * 100 // 100円単位に切り下げ
    : 100;

  // FF CSV出力
  const [csvExporting, setCsvExporting] = useState(false);
  const [csvResult, setCsvResult] = useState<{ totalBets: number; winBets: number; totalAmount: number; filePath: string } | null>(null);

  // 買い確定
  const [confirmedBets, setConfirmedBets] = useState<import('@/app/api/bankroll/confirmed-bets/route').ConfirmedBet[]>([]);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);

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
          // 直近の日付をデフォルト（未来7日以内も含む＝前日準備対応）
          const todayStr = today;
          const weekLater = new Date();
          weekLater.setDate(weekLater.getDate() + 7);
          const weekLaterStr = weekLater.toISOString().slice(0, 10);
          const nearFuture = dates.filter((d: string) => d >= todayStr && d <= weekLaterStr).pop();
          const defaultDate = nearFuture || dates.find((d: string) => d <= todayStr) || dates[0];
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
            bet_type: b.bet_type,
            wide_pair: b.wide_pair,
            wide_source: b.wide_source,
            track_type: b.track_type ?? race?.track_type,
            vb_score: b.vb_score ?? null,
            place_ev: b.place_ev ?? null,
            kelly_amount: b.kelly_amount ?? null,
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

      // 全プリセットの推奨をマップとして保持
      const presetsMap: Record<string, RecommendationEntry[]> = {};
      const others: OtherPresetData[] = [];

      if (data.recommendations) {
        for (const [key, preset] of Object.entries(data.recommendations)) {
          if (!preset || !preset.bets || preset.bets.length === 0) continue;

          const mappedBets = preset.bets.map((b) => {
            const race = data.races?.find(r => r.race_id === b.race_id);
            return {
              race_id: b.race_id,
              venue: b.venue || race?.venue_name || '',
              race_number: b.race_number || race?.race_number || 0,
              umaban: b.umaban,
              horse_name: b.horse_name,
              odds: b.odds,
              rank_w: (key === 'intersection' ? 1 : 0),
              win_vb_gap: b.win_gap ?? b.gap ?? 0,
              win_ev: b.win_ev ?? 0,
              predicted_margin: b.predicted_margin ?? null,
              ar_deviation: b.ar_deviation ?? null,
              pred_proba_w_cal: b.pred_proba_w_cal ?? null,
              win_amount: b.win_amount,
              place_amount: b.place_amount,
              strength: b.strength,
              track_type: race?.track_type,
              bet_type: b.bet_type || '単勝',
              wide_pair: b.wide_pair ?? null,
              wide_source: b.wide_source ?? null,
              place_ev: b.place_ev ?? null,
              vb_score: b.vb_score ?? null,
              kelly_amount: b.kelly_amount ?? null,
              kelly_capped: b.kelly_capped ?? null,
              adaptive_rule: b.market_signal?.startsWith('rule:') ? b.market_signal.slice(5) : null,
            } as RecommendationEntry;
          });

          mappedBets.sort((a, b) => {
            if (a.race_number !== b.race_number) return a.race_number - b.race_number;
            if (a.venue !== b.venue) return a.venue.localeCompare(b.venue);
            return a.umaban - b.umaban;
          });
          presetsMap[key] = mappedBets;

          if (key !== 'intersection') {
            others.push({
              key,
              label: PRESET_LABELS[key] || key,
              betCount: preset.bets.length,
              totalAmount: preset.summary?.total_amount ?? preset.bets.reduce((s, b) => s + (b.win_amount || 0) + (b.place_amount || 0), 0),
              bets: mappedBets,
            });
          }
        }
        others.sort((a, b) => b.betCount - a.betCount);
      }
      setAllPresetsMap(presetsMap);
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

  // 全推奨マージ（union）
  const allMergedRecs = useMemo((): RecommendationEntry[] => {
    const seen = new Map<string, RecommendationEntry>();
    for (const entries of Object.values(allPresetsMap)) {
      for (const e of entries) {
        // ワイド/馬連はペア情報でユニーク化、それ以外はumaban
        const key = e.wide_pair
          ? `${e.race_id}-${e.bet_type}-W${e.wide_pair[0]}-${e.wide_pair[1]}`
          : `${e.race_id}-${e.umaban}`;
        const existing = seen.get(key);
        if (!existing || (e.win_amount + e.place_amount) > (existing.win_amount + existing.place_amount)) {
          seen.set(key, e);
        }
      }
    }
    return Array.from(seen.values()).sort((a, b) => {
      if (a.race_number !== b.race_number) return a.race_number - b.race_number;
      if (a.venue !== b.venue) return a.venue.localeCompare(b.venue);
      return a.umaban - b.umaban;
    });
  }, [allPresetsMap]);

  // 表示する推奨リスト（プリセット + レース番号フィルタ）
  const displayRecs = useMemo(() => {
    const base = allPresetsMap[activePreset] || [];
    if (raceRangeMin === 0 && raceRangeMax === 0) return base;
    return base.filter(r => {
      if (raceRangeMin > 0 && r.race_number < raceRangeMin) return false;
      if (raceRangeMax > 0 && r.race_number > raceRangeMax) return false;
      return true;
    });
  }, [activePreset, allMergedRecs, recommendations, allPresetsMap, raceRangeMin, raceRangeMax]);

  // FF CSV出力（TARGET買い目取り込み用）
  // 常に画面の推奨リスト(displayRecs)から生成 — 画面=CSVを保証
  const exportFfCsv = async () => {
    const bets: { raceId: string; umaban: number; umaban2?: number; betType: number; amount: number }[] = [];

    for (const rec of displayRecs) {
      const amount = getRecAmount(rec);

      if (rec.bet_type === 'ワイド' && rec.wide_pair && rec.wide_pair.length === 2) {
        bets.push({
          raceId: rec.race_id,
          umaban: rec.wide_pair[0],
          umaban2: rec.wide_pair[1],
          betType: 4,
          amount,
        });
      } else if (rec.bet_type === '馬連' && rec.wide_pair && rec.wide_pair.length === 2) {
        bets.push({
          raceId: rec.race_id,
          umaban: rec.wide_pair[0],
          umaban2: rec.wide_pair[1],
          betType: 3,
          amount,
        });
      } else if (rec.bet_type === '馬単' && rec.wide_pair && rec.wide_pair.length === 2) {
        bets.push({
          raceId: rec.race_id,
          umaban: rec.wide_pair[0],   // 1着候補
          umaban2: rec.wide_pair[1],  // 2着候補
          betType: 5,
          amount,
        });
      } else if (rec.bet_type === 'ワイド' || rec.bet_type === '馬連' || rec.bet_type === '馬単') {
        console.warn(`[FF CSV] ${rec.bet_type}にwide_pairなし、スキップ: ${rec.race_id}`);
      } else if (rec.bet_type === '単複') {
        // 単複 → 単勝+複勝の2行。金額を半分ずつ
        const halfAmt = Math.max(Math.floor(amount / 2 / 100) * 100, 100);
        const winAmt = halfAmt;
        const placeAmt = halfAmt;
        bets.push({ raceId: rec.race_id, umaban: rec.umaban, betType: 0, amount: winAmt });
        bets.push({ raceId: rec.race_id, umaban: rec.umaban, betType: 1, amount: placeAmt });
      } else {
        bets.push({
          raceId: rec.race_id,
          umaban: rec.umaban,
          betType: (rec.bet_type === '複勝') ? 1 : 0,
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
      setCsvResult(null);
      // 確定betもリロード
      fetch(`/api/bankroll/confirmed-bets?date=${selectedDate}`)
        .then(r => r.ok ? r.json() : { bets: [] })
        .then(d => setConfirmedBets(d.bets ?? []))
        .catch(() => setConfirmedBets([]));
    }
  }, [selectedDate, loadPredictions]);

  // 確定ベットのIDを生成
  const makeConfirmedId = (rec: RecommendationEntry) => {
    const pair = rec.wide_pair ? `W${rec.wide_pair[0]}-${rec.wide_pair[1]}` : String(rec.umaban);
    return `${rec.race_id}-${rec.bet_type}-${pair}`;
  };

  // 確定ボタン押下（トグル: 確定/解除）
  const toggleConfirmBet = async (rec: RecommendationEntry) => {
    const id = makeConfirmedId(rec);
    setConfirmingId(id);
    try {
      const payload = {
        id,
        confirmed_at: new Date().toISOString(),
        date: selectedDate,
        race_id: rec.race_id,
        venue: rec.venue,
        race_number: rec.race_number,
        umaban: rec.umaban,
        horse_name: rec.horse_name,
        bet_type: rec.bet_type,
        wide_pair: rec.wide_pair ?? null,
        wide_source: rec.wide_source ?? null,
        odds_at_confirm: rec.odds,
        ev_at_confirm: rec.win_ev,
        gap_at_confirm: rec.win_vb_gap,
        ar_deviation: rec.ar_deviation ?? null,
        pred_proba_w: rec.pred_proba_w_cal ?? null,
        amount: getRecAmount(rec),
        preset: activePreset,
        adaptive_rule: rec.adaptive_rule ?? null,
      };
      const res = await fetch('/api/bankroll/confirmed-bets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      setConfirmedBets(data.bets ?? []);
    } finally {
      setConfirmingId(null);
    }
  };

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

  // adaptive: Kelly率ベースの傾斜配分 (K1/3の馬に2.6倍、K1/4に2倍)
  // 非adaptive: Kelly額 vs デフォルト均等額の大きい方
  const getRecAmount = useCallback((r: RecommendationEntry): number => {
    if (activePreset === 'adaptive' && bankrollBalance != null && bankrollBalance > 0) {
      const kc = r.kelly_capped ?? 0;
      // Kelly率がある単勝: bankroll × betPct% × kelly_capped で計算
      if (kc > 0) {
        const amt = Math.floor(bankrollBalance * (betPct / 100) * kc / 100) * 100;
        return Math.max(100, amt);
      }
      // ワイド/馬連等(kelly_capped=0): Python bet_engine計算済みkelly_amountをバンクロール比率でスケール
      const kellyAmt = r.kelly_amount || 0;
      if (kellyAmt > 0) {
        // Python側はbankroll=100,000で計算 → 実バンクロールに比例スケール
        const scaledAmt = Math.floor(kellyAmt * (bankrollBalance / 100000) / 100) * 100;
        return Math.max(100, scaledAmt);
      }
      const defAmt = defaultBetAmount || r.win_amount || 100;
      return Math.max(100, defAmt);
    }
    const kellyAmt = r.kelly_amount || 0;
    const defAmt = defaultBetAmount || r.win_amount || 100;
    return Math.max(kellyAmt, defAmt);
  }, [activePreset, bankrollBalance, betPct, defaultBetAmount]);

  // 表示中の合計投資額
  const totalInvest = displayRecs.reduce((s, r) => s + getRecAmount(r), 0);

  // 全推奨サマリー計算
  const allSummary = useMemo(() => {
    const winCount = displayRecs.filter(r => r.bet_type === '単勝' || r.bet_type === '単複').length;
    const placeCount = displayRecs.filter(r => r.bet_type === '複勝' || r.bet_type === '単複').length;
    const obstacleCount = displayRecs.filter(r => r.track_type === 'obstacle').length;
    const wideCount = displayRecs.filter(r => r.bet_type === 'ワイド').length;
    const umarenCount = displayRecs.filter(r => r.bet_type === '馬連').length;
    const umatanCount = displayRecs.filter(r => r.bet_type === '馬単').length;
    const gekisenWideCount = displayRecs.filter(r => r.bet_type === 'ワイド' && r.wide_source === '激戦').length;
    return { winCount, placeCount, obstacleCount, wideCount, umarenCount, umatanCount, gekisenWideCount };
  }, [displayRecs]);

  // プリセット選択肢: シミュレーションで黒字確認済みのみ
  // adaptive: K1/8 ROI+99%, K1/4 ROI+134% (Kelly率傾斜配分)
  // relaxed: K1/8 ROI+53%, K1/4 ROI+128% (均等Kelly)
  // intersection: K1/8 ROI+42%, K1/4 ROI+98%
  const PRESET_CHOICES = ['adaptive', 'relaxed', 'intersection'] as const;

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

      {/* プリセット切替 + サマリー */}
      {predictions && (
        <>
          {/* プリセットセレクター */}
          <div className="flex items-center gap-2 flex-wrap">
            {PRESET_CHOICES.map(key => {
              const count = allPresetsMap[key]?.length ?? 0;
              return (
                <button
                  key={key}
                  onClick={() => setActivePreset(key)}
                  className={`px-3 py-1.5 text-xs rounded-full border transition-colors ${
                    activePreset === key
                      ? 'bg-primary text-primary-foreground border-primary'
                      : 'bg-muted/40 text-muted-foreground border-transparent hover:bg-muted'
                  }`}
                >
                  {PRESET_LABELS[key] || key}
                  {count > 0 && <span className="ml-1 opacity-75">({count})</span>}
                </button>
              );
            })}

            {/* レース番号フィルタ */}
            <div className="flex items-center gap-1.5 ml-auto">
              <span className="text-xs text-muted-foreground">R:</span>
              {[
                { label: '全', min: 0, max: 0 },
                { label: '1-4', min: 1, max: 4 },
                { label: '5-8', min: 5, max: 8 },
                { label: '9-12', min: 9, max: 12 },
              ].map(({ label, min, max }) => {
                const isActive = raceRangeMin === min && raceRangeMax === max;
                return (
                  <button
                    key={label}
                    onClick={() => { setRaceRangeMin(min); setRaceRangeMax(max); }}
                    className={`px-2 py-1 text-xs rounded border transition-colors ${
                      isActive
                        ? 'bg-indigo-600 text-white border-indigo-600'
                        : 'bg-muted/40 text-muted-foreground border-transparent hover:bg-muted'
                    }`}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* サマリーカード */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <Card>
              <CardContent className="pt-4 pb-3">
                <div className="text-xs text-muted-foreground mb-1">モデル</div>
                <div className="text-xl font-bold">v{predictions.model_version}</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4 pb-3">
                <div className="text-xs text-muted-foreground mb-1">表示中の推奨</div>
                <div className="text-xl font-bold text-indigo-600">{displayRecs.length}件</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4 pb-3">
                <div className="text-xs text-muted-foreground mb-1">全推奨(union)</div>
                <div className="text-xl font-bold text-gray-500">
                  {allMergedRecs.length}件
                </div>
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
        </>
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
                  <div className="text-xs text-muted-foreground">均等{betPct}% / Kelly 1/4</div>
                  <div className="text-lg font-bold text-indigo-600">¥{defaultBetAmount.toLocaleString()}</div>
                  <div className="text-[10px] text-muted-foreground">Kelly額はEV×オッズから自動計算</div>
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
              {(PRESET_LABELS[activePreset] || activePreset) + ' 推奨'}
            </CardTitle>
            {displayRecs.length > 0 && (
              <div className="flex items-center gap-2">
                {csvResult && (
                  <span className="text-xs text-green-600">
                    {displayRecs.length}推奨({csvResult.totalBets}行) / ¥{csvResult.totalAmount.toLocaleString()} → CSV出力済
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
          ) : displayRecs.length === 0 ? (
            <div className="py-6">
              <div className="text-center mb-6">
                <p className="text-muted-foreground">
                  {`${PRESET_LABELS[activePreset] || activePreset} の推奨はありません`}
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  厳選プリセットは月数回 — 0件の日が多いのは正常です
                </p>
              </div>
              {activePreset === 'intersection' && nearMisses.length > 0 && (
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
                      {nearMisses.map((nm, idx) => (
                        <tr key={`${nm.race_id}-${nm.umaban}-nm${idx}`}
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
            <>
            {/* 全推奨サマリー */}
            {activePreset === 'all' && displayRecs.length > 0 && (
              <div className="grid grid-cols-5 gap-3 mb-4">
                <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold">{displayRecs.length}</div>
                  <div className="text-xs text-muted-foreground">推奨馬券</div>
                </div>
                <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold">{allSummary.winCount}</div>
                  <div className="text-xs text-muted-foreground">単勝</div>
                </div>
                <div className="bg-purple-50 dark:bg-purple-900/20 rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold">{allSummary.placeCount}</div>
                  <div className="text-xs text-muted-foreground">複勝含</div>
                </div>
                <div className="bg-amber-50 dark:bg-amber-900/20 rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold">{allSummary.obstacleCount}</div>
                  <div className="text-xs text-muted-foreground">障害</div>
                </div>
                {allSummary.wideCount > 0 && (
                  <div className="bg-fuchsia-50 dark:bg-fuchsia-900/20 rounded-lg p-3 text-center">
                    <div className="text-2xl font-bold">{allSummary.wideCount}</div>
                    <div className="text-xs text-muted-foreground">ワイド</div>
                  </div>
                )}
                {allSummary.umarenCount > 0 && (
                  <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3 text-center">
                    <div className="text-2xl font-bold">{allSummary.umarenCount}</div>
                    <div className="text-xs text-muted-foreground">馬連</div>
                  </div>
                )}
                {allSummary.umatanCount > 0 && (
                  <div className="bg-orange-50 dark:bg-orange-900/20 rounded-lg p-3 text-center">
                    <div className="text-2xl font-bold">{allSummary.umatanCount}</div>
                    <div className="text-xs text-muted-foreground">馬単</div>
                  </div>
                )}
                {allSummary.gekisenWideCount > 0 && (
                  <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-3 text-center">
                    <div className="text-2xl font-bold">{allSummary.gekisenWideCount}</div>
                    <div className="text-xs text-muted-foreground">激戦W</div>
                  </div>
                )}
              </div>
            )}
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-xs text-muted-foreground">
                    <th className="py-2 px-2 text-left">場</th>
                    <th className="py-2 px-1 text-center">R</th>
                    <th className="py-2 px-1 text-center">馬番</th>
                    <th className="py-2 px-2 text-left">馬名</th>
                    <th className="py-2 px-1 text-center">券種</th>
                    <th className="py-2 px-1 text-center">強度</th>
                    <th className="py-2 px-1 text-right">Gap</th>
                    {activePreset !== 'intersection' && (
                      <th className="py-2 px-1 text-right">VBs</th>
                    )}
                    <th className="py-2 px-1 text-right">EV</th>
                    <th className="py-2 px-1 text-right">複EV</th>
                    <th className="py-2 px-1 text-right">AR</th>
                    <th className="py-2 px-1 text-right">ARd</th>
                    <th className="py-2 px-1 text-right">オッズ</th>
                    <th className="py-2 px-1 text-right">金額</th>
                    <th className="py-2 px-1 text-center">着順</th>
                    <th className="py-2 px-1 text-center">結果</th>
                    <th className="py-2 px-1 text-center">確定</th>
                  </tr>
                </thead>
                <tbody>
                  {displayRecs.map((rec, idx) => {
                    const recAmount = getRecAmount(rec);
                    const fp = predictions?.finish_positions;
                    // 着順取得
                    const finish1 = fp?.[rec.race_id]?.[rec.umaban] ?? null;
                    const finish2 = rec.wide_pair ? fp?.[rec.race_id]?.[rec.wide_pair[1]] ?? null : null;
                    // 的中判定
                    let isHit: boolean | null = null;
                    if (fp?.[rec.race_id]) {
                      if (rec.bet_type === 'ワイド' || rec.bet_type === '馬連') {
                        const f1 = rec.wide_pair ? fp[rec.race_id]?.[rec.wide_pair[0]] : null;
                        const f2 = rec.wide_pair ? fp[rec.race_id]?.[rec.wide_pair[1]] : null;
                        if (f1 != null && f2 != null && f1 > 0 && f2 > 0) {
                          if (rec.bet_type === 'ワイド') {
                            isHit = f1 <= 3 && f2 <= 3;
                          } else {
                            isHit = (f1 === 1 && f2 === 2) || (f1 === 2 && f2 === 1);
                          }
                        }
                      } else if (rec.bet_type === '単勝' || rec.bet_type === '単複') {
                        if (finish1 != null && finish1 > 0) isHit = finish1 === 1;
                      } else if (rec.bet_type === '複勝') {
                        if (finish1 != null && finish1 > 0) isHit = finish1 <= 3;
                      }
                    }
                    const rowKey = rec.wide_pair
                      ? `${rec.race_id}-${rec.bet_type}-W${rec.wide_pair[0]}-${rec.wide_pair[1]}`
                      : `${rec.race_id}-${rec.umaban}`;

                    return (
                      <tr key={`${rowKey}-${idx}`}
                        className={`border-b hover:bg-indigo-50 dark:hover:bg-indigo-950/30 ${isHit === true ? 'bg-green-50 dark:bg-green-950/20' : ''} ${getGapBg(rec.win_vb_gap)}`}>
                        <td className="py-2 px-2 font-medium">
                          {rec.venue}
                          {rec.track_type === 'obstacle' && (
                            <span className="ml-1 text-[10px] px-1 py-0.5 rounded bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300">
                              障害
                            </span>
                          )}
                        </td>
                        <td className="py-2 px-1 text-center">{rec.race_number}</td>
                        <td className="py-2 px-1 text-center">
                          {(rec.bet_type === 'ワイド' || rec.bet_type === '馬連') && rec.wide_pair ? (
                            <span className="inline-flex items-center gap-0.5">
                              <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full font-bold text-xs ${rec.bet_type === '馬連' ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700' : 'bg-purple-100 dark:bg-purple-900/30 text-purple-700'}`}>
                                {rec.wide_pair[0]}
                              </span>
                              <span className="text-[10px] text-muted-foreground">-</span>
                              <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full font-bold text-xs ${rec.bet_type === '馬連' ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700' : 'bg-purple-100 dark:bg-purple-900/30 text-purple-700'}`}>
                                {rec.wide_pair[1]}
                              </span>
                            </span>
                          ) : (
                            <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-gray-100 dark:bg-gray-800 font-bold text-sm">
                              {rec.umaban}
                            </span>
                          )}
                        </td>
                        <td className="py-2 px-2 font-medium">{rec.horse_name}</td>
                        <td className="py-2 px-1 text-center">
                          {rec.bet_type === 'ワイド' ? (
                            <Badge variant="outline" className={`text-[10px] border-purple-400 text-purple-600 ${rec.wide_source === '激戦' ? 'bg-red-50 border-red-400 text-red-600' : 'bg-purple-50'}`}>
                              {rec.wide_source === '激戦' ? '激戦W' : rec.wide_source === '障害' ? '障害W' : 'ワイド'}
                            </Badge>
                          ) : rec.bet_type === '馬連' ? (
                            <Badge variant="outline" className="text-[10px] border-blue-400 text-blue-600 bg-blue-50">
                              {rec.wide_source === '障害' ? '障害連' : '馬連'}
                            </Badge>
                          ) : rec.bet_type && rec.bet_type !== '単勝' ? (
                            <Badge variant="outline" className="text-[10px]">{rec.bet_type}</Badge>
                          ) : rec.adaptive_rule ? (
                            <Badge variant="outline" className={`text-[10px] ${
                              rec.adaptive_rule === 'danger_sniper' ? 'border-red-400 text-red-600 bg-red-50' :
                              rec.adaptive_rule === 'high_ev_win' ? 'border-amber-400 text-amber-600 bg-amber-50' :
                              'border-gray-300 text-muted-foreground'
                            }`}>
                              {rec.adaptive_rule === 'danger_sniper' ? '狙撃' :
                               rec.adaptive_rule === 'high_ev_win' ? '高EV' : '単勝'}
                            </Badge>
                          ) : (
                            <span className="text-xs text-muted-foreground">単勝</span>
                          )}
                        </td>
                        <td className="py-2 px-1 text-center">
                          <Badge variant={rec.strength === 'strong' ? 'default' : 'secondary'}
                            className={rec.strength === 'strong' ? 'bg-indigo-600' : ''}>
                            {rec.strength === 'strong' ? 'S' : 'N'}
                          </Badge>
                        </td>
                        <td className="py-2 px-1 text-right font-mono font-bold text-amber-600">
                          +{rec.win_vb_gap}
                        </td>
                        {activePreset !== 'intersection' && (
                          <td className="py-2 px-1 text-right font-mono">
                            {rec.vb_score != null ? (
                              <span className={rec.vb_score >= 7 ? 'text-indigo-600 font-bold' :
                                rec.vb_score >= 5 ? 'text-blue-600 font-semibold' : ''}>
                                {rec.vb_score.toFixed(1)}
                              </span>
                            ) : '—'}
                          </td>
                        )}
                        <td className={`py-2 px-1 text-right font-mono ${getEvColor(rec.win_ev)}`}>
                          {rec.win_ev.toFixed(2)}
                        </td>
                        <td className="py-2 px-1 text-right font-mono">
                          {rec.place_ev != null && rec.place_ev > 0 ? (
                            <span className={rec.place_ev >= 1.5 ? 'text-purple-600 font-semibold' :
                              rec.place_ev >= 1.0 ? 'text-purple-500' : 'text-muted-foreground'}>
                              {rec.place_ev.toFixed(2)}
                            </span>
                          ) : '—'}
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
                        <td className="py-2 px-1 text-right font-mono font-bold text-orange-600">
                          ¥{recAmount.toLocaleString()}
                        </td>
                        <td className="py-2 px-1 text-center font-mono text-xs">
                          {(rec.bet_type === 'ワイド' || rec.bet_type === '馬連') && rec.wide_pair ? (
                            fp?.[rec.race_id] ? (
                              <span>
                                <span className={fp[rec.race_id]?.[rec.wide_pair[0]] != null && fp[rec.race_id][rec.wide_pair[0]] <= 3 ? 'text-green-600 font-bold' : ''}>
                                  {fp[rec.race_id]?.[rec.wide_pair[0]] || '—'}
                                </span>
                                <span className="text-muted-foreground">-</span>
                                <span className={fp[rec.race_id]?.[rec.wide_pair[1]] != null && fp[rec.race_id][rec.wide_pair[1]] <= 3 ? 'text-green-600 font-bold' : ''}>
                                  {fp[rec.race_id]?.[rec.wide_pair[1]] || '—'}
                                </span>
                              </span>
                            ) : '—'
                          ) : (
                            finish1 != null && finish1 > 0 ? (
                              <span className={finish1 <= 3 ? 'text-green-600 font-bold' : ''}>
                                {finish1}着
                              </span>
                            ) : '—'
                          )}
                        </td>
                        <td className="py-2 px-1 text-center">
                          {isHit === true && <Badge className="bg-green-600 text-white text-[10px]">的中</Badge>}
                          {isHit === false && <Badge variant="secondary" className="text-[10px]">外れ</Badge>}
                        </td>
                        <td className="py-2 px-1 text-center">
                          {(() => {
                            const cid = makeConfirmedId(rec);
                            const isConfirmed = confirmedBets.some(b => b.id === cid);
                            const isLoading = confirmingId === cid;
                            return (
                              <button
                                onClick={() => toggleConfirmBet(rec)}
                                disabled={isLoading}
                                title={isConfirmed ? '確定解除' : '買い確定（推奨から消えても記録残す）'}
                                className={`p-1 rounded transition-colors ${isConfirmed ? 'text-amber-500 hover:text-amber-600' : 'text-gray-300 hover:text-amber-400'}`}
                              >
                                {isLoading ? (
                                  <Loader2 className="h-4 w-4 animate-spin" />
                                ) : isConfirmed ? (
                                  <BookmarkCheck className="h-4 w-4" />
                                ) : (
                                  <Bookmark className="h-4 w-4" />
                                )}
                              </button>
                            );
                          })()}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
                {totalInvest > 0 && (() => {
                  const fp = predictions?.finish_positions;
                  const hitCount = fp ? displayRecs.filter(rec => {
                    const raceFinish = fp[rec.race_id];
                    if (!raceFinish) return false;
                    if ((rec.bet_type === 'ワイド') && rec.wide_pair) {
                      const f1 = raceFinish[rec.wide_pair[0]];
                      const f2 = raceFinish[rec.wide_pair[1]];
                      return f1 > 0 && f2 > 0 && f1 <= 3 && f2 <= 3;
                    } else if (rec.bet_type === '馬連' && rec.wide_pair) {
                      const f1 = raceFinish[rec.wide_pair[0]];
                      const f2 = raceFinish[rec.wide_pair[1]];
                      return (f1 === 1 && f2 === 2) || (f1 === 2 && f2 === 1);
                    } else if (rec.bet_type === '単勝' || rec.bet_type === '単複') {
                      return raceFinish[rec.umaban] === 1;
                    } else if (rec.bet_type === '複勝') {
                      return raceFinish[rec.umaban] > 0 && raceFinish[rec.umaban] <= 3;
                    }
                    return false;
                  }).length : 0;
                  const hasResults = fp && Object.keys(fp).length > 0;
                  return (
                    <tfoot>
                      <tr className="border-t-2 font-bold">
                        <td colSpan={activePreset !== 'intersection' ? 15 : 14} className="py-2 px-2 text-right">
                          合計
                          {hasResults && (
                            <span className={`ml-3 text-xs font-normal ${hitCount > 0 ? 'text-green-600' : 'text-muted-foreground'}`}>
                              的中 {hitCount}/{displayRecs.length}
                            </span>
                          )}
                        </td>
                        <td className="py-2 px-1 text-right font-mono text-red-600">
                          ¥{totalInvest.toLocaleString()}
                        </td>
                      </tr>
                    </tfoot>
                  );
                })()}
              </table>
            </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* ニアミス（intersectionモードのみ表示） */}
      {activePreset === 'intersection' && recommendations.length > 0 && nearMisses.length > 0 && (
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
                {nearMisses.map((nm, idx) => (
                  <tr key={`${nm.race_id}-${nm.umaban}-nm2-${idx}`}
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

      {/* 他プリセット参考情報（intersectionモードのみ） */}
      {activePreset === 'intersection' && otherPresets.length > 0 && (
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
                          {preset.bets.map((b, idx) => (
                            <tr key={`${b.race_id}-${b.umaban}-${(b as any).wide_pair ? `W${(b as any).wide_pair.join('-')}` : idx}`} className="border-b last:border-0 hover:bg-muted/30">
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
      {activePreset === 'intersection' && (
        <Card>
          <CardContent className="py-4">
            <div className="text-xs text-muted-foreground space-y-1">
              <p><strong>Intersection Filter</strong> — v7.3バックテスト実証済み (2025-03〜2026-02, 3,364レース)</p>
              <p>ROI 310.7% / 的中率 19.6% / 年間46ベット / 月平均3.8回</p>
              <p>推奨配分: 資金の2%（MaxDD 14%, 年間+340%成長）</p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 買い確定リスト */}
      {confirmedBets.length > 0 && (
        <Card className="border-amber-200 dark:border-amber-800">
          <CardHeader className="py-3">
            <CardTitle className="text-sm flex items-center gap-2 text-amber-700 dark:text-amber-400">
              <BookmarkCheck className="h-4 w-4" />
              買い確定済み（{confirmedBets.length}件）
              <span className="text-xs font-normal text-muted-foreground ml-1">
                推奨から外れても残る記録
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-xs text-muted-foreground">
                    <th className="py-1.5 px-2 text-left">確定時刻</th>
                    <th className="py-1.5 px-2 text-left">場</th>
                    <th className="py-1.5 px-1 text-center">R</th>
                    <th className="py-1.5 px-1 text-center">馬番</th>
                    <th className="py-1.5 px-2 text-left">馬名</th>
                    <th className="py-1.5 px-1 text-center">券種</th>
                    <th className="py-1.5 px-1 text-right">EV</th>
                    <th className="py-1.5 px-1 text-right">オッズ</th>
                    <th className="py-1.5 px-1 text-right">金額</th>
                    <th className="py-1.5 px-1 text-center">着順</th>
                    <th className="py-1.5 px-1 text-center">結果</th>
                    <th className="py-1.5 px-1 text-center">解除</th>
                  </tr>
                </thead>
                <tbody>
                  {confirmedBets.map((cb) => {
                    const fp = predictions?.finish_positions;
                    const finish1 = fp?.[cb.race_id]?.[cb.umaban] ?? null;
                    let isHit: boolean | null = null;
                    if (fp?.[cb.race_id]) {
                      if (cb.bet_type === 'ワイド' || cb.bet_type === '馬連') {
                        const f1 = cb.wide_pair ? fp[cb.race_id]?.[cb.wide_pair[0]] : null;
                        const f2 = cb.wide_pair ? fp[cb.race_id]?.[cb.wide_pair[1]] : null;
                        if (f1 != null && f2 != null && f1 > 0 && f2 > 0) {
                          isHit = cb.bet_type === 'ワイド' ? f1 <= 3 && f2 <= 3 : (f1 === 1 && f2 === 2) || (f1 === 2 && f2 === 1);
                        }
                      } else if (cb.bet_type === '単勝' || cb.bet_type === '単複') {
                        if (finish1 != null && finish1 > 0) isHit = finish1 === 1;
                      } else if (cb.bet_type === '複勝') {
                        if (finish1 != null && finish1 > 0) isHit = finish1 <= 3;
                      }
                    }
                    const isCurrentlyInRecs = displayRecs.some(r => makeConfirmedId(r) === cb.id);
                    return (
                      <tr key={cb.id} className={`border-b ${isHit === true ? 'bg-green-50 dark:bg-green-950/20' : ''}`}>
                        <td className="py-1.5 px-2 text-xs text-muted-foreground">
                          {new Date(cb.confirmed_at).toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' })}
                        </td>
                        <td className="py-1.5 px-2 font-medium">
                          {cb.venue}
                          {!isCurrentlyInRecs && (
                            <span className="ml-1 text-[9px] px-1 py-0.5 rounded bg-gray-100 text-gray-400 dark:bg-gray-800">消</span>
                          )}
                        </td>
                        <td className="py-1.5 px-1 text-center">{cb.race_number}</td>
                        <td className="py-1.5 px-1 text-center">
                          {cb.wide_pair ? (
                            <span className="font-mono text-xs">{cb.wide_pair[0]}-{cb.wide_pair[1]}</span>
                          ) : (
                            <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-gray-100 dark:bg-gray-800 font-bold text-xs">
                              {cb.umaban}
                            </span>
                          )}
                        </td>
                        <td className="py-1.5 px-2 font-medium">{cb.horse_name}</td>
                        <td className="py-1.5 px-1 text-center text-xs">{cb.bet_type}</td>
                        <td className={`py-1.5 px-1 text-right font-mono text-xs ${getEvColor(cb.ev_at_confirm)}`}>
                          {cb.ev_at_confirm.toFixed(2)}
                        </td>
                        <td className="py-1.5 px-1 text-right font-mono text-xs">{cb.odds_at_confirm.toFixed(1)}</td>
                        <td className="py-1.5 px-1 text-right font-mono text-xs text-orange-600">¥{cb.amount.toLocaleString()}</td>
                        <td className="py-1.5 px-1 text-center font-mono text-xs">
                          {finish1 != null && finish1 > 0 ? (
                            <span className={finish1 <= 3 ? 'text-green-600 font-bold' : ''}>{finish1}着</span>
                          ) : '—'}
                        </td>
                        <td className="py-1.5 px-1 text-center">
                          {isHit === true && <Badge className="bg-green-600 text-white text-[10px]">的中</Badge>}
                          {isHit === false && <Badge variant="secondary" className="text-[10px]">外れ</Badge>}
                        </td>
                        <td className="py-1.5 px-1 text-center">
                          <button
                            onClick={async () => {
                              const res = await fetch('/api/bankroll/confirmed-bets', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify(cb),
                              });
                              const data = await res.json();
                              setConfirmedBets(data.bets ?? []);
                            }}
                            className="p-1 text-gray-300 hover:text-red-400 transition-colors"
                            title="確定解除"
                          >
                            <XCircle className="h-3.5 w-3.5" />
                          </button>
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

      {/* 雷切（三連単VB頭） + スポット馬券 */}
      {((predictions?.sanrentan_formation && predictions.sanrentan_formation.length > 0) ||
        (predictions?.multi_leg_recommendations && predictions.multi_leg_recommendations.length > 0)) && (
        <MultiLegRecommendations
          recommendations={predictions.multi_leg_recommendations ?? []}
          sanrentanFormation={predictions.sanrentan_formation}
          races={(predictions.races ?? []) as unknown as PredictionRace[]}
          venueFilter="all"
          trackFilter="all"
          raceNumFilter={0}
        />
      )}
    </div>
  );
}
