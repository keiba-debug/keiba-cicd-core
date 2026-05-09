'use client';

/**
 * 単一レース用オッズ詳細ページ
 * 
 * 1つのレースを複数パターン（上位人気、オッズ帯別など）で同時表示
 * シェア分析、時系列オッズテーブルも表示
 */

import { useState, useEffect, useMemo, useCallback } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { RefreshCw, ArrowLeft, TrendingUp, Clock, PieChart, Target, Wallet } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import type { RaceOdds, HorseOdds } from '@/lib/data/rt-data-types';
import { getTrackNameFromRaceId } from '@/lib/data/rt-data-types';
import { getWakuColor } from '@/types/race-data';
import type { ExpectedValueHorse, MyMark, PositionMark, ConfidenceMark } from '@/types/prediction';
import { convertMarkToWinRate } from '@/types/prediction';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { TargetMarkInputModal, RaceNavBar } from '@/components/race-v2';
import type { PredictionRace } from '@/lib/data/predictions-reader';
import { SignalTab } from '@/components/odds-race/SignalTab';
import { CompositeFilterTab } from '@/components/odds-race/CompositeFilterTab';
import { ChartTab } from '@/components/odds-race/ChartTab';
import { NiigataChokuTab } from '@/components/odds-race/NiigataChokuTab';
import { enrichHorses } from '@/components/odds-race/buy-zone';
import { parseRaceIdForMarks, fetchMyMarksBoth } from '@/components/odds-race/my-marks-utils';

/** 新潟芝1000m直線（千直）判定 */
function isNiigataChoku(
  raceId: string,
  raceCond?: { track?: string; distance?: number } | null
): boolean {
  if (!raceCond) return false;
  if (raceId.length !== 16 || raceId.substring(8, 10) !== '04') return false;
  if (raceCond.distance !== 1000) return false;
  return raceCond.track === '芝' || raceCond.track === 'turf';
}

/** 直前変動の型 */
interface LastMinuteInfo {
  beforeOdds: number | null;
  finalOdds: number | null;
  change: number | null;
  changePercent: number | null;
  level: 'hot' | 'warm' | 'cold' | 'stable' | 'unknown';
}

/** 時系列データの型 */
interface TimeSeriesData {
  raceId: string;
  snapshotCount: number;
  sampledCount: number;
  firstTime: string;
  lastTime: string;
  horses: Array<{
    umaban: string;
    horseName: string;
    waku?: string;
    finishPosition?: string;
    lastMinute?: LastMinuteInfo | null;
  }>;
  timeSeries: Array<{
    timeLabel: string;
    odds: Record<string, number>;
  }>;
  lastMinuteChanges?: LastMinuteInfo[];
}

/** 直前変動レベルの表示情報 */
function getLastMinuteDisplay(level: LastMinuteInfo['level']): {
  icon: string;
  label: string;
  className: string;
} {
  switch (level) {
    case 'hot':
      return {
        icon: '🔥',
        label: '急上昇',
        className: 'bg-red-500 text-white font-bold',
      };
    case 'warm':
      return {
        icon: '↗️',
        label: '人気化',
        className: 'bg-orange-400 text-white font-semibold',
      };
    case 'cold':
      return {
        icon: '↘️',
        label: '人気落',
        className: 'bg-blue-400 text-white',
      };
    default:
      return { icon: '', label: '', className: '' };
  }
}

/** 着順の色を取得 */
function getFinishPositionClass(position?: string | null): string {
  if (!position) return '';
  const pos = parseInt(position, 10);
  if (isNaN(pos)) return '';
  switch (pos) {
    case 1: return 'bg-yellow-400 text-yellow-900 font-bold';
    case 2: return 'bg-gray-300 text-gray-800 font-bold';
    case 3: return 'bg-amber-600 text-amber-100 font-bold';
    default: return 'text-muted-foreground';
  }
}

function getFinishPositionIcon(position?: string | null): string {
  if (!position) return '';
  const pos = parseInt(position, 10);
  if (isNaN(pos)) return position;
  switch (pos) {
    case 1: return '🥇';
    case 2: return '🥈';
    case 3: return '🥉';
    default: return String(pos);
  }
}

/** シェア表示コンポーネント */
function OddsSharePanel({ horses }: { horses: HorseOdds[] }) {
  // オッズから得票率を計算
  const shareData = useMemo(() => {
    const validHorses = horses.filter((h) => h.winOdds != null && h.winOdds > 0);
    if (validHorses.length === 0) return [];
    
    // 合計得票率の逆数
    const totalInverse = validHorses.reduce((sum, h) => sum + (1 / (h.winOdds ?? 1)), 0);
    
    return validHorses
      .map((h) => {
        const share = ((1 / (h.winOdds ?? 1)) / totalInverse) * 100;
        return {
          umaban: h.umaban,
          horseName: h.horseName,
          waku: h.waku,
          odds: h.winOdds ?? 0,
          share,
          finishPosition: h.finishPosition,
        };
      })
      .sort((a, b) => b.share - a.share);
  }, [horses]);

  if (shareData.length === 0) {
    return (
      <Card>
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-sm font-bold flex items-center gap-2">
            <PieChart className="h-4 w-4" />
            馬別シェア
          </CardTitle>
        </CardHeader>
        <CardContent className="py-4 text-center text-muted-foreground text-sm">
          データなし
        </CardContent>
      </Card>
    );
  }

  const maxShare = Math.max(...shareData.map((d) => d.share));

  return (
    <Card>
      <CardHeader className="py-3 px-4 border-b">
        <CardTitle className="text-sm font-bold flex items-center gap-2">
          <PieChart className="h-4 w-4" />
          馬別シェア（得票率）
        </CardTitle>
        <p className="text-xs text-muted-foreground">オッズから算出した推定得票率</p>
      </CardHeader>
      <CardContent className="p-4">
        <div className="space-y-2">
          {shareData.map((d) => {
            const wakuNum = d.waku ? parseInt(d.waku, 10) : null;
            const wakuColorClass = wakuNum ? getWakuColor(wakuNum) : 'bg-gray-200';
            const barWidth = (d.share / maxShare) * 100;
            
            return (
              <div key={d.umaban} className="flex items-center gap-2 text-xs">
                <div className={`w-5 h-5 rounded text-center text-[10px] font-bold flex items-center justify-center ${wakuColorClass}`}>
                  {parseInt(d.umaban, 10)}
                </div>
                <div className="w-20 truncate" title={d.horseName}>
                  {d.horseName || '-'}
                </div>
                <div className="flex-1 h-5 bg-muted rounded-sm overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-emerald-500 to-emerald-400 rounded-sm transition-all"
                    style={{ width: `${barWidth}%` }}
                  />
                </div>
                <div className="w-14 text-right font-mono tabular-nums">
                  {d.share.toFixed(1)}%
                </div>
                <div className="w-12 text-right font-mono tabular-nums text-muted-foreground">
                  {d.odds.toFixed(1)}倍
                </div>
                {d.finishPosition && (
                  <div className={`w-6 text-center ${getFinishPositionClass(d.finishPosition)}`}>
                    {getFinishPositionIcon(d.finishPosition)}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

/** 時系列オッズテーブル */
function TimeSeriesTable({ raceId }: { raceId: string }) {
  const [data, setData] = useState<TimeSeriesData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dataSource, setDataSource] = useState<string>('');

  // 当日判定
  const isToday = useMemo(() => {
    const dateStr = raceId.substring(0, 8);
    const today = new Date().toISOString().slice(0, 10).replace(/-/g, '');
    return dateStr === today;
  }, [raceId]);

  const fetchData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    try {
      const res = await fetch(`/api/odds/ji-timeseries?raceId=${raceId}&_t=${Date.now()}`);
      if (!res.ok) {
        setError('時系列データなし');
        return;
      }
      const json = await res.json();
      setData(json);
      setDataSource(json.source || '');
      setError(null);
    } catch {
      setError('取得失敗');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [raceId]);

  // 初回読み込み + 当日自動ポーリング (30秒)
  useEffect(() => {
    fetchData();
    if (isToday) {
      const interval = setInterval(() => fetchData(), 30000);
      return () => clearInterval(interval);
    }
  }, [fetchData, isToday]);

  if (loading) {
    return (
      <Card>
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-sm font-bold flex items-center gap-2">
            <Clock className="h-4 w-4" />
            時系列オッズ
          </CardTitle>
        </CardHeader>
        <CardContent className="py-4 text-center">
          <RefreshCw className="animate-spin h-6 w-6 mx-auto text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  if (error || !data || data.timeSeries.length === 0) {
    return (
      <Card>
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-sm font-bold flex items-center gap-2">
            <Clock className="h-4 w-4" />
            時系列オッズ
          </CardTitle>
          <div className="flex items-center gap-2 mt-1">
            <Button onClick={() => fetchData(true)} variant="ghost" size="sm" className="h-6 px-2" disabled={refreshing}>
              <RefreshCw className={`h-3 w-3 ${refreshing ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="py-4 text-center text-muted-foreground text-sm">
          {error || '時系列データがありません'}
        </CardContent>
      </Card>
    );
  }

  // 最新15件を表示（逆順）
  const recentTimeSeries = [...data.timeSeries].reverse().slice(0, 15);

  // 直前変動がある馬を抽出
  const hotHorses = data.horses.filter((h) => h.lastMinute?.level === 'hot' || h.lastMinute?.level === 'warm');

  return (
    <Card>
      <CardHeader className="py-3 px-4 border-b">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-bold flex items-center gap-2">
            <Clock className="h-4 w-4" />
            時系列オッズ
          </CardTitle>
          <div className="flex items-center gap-2">
            {dataSource && (
              <Badge variant="outline" className="text-[10px]">
                {dataSource === 'db' ? 'DB' : 'File'}
              </Badge>
            )}
            {isToday && (
              <Badge variant="secondary" className="text-[10px]">
                自動更新中
              </Badge>
            )}
            <Button onClick={() => fetchData(true)} variant="ghost" size="sm" className="h-7 px-2" disabled={refreshing}>
              <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          {data.firstTime} 〜 {data.lastTime}（{data.snapshotCount}件中{data.sampledCount}件表示）
        </p>
      </CardHeader>

      {/* 直前変動アラート */}
      {hotHorses.length > 0 && (
        <div className="px-4 py-2 bg-gradient-to-r from-red-50 to-orange-50 dark:from-red-900/20 dark:to-orange-900/20 border-b">
          <p className="text-xs font-bold text-red-700 dark:text-red-400 mb-1">
            🔥 締切直前で人気上昇！
          </p>
          <div className="flex flex-wrap gap-2">
            {hotHorses.map((h) => {
              const display = getLastMinuteDisplay(h.lastMinute?.level || 'unknown');
              const changePercent = h.lastMinute?.changePercent ?? 0;
              return (
                <span
                  key={h.umaban}
                  className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs ${display.className}`}
                  title={`${h.lastMinute?.beforeOdds?.toFixed(1)} → ${h.lastMinute?.finalOdds?.toFixed(1)}倍`}
                >
                  {display.icon} {parseInt(h.umaban, 10)}. {h.horseName}
                  <span className="opacity-80">({changePercent.toFixed(0)}%)</span>
                </span>
              );
            })}
          </div>
        </div>
      )}

      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-2 py-1.5 text-left font-bold sticky left-0 bg-muted/50 z-10">時刻</th>
                {data.horses.map((h) => {
                  const wakuNum = h.waku ? parseInt(h.waku, 10) : null;
                  const wakuColorClass = wakuNum ? getWakuColor(wakuNum) : '';
                  const lastMinuteDisplay = h.lastMinute ? getLastMinuteDisplay(h.lastMinute.level) : null;
                  return (
                    <th
                      key={h.umaban}
                      className={`px-1 py-1.5 text-center font-bold min-w-[3rem] ${wakuColorClass}`}
                      title={h.horseName}
                    >
                      <div className="flex flex-col items-center">
                        <span>{parseInt(h.umaban, 10)}</span>
                        {lastMinuteDisplay?.icon && (
                          <span className="text-[10px]">{lastMinuteDisplay.icon}</span>
                        )}
                      </div>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {recentTimeSeries.map((snapshot, idx) => {
                const prevSnapshot = idx < recentTimeSeries.length - 1 ? recentTimeSeries[idx + 1] : null;

                return (
                  <tr key={snapshot.timeLabel} className="border-b hover:bg-muted/30">
                    <td className="px-2 py-1 font-mono text-muted-foreground sticky left-0 bg-background z-10">
                      {snapshot.timeLabel}
                    </td>
                    {data.horses.map((h) => {
                      const odds = snapshot.odds[h.umaban] ?? snapshot.odds[h.umaban.replace(/^0+/, '')];
                      const prevOdds = prevSnapshot
                        ? prevSnapshot.odds[h.umaban] ?? prevSnapshot.odds[h.umaban.replace(/^0+/, '')]
                        : null;

                      let changeClass = '';
                      if (prevOdds != null && odds != null) {
                        if (odds < prevOdds * 0.95) changeClass = 'text-red-600 dark:text-red-400 font-bold';
                        else if (odds > prevOdds * 1.05) changeClass = 'text-blue-600 dark:text-blue-400';
                      }

                      return (
                        <td
                          key={h.umaban}
                          className={`px-1 py-1 text-center font-mono tabular-nums ${changeClass}`}
                        >
                          {odds != null ? odds.toFixed(1) : '-'}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

/** 予想支援パネル */
function PredictionSupportPanel({ horses, raceId }: { horses: HorseOdds[]; raceId: string }) {
  const [bankroll, setBankroll] = useState(100000);
  const [predictions, setPredictions] = useState<Map<string, number>>(new Map());
  const [marks, setMarks] = useState<Map<string, MyMark>>(new Map());
  const [expectedValues, setExpectedValues] = useState<ExpectedValueHorse[]>([]);
  const [calculating, setCalculating] = useState(false);

  // 印から勝率を自動計算して predictions に反映
  const applyMarksToWinRate = () => {
    const newPredictions = new Map<string, number>();
    marks.forEach((mark, umaban) => {
      const winRate = convertMarkToWinRate(mark);
      if (winRate != null) {
        newPredictions.set(umaban, winRate);
      }
    });
    setPredictions(newPredictions);
  };

  // 期待値を計算
  const calculateExpectedValues = async () => {
    setCalculating(true);
    try {
      const res = await fetch(`/api/odds/expected-value?raceId=${raceId}&bankroll=${bankroll}`);
      if (!res.ok) {
        throw new Error('期待値計算失敗');
      }
      const data = await res.json();

      // ユーザー入力の勝率がある場合は上書き
      const results: ExpectedValueHorse[] = data.horses.map((ev: ExpectedValueHorse) => {
        const userWinRate = predictions.get(ev.umaban);
        if (userWinRate != null && userWinRate > 0) {
          // 再計算
          const winRate = userWinRate / 100;
          const odds = ev.winOdds ?? 0;

          if (odds <= 0) return ev;

          const expectedValueRate = winRate * odds * 100;
          const b = odds - 1.0;
          const p = winRate;
          const q = 1.0 - p;
          const fullKelly = (b * p - q) / b;
          const kellyFraction = Math.max(0, fullKelly * 0.25);
          const bet = Math.floor(bankroll * kellyFraction);
          const recommendedBet = Math.floor(bet / 100) * 100;

          let recommendation: ExpectedValueHorse['recommendation'];
          if (expectedValueRate >= 120) recommendation = 'strong_buy';
          else if (expectedValueRate >= 110) recommendation = 'buy';
          else if (expectedValueRate >= 95) recommendation = 'neutral';
          else if (expectedValueRate >= 80) recommendation = 'sell';
          else recommendation = 'none';

          return {
            ...ev,
            estimatedWinRate: userWinRate,
            expectedValueRate,
            kellyFraction,
            recommendedBet: recommendedBet >= 100 ? recommendedBet : 0,
            recommendation,
          };
        }
        return ev;
      });

      setExpectedValues(results.sort((a, b) => (b.expectedValueRate ?? 0) - (a.expectedValueRate ?? 0)));
    } catch (error) {
      console.error('期待値計算エラー:', error);
    } finally {
      setCalculating(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* 設定セクション */}
      <Card>
        <CardHeader className="py-3 px-4 border-b">
          <CardTitle className="text-sm font-bold">期待値計算設定</CardTitle>
        </CardHeader>
        <CardContent className="p-4 space-y-3">
          <div className="flex items-center gap-4">
            <Label className="min-w-[80px]">資金（円）:</Label>
            <Input
              type="number"
              value={bankroll}
              onChange={(e) => setBankroll(parseInt(e.target.value) || 100000)}
              className="w-32"
            />
          </div>
          <Button onClick={calculateExpectedValues} disabled={calculating}>
            {calculating ? (
              <>
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                計算中...
              </>
            ) : (
              '期待値を計算'
            )}
          </Button>
        </CardContent>
      </Card>

      {/* 印選択テーブル */}
      <Card>
        <CardHeader className="py-3 px-4 border-b">
          <CardTitle className="text-sm font-bold">🎯 自分の印入力</CardTitle>
          <p className="text-xs text-muted-foreground">
            位置と信頼度を選択して勝率を自動計算（試験版）
          </p>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-2 py-1.5 text-left font-bold w-8">枠</th>
                  <th className="px-2 py-1.5 text-left font-bold w-10">馬番</th>
                  <th className="px-2 py-1.5 text-left font-bold min-w-[4rem]">馬名</th>
                  <th className="px-2 py-1.5 text-center font-bold min-w-[12rem]">位置評価</th>
                  <th className="px-2 py-1.5 text-center font-bold min-w-[9rem]">信頼度</th>
                  <th className="px-2 py-1.5 text-center font-bold w-16">勝率</th>
                </tr>
              </thead>
              <tbody>
                {horses.map((h) => {
                  const wakuNum = h.waku ? parseInt(h.waku, 10) : null;
                  const wakuColorClass = wakuNum ? getWakuColor(wakuNum) : 'bg-gray-100';
                  const currentMark = marks.get(h.umaban) || { position: null, confidence: null };
                  const calculatedWinRate = convertMarkToWinRate(currentMark);

                  const positionOptions: PositionMark[] = ['🥇本命', '🥈対抗', '🥉穴', '📍連下', '❌消し'];
                  const confidenceOptions: ConfidenceMark[] = ['★★★堅い', '★★普通', '★未知数'];

                  return (
                    <tr key={h.umaban} className="border-b hover:bg-muted/30">
                      <td className={`px-2 py-1.5 text-center text-[10px] font-bold border ${wakuColorClass}`}>
                        {h.waku || '-'}
                      </td>
                      <td className="px-2 py-1.5 text-center font-mono">
                        {parseInt(h.umaban, 10)}
                      </td>
                      <td className="px-2 py-1.5 truncate max-w-[6rem]" title={h.horseName}>
                        {h.horseName || '-'}
                      </td>
                      <td className="px-2 py-1.5">
                        <div className="flex gap-1 flex-wrap">
                          {positionOptions.map((opt) => (
                            <Button
                              key={opt}
                              size="sm"
                              variant={currentMark.position === opt ? 'default' : 'outline'}
                              className="h-6 text-[10px] px-1.5"
                              onClick={() => {
                                const newMarks = new Map(marks);
                                newMarks.set(h.umaban, { ...currentMark, position: opt });
                                setMarks(newMarks);
                              }}
                            >
                              {opt}
                            </Button>
                          ))}
                        </div>
                      </td>
                      <td className="px-2 py-1.5">
                        <div className="flex gap-1 flex-wrap">
                          {confidenceOptions.map((opt) => (
                            <Button
                              key={opt}
                              size="sm"
                              variant={currentMark.confidence === opt ? 'default' : 'outline'}
                              className="h-6 text-[10px] px-1.5"
                              onClick={() => {
                                const newMarks = new Map(marks);
                                newMarks.set(h.umaban, { ...currentMark, confidence: opt });
                                setMarks(newMarks);
                              }}
                            >
                              {opt}
                            </Button>
                          ))}
                        </div>
                      </td>
                      <td className="px-2 py-1.5 text-center font-bold text-blue-600">
                        {calculatedWinRate != null ? `${calculatedWinRate}%` : '-'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="p-4 border-t">
            <Button onClick={applyMarksToWinRate} variant="default" className="w-full">
              印から勝率を反映
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 勝率入力テーブル */}
      <Card>
        <CardHeader className="py-3 px-4 border-b">
          <CardTitle className="text-sm font-bold">📝 予想勝率（直接入力・微調整用）</CardTitle>
          <p className="text-xs text-muted-foreground">
            印から反映した勝率を微調整したい場合はここで編集できます
          </p>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-2 py-1.5 text-left font-bold w-8">枠</th>
                  <th className="px-2 py-1.5 text-left font-bold w-10">馬番</th>
                  <th className="px-2 py-1.5 text-left font-bold min-w-[4rem]">馬名</th>
                  <th className="px-2 py-1.5 text-right font-bold w-14">オッズ</th>
                  <th className="px-2 py-1.5 text-center font-bold w-24">予想勝率(%)</th>
                </tr>
              </thead>
              <tbody>
                {horses.map((h) => {
                  const wakuNum = h.waku ? parseInt(h.waku, 10) : null;
                  const wakuColorClass = wakuNum ? getWakuColor(wakuNum) : 'bg-gray-100';

                  return (
                    <tr key={h.umaban} className="border-b hover:bg-muted/30">
                      <td className={`px-2 py-1.5 text-center text-[10px] font-bold border ${wakuColorClass}`}>
                        {h.waku || '-'}
                      </td>
                      <td className="px-2 py-1.5 text-center font-mono">
                        {parseInt(h.umaban, 10)}
                      </td>
                      <td className="px-2 py-1.5 truncate max-w-[6rem]" title={h.horseName}>
                        {h.horseName || '-'}
                      </td>
                      <td className="px-2 py-1.5 text-right font-mono tabular-nums">
                        {h.winOdds?.toFixed(1)}
                      </td>
                      <td className="px-2 py-1.5">
                        <Input
                          type="number"
                          min={0}
                          max={100}
                          step={0.1}
                          placeholder="0.0"
                          value={predictions.get(h.umaban) || ''}
                          onChange={(e) => {
                            const newPredictions = new Map(predictions);
                            const value = parseFloat(e.target.value);
                            if (!isNaN(value)) {
                              newPredictions.set(h.umaban, value);
                            } else {
                              newPredictions.delete(h.umaban);
                            }
                            setPredictions(newPredictions);
                          }}
                          className="w-20 text-center text-xs"
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* 期待値結果テーブル */}
      {expectedValues.length > 0 && (
        <Card>
          <CardHeader className="py-3 px-4 border-b">
            <CardTitle className="text-sm font-bold">期待値分析結果</CardTitle>
            <p className="text-xs text-muted-foreground">
              期待値110%以上が購入推奨、Kelly基準(0.25)で推奨賭け金を計算
            </p>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-xs border-collapse">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="px-2 py-1.5 text-left font-bold w-8">枠</th>
                    <th className="px-2 py-1.5 text-left font-bold w-10">馬番</th>
                    <th className="px-2 py-1.5 text-left font-bold min-w-[4rem]">馬名</th>
                    <th className="px-2 py-1.5 text-right font-bold w-12">勝率</th>
                    <th className="px-2 py-1.5 text-right font-bold w-14">オッズ</th>
                    <th className="px-2 py-1.5 text-right font-bold w-16">期待値率</th>
                    <th className="px-2 py-1.5 text-right font-bold w-20">推奨賭け金</th>
                    <th className="px-2 py-1.5 text-center font-bold w-16">判定</th>
                  </tr>
                </thead>
                <tbody>
                  {expectedValues.map((ev) => {
                    const horse = horses.find((h) => h.umaban === ev.umaban);
                    const wakuNum = horse?.waku ? parseInt(horse.waku, 10) : null;
                    const wakuColorClass = wakuNum ? getWakuColor(wakuNum) : 'bg-gray-100';

                    return (
                      <tr key={ev.umaban} className="border-b hover:bg-muted/30">
                        <td className={`px-2 py-1.5 text-center text-[10px] font-bold border ${wakuColorClass}`}>
                          {horse?.waku || '-'}
                        </td>
                        <td className="px-2 py-1.5 text-center font-mono">
                          {parseInt(ev.umaban, 10)}
                        </td>
                        <td className="px-2 py-1.5 truncate max-w-[6rem]" title={ev.horseName}>
                          {ev.horseName || '-'}
                        </td>
                        <td className="px-2 py-1.5 text-right font-mono tabular-nums">
                          {ev.estimatedWinRate != null ? `${ev.estimatedWinRate.toFixed(1)}%` : '-'}
                        </td>
                        <td className="px-2 py-1.5 text-right font-mono tabular-nums">
                          {ev.winOdds?.toFixed(1)}
                        </td>
                        <td className={`px-2 py-1.5 text-right font-mono tabular-nums font-bold ${
                          (ev.expectedValueRate ?? 0) >= 110 ? 'text-green-600 dark:text-green-400' :
                          (ev.expectedValueRate ?? 0) >= 100 ? 'text-yellow-600 dark:text-yellow-400' :
                          'text-red-600 dark:text-red-400'
                        }`}>
                          {ev.expectedValueRate != null ? `${ev.expectedValueRate.toFixed(1)}%` : '-'}
                        </td>
                        <td className="px-2 py-1.5 text-right font-mono tabular-nums">
                          {ev.recommendedBet != null ? `¥${ev.recommendedBet.toLocaleString()}` : '-'}
                        </td>
                        <td className="px-2 py-1.5 text-center">
                          {ev.recommendation === 'strong_buy' && <Badge variant="default" className="bg-green-600">🟢 強推奨</Badge>}
                          {ev.recommendation === 'buy' && <Badge variant="default" className="bg-yellow-600">🟡 推奨</Badge>}
                          {ev.recommendation === 'neutral' && <Badge variant="outline">⚪ 中立</Badge>}
                          {ev.recommendation === 'sell' && <Badge variant="outline" className="text-red-600">🔴 非推奨</Badge>}
                          {ev.recommendation === 'none' && <Badge variant="outline" className="text-gray-400">-</Badge>}
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
    </div>
  );
}

export default function OddsRacePage() {
  const params = useParams();
  const raceId = params.raceId as string;

  const [odds, setOdds] = useState<RaceOdds | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // ML予測 + My印 + 直前変動
  const [predictions, setPredictions] = useState<PredictionRace | null>(null);
  const [myMarks1, setMyMarks1] = useState<Record<number, string>>({});
  const [myMarks2, setMyMarks2] = useState<Record<number, string>>({});
  const [surgeMap, setSurgeMap] = useState<
    Map<
      string,
      {
        level: 'hot' | 'warm' | 'cold' | 'stable' | 'unknown';
        changePercent: number | null;
        beforeOdds: number | null;
        finalOdds: number | null;
      }
    >
  >(new Map());

  const raceInfoForMarks = useMemo(() => parseRaceIdForMarks(raceId), [raceId]);

  const fetchOdds = useCallback(async () => {
    if (!raceId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/odds/race?raceId=${raceId}`);
      if (!res.ok) throw new Error('データ取得失敗');
      const data = await res.json();
      setOdds(data);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [raceId]);

  // ML予測
  const fetchPredictions = useCallback(async () => {
    if (!raceId || raceId.length !== 16) return;
    const d = `${raceId.slice(0, 4)}-${raceId.slice(4, 6)}-${raceId.slice(6, 8)}`;
    try {
      const res = await fetch(`/api/ml/predictions-raw?date=${d}`);
      if (!res.ok) {
        setPredictions(null);
        return;
      }
      const data = await res.json();
      const race = (data.races as PredictionRace[] | undefined)?.find((r) => r.race_id === raceId);
      setPredictions(race ?? null);
    } catch {
      setPredictions(null);
    }
  }, [raceId]);

  // My印（馬印1+2）
  const fetchMyMarks = useCallback(async () => {
    if (!raceInfoForMarks) return;
    const { marks1, marks2 } = await fetchMyMarksBoth(raceInfoForMarks);
    setMyMarks1(marks1);
    setMyMarks2(marks2);
  }, [raceInfoForMarks]);

  // 直前変動（ji-timeseries APIから lastMinute 抽出）
  const fetchSurge = useCallback(async () => {
    if (!raceId) return;
    try {
      const res = await fetch(`/api/odds/ji-timeseries?raceId=${raceId}`);
      if (!res.ok) {
        setSurgeMap(new Map());
        return;
      }
      const data = await res.json();
      const m = new Map<string, {
        level: 'hot' | 'warm' | 'cold' | 'stable' | 'unknown';
        changePercent: number | null;
        beforeOdds: number | null;
        finalOdds: number | null;
      }>();
      for (const h of data.horses ?? []) {
        if (h.lastMinute) {
          m.set(String(h.umaban), {
            level: h.lastMinute.level,
            changePercent: h.lastMinute.changePercent,
            beforeOdds: h.lastMinute.beforeOdds,
            finalOdds: h.lastMinute.finalOdds,
          });
        }
      }
      setSurgeMap(m);
    } catch {
      setSurgeMap(new Map());
    }
  }, [raceId]);

  useEffect(() => {
    fetchOdds();
    fetchPredictions();
    fetchMyMarks();
    fetchSurge();
  }, [fetchOdds, fetchPredictions, fetchMyMarks, fetchSurge]);

  // EnrichedHorse[] の計算
  const enrichedHorses = useMemo(() => {
    if (!odds) return [];
    return enrichHorses(odds.horses, predictions, myMarks1, myMarks2);
  }, [odds, predictions, myMarks1, myMarks2]);

  const hasMl = predictions != null && predictions.entries.length > 0;

  const trackName = getTrackNameFromRaceId(raceId);
  const raceNum = raceId.length >= 16 ? parseInt(raceId.substring(14, 16), 10) : 0;

  // レース条件の表示
  const raceConditionLabel = useMemo(() => {
    if (!odds?.raceCondition) return null;
    const { track, distance, raceCondition } = odds.raceCondition;
    const parts: string[] = [];
    if (track && distance) parts.push(`${track}${distance}m`);
    if (raceCondition) parts.push(raceCondition);
    return parts.join(' ');
  }, [odds]);

  // 分析コメント
  const analysisLabel = odds?.analysis?.label;

  // ブラウザタブのタイトルを更新
  useEffect(() => {
    if (!trackName || raceNum <= 0) return;
    const head = `${trackName}${raceNum}R`;
    const cond = raceConditionLabel ? ` ${raceConditionLabel}` : '';
    document.title = `${head}${cond} | オッズ`;
  }, [trackName, raceNum, raceConditionLabel]);

  if (loading) {
    return (
      <div className="py-12 text-center">
        <RefreshCw className="animate-spin h-8 w-8 mx-auto text-muted-foreground" />
        <p className="mt-4 text-muted-foreground">読み込み中...</p>
      </div>
    );
  }

  if (error || !odds) {
    return (
      <div className="py-12 text-center">
        <p className="text-destructive">{error || 'データがありません'}</p>
        <Button onClick={fetchOdds} variant="outline" className="mt-4">
          再読み込み
        </Button>
      </div>
    );
  }

  // 同日ナビゲーション用パラメータ
  const navDate = raceId.length >= 8
    ? `${raceId.substring(0, 4)}-${raceId.substring(4, 6)}-${raceId.substring(6, 8)}`
    : '';

  return (
    <div className="py-6 space-y-6">
      {/* レースナビゲーション（競馬場×レース番号タブ） */}
      {navDate && trackName && raceNum > 0 && (
        <RaceNavBar
          date={navDate}
          track={trackName}
          raceId={raceId}
          raceNumber={raceNum}
        />
      )}

      {/* ヘッダー */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/odds-board">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="h-4 w-4 mr-1" />
              オッズボード
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2 flex-wrap">
              <TrendingUp className="h-6 w-6" />
              {trackName} {raceNum}R オッズ表
              {isNiigataChoku(raceId, odds?.raceCondition) && (
                <Link
                  href="/analysis/specialists/niigata-1000m"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs font-bold px-2 py-0.5 rounded-full bg-blue-600 text-white hover:bg-blue-700 transition-colors"
                  title="新潟芝1000m直線（千直）専門解説へ"
                >
                  千直 →
                </Link>
              )}
            </h1>
            {raceConditionLabel && (
              <p className="text-sm text-muted-foreground mt-1">{raceConditionLabel}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {analysisLabel && analysisLabel !== '-' && (
            <Badge variant="outline" className="text-sm">
              {analysisLabel}
            </Badge>
          )}
          {raceInfoForMarks && (
            <TargetMarkInputModal
              raceInfo={raceInfoForMarks}
              entries={odds.horses.map((h) => ({
                horse_number: parseInt(h.umaban, 10),
                horse_name: h.horseName ?? `${parseInt(h.umaban, 10)}番`,
                entry_data: { waku: h.waku ?? null },
              }))}
              trigger={
                <Button variant="outline" size="sm">
                  <Target className="h-4 w-4 mr-1" />
                  My印を編集
                </Button>
              }
              onSaved={() => fetchMyMarks()}
            />
          )}
          <Link href={`/my-bets/${raceId}`} target="_blank">
            <Button variant="outline" size="sm">
              <Wallet className="h-4 w-4 mr-1" />
              My印買い目
            </Button>
          </Link>
          <Button
            onClick={() => {
              fetchOdds();
              fetchPredictions();
              fetchMyMarks();
              fetchSurge();
            }}
            variant="outline"
            size="sm"
          >
            <RefreshCw className="h-4 w-4 mr-1" />
            更新
          </Button>
          {odds.keibabookRaceId && (
            <Link
              href={`/races-v2/${raceId.substring(0, 4)}-${raceId.substring(4, 6)}-${raceId.substring(6, 8)}/${trackName}/${odds.keibabookRaceId}`}
              target="_blank"
            >
              <Button variant="outline" size="sm">
                出走表 →
              </Button>
            </Link>
          )}
        </div>
      </div>

      {/* My印サマリー（どのタブからも見える） */}
      {(Object.keys(myMarks1).length > 0 || Object.keys(myMarks2).length > 0) && (
        <Card className="bg-amber-50 dark:bg-amber-950/20 border-amber-200 dark:border-amber-800">
          <CardContent className="py-2 px-4 flex flex-wrap items-center gap-3 text-xs">
            <span className="font-bold">🎯 My印:</span>
            {Object.keys(myMarks1).length > 0 ? (
              <span>
                <span className="text-muted-foreground">[1] </span>
                {Object.entries(myMarks1)
                  .filter(([, m]) => m)
                  .sort(([a], [b]) => parseInt(a, 10) - parseInt(b, 10))
                  .map(([n, m]) => `${m}${n}`)
                  .join(' ') || '(なし)'}
              </span>
            ) : (
              <span className="text-muted-foreground">[1] (なし)</span>
            )}
            {Object.keys(myMarks2).length > 0 && (
              <span>
                <span className="text-muted-foreground">[2] </span>
                {Object.entries(myMarks2)
                  .filter(([, m]) => m)
                  .sort(([a], [b]) => parseInt(a, 10) - parseInt(b, 10))
                  .map(([n, m]) => `${m}${n}`)
                  .join(' ')}
              </span>
            )}
          </CardContent>
        </Card>
      )}

      {/* タブ切替 */}
      <Tabs defaultValue="signal" className="w-full">
        <TabsList className={`grid w-full ${isNiigataChoku(raceId, odds?.raceCondition) ? 'grid-cols-7' : 'grid-cols-6'}`}>
          <TabsTrigger value="signal">🎯 シグナル</TabsTrigger>
          <TabsTrigger value="chart">📈 チャート</TabsTrigger>
          <TabsTrigger value="filter">🔍 複合フィルタ</TabsTrigger>
          {isNiigataChoku(raceId, odds?.raceCondition) && (
            <TabsTrigger value="niigata-choku">🌪 千直</TabsTrigger>
          )}
          <TabsTrigger value="share">📊 シェア</TabsTrigger>
          <TabsTrigger value="timeseries">⏱ 時系列表</TabsTrigger>
          <TabsTrigger value="prediction">💰 予想支援</TabsTrigger>
        </TabsList>

        {/* シグナルタブ（新規・デフォルト） */}
        <TabsContent value="signal" className="mt-4">
          <SignalTab horses={enrichedHorses} surgeMap={surgeMap} hasMl={hasMl} />
        </TabsContent>

        {/* チャートタブ（新規・lightweight-charts） */}
        <TabsContent value="chart" className="mt-4">
          <ChartTab raceId={raceId} horses={enrichedHorses} />
        </TabsContent>

        {/* 複合フィルタタブ（新規） */}
        <TabsContent value="filter" className="mt-4">
          <CompositeFilterTab horses={enrichedHorses} surgeMap={surgeMap} hasMl={hasMl} />
        </TabsContent>

        {/* 千直タブ（新潟芝1000m直線時のみ・Phase 3d） */}
        {isNiigataChoku(raceId, odds?.raceCondition) && (
          <TabsContent value="niigata-choku" className="mt-4">
            <NiigataChokuTab entries={predictions?.entries ?? []} raceId={raceId} />
          </TabsContent>
        )}

        {/* シェア分析タブ */}
        <TabsContent value="share" className="mt-4">
          <OddsSharePanel horses={odds.horses} />
        </TabsContent>

        {/* 時系列タブ */}
        <TabsContent value="timeseries" className="mt-4">
          <TimeSeriesTable raceId={raceId} />
        </TabsContent>

        {/* 予想支援タブ */}
        <TabsContent value="prediction" className="mt-4">
          <PredictionSupportPanel horses={odds.horses} raceId={raceId} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
