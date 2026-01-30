'use client';

/**
 * 出走表コンポーネント（可視化強化版）
 * JSON → 直接レンダリング
 * 
 * 改善点:
 * - レイティングにミニバーグラフ追加
 * - オッズ人気にヒートマップカラーリング
 * - AI指数のランク別ハイライト強化
 */

import React from 'react';
import Link from 'next/link';
import {
  HorseEntry,
  getWakuColor,
  toCircleNumber,
  TRAINING_ARROW_LABELS,
} from '@/types/race-data';
import { POSITIVE_TEXT, POSITIVE_BG, POSITIVE_BG_MUTED, RATING_TOP, RATING_HIGH, RATING_MID_HIGH, RATING_MID, getRatingColor } from '@/lib/positive-colors';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { TrainingSummaryData } from '@/lib/data/training-summary-reader';

interface HorseEntryTableProps {
  entries: HorseEntry[];
  showResult?: boolean;
  trainingSummaryMap?: Record<string, TrainingSummaryData>;
}

// レイティング文字列を数値に変換するヘルパー
function parseRating(rating: string | number | undefined | null): number {
  if (rating === undefined || rating === null || rating === '') return 0;
  if (typeof rating === 'number') return isNaN(rating) ? 0 : rating;
  const parsed = parseFloat(String(rating));
  return isNaN(parsed) ? 0 : parsed;
}

// AI指数の値を数値に変換するヘルパー
function parseAiIndex(aiIndex?: string | number): number {
  if (!aiIndex || aiIndex === '' || aiIndex === '-') return 0;
  if (typeof aiIndex === 'number') return isNaN(aiIndex) ? 0 : aiIndex;
  const parsed = parseFloat(String(aiIndex));
  return isNaN(parsed) ? 0 : parsed;
}

// レイティングセルコンポーネント（レース内相対表示版）
// 色分けルール:
// - 黄色系背景: 1位グループ
// - 青系背景: 2-3位グループ
// - 緑系背景: 上位30%
interface RatingCellProps {
  rating: string | number | undefined;
  minRating: number;
  maxRating: number;
  rank: number;  // レース内順位（1が最高）
  totalCount: number;  // 有効レイティング馬数
}

function RatingCell({ rating, minRating, maxRating, rank, totalCount }: RatingCellProps) {
  const ratingNum = parseRating(rating);
  
  // 数値として有効な場合はミニバー表示、そうでなければ元の値を表示
  if (ratingNum > 0 && rank > 0) {
    // 順位に応じた背景色
    const getBgColor = () => {
      // 1位: 黄色系
      if (rank === 1) return "bg-amber-50 dark:bg-amber-900/10";
      // 2-3位: 青系
      if (rank <= 3) return "bg-blue-50 dark:bg-blue-900/10";
      // 上位30%: 緑系
      if (rank <= Math.ceil(totalCount * 0.3)) return "bg-emerald-50 dark:bg-emerald-900/10";
      return "";
    };
    
    return (
      <td className={cn("px-2 py-1.5 text-center border", getBgColor())}>
        <RatingMiniBar 
          rating={ratingNum} 
          minRating={minRating}
          maxRating={maxRating} 
          rank={rank}
          totalCount={totalCount}
        />
      </td>
    );
  }
  
  // 数値変換できない場合は元の値をそのまま表示
  return (
    <td className={cn(
      "px-2 py-1.5 text-center border font-mono",
      getRatingColor(rating as string)
    )}>
      {rating || '-'}
    </td>
  );
}

// レイティングのミニバーコンポーネント（レース内相対表示版）
// 色分けルール:
// - 黄色系: 1位グループ（最上位）
// - 青系: 2位グループ
// - 緑系: 3位グループ
// - 赤色系: 特別注目（将来拡張用）
interface RatingMiniBarProps {
  rating: number;
  minRating: number;
  maxRating: number;
  rank: number;      // レース内順位（1が最高）
  totalCount: number;
  isHighlighted?: boolean;  // 特別注目フラグ（赤色系）
}

function RatingMiniBar({ rating, minRating, maxRating, rank, totalCount, isHighlighted }: RatingMiniBarProps) {
  // バーの幅: レース内での相対位置（最低20%、最高100%）
  const range = maxRating - minRating;
  const percentage = range > 0 
    ? 20 + ((rating - minRating) / range) * 80  // 20-100%の範囲
    : 50;
  
  // 順位に応じた色
  const getBarColor = () => {
    // 特別注目は赤色系
    if (isHighlighted) return 'bg-gradient-to-r from-red-600 to-red-400';
    // 1位グループ: 黄色系（ゴールド）
    if (rank === 1) return 'bg-gradient-to-r from-yellow-500 to-amber-400';
    // 2位グループ: 青系
    if (rank === 2) return 'bg-gradient-to-r from-blue-600 to-blue-400';
    if (rank === 3) return 'bg-gradient-to-r from-blue-500 to-blue-300';
    // 3位グループ: 緑系（上位30%）
    if (rank <= Math.ceil(totalCount * 0.3)) return 'bg-gradient-to-r from-emerald-500 to-emerald-400';
    // 中位
    if (rank <= Math.ceil(totalCount * 0.5)) return 'bg-gradient-to-r from-green-400 to-green-300';
    // それ以下
    return 'bg-gradient-to-r from-gray-400 to-gray-300 dark:from-gray-500 dark:to-gray-400';
  };
  
  // テキスト色（順位ベース）
  const getTextColor = () => {
    if (isHighlighted) return "text-red-600 dark:text-red-400 font-bold";
    if (rank === 1) return "text-amber-600 dark:text-amber-400 font-bold";
    if (rank <= 3) return "text-blue-600 dark:text-blue-400 font-bold";
    if (rank <= Math.ceil(totalCount * 0.3)) return "text-emerald-600 dark:text-emerald-400";
    return "text-gray-600 dark:text-gray-400";
  };
  
  // 順位アイコン
  const getRankIcon = () => {
    if (rank === 1) return '🥇';
    if (rank === 2) return '🥈';
    if (rank === 3) return '🥉';
    return null;
  };
  
  return (
    <div className="flex flex-col items-center gap-0.5">
      <div className="flex items-center gap-1">
        <span className={cn("font-mono text-sm", getTextColor())}>
          {rating.toFixed(1)}
        </span>
        {rank <= 3 && (
          <span className="text-sm">{getRankIcon()}</span>
        )}
      </div>
      <div className="w-14 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
        <div 
          className={cn("h-full rounded-full transition-all duration-500", getBarColor())}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

// オッズ人気バッジ
function OddsRankBadge({ rank, odds }: { rank: number; odds: string }) {
  // NaNや無効な値をチェック
  const validRank = isNaN(rank) ? 0 : rank;
  
  const getBadgeStyle = () => {
    if (validRank === 1) return 'bg-gradient-to-r from-red-500 to-red-400 text-white font-bold shadow-sm';
    if (validRank === 2) return 'bg-gradient-to-r from-blue-500 to-blue-400 text-white';
    if (validRank === 3) return 'bg-gradient-to-r from-emerald-500 to-emerald-400 text-white';
    if (validRank <= 5 && validRank > 0) return 'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300';
    return 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-500';
  };
  
  return (
    <div className="flex flex-col items-end gap-0.5">
      <span className={cn(
        "font-bold",
        validRank === 1 && "text-red-600 dark:text-red-400",
        validRank === 2 && "text-blue-600 dark:text-blue-400",
        validRank === 3 && "text-emerald-600 dark:text-emerald-400"
      )}>
        {odds || '-'}
      </span>
      <span className={cn(
        "inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold",
        getBadgeStyle()
      )}>
        {validRank > 0 ? validRank : '-'}
      </span>
    </div>
  );
}

export default function HorseEntryTable({ 
  entries, 
  showResult = false,
  trainingSummaryMap = {},
}: HorseEntryTableProps) {
  // 馬番順にソート
  const sortedEntries = [...entries].sort((a, b) => a.horse_number - b.horse_number);
  
  // レイティング統計を計算（レース内相対表示用）
  const ratings = entries
    .map(e => ({ horseNumber: e.horse_number, rating: parseRating(e.entry_data.rating) }))
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

  // AI指数統計を計算（レース内相対表示用）
  const aiIndices = entries
    .map(e => ({ horseNumber: e.horse_number, aiIndex: parseAiIndex(e.entry_data.ai_index) }))
    .filter(a => a.aiIndex > 0);
  const sortedAiIndices = [...aiIndices].sort((a, b) => b.aiIndex - a.aiIndex);
  const aiIndexRankMap = new Map<number, number>();
  sortedAiIndices.forEach((a, idx) => {
    aiIndexRankMap.set(a.horseNumber, idx + 1);
  });
  // 2位の値を取得（特別抜けているかどうかの判定用）
  const secondAiIndex = sortedAiIndices.length > 1 ? sortedAiIndices[1].aiIndex : 0;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-gray-100 dark:bg-gray-800">
            <th className="px-2 py-2 text-center border w-10">枠</th>
            <th className="px-2 py-2 text-center border w-10">馬番</th>
            <th className="px-2 py-2 text-left border min-w-32">馬名</th>
            <th className="px-2 py-2 text-center border w-16">性齢</th>
            <th className="px-2 py-2 text-left border min-w-20">騎手</th>
            <th className="px-2 py-2 text-center border w-12">斤量</th>
            <th className="px-2 py-2 text-right border w-16">オッズ</th>
            <th className="px-2 py-2 text-center border w-16">AI指数</th>
            <th className="px-2 py-2 text-center border w-12">レート</th>
            <th className="px-2 py-2 text-center border w-10">印</th>
            <th className="px-2 py-2 text-center border w-10">P</th>
            <th className="px-2 py-2 text-left border min-w-24">短評</th>
            <th className="px-2 py-2 text-center border w-10">調教</th>
            <th className="px-2 py-2 text-left border min-w-28">調教短評</th>
            <th className="px-2 py-2 text-center border w-12">パ評価</th>
            <th className="px-2 py-2 text-left border min-w-24">パコメント</th>
            {showResult && (
              <>
                <th className="px-2 py-2 text-center border w-10">着</th>
                <th className="px-2 py-2 text-center border w-16">タイム</th>
                <th className="px-2 py-2 text-center border w-12">上り</th>
              </>
            )}
          </tr>
        </thead>
        <tbody>
          {sortedEntries.map((entry) => (
            <HorseEntryRow 
              key={entry.horse_number} 
              entry={entry} 
              showResult={showResult}
              trainingSummary={trainingSummaryMap[entry.horse_name]}
              minRating={minRating}
              maxRating={maxRating}
              ratingRank={ratingRankMap.get(entry.horse_number) || 0}
              ratingTotalCount={ratings.length}
              aiIndexRank={aiIndexRankMap.get(entry.horse_number) || 0}
              secondAiIndex={secondAiIndex}
              aiIndexTotalCount={aiIndices.length}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface HorseEntryRowProps {
  entry: HorseEntry;
  showResult: boolean;
  trainingSummary?: TrainingSummaryData;
  minRating: number;
  maxRating: number;
  ratingRank: number;  // レース内順位
  ratingTotalCount: number;  // 有効レイティング馬数
  aiIndexRank: number;  // AI指数レース内順位
  secondAiIndex: number;  // 2位のAI指数値（特別抜けているかどうかの判定用）
  aiIndexTotalCount: number;  // 有効AI指数馬数
}

function HorseEntryRow({ 
  entry, 
  showResult, 
  trainingSummary, 
  minRating,
  maxRating,
  ratingRank,
  ratingTotalCount,
  aiIndexRank,
  secondAiIndex,
  aiIndexTotalCount
}: HorseEntryRowProps) {
  const { entry_data, training_data, result } = entry;
  const wakuColorClass = getWakuColor(entry_data.waku);
  
  // 印の背景色
  const getMarkBgColor = (mark: string) => {
    switch (mark) {
      case '◎': return 'bg-red-100 dark:bg-red-900/30';
      case '○': return 'bg-blue-100 dark:bg-blue-900/30';
      case '▲': return 'bg-yellow-100 dark:bg-yellow-900/30';
      case '△': return 'bg-gray-100 dark:bg-gray-700/30';
      default: return '';
    }
  };

  // パドック評価の背景色
  const getPaddockMarkBgColor = (mark?: string) => {
    if (!mark) return '';
    switch (mark) {
      case '◎': return 'bg-green-100 dark:bg-green-900/30';
      case '○': return 'bg-teal-100 dark:bg-teal-900/30';
      case '▲': return 'bg-amber-100 dark:bg-amber-900/30';
      case '△': return 'bg-gray-100 dark:bg-gray-700/30';
      default: return '';
    }
  };

  // 調教矢印の色
  const getArrowColor = (arrow: string) => {
    switch (arrow) {
      case '↗': return 'text-green-600 dark:text-green-400';
      case '↘': return 'text-red-600 dark:text-red-400';
      default: return 'text-gray-500';
    }
  };

  // 調教矢印のセル背景色
  const getTrainingBgColor = (arrow?: string) => {
    if (!arrow) return '';
    switch (arrow) {
      case '↗': return 'bg-green-100 dark:bg-green-900/30';
      case '↘': return 'bg-red-100 dark:bg-red-900/30';
      default: return '';
    }
  };

  // AI指数ランクのセル背景色（レース内順位ベース）
  const getAiIndexColor = (aiIndex: string | number | undefined, rank: number, secondValue: number, totalCount: number): string => {
    if (!aiIndex || aiIndex === '' || aiIndex === '-' || rank === 0) return '';
    
    const value = parseAiIndex(aiIndex);
    if (value === 0) return '';
    
    // 特別抜けている場合（1位で2位との差が15%以上）: 赤色
    if (rank === 1 && secondValue > 0) {
      const diffPercent = ((value - secondValue) / secondValue) * 100;
      if (diffPercent >= 15) {
        return 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-200 font-bold';
      }
    }
    
    // 1位: 黄色系
    if (rank === 1) return 'bg-amber-50 dark:bg-amber-900/20 text-amber-800 dark:text-amber-200 font-semibold';
    // 2-3位: 青系
    if (rank <= 3) return 'bg-blue-50 dark:bg-blue-900/20 text-blue-800 dark:text-blue-200 font-medium';
    // 上位30%: 緑系
    if (rank <= Math.ceil(totalCount * 0.3)) return 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-800 dark:text-emerald-200';
    
    return '';
  };

  // 総合ポイントに基づく背景色（プラス色で統一）
  const getPointBgColor = (point: number) => {
    if (point >= 30) return `${POSITIVE_BG} font-bold`;
    if (point >= 20) return POSITIVE_BG_MUTED;
    if (point >= 10) return 'bg-emerald-50 dark:bg-emerald-900/10 text-emerald-700 dark:text-emerald-300';
    return '';
  };

  // 人気による行の背景色
  const oddsRankRaw = parseInt(entry_data.odds_rank, 10);
  const oddsRank = isNaN(oddsRankRaw) ? 0 : oddsRankRaw;
  const rowBgClass = oddsRank === 1 
    ? 'bg-amber-50 dark:bg-amber-900/10' 
    : oddsRank <= 3 
      ? 'bg-blue-50/50 dark:bg-blue-900/5' 
      : '';

  return (
    <tr className={`hover:bg-gray-50 dark:hover:bg-gray-800/50 ${rowBgClass}`}>
      {/* 枠番 */}
      <td className={`px-2 py-1.5 text-center border ${wakuColorClass}`}>
        {entry_data.waku}
      </td>
      
      {/* 馬番 */}
      <td className="px-2 py-1.5 text-center border font-bold">
        {entry.horse_number}
      </td>
      
      {/* 馬名 */}
      <td className="px-2 py-1.5 border">
        <Link 
          href={`/horses-v2/${entry.horse_id}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-600 dark:text-blue-400 hover:underline font-medium"
        >
          {entry.horse_name}
        </Link>
      </td>
      
      {/* 性齢 */}
      <td className="px-2 py-1.5 text-center border text-gray-600 dark:text-gray-400">
        {entry_data.age}
      </td>
      
      {/* 騎手 */}
      <td className="px-2 py-1.5 border">
        {entry_data.jockey}
      </td>
      
      {/* 斤量 */}
      <td className="px-2 py-1.5 text-center border">
        {entry_data.weight}
        {entry_data.weight_diff && (
          <span className={`text-xs ml-0.5 ${
            entry_data.weight_diff.startsWith('+') 
              ? 'text-red-500' 
              : entry_data.weight_diff.startsWith('-') 
                ? 'text-blue-500' 
                : ''
          }`}>
            {entry_data.weight_diff}
          </span>
        )}
      </td>
      
      {/* オッズ */}
      <td className={cn(
        "px-2 py-1.5 border",
        oddsRank === 1 && "bg-red-50 dark:bg-red-900/10",
        oddsRank === 2 && "bg-blue-50 dark:bg-blue-900/10",
        oddsRank === 3 && "bg-emerald-50 dark:bg-emerald-900/10"
      )}>
        <OddsRankBadge rank={oddsRank} odds={entry_data.odds} />
      </td>
      
      {/* AI指数 */}
      <td className={cn(
        "px-2 py-1.5 text-center border font-mono",
        getAiIndexColor(entry_data.ai_index, aiIndexRank, secondAiIndex, aiIndexTotalCount)
      )}>
        {entry_data.ai_index || '-'}
        {entry_data.ai_rank && (
          <Badge variant="outline" className="ml-1 text-xs px-1">
            {entry_data.ai_rank}
          </Badge>
        )}
      </td>
      
      {/* レイティング */}
      <RatingCell 
        rating={entry_data.rating} 
        minRating={minRating}
        maxRating={maxRating} 
        rank={ratingRank}
        totalCount={ratingTotalCount}
      />
      
      {/* 本誌印 */}
      <td className={`px-2 py-1.5 text-center border text-lg font-bold ${getMarkBgColor(entry_data.honshi_mark)}`}>
        {entry_data.honshi_mark || '-'}
      </td>
      
      {/* 総合ポイント */}
      <td className={`px-2 py-1.5 text-center border ${getPointBgColor(entry_data.aggregate_mark_point)}`}>
        {entry_data.aggregate_mark_point > 0 ? entry_data.aggregate_mark_point : '-'}
      </td>
      
      {/* 短評 */}
      <td className="px-2 py-1.5 border text-xs text-gray-700 dark:text-gray-300">
        {entry_data.short_comment || '-'}
      </td>
      

      {/* 調教 */}
      <td className={cn(
        "px-2 py-1.5 text-center border",
        getTrainingBgColor(training_data?.training_arrow)
      )}>
        <span className={cn(
          "inline-flex items-center justify-center w-6 h-6 rounded-full text-sm font-bold",
          training_data?.training_arrow === '↗' && "bg-green-500 text-white",
          training_data?.training_arrow === '↘' && "bg-red-500 text-white",
          training_data?.training_arrow === '→' && "bg-gray-300 text-gray-700 dark:bg-gray-600 dark:text-gray-300"
        )}>
          {training_data?.training_arrow || training_data?.evaluation || '-'}
        </span>
      </td>
      
      {/* 調教短評 */}
      <td className="px-2 py-1.5 border text-xs text-gray-700 dark:text-gray-300">
        {training_data?.short_review || '-'}
      </td>
      
      {/* パドック評価 */}
      <td className={`px-2 py-1.5 text-center border text-lg font-bold ${getPaddockMarkBgColor(entry.paddock_info?.mark)}`}>
        {entry.paddock_info?.mark || '-'}
      </td>
      
      {/* パドックコメント */}
      <td className="px-2 py-1.5 border text-xs text-gray-700 dark:text-gray-300">
        {entry.paddock_info?.comment || '-'}
      </td>
      
      {/* 結果（オプション） */}
      {showResult && result && (
        <>
          <td className="px-2 py-1.5 text-center border font-bold">
            <FinishPositionBadge position={result.finish_position} />
          </td>
          <td className="px-2 py-1.5 text-center border font-mono">
            {result.time}
          </td>
          <td className="px-2 py-1.5 text-center border font-mono">
            {result.last_3f}
          </td>
        </>
      )}
      {showResult && !result && (
        <>
          <td className="px-2 py-1.5 text-center border">-</td>
          <td className="px-2 py-1.5 text-center border">-</td>
          <td className="px-2 py-1.5 text-center border">-</td>
        </>
      )}
    </tr>
  );
}

interface FinishPositionBadgeProps {
  position: string;
}

function FinishPositionBadge({ position }: FinishPositionBadgeProps) {
  const pos = parseInt(position, 10);
  
  let bgColor = 'bg-gray-100 text-gray-800';
  if (pos === 1) bgColor = 'bg-yellow-400 text-yellow-900';
  else if (pos === 2) bgColor = 'bg-gray-300 text-gray-800';
  else if (pos === 3) bgColor = 'bg-amber-600 text-white';
  else if (pos <= 5) bgColor = 'bg-blue-100 text-blue-800';
  
  return (
    <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-sm font-bold ${bgColor}`}>
      {position}
    </span>
  );
}
