'use client';

/**
 * 出走表コンポーネント（新方式）
 * JSON → 直接レンダリング
 */

import React from 'react';
import Link from 'next/link';
import {
  HorseEntry,
  getWakuColor,
  toCircleNumber,
  TRAINING_ARROW_LABELS,
} from '@/types/race-data';
import { Badge } from '@/components/ui/badge';

// 調教サマリー型
interface TrainingSummaryData {
  lapRank?: string;
  timeRank?: string;
  detail?: string;
}

interface HorseEntryTableProps {
  entries: HorseEntry[];
  showResult?: boolean;
  trainingSummaryMap?: Record<string, TrainingSummaryData>;
}

export default function HorseEntryTable({ 
  entries, 
  showResult = false,
  trainingSummaryMap = {},
}: HorseEntryTableProps) {
  // 馬番順にソート
  const sortedEntries = [...entries].sort((a, b) => a.horse_number - b.horse_number);

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
            <th className="px-2 py-2 text-center border w-10" title="調教タイム分類">ﾀｲﾑ</th>
            <th className="px-2 py-2 text-center border w-10" title="調教ラップ分類">ﾗｯﾌﾟ</th>
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
}

function HorseEntryRow({ entry, showResult, trainingSummary }: HorseEntryRowProps) {
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

  // 調教タイム分類の背景色（坂, コ, 両）
  const getTimeRankBgColor = (rank?: string) => {
    if (!rank || rank === '-') return '';
    switch (rank) {
      case '両': return 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300';
      case '坂': return 'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300';
      case 'コ': return 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300';
      default: return '';
    }
  };

  // 調教ラップ分類の背景色（SS, S+, A-, B=, etc.）
  const getLapRankBgColor = (rank?: string) => {
    if (!rank) return '';
    if (rank.startsWith('SS')) return 'bg-red-200 dark:bg-red-800/50 text-red-800 dark:text-red-200';
    if (rank.startsWith('S')) return 'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300';
    if (rank.startsWith('A')) return 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300';
    if (rank.startsWith('B')) return 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300';
    if (rank.startsWith('C')) return 'bg-gray-100 dark:bg-gray-800/30 text-gray-600 dark:text-gray-400';
    return '';
  };

  // AI指数ランクのセル背景色
  const getAiRankBgColor = (rank?: string) => {
    if (!rank) return '';
    switch (rank) {
      case 'Ａ':
      case 'A': return 'bg-purple-100 dark:bg-purple-900/30';
      case 'Ｂ':
      case 'B': return 'bg-blue-50 dark:bg-blue-900/20';
      default: return '';
    }
  };

  // 総合ポイントに基づく背景色
  const getPointBgColor = (point: number) => {
    if (point >= 30) return 'bg-red-100 dark:bg-red-900/30 font-bold';
    if (point >= 20) return 'bg-orange-100 dark:bg-orange-900/30';
    if (point >= 10) return 'bg-yellow-100 dark:bg-yellow-900/30';
    return '';
  };

  // 人気による行の背景色
  const oddsRank = parseInt(entry_data.odds_rank, 10);
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
      <td className="px-2 py-1.5 text-right border">
        <span className={oddsRank <= 3 ? 'font-bold' : ''}>
          {entry_data.odds}
        </span>
        <span className="text-xs text-gray-500 ml-1">
          ({entry_data.odds_rank})
        </span>
      </td>
      
      {/* AI指数 */}
      <td className={`px-2 py-1.5 text-center border ${getAiRankBgColor(entry_data.ai_rank)}`}>
        <span className="font-mono">{entry_data.ai_index}</span>
        {entry_data.ai_rank && (
          <Badge variant="outline" className="ml-1 text-xs px-1">
            {entry_data.ai_rank}
          </Badge>
        )}
      </td>
      
      {/* レイティング */}
      <td className="px-2 py-1.5 text-center border font-mono">
        {entry_data.rating || '-'}
      </td>
      
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
      
      {/* 調教タイム分類（TARGET） */}
      <td className={`px-2 py-1.5 text-center border font-bold ${getTimeRankBgColor(trainingSummary?.timeRank)}`}>
        {trainingSummary?.timeRank || '-'}
      </td>
      
      {/* 調教ラップ分類（TARGET） */}
      <td className={`px-2 py-1.5 text-center border font-bold ${getLapRankBgColor(trainingSummary?.lapRank)}`}>
        {trainingSummary?.lapRank || '-'}
      </td>
      
      {/* 調教 */}
      <td className={`px-2 py-1.5 text-center border ${getTrainingBgColor(training_data?.training_arrow)} ${getArrowColor(training_data?.training_arrow || '')}`}>
        {training_data?.training_arrow || training_data?.evaluation || '-'}
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
