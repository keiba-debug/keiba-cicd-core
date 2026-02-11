'use client';

/**
 * レース結果コンポーネント（新方式）
 */

import React, { useState, useMemo } from 'react';
import { 
  HorseEntry, 
  PayoutEntry, 
  TenkaiData,
  getWakuColor, 
  toCircleNumber,
  parseFinishPosition,
} from '@/types/race-data';
import { Badge } from '@/components/ui/badge';
import { ChevronDown, ChevronUp, Trophy, Timer, TrendingUp, TrendingDown, Minus, Activity } from 'lucide-react';
import { calculateActualRpci, type CourseRpciInfo, type RaceRpciAnalysis } from '@/lib/data/rpci-utils';
import type { BabaCondition } from '@/lib/data/baba-reader';
import { POSITIVE_TEXT, getRatingColor } from '@/lib/positive-colors';
import { cn } from '@/lib/utils';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { Button } from '@/components/ui/button';

// 新しい可視化コンポーネント
import {
  Last3FComparisonChart,
  MarginVisualization,
  PositionGainIndicator,
  EarlyPositionComparison,
  RaceProgressVisualization,
} from './result-visualizations';

// 丸数字マップ（通過順パース用）
const circleNumMap: Record<string, number> = {
  '①': 1, '②': 2, '③': 3, '④': 4, '⑤': 5,
  '⑥': 6, '⑦': 7, '⑧': 8, '⑨': 9, '⑩': 10,
  '⑪': 11, '⑫': 12, '⑬': 13, '⑭': 14, '⑮': 15,
  '⑯': 16, '⑰': 17, '⑱': 18,
};

/**
 * 通過順位文字列をハイフン区切りでフォーマット
 * @param raw - 通過順位の生文字列 (例: "5555", "⑫1213", "3-2-3-1")
 * @param totalHorses - 出走頭数（2桁判定に使用）
 * @returns ハイフン区切りの通過順位文字列
 */
function formatPassingOrders(raw: string | undefined, totalHorses: number = 18): string {
  if (!raw) return '-';
  
  // すでにハイフン区切りの場合はそのまま返す
  if (raw.includes('-')) {
    return raw;
  }
  
  const positions: number[] = [];
  let remaining = raw;
  
  // 頭数が10頭以上の場合、2桁数字を考慮
  const hasTwoDigitNumbers = totalHorses >= 10;
  
  while (remaining.length > 0) {
    let matched = false;
    
    // まず丸数字をチェック
    for (const [circle, num] of Object.entries(circleNumMap)) {
      if (remaining.startsWith(circle)) {
        positions.push(num);
        remaining = remaining.slice(circle.length);
        matched = true;
        break;
      }
    }
    
    if (matched) continue;
    
    // 2桁数字をチェック（10頭以上のレースの場合）
    if (hasTwoDigitNumbers && remaining.length >= 2) {
      const twoDigit = remaining.slice(0, 2);
      const twoDigitNum = parseInt(twoDigit);
      // 10-18（または頭数まで）の範囲なら2桁として解釈
      if (!isNaN(twoDigitNum) && twoDigitNum >= 10 && twoDigitNum <= Math.max(totalHorses, 18)) {
        positions.push(twoDigitNum);
        remaining = remaining.slice(2);
        continue;
      }
    }
    
    // 1桁数字をチェック
    const oneDigit = remaining.slice(0, 1);
    const oneDigitNum = parseInt(oneDigit);
    if (!isNaN(oneDigitNum) && oneDigitNum > 0) {
      positions.push(oneDigitNum);
      remaining = remaining.slice(1);
      continue;
    }
    
    // マッチしない文字はスキップ
    remaining = remaining.slice(1);
  }
  
  if (positions.length === 0) {
    return '-';
  }
  
  return positions.join('-');
}

interface RaceResultSectionProps {
  entries: HorseEntry[];
  payouts?: PayoutEntry[] | null;
  tenkaiData?: TenkaiData | null;
  distance?: number; // レース距離（メートル）
  rpciInfo?: CourseRpciInfo | null; // RPCI基準値情報
  babaInfo?: BabaCondition | null; // 馬場コンディション（クッション値・含水率）
  raceId?: string; // レースID（スタートメモ用）
  raceDate?: string; // レース日付（スタートメモ用）
  raceName?: string; // レース名（スタートメモ用）
}

export default function RaceResultSection({ entries, payouts, tenkaiData, distance, rpciInfo, babaInfo, raceId, raceDate, raceName }: RaceResultSectionProps) {
  const [isOpen, setIsOpen] = useState(true);
  
  // 結果のある馬のみフィルタしてソート
  const resultsEntries = entries
    .filter(e => e.result && e.result.finish_position)
    .sort((a, b) => {
      const posA = parseFinishPosition(a.result!.finish_position);
      const posB = parseFinishPosition(b.result!.finish_position);
      return posA - posB;
    });

  if (resultsEntries.length === 0) {
    return null;
  }

  // 上り最速を特定
  const fastestLast3f = getFastestLast3fEntry(resultsEntries);

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
  const rpciAnalysis = useMemo(() => {
    return calculateActualRpci(entries, rpciInfo);
  }, [entries, rpciInfo]);

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
                    <th className="px-2 py-2 text-left border min-w-16">騎手</th>
                    <th className="px-2 py-2 text-right border w-16">オッズ</th>
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
      {/* RPCI分析結果 */}
      {rpciAnalysis && (
        <RpciAnalysisCard 
          analysis={rpciAnalysis} 
          courseInfo={rpciInfo || undefined} 
        />
      )}

      {/* レース展開図（残600m → ゴール） */}
      <RaceProgressVisualization entries={entries} distance={distance || 0} defaultOpen={false} />

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
}

function ResultRow({ entry, isFastestLast3f, ratingStats, totalHorses }: ResultRowProps) {
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
        {entry.horse_name}
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
 * RPCI分析結果カード
 */
interface RpciAnalysisCardProps {
  analysis: RaceRpciAnalysis;
  courseInfo?: CourseRpciInfo;
}

function RpciAnalysisCard({ analysis, courseInfo }: RpciAnalysisCardProps) {
  // 傾向に応じたスタイル
  const getTrendStyle = (trend: 'instantaneous' | 'sustained' | 'neutral') => {
    switch (trend) {
      case 'instantaneous':
        return { 
          bg: 'bg-blue-50', 
          border: 'border-blue-200', 
          text: 'text-blue-700',
          icon: <TrendingUp className="w-5 h-5" />,
          label: '瞬発戦'
        };
      case 'sustained':
        return { 
          bg: 'bg-red-50', 
          border: 'border-red-200', 
          text: 'text-red-700',
          icon: <TrendingDown className="w-5 h-5" />,
          label: '持続戦'
        };
      default:
        return { 
          bg: 'bg-gray-50', 
          border: 'border-gray-200', 
          text: 'text-gray-700',
          icon: <Minus className="w-5 h-5" />,
          label: '平均的'
        };
    }
  };

  const style = getTrendStyle(analysis.actualTrend);
  
  // 基準値との比較
  const getComparisonStyle = (compared: 'faster' | 'slower' | 'typical') => {
    switch (compared) {
      case 'slower':
        return { color: 'text-blue-600', label: 'スロー' };
      case 'faster':
        return { color: 'text-red-600', label: 'ハイペース' };
      default:
        return { color: 'text-gray-600', label: '平均的' };
    }
  };

  const compStyle = getComparisonStyle(analysis.comparedToStandard);

  return (
    <div className={`rounded-lg border p-4 ${style.bg} ${style.border}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-full ${style.bg} ${style.text}`}>
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <div className="text-sm font-medium text-gray-600">このレースのペース分析</div>
            <div className={`text-lg font-bold flex items-center gap-2 ${style.text}`}>
              {style.icon}
              <span>{style.label}</span>
              <span className="text-base font-normal">(RPCI: {analysis.actualRpci.toFixed(1)})</span>
            </div>
          </div>
        </div>
        
        {/* 基準値との比較 */}
        {courseInfo && (
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
      <div className="mt-3 pt-3 border-t border-gray-200 grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        <div>
          <div className="text-gray-500 text-xs">実測RPCI</div>
          <div className="font-mono font-bold">{analysis.actualRpci.toFixed(2)}</div>
        </div>
        {courseInfo && (
          <>
            <div>
              <div className="text-gray-500 text-xs">瞬発戦閾値</div>
              <div className="font-mono text-blue-600">&gt;{courseInfo.thresholds.instantaneous.toFixed(1)}</div>
            </div>
            <div>
              <div className="text-gray-500 text-xs">持続戦閾値</div>
              <div className="font-mono text-red-600">&lt;{courseInfo.thresholds.sustained.toFixed(1)}</div>
            </div>
          </>
        )}
        <div>
          <div className="text-gray-500 text-xs">算出馬数</div>
          <div className="font-mono">{analysis.sourceHorses}頭</div>
        </div>
      </div>
    </div>
  );
}
