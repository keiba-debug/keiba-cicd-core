'use client';

/**
 * 調教・厩舎情報コンポーネント（新方式）
 */

import React, { useState } from 'react';
import { HorseEntry, getWakuColor, normalizeHorseName } from '@/types/race-data';
import { POSITIVE_BG, POSITIVE_BG_MUTED } from '@/lib/positive-colors';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';

// 調教サマリー型
interface TrainingSummaryData {
  lapRank?: string;
  timeRank?: string;
  detail?: string;
}

interface TrainingInfoSectionProps {
  entries: HorseEntry[];
  trainingSummaryMap?: Record<string, TrainingSummaryData>;
}

export default function TrainingInfoSection({ entries, trainingSummaryMap = {} }: TrainingInfoSectionProps) {
  // デフォルトは折りたたみ（初期レンダリング高速化）
  const [isOpen, setIsOpen] = useState(false);
  
  // 馬番順にソート
  const sortedEntries = [...entries].sort((a, b) => a.horse_number - b.horse_number);
  
  // 調教または厩舎談話があるエントリーのみフィルター
  const entriesWithInfo = sortedEntries.filter(entry => 
    entry.training_data?.attack_explanation ||
    entry.training_data?.short_review ||
    entry.stable_comment?.comment ||
    entry.previous_race_interview?.interview ||
    entry.previous_race_interview?.next_race_memo
  );

  if (entriesWithInfo.length === 0) {
    return null;
  }

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <div className="border rounded-lg">
        <CollapsibleTrigger asChild>
          <Button
            variant="ghost"
            className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-gray-800"
          >
            <span className="text-lg font-semibold">📝 調教・厩舎情報</span>
            {isOpen ? (
              <ChevronUp className="w-5 h-5" />
            ) : (
              <ChevronDown className="w-5 h-5" />
            )}
          </Button>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-gray-100 dark:bg-gray-800">
                  <th className="px-2 py-2 text-center border w-10">枠</th>
                  <th className="px-2 py-2 text-center border w-10">馬番</th>
                  <th className="px-2 py-2 text-left border min-w-24">馬名</th>
                  <th className="px-2 py-2 text-center border w-10" title="調教タイム分類">ﾀｲﾑ</th>
                  <th className="px-2 py-2 text-center border w-10" title="調教ラップ分類">ﾗｯﾌﾟ</th>
                  <th className="px-2 py-2 text-left border min-w-40" title="調教詳細（最終・1週前）">調教詳細</th>
                  <th className="px-2 py-2 text-center border w-10">調教</th>
                  <th className="px-2 py-2 text-left border min-w-28">調教短評</th>
                  <th className="px-2 py-2 text-left border min-w-48">攻め馬解説</th>
                  <th className="px-2 py-2 text-left border min-w-48">厩舎談話</th>
                  <th className="px-2 py-2 text-left border min-w-48">前走インタビュー</th>
                  <th className="px-2 py-2 text-left border min-w-40">次走へのメモ</th>
                </tr>
              </thead>
              <tbody>
                {sortedEntries.map((entry) => (
                  <TrainingInfoRow 
                    key={entry.horse_number} 
                    entry={entry} 
                    trainingSummary={trainingSummaryMap[entry.horse_name] || trainingSummaryMap[normalizeHorseName(entry.horse_name)]}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}

interface TrainingInfoRowProps {
  entry: HorseEntry;
  trainingSummary?: TrainingSummaryData;
}

function TrainingInfoRow({ entry, trainingSummary }: TrainingInfoRowProps) {
  const { entry_data, training_data, stable_comment, previous_race_interview } = entry;
  const wakuColorClass = getWakuColor(entry_data.waku);

  // 調教矢印の色
  const getArrowColor = (arrow: string) => {
    switch (arrow) {
      case '↗': return 'text-green-600 dark:text-green-400 font-bold';
      case '↘': return 'text-red-600 dark:text-red-400 font-bold';
      default: return 'text-gray-500';
    }
  };

  // 調教タイム分類の背景色（プラス色で統一）
  const getTimeRankBgColor = (rank?: string) => {
    if (!rank || rank === '-') return '';
    switch (rank) {
      case '両': return POSITIVE_BG;
      case '坂':
      case 'コ': return POSITIVE_BG_MUTED;
      default: return '';
    }
  };

  // 調教ラップ分類の背景色（S+/A+ のみプラス色で強調）
  const getLapRankBgColor = (rank?: string) => {
    if (!rank) return '';
    if (rank === 'S+' || rank === 'S=') return POSITIVE_BG;
    if (rank === 'A+' || rank === 'A=') return POSITIVE_BG_MUTED;
    return '';
  };

  // テキストを短縮
  const truncateText = (text: string | undefined, maxLength: number): string => {
    if (!text) return '-';
    // 改行を空白に変換
    const cleaned = text.replace(/\n/g, ' ').replace(/\s+/g, ' ').trim();
    if (cleaned.length <= maxLength) return cleaned;
    return cleaned.substring(0, maxLength) + '...';
  };

  return (
    <tr className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
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
      
      {/* 調教タイム分類（TARGET） */}
      <td className={`px-2 py-1.5 text-center border font-bold ${getTimeRankBgColor(trainingSummary?.timeRank)}`}>
        {trainingSummary?.timeRank || '-'}
      </td>
      
      {/* 調教ラップ分類（TARGET） */}
      <td className={`px-2 py-1.5 text-center border font-bold ${getLapRankBgColor(trainingSummary?.lapRank)}`}>
        {trainingSummary?.lapRank || '-'}
      </td>
      
      {/* 調教詳細（TARGET） */}
      <td className="px-2 py-1.5 border text-xs text-gray-700 dark:text-gray-300">
        {trainingSummary?.detail || '-'}
      </td>
      
      {/* 調教評価 */}
      <td className={`px-2 py-1.5 text-center border ${getArrowColor(training_data?.training_arrow || '')}`}>
        {training_data?.training_arrow || training_data?.evaluation || '-'}
      </td>
      
      {/* 調教短評 */}
      <td className="px-2 py-1.5 border text-xs text-gray-700 dark:text-gray-300">
        {training_data?.short_review || '-'}
      </td>
      
      {/* 攻め馬解説 */}
      <td className="px-2 py-1.5 border text-xs text-gray-700 dark:text-gray-300">
        <ExpandableText 
          text={training_data?.attack_explanation} 
          maxLength={60}
        />
      </td>
      
      {/* 厩舎談話 */}
      <td className="px-2 py-1.5 border text-xs text-gray-700 dark:text-gray-300">
        <ExpandableText 
          text={stable_comment?.comment} 
          maxLength={60}
        />
      </td>
      
      {/* 前走インタビュー */}
      <td className="px-2 py-1.5 border text-xs text-gray-700 dark:text-gray-300">
        <ExpandableText 
          text={previous_race_interview?.interview} 
          maxLength={60}
        />
      </td>
      
      {/* 次走へのメモ */}
      <td className="px-2 py-1.5 border text-xs text-gray-700 dark:text-gray-300">
        <ExpandableText 
          text={previous_race_interview?.next_race_memo} 
          maxLength={50}
        />
      </td>
    </tr>
  );
}

interface ExpandableTextProps {
  text: string | undefined;
  maxLength: number;
}

function ExpandableText({ text, maxLength }: ExpandableTextProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  
  if (!text) return <span className="text-gray-400">-</span>;
  
  // 改行を空白に変換
  const cleaned = text.replace(/\n/g, ' ').replace(/\s+/g, ' ').trim();
  
  if (cleaned.length <= maxLength) {
    return <span>{cleaned}</span>;
  }
  
  if (isExpanded) {
    return (
      <span>
        {cleaned}
        <button
          onClick={() => setIsExpanded(false)}
          className="ml-1 text-blue-500 hover:underline"
        >
          [閉じる]
        </button>
      </span>
    );
  }
  
  return (
    <span>
      {cleaned.substring(0, maxLength)}...
      <button
        onClick={() => setIsExpanded(true)}
        className="ml-1 text-blue-500 hover:underline"
      >
        [続き]
      </button>
    </span>
  );
}

/**
 * 簡易カード形式の調教情報表示（モバイル向け）
 */
export function TrainingInfoCards({ entries }: TrainingInfoSectionProps) {
  const [expandedHorses, setExpandedHorses] = useState<Set<number>>(new Set());
  
  // 馬番順にソート
  const sortedEntries = [...entries].sort((a, b) => a.horse_number - b.horse_number);
  
  const toggleExpand = (horseNumber: number) => {
    setExpandedHorses(prev => {
      const next = new Set(prev);
      if (next.has(horseNumber)) {
        next.delete(horseNumber);
      } else {
        next.add(horseNumber);
      }
      return next;
    });
  };

  return (
    <div className="space-y-2">
      <h3 className="text-lg font-semibold px-2">📝 調教・厩舎情報</h3>
      
      {sortedEntries.map((entry) => {
        const { training_data, stable_comment, previous_race_interview } = entry;
        const hasInfo = training_data?.attack_explanation || 
                       stable_comment?.comment || 
                       previous_race_interview?.interview;
        
        if (!hasInfo) return null;
        
        const isExpanded = expandedHorses.has(entry.horse_number);
        
        return (
          <div 
            key={entry.horse_number}
            className="border rounded-lg overflow-hidden"
          >
            <button
              onClick={() => toggleExpand(entry.horse_number)}
              className="w-full flex items-center gap-2 p-3 hover:bg-gray-50 dark:hover:bg-gray-800"
            >
              <span className={`w-6 h-6 flex items-center justify-center rounded text-sm ${getWakuColor(entry.entry_data.waku)}`}>
                {entry.entry_data.waku}
              </span>
              <span className="font-bold">{entry.horse_number}</span>
              <span className="font-medium flex-1 text-left">{entry.horse_name}</span>
              {training_data?.training_arrow && (
                <Badge variant={training_data.training_arrow === '↗' ? 'default' : 'secondary'}>
                  {training_data.training_arrow}
                </Badge>
              )}
              {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
            
            {isExpanded && (
              <div className="p-3 border-t space-y-2 text-sm">
                {training_data?.attack_explanation && (
                  <div>
                    <span className="font-medium text-gray-600 dark:text-gray-400">攻め馬解説: </span>
                    <span>{training_data.attack_explanation}</span>
                  </div>
                )}
                {stable_comment?.comment && (
                  <div>
                    <span className="font-medium text-gray-600 dark:text-gray-400">厩舎談話: </span>
                    <span>{stable_comment.comment}</span>
                  </div>
                )}
                {previous_race_interview?.interview && (
                  <div>
                    <span className="font-medium text-gray-600 dark:text-gray-400">前走インタビュー: </span>
                    <span>{previous_race_interview.interview}</span>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
