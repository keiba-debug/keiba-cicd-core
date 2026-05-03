'use client';

/**
 * チャートタブ
 *
 * オッズ時系列を lightweight-charts で可視化:
 * - ライン: 複数馬重ね描き（Y軸対数）
 * - ローソク足: 馬1頭ずつ、時間枠 5/15/30/60分
 *
 * /api/odds/ji-timeseries の snapshots を直接消費する。
 */

import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import {
  createChart,
  LineSeries,
  CandlestickSeries,
  createSeriesMarkers,
  ColorType,
  CrosshairMode,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
  type SeriesMarker,
} from 'lightweight-charts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { RefreshCw } from 'lucide-react';
import { getWakuColor } from '@/types/race-data';
import {
  toLineSeries,
  toCandleSeries,
  detectSurgeMarkers,
  colorForUmaban,
  type OddsSnapshot,
  type Bucket,
} from './chart-utils';
import { getMyMarkColor, type EnrichedHorse } from './buy-zone';

interface ChartTabProps {
  raceId: string;
  horses: EnrichedHorse[];
}

type Mode = 'line' | 'candle';

const BUCKET_OPTIONS: { value: Bucket; label: string }[] = [
  { value: '5m', label: '5分' },
  { value: '15m', label: '15分' },
  { value: '30m', label: '30分' },
  { value: '1h', label: '1時間' },
];

interface SnapshotsResponse {
  raceId: string;
  snapshotCount: number;
  timeSeries: OddsSnapshot[];
}

export function ChartTab({ raceId, horses }: ChartTabProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<Map<string, ISeriesApi<'Line' | 'Candlestick'>>>(new Map());

  const [snapshots, setSnapshots] = useState<OddsSnapshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>('line');
  const [bucket, setBucket] = useState<Bucket>('15m');
  // ライン用: 複数選択
  const [selected, setSelected] = useState<Set<string>>(new Set());
  // ローソク用: 単一選択（モード切替時に互いに干渉しないよう独立）
  const [candleUmaban, setCandleUmaban] = useState<string | null>(null);
  const [showSurgeMarkers, setShowSurgeMarkers] = useState(true);
  // 株/FX流: 上=人気(オッズ低)・下=不人気(オッズ高) になるよう Y軸反転
  const [invertedScale, setInvertedScale] = useState(true);

  const raceIdYear = raceId.substring(0, 4);

  // 初期選択: 人気1-3番（horses が来たタイミング）
  useEffect(() => {
    if (horses.length === 0 || selected.size > 0) return;
    const sortedByNinki = horses
      .filter((h) => h.ninki != null)
      .sort((a, b) => (a.ninki ?? 99) - (b.ninki ?? 99));
    const top3 = sortedByNinki.slice(0, 3).map((h) => h.umaban);
    setSelected(new Set(top3));
    // ローソク用は単勝1番人気を初期表示
    if (candleUmaban == null && sortedByNinki.length > 0) {
      setCandleUmaban(sortedByNinki[0].umaban);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [horses]);

  // データ取得
  const fetchSnapshots = useCallback(async () => {
    if (!raceId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/odds/ji-timeseries?raceId=${raceId}`);
      if (!res.ok) {
        setError('時系列データなし');
        setSnapshots([]);
        return;
      }
      const data: SnapshotsResponse = await res.json();
      setSnapshots(data.timeSeries ?? []);
    } catch {
      setError('取得失敗');
      setSnapshots([]);
    } finally {
      setLoading(false);
    }
  }, [raceId]);

  useEffect(() => {
    fetchSnapshots();
  }, [fetchSnapshots]);

  // チャート初期化
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: 'rgb(100, 116, 139)',
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: 'rgba(148, 163, 184, 0.1)' },
        horzLines: { color: 'rgba(148, 163, 184, 0.1)' },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: {
        borderColor: 'rgba(148, 163, 184, 0.3)',
        // ライン時は対数。ローソク時は線形（OHLC比較しやすく）
        mode: 0, // 0=Normal (linear). モード切替時に上書き
      },
      timeScale: {
        borderColor: 'rgba(148, 163, 184, 0.3)',
        timeVisible: true,
        secondsVisible: false,
      },
      localization: {
        locale: 'ja-JP',
        timeFormatter: (time: UTCTimestamp) => {
          const d = new Date((time as number) * 1000);
          // UTC として埋めた値を JST 風に表示（時刻だけ取り出す）
          const hh = String(d.getUTCHours()).padStart(2, '0');
          const mi = String(d.getUTCMinutes()).padStart(2, '0');
          return `${hh}:${mi}`;
        },
      },
    });

    chartRef.current = chart;

    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current.clear();
    };
  }, []);

  // モード/反転切替時に priceScale を更新
  useEffect(() => {
    if (!chartRef.current) return;
    chartRef.current.priceScale('right').applyOptions({
      mode: mode === 'line' ? 1 : 0, // 1=Logarithmic, 0=Normal
      invertScale: invertedScale,
    });
  }, [mode, invertedScale]);

  // データ更新時にシリーズを再構築
  useEffect(() => {
    if (!chartRef.current || snapshots.length === 0) return;

    const chart = chartRef.current;

    // 既存シリーズ全削除
    for (const s of seriesRef.current.values()) {
      try {
        chart.removeSeries(s);
      } catch {
        // ignore
      }
    }
    seriesRef.current.clear();

    const selectedHorses = horses.filter((h) => selected.has(h.umaban));

    if (mode === 'line') {
      selectedHorses.forEach((h, idx) => {
        const data = toLineSeries(snapshots, h.umaban, raceIdYear);
        if (data.length === 0) return;
        const series = chart.addSeries(LineSeries, {
          color: colorForUmaban(h.umaban, idx),
          lineWidth: 2,
          title: `${parseInt(h.umaban, 10)}.${(h.horseName ?? '').slice(0, 4)}`,
          priceLineVisible: false,
          lastValueVisible: true,
        });
        series.setData(data);
        // 急騰マーカー
        if (showSurgeMarkers) {
          const surges = detectSurgeMarkers(snapshots, h.umaban, raceIdYear);
          if (surges.length > 0) {
            const markers: SeriesMarker<UTCTimestamp>[] = surges.map((s) => ({
              time: s.time,
              position: 'belowBar',
              color: '#dc2626',
              shape: 'arrowUp',
              text: `🔥${s.changePercent.toFixed(0)}%`,
            }));
            createSeriesMarkers(series, markers);
          }
        }
        seriesRef.current.set(h.umaban, series);
      });
    } else {
      // ローソク足: candleUmaban で指定した1頭のみ表示
      const target = horses.find((h) => h.umaban === candleUmaban) ?? selectedHorses[0];
      if (target) {
        const data = toCandleSeries(snapshots, target.umaban, raceIdYear, bucket);
        if (data.length > 0) {
          // 反転時: 視覚的"上"=データ下落=人気上昇 → 陽線として青
          //         視覚的"下"=データ上昇=不人気    → 陰線として赤
          // 通常時: データ上昇=オッズ上昇=不人気 → 青、データ下落=人気=赤
          const upColor = invertedScale ? '#ef4444' : '#3b82f6';
          const downColor = invertedScale ? '#3b82f6' : '#ef4444';
          const series = chart.addSeries(CandlestickSeries, {
            upColor,
            downColor,
            wickUpColor: upColor,
            wickDownColor: downColor,
            borderVisible: false,
            priceLineVisible: false,
            lastValueVisible: true,
          });
          series.setData(data);
          if (showSurgeMarkers) {
            const surges = detectSurgeMarkers(snapshots, target.umaban, raceIdYear);
            if (surges.length > 0) {
              const markers: SeriesMarker<UTCTimestamp>[] = surges.map((s) => ({
                time: s.time,
                position: 'belowBar',
                color: '#dc2626',
                shape: 'arrowUp',
                text: `🔥${s.changePercent.toFixed(0)}%`,
              }));
              createSeriesMarkers(series, markers);
            }
          }
          seriesRef.current.set(target.umaban, series);
        }
      }
    }

    // 時間軸を全データにフィット
    chart.timeScale().fitContent();
  }, [snapshots, horses, selected, candleUmaban, mode, bucket, showSurgeMarkers, raceIdYear, invertedScale]);

  // クイック選択
  const selectQuick = useCallback(
    (kind: 'top3' | 'vb' | 'my' | 'top5' | 'all' | 'none') => {
      const next = new Set<string>();
      switch (kind) {
        case 'top3':
          horses
            .filter((h) => h.ninki != null)
            .sort((a, b) => (a.ninki ?? 99) - (b.ninki ?? 99))
            .slice(0, 3)
            .forEach((h) => next.add(h.umaban));
          break;
        case 'top5':
          horses
            .filter((h) => h.ninki != null)
            .sort((a, b) => (a.ninki ?? 99) - (b.ninki ?? 99))
            .slice(0, 5)
            .forEach((h) => next.add(h.umaban));
          break;
        case 'vb':
          horses.filter((h) => h.isVb).forEach((h) => next.add(h.umaban));
          break;
        case 'my':
          horses.filter((h) => h.myMark1 || h.myMark2).forEach((h) => next.add(h.umaban));
          break;
        case 'all':
          horses.forEach((h) => next.add(h.umaban));
          break;
        case 'none':
          break;
      }
      setSelected(next);
    },
    [horses]
  );

  const toggleHorse = useCallback((umaban: string) => {
    // ローソク足モードは独立した単一選択 (selected には触れない)
    if (mode === 'candle') {
      setCandleUmaban(umaban);
      return;
    }
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(umaban)) next.delete(umaban);
      else next.add(umaban);
      return next;
    });
  }, [mode]);

  // ローソク時の表示馬
  const candleTarget = useMemo(() => {
    if (mode !== 'candle') return null;
    return (
      horses.find((h) => h.umaban === candleUmaban) ??
      horses.find((h) => selected.has(h.umaban)) ??
      null
    );
  }, [mode, horses, candleUmaban, selected]);

  return (
    <div className="space-y-4">
      {/* ツールバー */}
      <Card>
        <CardHeader className="py-3 px-4 border-b">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <CardTitle className="text-sm font-bold">📈 オッズ時系列チャート</CardTitle>
            <div className="flex items-center gap-2">
              {snapshots.length > 0 && (
                <Badge variant="outline" className="text-xs">
                  {snapshots.length}件のスナップショット
                </Badge>
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={fetchSnapshots}
                disabled={loading}
                className="h-7"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-3 space-y-2">
          {/* モード */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold text-muted-foreground min-w-[5rem]">モード:</span>
            <Button
              size="sm"
              variant={mode === 'line' ? 'default' : 'outline'}
              onClick={() => setMode('line')}
              className="h-7 text-xs"
            >
              📈 ライン（多頭重ね・対数）
            </Button>
            <Button
              size="sm"
              variant={mode === 'candle' ? 'default' : 'outline'}
              onClick={() => setMode('candle')}
              className="h-7 text-xs"
            >
              🕯 ローソク足（1頭）
            </Button>
            <Button
              size="sm"
              variant={showSurgeMarkers ? 'default' : 'outline'}
              onClick={() => setShowSurgeMarkers((v) => !v)}
              className="h-7 text-xs"
              title="-15%以上下落した時刻にマーカー表示"
            >
              🔥 急騰マーカー
            </Button>
            <Button
              size="sm"
              variant={invertedScale ? 'default' : 'outline'}
              onClick={() => setInvertedScale((v) => !v)}
              className="h-7 text-xs"
              title="株/FX流: 上=人気(オッズ低)、下=不人気(オッズ高)"
            >
              {invertedScale ? '🔃 反転中(人気↑)' : '↕ Y軸反転'}
            </Button>
          </div>
          {/* ローソク時間枠 */}
          {mode === 'candle' && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-semibold text-muted-foreground min-w-[5rem]">時間枠:</span>
              {BUCKET_OPTIONS.map((opt) => (
                <Button
                  key={opt.value}
                  size="sm"
                  variant={bucket === opt.value ? 'default' : 'outline'}
                  onClick={() => setBucket(opt.value)}
                  className="h-7 text-xs"
                >
                  {opt.label}
                </Button>
              ))}
            </div>
          )}
          {/* クイック選択（ライン時のみ） */}
          {mode === 'line' && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-semibold text-muted-foreground min-w-[5rem]">クイック:</span>
              <Button size="sm" variant="outline" onClick={() => selectQuick('top3')} className="h-7 text-xs">
                人気Top3
              </Button>
              <Button size="sm" variant="outline" onClick={() => selectQuick('top5')} className="h-7 text-xs">
                人気Top5
              </Button>
              <Button size="sm" variant="outline" onClick={() => selectQuick('vb')} className="h-7 text-xs">
                VB馬
              </Button>
              <Button size="sm" variant="outline" onClick={() => selectQuick('my')} className="h-7 text-xs">
                My印あり
              </Button>
              <Button size="sm" variant="outline" onClick={() => selectQuick('all')} className="h-7 text-xs">
                全馬
              </Button>
              <Button size="sm" variant="outline" onClick={() => selectQuick('none')} className="h-7 text-xs">
                クリア
              </Button>
              <span className="ml-auto text-xs text-muted-foreground">
                選択: <strong>{selected.size}</strong> / {horses.length}頭
              </span>
            </div>
          )}
          {mode === 'candle' && (
            <p className="text-xs text-muted-foreground">
              ローソク足は1頭のみ表示。下の馬選択ボタンで切替できます。
            </p>
          )}
        </CardContent>
      </Card>

      {/* チャート本体（コンテナは常時マウント、状態は overlay で表示） */}
      <Card>
        <CardContent className="p-3">
          {mode === 'candle' && candleTarget && !loading && !error && snapshots.length > 0 && selected.size > 0 && (
            <p className="text-xs text-muted-foreground mb-2">
              ローソク足表示中: <strong>{parseInt(candleTarget.umaban, 10)}番 {candleTarget.horseName}</strong>
              （複数選択時は先頭1頭のみ表示）
              {invertedScale ? (
                <span className="ml-3">
                  <span className="inline-block w-3 h-2 bg-blue-500 mr-1 align-middle" />青=陽線(人気↑)
                  <span className="inline-block w-3 h-2 bg-red-500 ml-2 mr-1 align-middle" />赤=陰線(人気↓)
                  <span className="ml-2 text-[10px]">※Y軸反転中: 上=低オッズ</span>
                </span>
              ) : (
                <span className="ml-3">
                  <span className="inline-block w-3 h-2 bg-red-500 mr-1 align-middle" />赤=人気上昇
                  <span className="inline-block w-3 h-2 bg-blue-500 ml-2 mr-1 align-middle" />青=人気低下
                </span>
              )}
            </p>
          )}
          <div className="relative w-full" style={{ height: '420px' }}>
            <div ref={containerRef} className="absolute inset-0" />
            {(() => {
              const noSelection =
                mode === 'candle' ? candleTarget == null : selected.size === 0;
              const showOverlay = loading || error || snapshots.length === 0 || noSelection;
              if (!showOverlay) return null;
              return (
                <div className="absolute inset-0 flex items-center justify-center bg-background/80 backdrop-blur-sm text-sm text-muted-foreground">
                  {loading ? (
                    <RefreshCw className="animate-spin h-6 w-6" />
                  ) : error ? (
                    error
                  ) : snapshots.length === 0 ? (
                    '時系列データなし'
                  ) : (
                    '下のリストから馬を選んでください'
                  )}
                </div>
              );
            })()}
          </div>
        </CardContent>
      </Card>

      {/* 馬選択リスト */}
      <Card>
        <CardHeader className="py-3 px-4 border-b">
          <CardTitle className="text-sm font-bold">馬選択</CardTitle>
        </CardHeader>
        <CardContent className="p-3">
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-2">
            {horses.map((h, idx) => {
              const isSelected = mode === 'candle'
                ? h.umaban === candleUmaban
                : selected.has(h.umaban);
              const wakuNum = h.waku ? parseInt(h.waku, 10) : null;
              const wakuColorClass = wakuNum ? getWakuColor(wakuNum) : 'bg-gray-100';
              const color = colorForUmaban(h.umaban, idx);
              return (
                <button
                  key={h.umaban}
                  onClick={() => toggleHorse(h.umaban)}
                  className={`flex items-center gap-2 px-2 py-1.5 rounded text-xs border transition ${
                    isSelected
                      ? 'bg-primary/10 border-primary'
                      : 'border-muted hover:bg-muted/50'
                  }`}
                >
                  <span
                    className={`px-1 py-0.5 rounded text-[10px] font-bold border ${wakuColorClass}`}
                  >
                    {h.waku || '-'}
                  </span>
                  <span className="font-mono font-semibold w-5 text-center">
                    {parseInt(h.umaban, 10)}
                  </span>
                  {h.myMark1 && (
                    <span className={`text-sm ${getMyMarkColor(h.myMark1)}`}>{h.myMark1}</span>
                  )}
                  <span className="flex-1 text-left truncate" title={h.horseName}>
                    {h.horseName?.slice(0, 5) || '-'}
                  </span>
                  <span className="font-mono tabular-nums text-[11px] text-muted-foreground">
                    {h.winOdds?.toFixed(1) ?? '-'}
                  </span>
                  {isSelected && (
                    <span
                      className="inline-block w-3 h-3 rounded-full"
                      style={{ backgroundColor: color }}
                      title={`シリーズ色: ${color}`}
                    />
                  )}
                </button>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
