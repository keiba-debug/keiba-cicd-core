'use client';

/**
 * 株ボード風オッズ確認画面
 *
 * RT_DATA のオッズを株の板のように表示
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import Link from 'next/link';
import { RefreshCw, TrendingUp, ChevronLeft, ChevronRight, Filter, ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import type { RaceOdds, HorseOdds } from '@/lib/data/rt-data-types';
import { getTrackNameFromRaceId } from '@/lib/data/rt-data-types';
import { getWakuColor } from '@/types/race-data';
import type { ExpectedValueResponse } from '@/types/prediction';

const TRACK_ORDER: Record<string, number> = {
  札幌: 1, 函館: 2, 福島: 3, 新潟: 4, 東京: 5, 中山: 6,
  中京: 7, 京都: 8, 阪神: 9, 小倉: 10,
};

/** フィルタモード */
type FilterMode = 'all' | 'top5' | 'under10' | 'honshi' | 'ana' | 'gekisou' | 'expected_value';

/** ソートキー */
type SortKey = 'ninki' | 'odds' | 'ai' | 'rating' | 'umaban' | 'finish';
type SortOrder = 'asc' | 'desc';

const FILTER_OPTIONS: { value: FilterMode; label: string; description: string }[] = [
  { value: 'all', label: '全馬', description: '全ての馬を表示' },
  { value: 'top5', label: '上位5頭', description: '人気順Top5（詳細表示）' },
  { value: 'under10', label: '10倍以下', description: '単勝10倍以下' },
  { value: 'honshi', label: '本紙◎', description: '本紙印◎の馬のみ' },
  { value: 'ana', label: '穴馬候補', description: '10-30倍ゾーン' },
  { value: 'gekisou', label: '激走候補', description: 'AI指数高 × オッズ妙味' },
  { value: 'expected_value', label: '💰 期待値', description: '期待値110%以上' },
];

/** フィルタ適用 */
function applyFilter(horses: HorseOdds[], mode: FilterMode): HorseOdds[] {
  switch (mode) {
    case 'top5':
      return horses.filter((h) => (h.ninki ?? 99) <= 5);
    case 'under10':
      return horses.filter((h) => h.winOdds != null && h.winOdds <= 10);
    case 'honshi':
      return horses.filter((h) => h.honshiMark === '◎');
    case 'ana':
      return horses.filter((h) => h.winOdds != null && h.winOdds >= 10 && h.winOdds < 30);
    case 'gekisou':
      // AI指数が高く、オッズが妙味ある馬（AI指数上位50%以内 && 人気5番以下）
      const withAi = horses.filter((h) => h.aiIndex != null);
      if (withAi.length === 0) return [];
      const aiMedian = [...withAi].sort((a, b) => (b.aiIndex ?? 0) - (a.aiIndex ?? 0))[Math.floor(withAi.length / 2)]?.aiIndex ?? 0;
      return horses.filter((h) => {
        if (h.aiIndex == null) return false;
        const isHighAi = h.aiIndex >= aiMedian;
        const isUnderrated = (h.ninki ?? 0) >= 4;
        return isHighAi && isUnderrated;
      });
    case 'expected_value':
      // 期待値110%以上の馬のみ表示（期待値データが付与されている前提）
      return horses.filter((h) => {
        const evRate = (h as any).expectedValueRate;
        return evRate != null && evRate >= 110;
      });
    default:
      return horses;
  }
}

/** 印の色を取得 */
function getMarkColor(mark?: string): string {
  switch (mark) {
    case '◎': return 'text-red-600 dark:text-red-400 font-bold';
    case '○': return 'text-blue-600 dark:text-blue-400 font-bold';
    case '▲': return 'text-green-600 dark:text-green-400 font-semibold';
    case '△': return 'text-orange-500 dark:text-orange-400';
    case '×': return 'text-gray-400';
    default: return 'text-gray-300';
  }
}

/** 着順の色を取得 */
function getFinishPositionClass(position?: string | null): string {
  if (!position) return '';
  const pos = parseInt(position, 10);
  if (isNaN(pos)) return '';
  switch (pos) {
    case 1: return 'bg-yellow-400 text-yellow-900 font-bold';  // 1着: 金
    case 2: return 'bg-gray-300 text-gray-800 font-bold';      // 2着: 銀
    case 3: return 'bg-amber-600 text-amber-100 font-bold';    // 3着: 銅
    default: return 'text-muted-foreground';
  }
}

/** 着順アイコンを取得 */
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

/** 変動トレンドの色とアイコンを取得 */
function getTrendDisplay(trend?: 'up' | 'down' | 'stable' | 'unknown'): { icon: string; className: string } {
  switch (trend) {
    case 'down':
      // オッズ下落 = 人気上昇（注目）
      return { icon: '↓', className: 'text-red-500 dark:text-red-400' };
    case 'up':
      // オッズ上昇 = 人気低下
      return { icon: '↑', className: 'text-blue-500 dark:text-blue-400' };
    case 'stable':
      return { icon: '→', className: 'text-gray-400' };
    default:
      return { icon: '', className: '' };
  }
}

function formatRaceLabel(raceId: string): string {
  const track = getTrackNameFromRaceId(raceId);
  const r = raceId.substring(14, 16);
  const rNum = parseInt(r, 10);
  return `${track}${rNum}R`;
}

/**
 * オッズのゾーン別色分け
 * 1倍台: 赤（本命ゾーン）
 * 2-5倍: オレンジ（上位人気ゾーン）
 * 5-10倍: 緑（中位人気ゾーン）
 * 10-30倍: 青（穴候補ゾーン）
 * 30倍以上: グレー（大穴ゾーン）
 */
function getOddsZoneClass(odds: number | null): string {
  if (odds == null) return '';
  if (odds < 2.0) return 'text-red-600 dark:text-red-400 font-bold';
  if (odds < 5.0) return 'text-orange-600 dark:text-orange-400 font-semibold';
  if (odds < 10.0) return 'text-green-600 dark:text-green-500';
  if (odds < 30.0) return 'text-blue-600 dark:text-blue-400';
  return 'text-gray-500 dark:text-gray-400';
}

/**
 * 人気順で行の背景色を取得
 */
function getNinkiRowClass(ninki: number | null): string {
  if (ninki == null) return '';
  if (ninki === 1) return 'bg-amber-50 dark:bg-amber-900/20';
  if (ninki <= 3) return 'bg-blue-50/50 dark:bg-blue-900/10';
  return '';
}

/**
 * AI指数のヒートマップ色を取得
 * 高いほど濃い色（緑系）
 */
function getAiHeatmapClass(aiIndex: number | undefined, allAiValues: number[]): string {
  if (aiIndex == null || allAiValues.length === 0) return '';
  
  const sorted = [...allAiValues].sort((a, b) => b - a);
  const rank = sorted.indexOf(aiIndex);
  const percentile = (rank / sorted.length) * 100;

  // 上位20%: 濃い緑、上位40%: 緑、上位60%: 薄い緑、それ以外: なし
  if (percentile < 20) return 'bg-emerald-200 dark:bg-emerald-800/60 font-bold';
  if (percentile < 40) return 'bg-emerald-100 dark:bg-emerald-800/40 font-semibold';
  if (percentile < 60) return 'bg-emerald-50 dark:bg-emerald-800/20';
  return '';
}

/**
 * レイティングのヒートマップ色を取得
 * 高いほど濃い色（青系）
 */
function getRatingHeatmapClass(rating: number | undefined, allRatings: number[]): string {
  if (rating == null || allRatings.length === 0) return '';
  
  const sorted = [...allRatings].sort((a, b) => b - a);
  const rank = sorted.indexOf(rating);
  const percentile = (rank / sorted.length) * 100;

  if (percentile < 20) return 'bg-blue-200 dark:bg-blue-800/60 font-bold';
  if (percentile < 40) return 'bg-blue-100 dark:bg-blue-800/40 font-semibold';
  if (percentile < 60) return 'bg-blue-50 dark:bg-blue-800/20';
  return '';
}

interface OddsTableProps {
  odds: RaceOdds;
  filterMode: FilterMode;
  showDetails: boolean;
  expectedValues?: ExpectedValueResponse;
}

function OddsTable({ odds, filterMode, showDetails, expectedValues }: OddsTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('ninki');
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc');

  // ソートハンドラ
  const handleSort = useCallback((key: SortKey) => {
    if (sortKey === key) {
      setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortOrder(key === 'ai' || key === 'rating' ? 'desc' : 'asc');
    }
  }, [sortKey]);

  // ソートアイコン
  const SortIcon = ({ columnKey }: { columnKey: SortKey }) => {
    if (sortKey !== columnKey) {
      return <ArrowUpDown className="inline h-3 w-3 ml-0.5 opacity-40" />;
    }
    return sortOrder === 'asc' 
      ? <ArrowUp className="inline h-3 w-3 ml-0.5 text-primary" />
      : <ArrowDown className="inline h-3 w-3 ml-0.5 text-primary" />;
  };

  const filtered = useMemo(() => {
    // 期待値データをマージ
    let horsesWithEv = odds.horses;
    if (expectedValues) {
      const evMap = new Map(expectedValues.horses.map((ev) => [ev.umaban, ev.expectedValueRate]));
      horsesWithEv = odds.horses.map((h) => ({
        ...h,
        expectedValueRate: evMap.get(h.umaban) ?? evMap.get(h.umaban.replace(/^0+/, '')),
      }));
    }

    const applied = applyFilter(horsesWithEv, filterMode);
    return [...applied].sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case 'ninki':
          cmp = (a.ninki ?? 99) - (b.ninki ?? 99);
          break;
        case 'odds':
          cmp = (a.winOdds ?? 9999) - (b.winOdds ?? 9999);
          break;
        case 'ai':
          cmp = (b.aiIndex ?? 0) - (a.aiIndex ?? 0); // AI高い順がデフォルト
          break;
        case 'rating':
          cmp = (b.rating ?? 0) - (a.rating ?? 0); // 評価高い順がデフォルト
          break;
        case 'umaban':
          cmp = parseInt(a.umaban, 10) - parseInt(b.umaban, 10);
          break;
        case 'finish':
          // 着順でソート（数値変換、未着順は最後に）
          const posA = a.finishPosition ? parseInt(a.finishPosition.replace(/[^\d]/g, ''), 10) : 999;
          const posB = b.finishPosition ? parseInt(b.finishPosition.replace(/[^\d]/g, ''), 10) : 999;
          cmp = (isNaN(posA) ? 999 : posA) - (isNaN(posB) ? 999 : posB);
          break;
      }
      return sortOrder === 'asc' ? cmp : -cmp;
    });
  }, [odds.horses, filterMode, sortKey, sortOrder, expectedValues]);

  // ヒートマップ用の全AI値・レイティング配列
  const allAiValues = useMemo(
    () => odds.horses.filter((h) => h.aiIndex != null).map((h) => h.aiIndex!),
    [odds.horses]
  );
  const allRatings = useMemo(
    () => odds.horses.filter((h) => h.rating != null).map((h) => h.rating!),
    [odds.horses]
  );

  // 結果があるかをチェック（1頭でも着順があれば結果あり）
  const hasResults = useMemo(
    () => odds.horses.some((h) => h.finishPosition != null && h.finishPosition !== ''),
    [odds.horses]
  );

  if (filtered.length === 0) {
    return (
      <div className="py-4 text-center text-muted-foreground text-sm">
        該当馬なし
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="px-1.5 py-2 text-center font-bold w-8">枠</th>
            <th
              className="px-2 py-2 text-center font-bold w-10 cursor-pointer hover:bg-muted/70 select-none"
              onClick={() => handleSort('umaban')}
            >
              馬番<SortIcon columnKey="umaban" />
            </th>
            {showDetails && (
              <th className="px-1 py-2 text-center font-bold w-8">印</th>
            )}
            <th className="px-2 py-2 text-left font-bold min-w-[4rem]">馬名</th>
            {showDetails && (
              <th className="px-1 py-2 text-left font-bold w-16">騎手</th>
            )}
            <th
              className="px-2 py-2 text-right font-bold w-14 cursor-pointer hover:bg-muted/70 select-none"
              onClick={() => handleSort('odds')}
            >
              単勝<SortIcon columnKey="odds" />
            </th>
            {!showDetails && (
              <th className="px-2 py-2 text-right font-bold w-20">複勝</th>
            )}
            {showDetails && (
              <>
                <th
                  className="px-1 py-2 text-right font-bold w-12 cursor-pointer hover:bg-muted/70 select-none"
                  onClick={() => handleSort('ai')}
                >
                  AI<SortIcon columnKey="ai" />
                </th>
                <th
                  className="px-1 py-2 text-right font-bold w-12 cursor-pointer hover:bg-muted/70 select-none"
                  onClick={() => handleSort('rating')}
                >
                  評価<SortIcon columnKey="rating" />
                </th>
              </>
            )}
            {(filterMode === 'expected_value' || showDetails) && (
              <th className="px-2 py-2 text-right font-bold w-16">
                期待値
              </th>
            )}
            <th
              className="px-2 py-2 text-center font-bold w-10 cursor-pointer hover:bg-muted/70 select-none"
              onClick={() => handleSort('ninki')}
            >
              人気<SortIcon columnKey="ninki" />
            </th>
            {hasResults && (
              <th
                className="px-2 py-2 text-center font-bold w-10 cursor-pointer hover:bg-muted/70 select-none"
                onClick={() => handleSort('finish')}
              >
                着順<SortIcon columnKey="finish" />
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {filtered.map((h) => {
            const wakuNum = h.waku ? parseInt(h.waku, 10) : null;
            const wakuColorClass = wakuNum ? getWakuColor(wakuNum) : 'bg-gray-100';
            const rowBgClass = getNinkiRowClass(h.ninki);
            const oddsZoneClass = getOddsZoneClass(h.winOdds);
            const markClass = getMarkColor(h.honshiMark);

            return (
              <tr key={h.umaban} className={`border-b hover:bg-muted/30 ${rowBgClass}`}>
                {/* 枠番 */}
                <td className={`px-1.5 py-1.5 text-center text-xs font-bold border ${wakuColorClass}`}>
                  {h.waku || '-'}
                </td>
                {/* 馬番 */}
                <td className="px-2 py-1.5 text-center font-mono font-semibold">
                  {parseInt(h.umaban, 10)}
                </td>
                {/* 印 */}
                {showDetails && (
                  <td className={`px-1 py-1.5 text-center ${markClass}`}>
                    {h.honshiMark || '-'}
                  </td>
                )}
                {/* 馬名 */}
                <td className="px-2 py-1.5 truncate max-w-[5rem]" title={h.horseName}>
                  {h.horseName || '-'}
                </td>
                {/* 騎手 */}
                {showDetails && (
                  <td className="px-1 py-1.5 truncate max-w-[4rem] text-xs text-muted-foreground" title={h.jockey}>
                    {h.jockey || '-'}
                  </td>
                )}
                {/* 単勝オッズ + 変動マーク */}
                <td className={`px-2 py-1.5 text-right font-mono tabular-nums ${oddsZoneClass}`}>
                  <span className="inline-flex items-center gap-0.5">
                    {h.winOdds != null ? `${h.winOdds.toFixed(1)}` : '-'}
                    {h.oddsTrend && h.oddsTrend !== 'unknown' && (
                      <span
                        className={`text-xs ${getTrendDisplay(h.oddsTrend).className}`}
                        title={
                          h.firstOdds != null && h.winOdds != null
                            ? `朝一 ${h.firstOdds.toFixed(1)} → 現在 ${h.winOdds.toFixed(1)}`
                            : ''
                        }
                      >
                        {getTrendDisplay(h.oddsTrend).icon}
                      </span>
                    )}
                  </span>
                </td>
                {/* 複勝オッズ（詳細モードでは非表示） */}
                {!showDetails && (
                  <td className="px-2 py-1.5 text-right font-mono tabular-nums text-muted-foreground">
                    {h.placeOddsMin != null && h.placeOddsMax != null
                      ? `${h.placeOddsMin.toFixed(1)}-${h.placeOddsMax.toFixed(1)}`
                      : '-'}
                  </td>
                )}
                {/* AI指数・レイティング（ヒートマップ付き） */}
                {showDetails && (
                  <>
                    <td
                      className={`px-1 py-1.5 text-right font-mono tabular-nums text-xs ${getAiHeatmapClass(h.aiIndex, allAiValues)}`}
                      title={h.aiIndex != null ? `AI指数: ${h.aiIndex.toFixed(1)}` : ''}
                    >
                      {h.aiIndex != null ? h.aiIndex.toFixed(0) : '-'}
                    </td>
                    <td
                      className={`px-1 py-1.5 text-right font-mono tabular-nums text-xs ${getRatingHeatmapClass(h.rating, allRatings)}`}
                      title={h.rating != null ? `レイティング: ${h.rating.toFixed(1)}` : ''}
                    >
                      {h.rating != null ? h.rating.toFixed(1) : '-'}
                    </td>
                  </>
                )}
                {/* 期待値 */}
                {(filterMode === 'expected_value' || showDetails) && (
                  <td className="px-2 py-1.5 text-right font-mono tabular-nums">
                    {(h as any).expectedValueRate != null ? (
                      <span className={
                        (h as any).expectedValueRate >= 110 ? 'text-green-600 dark:text-green-400 font-bold' :
                        (h as any).expectedValueRate >= 100 ? 'text-yellow-600 dark:text-yellow-400' :
                        'text-red-600 dark:text-red-400'
                      }>
                        {(h as any).expectedValueRate.toFixed(1)}%
                      </span>
                    ) : '-'}
                  </td>
                )}
                {/* 人気 */}
                <td className="px-2 py-1.5 text-center">
                  {h.ninki != null ? (
                    <Badge variant={h.ninki <= 3 ? 'default' : 'secondary'} className="text-xs px-1.5">
                      {h.ninki}
                    </Badge>
                  ) : (
                    '-'
                  )}
                </td>
                {/* 着順（結果がある場合のみ） */}
                {hasResults && (
                  <td className={`px-2 py-1.5 text-center text-sm ${getFinishPositionClass(h.finishPosition)}`}>
                    {h.finishPosition ? getFinishPositionIcon(h.finishPosition) : '-'}
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function OddsBoardPage() {
  const [raceDates, setRaceDates] = useState<string[]>([]);
  const [dateStr, setDateStr] = useState<string>('');
  const [raceIds, setRaceIds] = useState<string[]>([]);
  const [oddsMap, setOddsMap] = useState<Record<string, RaceOdds>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterMode, setFilterMode] = useState<FilterMode>('all');
  const [selectedTrack, setSelectedTrack] = useState<string | 'all'>('all');
  const [expectedValueMap, setExpectedValueMap] = useState<Record<string, ExpectedValueResponse>>({});
  const [loadingEv, setLoadingEv] = useState(false);

  // 詳細表示モード（上位5頭、激走候補、期待値などでは詳細表示）
  const showDetails = filterMode === 'top5' || filterMode === 'gekisou' || filterMode === 'expected_value';

  // 開催場リストを抽出
  const tracks = useMemo(() => {
    const trackSet = new Set<string>();
    for (const id of raceIds) {
      const track = getTrackNameFromRaceId(id);
      if (track) trackSet.add(track);
    }
    return [...trackSet].sort((a, b) => (TRACK_ORDER[a] ?? 99) - (TRACK_ORDER[b] ?? 99));
  }, [raceIds]);

  const loadRaceDates = useCallback(async () => {
    try {
      const res = await fetch('/api/race-dates');
      if (!res.ok) return;
      const { dates } = await res.json();
      const yyyymmdd = (dates as string[]).map((d) => d.replace(/-/g, ''));
      setRaceDates(yyyymmdd);
      if (yyyymmdd.length > 0) {
        setDateStr((prev) => prev || yyyymmdd[0]);
      } else {
        const t = new Date();
        setDateStr(
          `${t.getFullYear()}${String(t.getMonth() + 1).padStart(2, '0')}${String(t.getDate()).padStart(2, '0')}`
        );
      }
    } catch {
      const t = new Date();
      setDateStr(
        `${t.getFullYear()}${String(t.getMonth() + 1).padStart(2, '0')}${String(t.getDate()).padStart(2, '0')}`
      );
    }
  }, []);

  const loadData = useCallback(async () => {
    if (!dateStr) return;
    setLoading(true);
    setError(null);
    try {
      const listRes = await fetch(`/api/odds/list?date=${dateStr}`);
      if (!listRes.ok) {
        const err = await listRes.json();
        throw new Error(err.error || 'Failed to load');
      }
      const { raceIds: ids } = await listRes.json();
      setRaceIds(ids || []);

      const map: Record<string, RaceOdds> = {};
      const results = await Promise.all(
        (ids || []).map(async (id: string) => {
          const res = await fetch(`/api/odds/race?raceId=${id}`);
          if (res.ok) {
            const data: RaceOdds = await res.json();
            return [id, data] as const;
          }
          return null;
        })
      );
      for (const r of results) {
        if (r) map[r[0]] = r[1];
      }
      setOddsMap(map);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setRaceIds([]);
      setOddsMap({});
    } finally {
      setLoading(false);
    }
  }, [dateStr]);

  const loadExpectedValues = useCallback(async () => {
    if (raceIds.length === 0) return;
    setLoadingEv(true);
    try {
      const map: Record<string, ExpectedValueResponse> = {};
      const results = await Promise.all(
        raceIds.map(async (raceId) => {
          const res = await fetch(`/api/odds/expected-value?raceId=${raceId}`);
          if (res.ok) {
            const data: ExpectedValueResponse = await res.json();
            return [raceId, data] as const;
          }
          return null;
        })
      );
      for (const r of results) {
        if (r) map[r[0]] = r[1];
      }
      setExpectedValueMap(map);
    } catch (e) {
      console.error('期待値取得エラー:', e);
    } finally {
      setLoadingEv(false);
    }
  }, [raceIds]);

  useEffect(() => {
    loadRaceDates();
  }, [loadRaceDates]);

  useEffect(() => {
    if (dateStr) loadData();
  }, [dateStr, loadData]);

  // 期待値フィルタが選択された時に期待値を取得
  useEffect(() => {
    if (filterMode === 'expected_value' && raceIds.length > 0 && Object.keys(expectedValueMap).length === 0) {
      loadExpectedValues();
    }
  }, [filterMode, raceIds, expectedValueMap, loadExpectedValues]);

  const currentIndex = raceDates.indexOf(dateStr);
  const prevDay = () => {
    if (raceDates.length === 0) return;
    if (currentIndex < 0) {
      setDateStr(raceDates[raceDates.length - 1]);
      return;
    }
    if (currentIndex >= raceDates.length - 1) return;
    setDateStr(raceDates[currentIndex + 1]);
  };
  const nextDay = () => {
    if (raceDates.length === 0) return;
    if (currentIndex <= 0) {
      if (currentIndex < 0) setDateStr(raceDates[0]);
      return;
    }
    setDateStr(raceDates[currentIndex - 1]);
  };

  // 開催場フィルタ＆ソート
  const sortedRaceIds = useMemo(() => {
    let filtered = raceIds;
    if (selectedTrack !== 'all') {
      filtered = raceIds.filter((id) => getTrackNameFromRaceId(id) === selectedTrack);
    }
    return [...filtered].sort((a, b) => {
      const trackA = getTrackNameFromRaceId(a);
      const trackB = getTrackNameFromRaceId(b);
      const orderA = TRACK_ORDER[trackA] ?? 99;
      const orderB = TRACK_ORDER[trackB] ?? 99;
      if (orderA !== orderB) return orderA - orderB;
      return parseInt(a.slice(14, 16), 10) - parseInt(b.slice(14, 16), 10);
    });
  }, [raceIds, selectedTrack]);

  const displayDate = dateStr
    ? `${dateStr.slice(0, 4)}/${dateStr.slice(4, 6)}/${dateStr.slice(6, 8)}`
    : '';

  return (
    <div className="py-6 space-y-6">
      <div className="flex flex-wrap items-center gap-4">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <TrendingUp className="h-7 w-7" />
          オッズボード
        </h1>
        <Badge variant="outline" className="text-xs">
          RT_DATA 速報
        </Badge>
      </div>

      <Card>
        <CardHeader className="pb-2 space-y-3">
          {/* 日付ナビゲーション */}
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="icon"
                onClick={prevDay}
                disabled={loading || raceDates.length === 0 || currentIndex >= raceDates.length - 1}
                title="前の開催日"
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="font-mono font-semibold min-w-[120px] text-center">{displayDate || '-'}</span>
              <Button
                variant="outline"
                size="icon"
                onClick={nextDay}
                disabled={loading || raceDates.length === 0 || currentIndex <= 0}
                title="次の開催日"
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
            <Button variant="outline" size="sm" onClick={loadData} disabled={loading}>
              <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
              更新
            </Button>
          </div>
          
          {/* フィルタモード選択 */}
          <div className="flex flex-wrap items-center gap-2">
            <Filter className="h-4 w-4 text-muted-foreground" />
            {FILTER_OPTIONS.map((opt) => (
              <Button
                key={opt.value}
                variant={filterMode === opt.value ? 'default' : 'outline'}
                size="sm"
                onClick={() => setFilterMode(opt.value)}
                title={opt.description}
                className="text-xs"
                disabled={opt.value === 'expected_value' && loadingEv}
              >
                {opt.value === 'expected_value' && loadingEv ? (
                  <>
                    <RefreshCw className="h-3 w-3 mr-1 animate-spin" />
                    読み込み中...
                  </>
                ) : (
                  opt.label
                )}
              </Button>
            ))}
          </div>

          {/* 開催場タブ */}
          {tracks.length > 1 && (
            <div className="flex flex-wrap items-center gap-2 border-t pt-3">
              <span className="text-sm text-muted-foreground">開催場:</span>
              <Button
                variant={selectedTrack === 'all' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setSelectedTrack('all')}
                className="text-xs"
              >
                全場
              </Button>
              {tracks.map((track) => (
                <Button
                  key={track}
                  variant={selectedTrack === track ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setSelectedTrack(track)}
                  className="text-xs"
                >
                  {track}
                </Button>
              ))}
            </div>
          )}
        </CardHeader>
      </Card>

      {error && (
        <Card className="border-destructive/50 bg-destructive/5">
          <CardContent className="py-4">
            <p className="text-destructive font-medium">{error}</p>
            <p className="text-sm text-muted-foreground mt-2">
              環境変数 JV_DATA_ROOT を設定し、TARGET frontier JV で RT_DATA が取得されているか確認してください。
            </p>
          </CardContent>
        </Card>
      )}

      {loading ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            読み込み中...
          </CardContent>
        </Card>
      ) : sortedRaceIds.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            この日のオッズデータはありません
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {sortedRaceIds.map((raceId) => {
            const odds = oddsMap[raceId];
            if (!odds) return null;

            const [y, m, d] = [raceId.slice(0, 4), raceId.slice(4, 6), raceId.slice(6, 8)];
            const track = getTrackNameFromRaceId(raceId);
            const dateStrForPath = `${y}-${m}-${d}`;
            const detailId = odds.keibabookRaceId;
            const racePath = detailId
              ? `/races-v2/${dateStrForPath}/${encodeURIComponent(track)}/${detailId}`
              : `/races-v2/${dateStrForPath}/${encodeURIComponent(track)}/${parseInt(raceId.slice(14, 16), 10)}`;

            // レース条件の表示用テキスト
            const condText = odds.raceCondition
              ? [
                  odds.raceCondition.track,
                  odds.raceCondition.distance ? `${odds.raceCondition.distance}m` : null,
                  odds.raceCondition.raceCondition,
                ]
                  .filter(Boolean)
                  .join(' ')
              : '';

            // 分析コメントのバッジ色
            const analysisColors: Record<string, string> = {
              ikkyou: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
              sankyou: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
              jyouikikkoh: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
              daikon: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
            };

            return (
              <Card key={raceId} className="overflow-hidden">
                <CardHeader className="py-2 px-4 bg-muted/30 space-y-1">
                  {/* 1行目: レース番号 + 出走表リンク */}
                  <CardTitle className="text-base flex items-center justify-between gap-2">
                    <Link
                      href={racePath}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:underline font-semibold"
                    >
                      {formatRaceLabel(raceId)}
                    </Link>
                    <Link
                      href={racePath}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:underline text-sm font-medium"
                    >
                      出走表 →
                    </Link>
                  </CardTitle>
                  {/* 2行目: レース条件 + 分析コメント */}
                  <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    {condText && (
                      <span className="font-medium">{condText}</span>
                    )}
                    {odds.analysis && (
                      <span
                        className={`px-1.5 py-0.5 rounded font-bold ${analysisColors[odds.analysis.pattern] || 'bg-gray-100 text-gray-600'}`}
                        title={odds.analysis.description}
                      >
                        {odds.analysis.label}
                      </span>
                    )}
                  </div>
                </CardHeader>
                <CardContent className="p-0">
                  <OddsTable
                    odds={odds}
                    filterMode={filterMode}
                    showDetails={showDetails}
                    expectedValues={expectedValueMap[raceId]}
                  />
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
