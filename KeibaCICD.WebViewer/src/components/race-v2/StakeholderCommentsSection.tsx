'use client';

/**
 * 関係者コメント分析セクション
 * 
 * 厩舎・関係者からのコメント情報を表示
 * - 厩舎談話
 * - 前走インタビュー
 * - 次走へのメモ
 */

import React, { useState } from 'react';
import { HorseEntry, getWakuColor, formatTrainerName } from '@/types/race-data';
import { ChevronDown, ChevronUp, MessageSquare } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';

interface StakeholderCommentsSectionProps {
  entries: HorseEntry[];
}

export default function StakeholderCommentsSection({ entries }: StakeholderCommentsSectionProps) {
  const [isOpen, setIsOpen] = useState(true);
  
  // 馬番順にソート
  const sortedEntries = [...entries].sort((a, b) => a.horse_number - b.horse_number);
  
  // コメント情報があるエントリーのみフィルター
  const entriesWithComments = sortedEntries.filter(entry => 
    entry.stable_comment?.comment ||
    entry.previous_race_interview?.interview ||
    entry.previous_race_interview?.next_race_memo
  );

  if (entriesWithComments.length === 0) {
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
            <span className="text-lg font-semibold flex items-center gap-2">
              <MessageSquare className="w-5 h-5" />
              関係者コメント分析
            </span>
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
                  <th className="px-2 py-2 text-center border w-10">番</th>
                  <th className="px-2 py-2 text-left border min-w-24">馬名</th>
                  <th className="px-2 py-2 text-left border min-w-24">調教師</th>
                  <th className="px-2 py-2 text-left border" style={{ minWidth: '280px' }}>厩舎談話</th>
                  <th className="px-2 py-2 text-left border" style={{ minWidth: '280px' }}>前走インタビュー</th>
                  <th className="px-2 py-2 text-left border" style={{ minWidth: '200px' }}>次走へのメモ</th>
                </tr>
              </thead>
              <tbody>
                {sortedEntries.map((entry) => (
                  <StakeholderCommentRow 
                    key={entry.horse_number} 
                    entry={entry} 
                  />
                ))}
              </tbody>
            </table>
          </div>
          
          {/* データ件数 */}
          <div className="p-3 border-t bg-gray-50 dark:bg-gray-800/50 text-xs text-gray-600 dark:text-gray-400">
            <span>コメントあり: {entriesWithComments.length}頭 / 全{sortedEntries.length}頭</span>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}

interface StakeholderCommentRowProps {
  entry: HorseEntry;
}

function StakeholderCommentRow({ entry }: StakeholderCommentRowProps) {
  const { entry_data, stable_comment, previous_race_interview } = entry;
  const wakuColorClass = getWakuColor(entry_data.waku);
  
  // このエントリーにコメントがあるかどうか
  const hasComment = stable_comment?.comment || 
                     previous_race_interview?.interview || 
                     previous_race_interview?.next_race_memo;
  
  // コメントがない行は薄く表示
  const rowClass = hasComment 
    ? "hover:bg-gray-50 dark:hover:bg-gray-800/50" 
    : "hover:bg-gray-50 dark:hover:bg-gray-800/50 opacity-50";

  return (
    <tr className={rowClass}>
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
      
      {/* 調教師 */}
      <td 
        className="px-2 py-1.5 border text-xs text-gray-700 dark:text-gray-300 whitespace-nowrap"
        title={entry_data.trainer_comment || undefined}
      >
        {formatTrainerName(entry_data.trainer, entry_data.trainer_tozai)}
      </td>
      
      {/* 厩舎談話 */}
      <td className="px-2 py-1.5 border text-xs text-gray-700 dark:text-gray-300">
        <ExpandableText 
          text={stable_comment?.comment} 
          maxLength={100}
        />
      </td>
      
      {/* 前走インタビュー */}
      <td className="px-2 py-1.5 border text-xs text-gray-700 dark:text-gray-300">
        <ExpandableText 
          text={previous_race_interview?.interview} 
          maxLength={100}
        />
      </td>
      
      {/* 次走へのメモ */}
      <td className="px-2 py-1.5 border text-xs text-gray-700 dark:text-gray-300">
        <ExpandableText 
          text={previous_race_interview?.next_race_memo} 
          maxLength={80}
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
