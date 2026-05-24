'use client';

/**
 * シグナルタブ
 *
 * - 買い度判定テーブル（My印 + 単複EV判定 + 急騰アラート）
 * - 直前急騰検出パネル
 * - クイックフィルタ（My×ML一致）
 */

import { useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { getWakuColor } from '@/types/race-data';
import {
  getBuyZoneDisplay,
  getMyMarkColor,
  getMarketSignalDisplay,
  markPriority,
  type EnrichedHorse,
} from './buy-zone';

interface SignalTabProps {
  horses: EnrichedHorse[];
  /** 直前急騰情報（馬番→info）※既存 ji-timeseries API から取得 */
  surgeMap?: Map<
    string,
    { level: 'hot' | 'warm' | 'cold' | 'stable' | 'unknown'; changePercent: number | null; beforeOdds: number | null; finalOdds: number | null }
  >;
  hasMl: boolean;
}

type QuickFilter =
  | 'all'
  | 'my_honmei_hot'
  | 'my_top3_buy'
  | 'my_honmei_risk'
  | 'my_ana_vb'
  | 'surge_my'
  | 'my_keshi';

const QUICK_FILTERS: { value: QuickFilter; label: string; description: string; icon: string }[] = [
  { value: 'all', label: '全馬', description: '全ての馬を表示', icon: '📋' },
  { value: 'my_honmei_hot', label: 'My◎ × 激アツ', description: 'My本命でEV≥1.30', icon: '⭐' },
  { value: 'my_top3_buy', label: 'My◎○▲ × 買い+', description: 'My上位印×EV≥1.10', icon: '🎯' },
  { value: 'my_honmei_risk', label: 'My◎ × リスク', description: 'My本命がEV<0.70（要再考）', icon: '⚠️' },
  { value: 'my_ana_vb', label: 'MyⅢ/穴 × VB', description: '穴狙いとML一致', icon: '💎' },
  { value: 'surge_my', label: '直前急騰 × My', description: '急騰した自分の印馬', icon: '🔥' },
  { value: 'my_keshi', label: 'My消のみ', description: '切り捨て候補（消印を付けた馬）だけ表示', icon: '🚫' },
];

function applyQuickFilter(
  horses: EnrichedHorse[],
  filter: QuickFilter,
  surgeMap?: SignalTabProps['surgeMap']
): EnrichedHorse[] {
  switch (filter) {
    case 'my_honmei_hot':
      return horses.filter((h) => h.myMark1 === '◎' && h.winZone === 'hot');
    case 'my_top3_buy':
      return horses.filter(
        (h) =>
          (h.myMark1 === '◎' || h.myMark1 === '○' || h.myMark1 === '▲') &&
          (h.winZone === 'hot' || h.winZone === 'buy')
      );
    case 'my_honmei_risk':
      return horses.filter((h) => h.myMark1 === '◎' && h.winZone === 'risk');
    case 'my_ana_vb':
      return horses.filter(
        (h) => (h.myMark1 === 'Ⅲ' || h.myMark1 === '穴' || h.myMark2 === 'Ⅲ' || h.myMark2 === '穴') && h.isVb
      );
    case 'surge_my':
      return horses.filter((h) => {
        const surge = surgeMap?.get(h.umaban) ?? surgeMap?.get(h.umaban.replace(/^0+/, ''));
        const isSurging = surge?.level === 'hot' || surge?.level === 'warm';
        return isSurging && (h.myMark1 || h.myMark2);
      });
    case 'my_keshi':
      return horses.filter((h) => h.myMark1 === '消' || h.myMark2 === '消');
    default:
      return horses;
  }
}

function MyMarkCell({ mark }: { mark: string | null | undefined }) {
  if (!mark) return <span className="text-gray-300">-</span>;
  return <span className={getMyMarkColor(mark)}>{mark}</span>;
}

function ZoneBadge({ zone }: { zone: EnrichedHorse['winZone'] }) {
  const d = getBuyZoneDisplay(zone);
  if (zone === 'unknown') return <span className="text-gray-300 text-xs">-</span>;
  return (
    <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] ${d.className}`}>
      <span>{d.icon}</span>
      <span>{d.label}</span>
    </span>
  );
}

export function SignalTab({ horses, surgeMap, hasMl }: SignalTabProps) {
  const [quickFilter, setQuickFilter] = useState<QuickFilter>('all');

  const surgingHorses = useMemo(() => {
    if (!surgeMap) return [];
    return horses
      .map((h) => {
        const s = surgeMap.get(h.umaban) ?? surgeMap.get(h.umaban.replace(/^0+/, ''));
        return s && (s.level === 'hot' || s.level === 'warm') ? { horse: h, surge: s } : null;
      })
      .filter((x): x is NonNullable<typeof x> => x !== null)
      .sort((a, b) => (a.surge.changePercent ?? 0) - (b.surge.changePercent ?? 0));
  }, [horses, surgeMap]);

  const filtered = useMemo(() => {
    const applied = applyQuickFilter(horses, quickFilter, surgeMap);
    // ソート: My印優先度 → win EV降順
    return [...applied].sort((a, b) => {
      const myCmp = markPriority(b.myMark1) - markPriority(a.myMark1);
      if (myCmp !== 0) return myCmp;
      return (b.winEv ?? -Infinity) - (a.winEv ?? -Infinity);
    });
  }, [horses, quickFilter, surgeMap]);

  const hasResults = useMemo(() => horses.some((h) => h.finishPosition), [horses]);

  return (
    <div className="space-y-4">
      {/* 直前急騰アラート */}
      {surgingHorses.length > 0 && (
        <Card className="border-red-200 dark:border-red-800">
          <CardHeader className="py-3 px-4 bg-gradient-to-r from-red-50 to-orange-50 dark:from-red-900/20 dark:to-orange-900/20 border-b">
            <CardTitle className="text-sm font-bold flex items-center gap-2">
              🔥 直前急騰検出 ({surgingHorses.length}頭)
            </CardTitle>
          </CardHeader>
          <CardContent className="p-3">
            <div className="space-y-2">
              {surgingHorses.map(({ horse, surge }) => {
                const isMyTarget = horse.myMark1 || horse.myMark2;
                const isVbHot = horse.isVb || horse.winZone === 'hot' || horse.winZone === 'buy';
                const wakuNum = horse.waku ? parseInt(horse.waku, 10) : null;
                const wakuColorClass = wakuNum ? getWakuColor(wakuNum) : 'bg-gray-100';
                return (
                  <div
                    key={horse.umaban}
                    className={`flex items-center gap-2 p-2 rounded ${
                      isMyTarget
                        ? 'bg-red-100 dark:bg-red-900/30 ring-2 ring-red-400 dark:ring-red-600'
                        : 'bg-muted/30'
                    }`}
                  >
                    <span className={`px-1.5 py-0.5 rounded text-xs font-bold border ${wakuColorClass}`}>
                      {horse.waku || '-'}
                    </span>
                    <span className="font-mono font-semibold w-6 text-center">
                      {parseInt(horse.umaban, 10)}
                    </span>
                    <MyMarkCell mark={horse.myMark1} />
                    <span className="font-semibold flex-1 truncate">
                      {horse.horseName ?? `${horse.umaban}番`}
                    </span>
                    <span className="font-mono text-xs">
                      {surge.beforeOdds?.toFixed(1)} → <strong>{surge.finalOdds?.toFixed(1)}倍</strong>
                    </span>
                    <Badge
                      variant="outline"
                      className={
                        surge.level === 'hot'
                          ? 'bg-red-500 text-white border-red-500'
                          : 'bg-orange-400 text-white border-orange-400'
                      }
                    >
                      {surge.changePercent?.toFixed(0)}%
                    </Badge>
                    {isMyTarget && (
                      <Badge className="bg-red-600 text-white">⚠️ あなたの印</Badge>
                    )}
                    {isVbHot && hasMl && <ZoneBadge zone={horse.winZone} />}
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* クイックフィルタ */}
      <Card>
        <CardHeader className="py-3 px-4 border-b">
          <CardTitle className="text-sm font-bold">⚡ クイックフィルタ</CardTitle>
        </CardHeader>
        <CardContent className="p-3 flex flex-wrap gap-2">
          {QUICK_FILTERS.map((f) => {
            const isActive = quickFilter === f.value;
            return (
              <Button
                key={f.value}
                size="sm"
                variant={isActive ? 'default' : 'outline'}
                onClick={() => setQuickFilter(f.value)}
                title={f.description}
                className="text-xs"
              >
                {f.icon} {f.label}
              </Button>
            );
          })}
          <span className="ml-auto text-xs text-muted-foreground self-center">
            該当: <strong>{filtered.length}</strong> / {horses.length} 頭
          </span>
        </CardContent>
      </Card>

      {/* 買い度判定テーブル */}
      <Card>
        <CardHeader className="py-3 px-4 border-b">
          <CardTitle className="text-sm font-bold">🎯 買い度判定</CardTitle>
          <p className="text-xs text-muted-foreground">
            ML予測 EV による5段階判定。並びは My印優先度 → 単EV降順
          </p>
          <p className="text-[10px] text-muted-foreground mt-1">
            <span className="font-semibold">My印:</span>{' '}
            <span className={getMyMarkColor('◎')}>◎</span>本命{' / '}
            <span className={getMyMarkColor('○')}>○</span>対抗{' / '}
            <span className={getMyMarkColor('▲')}>▲</span>単穴{' / '}
            <span className={getMyMarkColor('△')}>△</span>連下{' / '}
            <span className={getMyMarkColor('Ⅲ')}>Ⅲ</span>3着押さえ{' / '}
            <span className={getMyMarkColor('穴')}>穴</span>穴馬{' / '}
            <span className={getMyMarkColor('消')}>消</span>切り捨て候補
          </p>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-1 py-1.5 text-center font-bold w-6">枠</th>
                  <th className="px-1 py-1.5 text-center font-bold w-8">番</th>
                  <th className="px-1 py-1.5 text-center font-bold w-8">My印</th>
                  <th className="px-1 py-1.5 text-center font-bold w-8">My2</th>
                  <th className="px-1 py-1.5 text-left font-bold min-w-[5rem]">馬名</th>
                  <th className="px-1 py-1.5 text-right font-bold w-12">単勝</th>
                  <th className="px-1 py-1.5 text-center font-bold w-8">人気</th>
                  {hasMl && (
                    <>
                      <th className="px-1 py-1.5 text-right font-bold w-12">単EV</th>
                      <th className="px-1 py-1.5 text-center font-bold w-20">単判定</th>
                      <th className="px-1 py-1.5 text-right font-bold w-12">複EV</th>
                      <th className="px-1 py-1.5 text-center font-bold w-20">複判定</th>
                      <th className="px-1 py-1.5 text-center font-bold w-8">VB</th>
                      <th className="px-1 py-1.5 text-center font-bold w-16">市場</th>
                    </>
                  )}
                  <th className="px-1 py-1.5 text-center font-bold w-6">本紙</th>
                  <th className="px-1 py-1.5 text-center font-bold w-10">急騰</th>
                  {hasResults && <th className="px-1 py-1.5 text-center font-bold w-8">着</th>}
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={hasMl ? 15 : 9} className="py-6 text-center text-muted-foreground">
                      該当馬なし
                    </td>
                  </tr>
                ) : (
                  filtered.map((h) => {
                    const wakuNum = h.waku ? parseInt(h.waku, 10) : null;
                    const wakuColorClass = wakuNum ? getWakuColor(wakuNum) : 'bg-gray-100';
                    const surge = surgeMap?.get(h.umaban) ?? surgeMap?.get(h.umaban.replace(/^0+/, ''));
                    const signal = getMarketSignalDisplay(h.marketSignal);
                    return (
                      <tr key={h.umaban} className="border-b hover:bg-muted/30">
                        <td className={`px-1 py-1 text-center text-[10px] font-bold border ${wakuColorClass}`}>
                          {h.waku || '-'}
                        </td>
                        <td className="px-1 py-1 text-center font-mono font-semibold">
                          {parseInt(h.umaban, 10)}
                        </td>
                        <td className="px-1 py-1 text-center text-base">
                          <MyMarkCell mark={h.myMark1} />
                        </td>
                        <td className="px-1 py-1 text-center text-base">
                          <MyMarkCell mark={h.myMark2} />
                        </td>
                        <td className="px-1 py-1 truncate max-w-[7rem]" title={h.horseName}>
                          {h.horseName || '-'}
                        </td>
                        <td className="px-1 py-1 text-right font-mono tabular-nums">
                          {h.winOdds != null ? h.winOdds.toFixed(1) : '-'}
                        </td>
                        <td className="px-1 py-1 text-center">
                          {h.ninki != null ? (
                            <Badge variant={h.ninki <= 3 ? 'default' : 'secondary'} className="text-[10px] px-1">
                              {h.ninki}
                            </Badge>
                          ) : (
                            '-'
                          )}
                        </td>
                        {hasMl && (
                          <>
                            <td className="px-1 py-1 text-right font-mono tabular-nums">
                              {h.winEv != null ? h.winEv.toFixed(2) : '-'}
                            </td>
                            <td className="px-1 py-1 text-center">
                              <ZoneBadge zone={h.winZone} />
                            </td>
                            <td className="px-1 py-1 text-right font-mono tabular-nums">
                              {h.placeEv != null ? h.placeEv.toFixed(2) : '-'}
                            </td>
                            <td className="px-1 py-1 text-center">
                              <ZoneBadge zone={h.placeZone} />
                            </td>
                            <td className="px-1 py-1 text-center">
                              {h.isVb ? (
                                <span className="bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-400 px-1 py-0.5 rounded font-bold text-[10px]">
                                  VB
                                </span>
                              ) : (
                                '-'
                              )}
                            </td>
                            <td className="px-1 py-1 text-center">
                              {signal ? (
                                <span className={`px-1 py-0.5 rounded text-[10px] ${signal.className}`}>
                                  {signal.label}
                                </span>
                              ) : (
                                '-'
                              )}
                            </td>
                          </>
                        )}
                        <td className="px-1 py-1 text-center text-muted-foreground text-[11px]">
                          {h.honshiMark || '-'}
                        </td>
                        <td className="px-1 py-1 text-center text-[10px]">
                          {surge && surge.level === 'hot' && (
                            <span className="bg-red-500 text-white px-1 py-0.5 rounded">🔥</span>
                          )}
                          {surge && surge.level === 'warm' && (
                            <span className="bg-orange-400 text-white px-1 py-0.5 rounded">↗</span>
                          )}
                          {(!surge || (surge.level !== 'hot' && surge.level !== 'warm')) && '-'}
                        </td>
                        {hasResults && (
                          <td className="px-1 py-1 text-center font-mono">
                            {h.finishPosition || '-'}
                          </td>
                        )}
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
