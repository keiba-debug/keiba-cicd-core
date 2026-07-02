'use client';

/**
 * レース結果コンポーネント（新方式）
 */

import React, { useState, useMemo } from 'react';
import {
  HorseEntry,
  PayoutEntry,
  TenkaiData,
  LapsData,
  getWakuColor,
  parseFinishPosition,
} from '@/types/race-data';
import { ChevronDown, ChevronUp, Trophy, Timer, TrendingUp, TrendingDown, Minus, Activity } from 'lucide-react';
import {
  calculateActualRpci, getRpciTrend,
  RACE_TREND_V2_LABELS, RACE_TREND_V2_COLORS, getLap33Interpretation,
  type CourseRpciInfo, type RaceRpciAnalysis, type RaceTrendV2Type,
} from '@/lib/data/rpci-utils';
import type { BabaCondition } from '@/lib/data/baba-reader';
import { formatPassingOrders, parsePassingOrders } from '@/lib/data/result-utils';
import { POSITIVE_TEXT, getRatingColor } from '@/lib/positive-colors';
import { cn } from '@/lib/utils';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { Button } from '@/components/ui/button';
import type { MlPredictionEntry } from './HorseEntryTable';

// 新しい可視化コンポーネント
import {
  Last3FComparisonChart,
  MarginVisualization,
  PositionGainIndicator,
  EarlyPositionComparison,
  RaceProgressVisualization,
} from './result-visualizations';

interface RaceResultSectionProps {
  entries: HorseEntry[];
  payouts?: PayoutEntry[] | null;
  tenkaiData?: TenkaiData | null;
  distance?: number; // レース距離（メートル）
  rpciInfo?: CourseRpciInfo | null; // RPCI基準値情報
  babaInfo?: BabaCondition | null; // 馬場コンディション（クッション値・含水率）
  laps?: LapsData | null; // ラップタイムデータ
  raceId?: string; // レースID（スタートメモ用）
  raceDate?: string; // レース日付（スタートメモ用）
  raceName?: string; // レース名（スタートメモ用）
  mlPredictions?: Record<number, MlPredictionEntry>; // 事前ML予測（答え合わせ列用）
  aiMarks?: Record<number, string> | null; // AI評価印（markSet=2 ◎○▲△等）
}

export default function RaceResultSection({ entries, payouts, tenkaiData, distance, rpciInfo, babaInfo, laps, raceId, raceDate, raceName, mlPredictions, aiMarks }: RaceResultSectionProps) {
  const [isOpen, setIsOpen] = useState(true);
  
  // 結果のある馬のみフィルタしてソート
  const resultsEntries = entries
    .filter(e => e.result && e.result.finish_position)
    .sort((a, b) => {
      const posA = parseFinishPosition(a.result!.finish_position);
      const posB = parseFinishPosition(b.result!.finish_position);
      return posA - posB;
    });

  // 上り最速を特定
  const fastestLast3f = getFastestLast3fEntry(resultsEntries);

  // 実測コーナー通過データの有無（ResultTenkaiReplay の描画条件と同じ）
  // 実測リプレイが出せるレースでは、タイム逆算の推定展開図は出さない
  const hasCornerReplay = resultsEntries.filter(
    e => parsePassingOrders(e.result?.passing_orders, entries.length).length >= 1
  ).length >= 2;

  // 事前評価列（AI印/W順/EV）の表示有無
  const hasMlColumns = !!mlPredictions && Object.keys(mlPredictions).length > 0;

  // レイティング統計を計算（レース内相対表示用）
  const ratingStats = useMemo(() => {
    const ratings = entries
      .map(e => ({ horseNumber: e.horse_number, rating: parseFloat(e.entry_data.rating) || 0 }))
      .filter(r => r.rating > 0);
    const ratingValues = ratings.map(r => r.rating);
    const maxRating = ratingValues.length > 0 ? Math.max(...ratingValues) : 50;
    const minRating = ratingValues.length > 0 ? Math.min(...ratingValues) : 40;
    
    // レース内順位を計算
    const sortedRatings = [...ratings].sort((a, b) => b.rating - a.rating);
    const ratingRankMap = new Map<number, number>();
    sortedRatings.forEach((r, idx) => {
      ratingRankMap.set(r.horseNumber, idx + 1);
    });
    
    return { minRating, maxRating, ratingRankMap, totalCount: ratings.length };
  }, [entries]);

  // 実際のRPCI分析を計算
  // JRA-VAN pace.rpciがある場合はそれを直接使用（TARGETのPCI3と一致）
  // ない場合は馬ごとのfirst_3f/last_3fから再計算（フォールバック）
  const rpciAnalysis = useMemo(() => {
    if (laps?.rpci != null) {
      // JRA-VAN公式RPCI — buildRpciAnalysis相当の結果を直接構築
      const { trend, label } = getRpciTrend(laps.rpci);
      let comparedToStandard: 'faster' | 'slower' | 'typical' = 'typical';
      let comparedToStandardLabel = 'コース平均的なペース';
      let deviation = 0;
      if (rpciInfo) {
        deviation = laps.rpci - rpciInfo.rpciMean;
        // 高RPCI → 後半遅い → ハイペース（持続戦）
        // 低RPCI → 後半速い → スローペース（瞬発戦）
        if (laps.rpci >= rpciInfo.thresholds.sustained) {
          comparedToStandard = 'faster';
          comparedToStandardLabel = 'ハイペース（持続戦）';
        } else if (laps.rpci <= rpciInfo.thresholds.instantaneous) {
          comparedToStandard = 'slower';
          comparedToStandardLabel = 'スローペース（瞬発戦）';
        }
      }
      return {
        actualRpci: laps.rpci,
        actualTrend: trend,
        actualTrendLabel: label,
        comparedToStandard,
        comparedToStandardLabel,
        deviation,
        sourceHorses: 0, // JRA-VAN公式値
      } as import('@/lib/data/rpci-utils').RaceRpciAnalysis;
    }
    return calculateActualRpci(entries, rpciInfo);
  }, [entries, rpciInfo, laps]);

  // ※ hooks の後に置くこと（rules-of-hooks）
  if (resultsEntries.length === 0) {
    return null;
  }

  return (
    <>
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <div className="border rounded-lg">
        <CollapsibleTrigger asChild>
          <Button
            variant="ghost"
            className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-gray-800"
          >
            <span className="text-lg font-semibold flex items-center gap-2">
              <Trophy className="w-5 h-5 text-yellow-500" />
              レース結果
            </span>
            {isOpen ? (
              <ChevronUp className="w-5 h-5" />
            ) : (
              <ChevronDown className="w-5 h-5" />
            )}
          </Button>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <div className="p-4 space-y-4">
            {/* 馬場コンディション（上がり3F・走破タイムの解釈補助） */}
            {babaInfo && (
              <div
                className="text-sm text-muted-foreground py-2 px-3 rounded-md border bg-muted/30"
                title="JRA早見表に基づく目安です。馬場状態は含水率だけで決まるものではありません。"
              >
                <span className="font-medium text-foreground">このレースの馬場: </span>
                {babaInfo.cushion != null && (
                  <span>クッション {babaInfo.cushion.toFixed(1)}{babaInfo.cushionLabel ? `（${babaInfo.cushionLabel}）` : ''}</span>
                )}
                {(babaInfo.moistureG != null || babaInfo.moisture4 != null) && (
                  <span>
                    {babaInfo.cushion != null ? ' / ' : ''}
                    含水率 G前 {babaInfo.moistureG != null ? `${babaInfo.moistureG.toFixed(1)}%` : '—'}
                    {' / '}4C {babaInfo.moisture4 != null ? `${babaInfo.moisture4.toFixed(1)}%` : '—'}
                    {babaInfo.moistureConditionLabel ? `（${babaInfo.moistureConditionLabel}の目安）` : ''}
                  </span>
                )}
                {babaInfo.cushion == null && babaInfo.moistureG == null && babaInfo.moisture4 == null && (
                  <span>クッション・含水率: 計測なし</span>
                )}
                <span className="ml-1 text-xs">上がり3F・走破タイムの参考にしてください。</span>
              </div>
            )}

            {/* 結果テーブル */}
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="bg-gray-100 dark:bg-gray-800">
                    <th className="px-2 py-2 text-center border w-10">着</th>
                    <th className="px-2 py-2 text-center border w-10">枠</th>
                    <th className="px-2 py-2 text-center border w-10">番</th>
                    <th className="px-2 py-2 text-left border min-w-24">馬名</th>
                    <th className="px-2 py-2 text-center border w-16">タイム</th>
                    <th className="px-2 py-2 text-center border w-12">着差</th>
                    <th className="px-2 py-2 text-center border w-12">前3F</th>
                    <th className="px-2 py-2 text-center border w-12">上3F</th>
                    <th className="px-2 py-2 text-center border w-20">通過</th>
                    <th className="px-2 py-2 text-center border w-10">4角</th>
                    <th className="px-2 py-2 text-center border w-12" title="JRDB実測コース取り（1:最内〜5:大外）">取り</th>
                    <th className="px-2 py-2 text-left border min-w-16">騎手</th>
                    <th className="px-2 py-2 text-right border w-16">オッズ</th>
                    {hasMlColumns && (
                      <>
                        <th className="px-2 py-2 text-center border w-14" title="事前のAI評価（AI印 + 勝率ランク）。緑=上位評価が好走 / 赤=本命(W1位)が着外 / 橙=ノーマーク激走">AI予想</th>
                        <th className="px-2 py-2 text-center border w-12" title="事前の単勝EV（キャリブレーション勝率×オッズ）">EV</th>
                      </>
                    )}
                    <th className="px-2 py-2 text-center border w-12">レート</th>
                    <th className="px-2 py-2 text-left border min-w-32">寸評</th>
                  </tr>
                </thead>
                <tbody>
                  {resultsEntries.slice(0, 12).map((entry) => (
                    <ResultRow
                      key={entry.horse_number}
                      entry={entry}
                      isFastestLast3f={entry.horse_number === fastestLast3f?.horse_number}
                      ratingStats={ratingStats}
                      totalHorses={entries.length}
                      mlPred={hasMlColumns ? mlPredictions?.[entry.horse_number] : undefined}
                      aiMark={aiMarks?.[entry.horse_number]}
                      showMlColumns={hasMlColumns}
                    />
                  ))}
                </tbody>
              </table>
            </div>

            {/* 配当情報 */}
            {payouts && payouts.length > 0 && (
              <PayoutTable payouts={payouts} />
            )}

            {/* 上位3頭のコメント */}
            <TopHorsesComments entries={resultsEntries.slice(0, 3)} />
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>

    {/* 視覚的分析セクション */}
    <div className="mt-4 space-y-4">
      {/* ペース分析（RPCI + 33ラップ + 判定根拠の統合カード） */}
      {(rpciAnalysis || laps) && (
        <PaceAnalysisCard
          analysis={rpciAnalysis}
          courseInfo={rpciInfo || undefined}
          laps={laps || undefined}
        />
      )}

      {/* ラップタイムチャート */}
      {laps?.lap_times && laps.lap_times.length > 0 && (
        <LapTimesChart lapTimes={laps.lap_times} distance={distance || 0} s3={laps.s3} l3={laps.l3} />
      )}

      {/* レース展開図（残600m → ゴール）— タイム逆算の推定値。
          実測コーナー通過があるレースは ResultTenkaiReplay が上位互換なので出さない */}
      {!hasCornerReplay && (
        <RaceProgressVisualization entries={entries} distance={distance || 0} defaultOpen={false} />
      )}

      {/* 序盤位置取り比較 */}
      <EarlyPositionComparison 
        entries={entries} 
        tenkaiData={tenkaiData || null} 
        defaultOpen={false}
        raceId={raceId}
        raceDate={raceDate}
        raceName={raceName}
      />

      {/* 着差バー */}
      <MarginVisualization entries={entries} defaultOpen={false} />

      {/* 上り3F比較チャート */}
      <Last3FComparisonChart entries={entries} defaultOpen={false} />

      {/* 伸び脚インジケータ */}
      <PositionGainIndicator entries={entries} defaultOpen={false} />
    </div>
    </>
  );
}

interface RatingStats {
  minRating: number;
  maxRating: number;
  ratingRankMap: Map<number, number>;
  totalCount: number;
}

interface ResultRowProps {
  entry: HorseEntry;
  isFastestLast3f: boolean;
  ratingStats: RatingStats;
  totalHorses: number;
  mlPred?: MlPredictionEntry;
  aiMark?: string;
  showMlColumns?: boolean;
}

function ResultRow({ entry, isFastestLast3f, ratingStats, totalHorses, mlPred, aiMark, showMlColumns }: ResultRowProps) {
  const { entry_data, result } = entry;
  if (!result) return null;

  const wakuColorClass = getWakuColor(entry_data.waku);
  const position = parseFinishPosition(result.finish_position);

  // 着順による行の背景色
  let rowBgClass = '';
  if (position === 1) rowBgClass = 'bg-yellow-50 dark:bg-yellow-900/10';
  else if (position === 2) rowBgClass = 'bg-gray-50 dark:bg-gray-700/10';
  else if (position === 3) rowBgClass = 'bg-amber-50 dark:bg-amber-900/10';

  // 寸評を取得
  const sunpyo = result.sunpyo || result.raw_data?.寸評 || '';

  // JRDB SED 不利補正（IDM補正ポイント。>0 = その分の不利があった）
  const furiTotal =
    (entry.jrdb_furi ?? 0) + (entry.jrdb_mae_furi ?? 0) +
    (entry.jrdb_naka_furi ?? 0) + (entry.jrdb_ato_furi ?? 0);
  const furiDetail = [
    entry.jrdb_furi ? `不利${entry.jrdb_furi}` : '',
    entry.jrdb_mae_furi ? `前${entry.jrdb_mae_furi}` : '',
    entry.jrdb_naka_furi ? `中${entry.jrdb_naka_furi}` : '',
    entry.jrdb_ato_furi ? `後${entry.jrdb_ato_furi}` : '',
    entry.jrdb_deokure ? `出遅${entry.jrdb_deokure}` : '',
    entry.jrdb_ichi_tori ? `位置取${entry.jrdb_ichi_tori}` : '',
  ].filter(Boolean).join(' / ');

  // JRDB実測コース取り
  const courseToriLabel = entry.jrdb_course_tori != null
    ? ({ 1: '最内', 2: '内', 3: '中', 4: '外', 5: '大外' } as Record<number, string>)[entry.jrdb_course_tori] ?? '-'
    : '-';

  // 事前AI評価 vs 結果の答え合わせ
  const rankW = mlPred?.rank_w ?? null;
  let aiVerdict: 'hit' | 'bust' | 'surprise' | null = null;
  if (rankW != null && position > 0) {
    if (rankW <= 3 && position <= 3) aiVerdict = 'hit';          // 上位評価が好走
    else if (rankW === 1 && position >= 6) aiVerdict = 'bust';   // 本命が着外
    else if (rankW >= 8 && position <= 3) aiVerdict = 'surprise'; // ノーマーク激走
  }
  const aiCellClass =
    aiVerdict === 'hit' ? 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-400 font-bold'
    : aiVerdict === 'bust' ? 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 font-bold'
    : aiVerdict === 'surprise' ? 'bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400 font-bold'
    : 'text-gray-600 dark:text-gray-400';
  const winEv = mlPred?.win_ev ?? null;

  return (
    <tr className={`hover:bg-gray-100 dark:hover:bg-gray-800/50 ${rowBgClass}`}>
      {/* 着順 */}
      <td className="px-2 py-1.5 text-center border">
        <PositionBadge position={position} />
      </td>
      
      {/* 枠番 */}
      <td className={`px-2 py-1.5 text-center border ${wakuColorClass}`}>
        {entry_data.waku}
      </td>
      
      {/* 馬番 */}
      <td className="px-2 py-1.5 text-center border font-bold">
        {entry.horse_number}
      </td>
      
      {/* 馬名 */}
      <td className="px-2 py-1.5 border font-medium">
        <span className="flex items-center gap-1">
          {entry.horse_name}
          {(entry.is_slow_start || (entry.jrdb_deokure ?? 0) > 0) && (
            <span className="inline-flex items-center justify-center w-4 h-4 rounded-sm bg-red-100 dark:bg-red-900/40 text-red-600 dark:text-red-400 text-[10px] font-bold shrink-0" title="出遅れ">
              遅
            </span>
          )}
          {furiTotal > 0 && (
            <span
              className="inline-flex items-center justify-center px-1 h-4 rounded-sm bg-orange-100 dark:bg-orange-900/40 text-orange-600 dark:text-orange-400 text-[10px] font-bold shrink-0"
              title={`JRDB不利補正: ${furiDetail}（IDM補正ポイント）`}
            >
              不利
            </span>
          )}
        </span>
      </td>
      
      {/* タイム */}
      <td className="px-2 py-1.5 text-center border font-mono">
        {result.time}
      </td>
      
      {/* 着差 */}
      <td className="px-2 py-1.5 text-center border text-gray-600 dark:text-gray-400">
        {result.margin || '-'}
      </td>
      
      {/* 前半3F */}
      <td className="px-2 py-1.5 text-center border font-mono text-gray-600 dark:text-gray-400">
        {result.first_3f || '-'}
      </td>
      
      {/* 上り3F（最速はプラス色で強調） */}
      <td className={`px-2 py-1.5 text-center border font-mono ${
        isFastestLast3f ? POSITIVE_TEXT : ''
      }`}>
        {result.last_3f}
        {isFastestLast3f && <span className="ml-0.5">🏃</span>}
      </td>
      
      {/* 通過順（ハイフン区切り） */}
      <td className="px-2 py-1.5 text-center border text-gray-600 dark:text-gray-400 font-mono text-xs">
        {formatPassingOrders(result.passing_orders, totalHorses)}
      </td>
      
      {/* 4角位置 */}
      <td className="px-2 py-1.5 text-center border text-gray-600 dark:text-gray-400">
        {result.last_corner_position || '-'}
      </td>

      {/* コース取り（JRDB実測） */}
      <td
        className={cn(
          "px-2 py-1.5 text-center border text-xs",
          entry.jrdb_course_tori != null && entry.jrdb_course_tori >= 4
            ? 'text-orange-600 dark:text-orange-400'
            : 'text-gray-600 dark:text-gray-400'
        )}
        title={entry.jrdb_course_tori != null ? `JRDBコース取り: ${entry.jrdb_course_tori}（1:最内〜5:大外）` : undefined}
      >
        {courseToriLabel}
      </td>
      
      {/* 騎手 */}
      <td className="px-2 py-1.5 border">
        {entry_data.jockey}
      </td>
      
      {/* オッズ */}
      <td className="px-2 py-1.5 text-right border">
        {entry_data.odds}
        <span className="text-xs text-gray-500 ml-1">
          ({entry_data.odds_rank})
        </span>
      </td>

      {/* 事前AI評価（答え合わせ） */}
      {showMlColumns && (
        <>
          <td
            className={cn("px-2 py-1.5 text-center border text-xs whitespace-nowrap", aiCellClass)}
            title={
              rankW != null
                ? `事前評価: 勝率${rankW}位${aiMark ? ` / AI印 ${aiMark}` : ''}${
                    aiVerdict === 'hit' ? ' → 好走（的中）' :
                    aiVerdict === 'bust' ? ' → 本命崩れ' :
                    aiVerdict === 'surprise' ? ' → ノーマーク激走' : ''
                  }`
                : undefined
            }
          >
            {aiMark && <span className="mr-0.5">{aiMark}</span>}
            {rankW != null ? <span className="font-mono">W{rankW}</span> : (aiMark ? '' : '-')}
          </td>
          <td className={cn(
            "px-2 py-1.5 text-center border font-mono text-xs",
            winEv != null && winEv >= 1.3 ? 'text-emerald-600 dark:text-emerald-400 font-bold'
            : winEv != null && winEv >= 1.0 ? 'text-emerald-600/70 dark:text-emerald-400/70'
            : 'text-gray-500 dark:text-gray-400'
          )}>
            {winEv != null ? winEv.toFixed(2) : '-'}
          </td>
        </>
      )}

      {/* レイティング */}
      <RatingResultCell 
        rating={entry_data.rating}
        horseNumber={entry.horse_number}
        ratingStats={ratingStats}
      />
      
      {/* 寸評 */}
      <td className="px-2 py-1.5 border text-xs text-gray-700 dark:text-gray-300">
        {sunpyo || '-'}
      </td>
    </tr>
  );
}

// レース結果用レイティングセル（色分け統一版）
// 色分けルール: 黄色系(1位) → 青系(2-3位) → 緑系(上位30%)
interface RatingResultCellProps {
  rating: string;
  horseNumber: number;
  ratingStats: RatingStats;
}

function RatingResultCell({ rating, horseNumber, ratingStats }: RatingResultCellProps) {
  const ratingNum = parseFloat(rating) || 0;
  const rank = ratingStats.ratingRankMap.get(horseNumber) || 0;
  const { minRating, maxRating, totalCount } = ratingStats;
  
  if (ratingNum <= 0 || rank <= 0) {
    return (
      <td className={cn("px-2 py-1.5 text-center border font-mono", getRatingColor(rating))}>
        {rating || '-'}
      </td>
    );
  }
  
  // バーの幅計算
  const range = maxRating - minRating;
  const percentage = range > 0 
    ? 20 + ((ratingNum - minRating) / range) * 80
    : 50;
  
  // 順位に応じた色（統一ルール）
  const getBarColor = () => {
    if (rank === 1) return 'bg-gradient-to-r from-yellow-500 to-amber-400';
    if (rank === 2) return 'bg-gradient-to-r from-blue-600 to-blue-400';
    if (rank === 3) return 'bg-gradient-to-r from-blue-500 to-blue-300';
    if (rank <= Math.ceil(totalCount * 0.3)) return 'bg-gradient-to-r from-emerald-500 to-emerald-400';
    if (rank <= Math.ceil(totalCount * 0.5)) return 'bg-gradient-to-r from-green-400 to-green-300';
    return 'bg-gradient-to-r from-gray-400 to-gray-300';
  };
  
  const getTextColor = () => {
    if (rank === 1) return "text-amber-600 dark:text-amber-400 font-bold";
    if (rank <= 3) return "text-blue-600 dark:text-blue-400 font-bold";
    if (rank <= Math.ceil(totalCount * 0.3)) return "text-emerald-600 dark:text-emerald-400";
    return "text-gray-600 dark:text-gray-400";
  };
  
  const getBgColor = () => {
    if (rank === 1) return "bg-amber-50 dark:bg-amber-900/10";
    if (rank <= 3) return "bg-blue-50 dark:bg-blue-900/10";
    if (rank <= Math.ceil(totalCount * 0.3)) return "bg-emerald-50 dark:bg-emerald-900/10";
    return "";
  };
  
  const getRankIcon = () => {
    if (rank === 1) return '🥇';
    if (rank === 2) return '🥈';
    if (rank === 3) return '🥉';
    return null;
  };
  
  return (
    <td className={cn("px-2 py-1.5 text-center border", getBgColor())}>
      <div className="flex flex-col items-center gap-0.5">
        <div className="flex items-center gap-0.5">
          <span className={cn("font-mono text-xs", getTextColor())}>
            {ratingNum.toFixed(1)}
          </span>
          {rank <= 3 && <span className="text-xs">{getRankIcon()}</span>}
        </div>
        <div className="w-10 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
          <div 
            className={cn("h-full rounded-full", getBarColor())}
            style={{ width: `${percentage}%` }}
          />
        </div>
      </div>
    </td>
  );
}

function PositionBadge({ position }: { position: number }) {
  let bgColor = 'bg-gray-100 text-gray-800';
  if (position === 1) bgColor = 'bg-yellow-400 text-yellow-900';
  else if (position === 2) bgColor = 'bg-gray-300 text-gray-800';
  else if (position === 3) bgColor = 'bg-amber-600 text-white';
  else if (position <= 5) bgColor = 'bg-blue-100 text-blue-800';

  return (
    <span className={`inline-flex items-center justify-center w-7 h-7 rounded-full text-sm font-bold ${bgColor}`}>
      {position}
    </span>
  );
}

interface PayoutTableProps {
  payouts: PayoutEntry[];
}

function PayoutTable({ payouts }: PayoutTableProps) {
  // 券種の日本語マッピング
  const payoutTypeLabels: Record<string, string> = {
    'tansho': '単勝',
    'fukusho': '複勝',
    'wakuren': '枠連',
    'umaren': '馬連',
    'wide': 'ワイド',
    'umatan': '馬単',
    'sanrenpuku': '3連複',
    'sanrentan': '3連単',
  };

  // 券種の順序
  const order = ['tansho', 'fukusho', 'wakuren', 'umaren', 'wide', 'umatan', 'sanrenpuku', 'sanrentan'];
  
  // グループ化
  const grouped: Record<string, PayoutEntry[]> = {};
  for (const payout of payouts) {
    if (!grouped[payout.type]) {
      grouped[payout.type] = [];
    }
    grouped[payout.type].push(payout);
  }

  return (
    <div className="mt-4">
      <h4 className="text-sm font-semibold mb-2">💴 払戻金</h4>
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="bg-gray-100 dark:bg-gray-800">
              <th className="px-2 py-1.5 text-left border">券種</th>
              <th className="px-2 py-1.5 text-center border">組番</th>
              <th className="px-2 py-1.5 text-right border">払戻金</th>
              <th className="px-2 py-1.5 text-center border">人気</th>
            </tr>
          </thead>
          <tbody>
            {order.map(type => {
              const entries = grouped[type];
              if (!entries) return null;
              
              return entries.map((payout, idx) => (
                <tr key={`${type}-${idx}`} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                  <td className="px-2 py-1 border font-medium">
                    {idx === 0 ? payoutTypeLabels[type] || type : ''}
                  </td>
                  <td className="px-2 py-1 text-center border">
                    {payout.combination}
                  </td>
                  <td className="px-2 py-1 text-right border font-mono">
                    ¥{payout.amount.toLocaleString()}
                  </td>
                  <td className="px-2 py-1 text-center border text-gray-500">
                    {payout.popularity || '-'}
                  </td>
                </tr>
              ));
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

interface TopHorsesCommentsProps {
  entries: HorseEntry[];
}

function TopHorsesComments({ entries }: TopHorsesCommentsProps) {
  const entriesWithComments = entries.filter(e => 
    e.result?.raw_data?.interview || e.result?.raw_data?.memo
  );

  if (entriesWithComments.length === 0) return null;

  return (
    <div className="mt-4">
      <h4 className="text-sm font-semibold mb-2">💬 騎手コメント</h4>
      <div className="space-y-3">
        {entriesWithComments.map(entry => {
          const interview = entry.result?.raw_data?.interview;
          const memo = entry.result?.raw_data?.memo;
          
          return (
            <div key={entry.horse_number} className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
              <div className="flex items-center gap-2 mb-1">
                <PositionBadge position={parseFinishPosition(entry.result!.finish_position)} />
                <span className="font-medium">{entry.horse_name}</span>
                <span className="text-sm text-gray-500">({entry.entry_data.jockey})</span>
              </div>
              {interview && (
                <p className="text-sm text-gray-700 dark:text-gray-300 mb-1">
                  {interview}
                </p>
              )}
              {memo && (
                <p className="text-xs text-gray-500 dark:text-gray-400 italic">
                  📝 {memo}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/**
 * 上り最速の馬を取得
 */
function getFastestLast3fEntry(entries: HorseEntry[]): HorseEntry | null {
  const withLast3f = entries.filter(e => 
    e.result?.last_3f && 
    !isNaN(parseFloat(e.result.last_3f))
  );
  
  if (withLast3f.length === 0) return null;
  
  return withLast3f.reduce((fastest, current) => {
    const fastestTime = parseFloat(fastest.result!.last_3f);
    const currentTime = parseFloat(current.result!.last_3f);
    return currentTime < fastestTime ? current : fastest;
  });
}

/**
 * ペース分析統合カード（RPCI + 33ラップ + 判定根拠）
 * 旧 RpciAnalysisCard と RaceTrendCard を1枚に統合 (Session 187)
 */
interface PaceAnalysisCardProps {
  analysis: RaceRpciAnalysis | null;
  courseInfo?: CourseRpciInfo;
  laps?: LapsData;
}

// =============================================================================

interface LapTimesChartProps {
  lapTimes: string[];  // ["7.3", "11.0", "11.5", ...]
  distance: number;    // レース距離(m)
  s3?: number;         // 前半3F実測（レースレベル・JRA-VAN）
  l3?: number;         // 後半3F実測（レースレベル・JRA-VAN）
}

function LapTimesChart({ lapTimes, distance, s3, l3 }: LapTimesChartProps) {
  const times = lapTimes.map(t => parseFloat(t)).filter(t => !isNaN(t) && t > 0);
  if (times.length < 2) return null;

  // ラップ区間のラベルを生成（200m刻み。最初だけ距離が違う場合がある）
  const firstLapDist = distance > 0 ? distance - (times.length - 1) * 200 : 200;
  const labels: string[] = [];
  let cumDist = 0;
  for (let i = 0; i < times.length; i++) {
    cumDist += i === 0 ? firstLapDist : 200;
    labels.push(`${cumDist}`);
  }

  // 通過タイム（累積）を計算
  const cumTimes: number[] = [];
  let cumTime = 0;
  for (const t of times) {
    cumTime += t;
    cumTimes.push(cumTime);
  }

  // SVGチャート描画用パラメータ
  const minLap = Math.min(...times);
  const maxLap = Math.max(...times);
  const range = Math.max(maxLap - minLap, 0.5);
  const chartW = 600;
  const chartH = 200;
  const padL = 40;
  const padR = 20;
  const padT = 20;
  const padB = 30;
  const plotW = chartW - padL - padR;
  const plotH = chartH - padT - padB;

  // Y軸: 速い(小さい値)=上、遅い(大きい値)=下
  // ラップが上がる(速くなる)→線が上がる、ラップが落ちる(遅くなる)→線が下がる
  const yMin = minLap - range * 0.15;
  const yMax = maxLap + range * 0.15;
  const toX = (i: number) => padL + (i / (times.length - 1)) * plotW;
  const toY = (v: number) => padT + ((v - yMin) / (yMax - yMin)) * plotH;

  // ポイント座標
  const points = times.map((t, i) => ({ x: toX(i), y: toY(t), val: t }));

  // Y軸目盛り（0.5秒刻み）
  const yTicks: number[] = [];
  const yStart = Math.ceil(yMin * 2) / 2;
  for (let v = yStart; v <= yMax; v += 0.5) {
    yTicks.push(v);
  }

  // 最速/最遅ラップ
  const fastestIdx = times.indexOf(minLap);
  const slowestIdx = times.indexOf(maxLap);

  // 区間ごとの加速/減速（前ラップとの差）
  const deltas: (number | null)[] = [null];
  for (let i = 1; i < times.length; i++) {
    deltas.push(+(times[i] - times[i - 1]).toFixed(1));
  }

  // L3F（ラスト3ハロン）の開始インデックス
  const l3fStartIdx = Math.max(0, times.length - 3);

  // セグメントの色: 加速(緑)/減速(赤)/横ばい(橙)
  const segmentColor = (delta: number) => {
    if (delta < -0.2) return '#16a34a'; // green: 加速
    if (delta > 0.2) return '#dc2626';  // red: 減速
    return '#f97316';                    // orange: 横ばい
  };

  // 最大加速/減速ポイント検出（注釈表示用）
  let maxAccelIdx = -1, maxDecelIdx = -1;
  let maxAccelDelta = 0, maxDecelDelta = 0;
  for (let i = 1; i < times.length; i++) {
    const d = times[i] - times[i - 1];
    if (d < maxAccelDelta) { maxAccelDelta = d; maxAccelIdx = i; }
    if (d > maxDecelDelta) { maxDecelDelta = d; maxDecelIdx = i; }
  }

  return (
    <Collapsible defaultOpen={true}>
      <div className="border rounded-lg">
        <CollapsibleTrigger asChild>
          <Button variant="ghost" className="w-full p-4 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-800">
            <div className="flex items-center gap-2">
              <Timer className="w-5 h-5 text-orange-600" />
              <span className="font-semibold">ラップタイム</span>
            </div>
            <ChevronDown className="w-4 h-4" />
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="px-4 pb-4 space-y-3">
            {/* 通過タイム表 */}
            <div className="overflow-x-auto">
              <table className="text-xs border-collapse">
                <thead>
                  <tr className="bg-gray-100 dark:bg-gray-800">
                    {labels.map((l, i) => (
                      <th key={i} className="px-2 py-1 border text-center font-normal text-gray-500 min-w-[48px]">
                        {l}m
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    {times.map((t, i) => (
                      <td key={i} className={cn(
                        "px-2 py-1 border text-center font-mono",
                        i === fastestIdx && "text-blue-600 font-bold bg-blue-50 dark:bg-blue-900/20",
                        i === slowestIdx && "text-red-600 font-bold bg-red-50 dark:bg-red-900/20",
                      )}>
                        {t.toFixed(1)}
                      </td>
                    ))}
                  </tr>
                  <tr className="text-gray-500">
                    {cumTimes.map((ct, i) => (
                      <td key={i} className="px-2 py-1 border text-center font-mono">
                        {ct >= 60
                          ? `${Math.floor(ct / 60)}:${(ct % 60).toFixed(1).padStart(4, '0')}`
                          : ct.toFixed(1)}
                      </td>
                    ))}
                  </tr>
                  {/* 差分行: 前ラップとの差 */}
                  <tr>
                    {deltas.map((d, i) => (
                      <td key={i} className={cn(
                        "px-2 py-0.5 border text-center font-mono text-[10px]",
                        d !== null && d < -0.2 && "text-green-600 dark:text-green-400",
                        d !== null && d > 0.2 && "text-red-600 dark:text-red-400",
                        (d === null || (d >= -0.2 && d <= 0.2)) && "text-gray-400",
                      )}>
                        {d === null ? '' : d > 0 ? `+${d.toFixed(1)}` : d.toFixed(1)}
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>

            {/* SVGチャート */}
            <div className="overflow-x-auto">
              <svg viewBox={`0 0 ${chartW} ${chartH}`} className="w-full max-w-[600px]" style={{ minWidth: 400 }}>
                {/* L3F ゾーンハイライト（勝負所） */}
                {times.length >= 4 && (
                  <>
                    <rect
                      x={toX(l3fStartIdx)}
                      y={padT}
                      width={toX(times.length - 1) - toX(l3fStartIdx)}
                      height={plotH}
                      fill="#818cf8"
                      opacity={0.07}
                      rx={3}
                    />
                    <text
                      x={toX(l3fStartIdx) + 3}
                      y={padT + plotH - 4}
                      fontSize={9}
                      fill="#818cf8"
                      opacity={0.5}
                      fontWeight="bold"
                    >
                      L3F
                    </text>
                  </>
                )}

                {/* グリッド線 */}
                {yTicks.map(v => (
                  <g key={v}>
                    <line
                      x1={padL} x2={chartW - padR}
                      y1={toY(v)} y2={toY(v)}
                      stroke="#e5e7eb" strokeWidth={0.5}
                    />
                    <text x={padL - 4} y={toY(v) + 3} textAnchor="end" fontSize={10} fill="#9ca3af">
                      {v.toFixed(1)}
                    </text>
                  </g>
                ))}

                {/* X軸ラベル */}
                {labels.map((l, i) => (
                  <text key={i} x={toX(i)} y={chartH - 5} textAnchor="middle" fontSize={10} fill="#9ca3af">
                    {l}
                  </text>
                ))}

                {/* 加速/減速セグメントライン（区間ごとに色分け） */}
                {points.map((p, i) => {
                  if (i === 0) return null;
                  const prev = points[i - 1];
                  const delta = times[i] - times[i - 1];
                  return (
                    <line
                      key={`seg-${i}`}
                      x1={prev.x} y1={prev.y}
                      x2={p.x} y2={p.y}
                      stroke={segmentColor(delta)}
                      strokeWidth={2.5}
                      strokeLinecap="round"
                    />
                  );
                })}

                {/* ポイント */}
                {points.map((p, i) => (
                  <g key={i}>
                    <circle
                      cx={p.x} cy={p.y} r={i === fastestIdx || i === slowestIdx ? 5 : 3.5}
                      fill={i === fastestIdx ? '#2563eb' : i === slowestIdx ? '#dc2626' : '#f97316'}
                      stroke="white" strokeWidth={1.5}
                    />
                    <text
                      x={p.x} y={p.y - 8}
                      textAnchor="middle" fontSize={9}
                      fill={i === fastestIdx ? '#2563eb' : i === slowestIdx ? '#dc2626' : '#6b7280'}
                      fontWeight={i === fastestIdx || i === slowestIdx ? 'bold' : 'normal'}
                    >
                      {p.val.toFixed(1)}
                    </text>
                  </g>
                ))}

                {/* 最大加速ポイント注釈 */}
                {maxAccelIdx > 0 && maxAccelDelta < -0.3 && (
                  <text
                    x={(points[maxAccelIdx].x + points[maxAccelIdx - 1].x) / 2}
                    y={Math.min(points[maxAccelIdx].y, points[maxAccelIdx - 1].y) - 16}
                    textAnchor="middle" fontSize={8} fill="#16a34a" fontWeight="bold"
                  >
                    {`▲${Math.abs(maxAccelDelta).toFixed(1)}加速`}
                  </text>
                )}

                {/* 最大減速ポイント注釈 */}
                {maxDecelIdx > 0 && maxDecelDelta > 0.3 && (
                  <text
                    x={(points[maxDecelIdx].x + points[maxDecelIdx - 1].x) / 2}
                    y={Math.max(points[maxDecelIdx].y, points[maxDecelIdx - 1].y) + 16}
                    textAnchor="middle" fontSize={8} fill="#dc2626" fontWeight="bold"
                  >
                    {`▼+${maxDecelDelta.toFixed(1)}減速`}
                  </text>
                )}
              </svg>
            </div>

            {/* ペース情報 */}
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
              <span>最速: <span className="text-blue-600 font-bold">{minLap.toFixed(1)}</span>秒 ({labels[fastestIdx]}m)</span>
              <span>最遅: <span className="text-red-600 font-bold">{maxLap.toFixed(1)}</span>秒 ({labels[slowestIdx]}m)</span>
              {/* 前後3F比較（同一距離の実測比較。ラップ本数の半割りは距離が揃わず不正確） */}
              {s3 != null && l3 != null && s3 > 0 && l3 > 0 && (
                <span>
                  テン3F: <span className="font-mono">{s3.toFixed(1)}</span>
                  {' / '}上がり3F: <span className="font-mono">{l3.toFixed(1)}</span>
                  {' '}
                  <span className={l3 - s3 >= 0.5 ? 'text-red-600 dark:text-red-400' : s3 - l3 >= 0.5 ? 'text-blue-600 dark:text-blue-400' : 'text-gray-500'}>
                    ({l3 - s3 > 0 ? '+' : ''}{(l3 - s3).toFixed(1)}秒 {l3 - s3 >= 0.5 ? '前傾' : s3 - l3 >= 0.5 ? '後傾' : '均等'})
                  </span>
                </span>
              )}
              <span className="text-gray-400">|</span>
              <span className="inline-flex items-center gap-1">
                <span className="inline-block w-3 h-0.5 bg-green-600 rounded"></span>
                <span>加速</span>
              </span>
              <span className="inline-flex items-center gap-1">
                <span className="inline-block w-3 h-0.5 bg-red-600 rounded"></span>
                <span>減速</span>
              </span>
              <span className="inline-flex items-center gap-1">
                <span className="inline-block w-3 h-0.5 bg-orange-500 rounded"></span>
                <span>維持</span>
              </span>
            </div>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}

function PaceAnalysisCard({ analysis, courseInfo, laps }: PaceAnalysisCardProps) {
  // 傾向に応じたスタイル
  const getTrendStyle = (trend: 'instantaneous' | 'sustained' | 'neutral') => {
    switch (trend) {
      case 'instantaneous':
        return {
          bg: 'bg-blue-50 dark:bg-blue-950/30',
          border: 'border-blue-200 dark:border-blue-900',
          text: 'text-blue-700 dark:text-blue-400',
          icon: <TrendingUp className="w-5 h-5" />,
          label: '瞬発戦'
        };
      case 'sustained':
        return {
          bg: 'bg-red-50 dark:bg-red-950/30',
          border: 'border-red-200 dark:border-red-900',
          text: 'text-red-700 dark:text-red-400',
          icon: <TrendingDown className="w-5 h-5" />,
          label: '持続戦'
        };
      default:
        return {
          bg: 'bg-gray-50 dark:bg-gray-900/40',
          border: 'border-gray-200 dark:border-gray-700',
          text: 'text-gray-700 dark:text-gray-300',
          icon: <Minus className="w-5 h-5" />,
          label: '平均的'
        };
    }
  };

  const style = getTrendStyle(analysis?.actualTrend ?? 'neutral');

  // 基準値との比較
  const getComparisonStyle = (compared: 'faster' | 'slower' | 'typical') => {
    switch (compared) {
      case 'slower':
        return { color: 'text-blue-600 dark:text-blue-400', label: 'スロー' };
      case 'faster':
        return { color: 'text-red-600 dark:text-red-400', label: 'ハイペース' };
      default:
        return { color: 'text-gray-600 dark:text-gray-400', label: '平均的' };
    }
  };

  const compStyle = analysis ? getComparisonStyle(analysis.comparedToStandard) : null;

  // 33ラップ + v2傾向（旧 RaceTrendCard 由来）
  const trendV2 = laps?.race_trend_v2 as RaceTrendV2Type | undefined;
  const lap33 = laps?.lap33;
  const detail = laps?.trend_detail;
  const trendV2Label = trendV2 ? RACE_TREND_V2_LABELS[trendV2] : null;
  const trendV2Color = trendV2 ? RACE_TREND_V2_COLORS[trendV2] : '';

  const signalLabel = (sig: string) => {
    if (sig === 'sprint') return <span className="text-blue-600 dark:text-blue-400">瞬発</span>;
    if (sig === 'sustained') return <span className="text-red-600 dark:text-red-400">持続</span>;
    return <span className="text-gray-500">中立</span>;
  };

  return (
    <div className={`rounded-lg border p-4 ${style.bg} ${style.border}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-full ${style.bg} ${style.text}`}>
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <div className="text-sm font-medium text-gray-600 dark:text-gray-400 flex items-center gap-2">
              このレースのペース分析
              {trendV2Label && (
                <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${trendV2Color}`}>
                  {trendV2Label}
                </span>
              )}
              {detail && (
                <span className="text-xs text-muted-foreground font-normal">
                  確信度 {Math.round(detail.confidence * 100)}%
                </span>
              )}
            </div>
            <div className={`text-lg font-bold flex items-center gap-2 ${style.text}`}>
              {style.icon}
              <span>{style.label}</span>
              {analysis && (
                <span className="text-base font-normal">(RPCI: {analysis.actualRpci.toFixed(1)})</span>
              )}
            </div>
          </div>
        </div>

        {/* 基準値との比較 */}
        {courseInfo && analysis && compStyle && (
          <div className="text-right">
            <div className="text-xs text-gray-500">
              コース基準: {courseInfo.rpciMean.toFixed(1)}
            </div>
            <div className={`text-sm font-medium ${compStyle.color}`}>
              {analysis.deviation > 0 ? '+' : ''}{analysis.deviation.toFixed(1)} ({compStyle.label})
            </div>
            <div className="text-xs text-gray-400">
              {analysis.comparedToStandardLabel}
            </div>
          </div>
        )}
      </div>

      {/* 詳細情報 */}
      <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700 grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
        {analysis && (
          <div>
            <div className="text-gray-500 text-xs">実測RPCI</div>
            <div className="font-mono font-bold">{analysis.actualRpci.toFixed(2)}</div>
          </div>
        )}
        {courseInfo && (
          <>
            {/* RPCIが閾値以下→瞬発戦 / 閾値以上→持続戦 */}
            <div>
              <div className="text-gray-500 text-xs">瞬発戦閾値</div>
              <div className="font-mono text-blue-600 dark:text-blue-400">&le;{courseInfo.thresholds.instantaneous.toFixed(1)}</div>
            </div>
            <div>
              <div className="text-gray-500 text-xs">持続戦閾値</div>
              <div className="font-mono text-red-600 dark:text-red-400">&ge;{courseInfo.thresholds.sustained.toFixed(1)}</div>
            </div>
          </>
        )}
        {lap33 != null && (
          <div>
            <div className="text-gray-500 text-xs">33ラップ</div>
            <div className="flex items-baseline gap-1">
              <span className={`font-mono font-bold ${lap33 >= 0.5 ? 'text-blue-600 dark:text-blue-400' : lap33 <= -0.5 ? 'text-red-600 dark:text-red-400' : 'text-gray-600 dark:text-gray-400'}`}>
                {lap33 > 0 ? '+' : ''}{lap33.toFixed(1)}
              </span>
              <span className="text-xs text-muted-foreground">{getLap33Interpretation(lap33)}</span>
            </div>
          </div>
        )}
        {detail ? (
          <div>
            <div className="text-gray-500 text-xs">判定根拠</div>
            <div className="flex flex-wrap gap-x-2 gap-y-0.5 text-xs pt-0.5">
              <span>L3F: {signalLabel(detail.l3f_signal)}</span>
              <span>RPCI: {signalLabel(detail.rpci_signal)}</span>
              <span>33: {signalLabel(detail.lap33_signal)}</span>
            </div>
          </div>
        ) : (
          analysis && (
            <div>
              <div className="text-gray-500 text-xs">データソース</div>
              <div className="font-mono">{analysis.sourceHorses > 0 ? `馬別再計算(${analysis.sourceHorses}頭)` : 'JRA-VAN公式'}</div>
            </div>
          )
        )}
      </div>
    </div>
  );
}
