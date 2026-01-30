'use client';

/**
 * 調教分析セクション
 *
 * - 最終追切: 当週の水曜か木曜（場所/スピード/ラップ）
 * - 土日追切: 前週の土曜か日曜、両方あればタイムが早いほう
 * - 一週前追切: 前週の水曜か木曜
 * - 調教評価（矢印）・攻め馬解説
 */

import React, { useState } from 'react';
import { HorseEntry, getWakuColor } from '@/types/race-data';
import { POSITIVE_TEXT, POSITIVE_BG, POSITIVE_BG_MUTED } from '@/lib/positive-colors';
import { ChevronDown, ChevronUp, Dumbbell } from 'lucide-react';
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
  // 最終追切: 当週の水曜か木曜
  finalLocation?: string;
  finalSpeed?: string;
  finalLap?: string;
  finalTime4F?: number;
  finalLap1?: number;
  // 土日追切: 前週の土曜か日曜（両方あればタイムが早いほう）
  weekendLocation?: string;
  weekendSpeed?: string;
  weekendLap?: string;
  weekendTime4F?: number;
  weekendLap1?: number;
  // 一週前追切: 前週の水曜か木曜
  weekAgoLocation?: string;
  weekAgoSpeed?: string;
  weekAgoLap?: string;
  weekAgoTime4F?: number;
  weekAgoLap1?: number;
}

interface TrainingAnalysisSectionProps {
  entries: HorseEntry[];
  trainingSummaryMap?: Record<string, TrainingSummaryData>;
}

export default function TrainingAnalysisSection({ 
  entries, 
  trainingSummaryMap = {} 
}: TrainingAnalysisSectionProps) {
  const [isOpen, setIsOpen] = useState(true);
  
  // 馬番順にソート
  const sortedEntries = [...entries].sort((a, b) => a.horse_number - b.horse_number);
  
  // 調教情報があるエントリーのみフィルター
  const entriesWithTraining = sortedEntries.filter(entry => 
    entry.training_data?.attack_explanation ||
    entry.training_data?.short_review ||
    entry.training_data?.evaluation ||
    entry.training_data?.training_arrow ||
    trainingSummaryMap[entry.horse_name]?.finalLap ||
    trainingSummaryMap[entry.horse_name]?.weekendLap ||
    trainingSummaryMap[entry.horse_name]?.weekAgoLap ||
    trainingSummaryMap[entry.horse_name]?.timeRank
  );

  if (entriesWithTraining.length === 0) {
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
              <Dumbbell className="w-5 h-5" />
              調教分析
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
                  <th className="px-2 py-2 text-left border min-w-20">馬名</th>
                  <th className="px-2 py-2 text-left border min-w-16">調教師</th>
                  {/* 最終 → 土日 → 一週前の順 */}
                  <th className="px-1 py-2 text-center border w-10" title="最終追切（当週水・木）場所">場所</th>
                  <th className="px-1 py-2 text-center border w-10" title="最終追切スピード（◎=好タイム）">速</th>
                  <th className="px-1 py-2 text-center border w-12" title="最終追切ラップ分類">ラップ</th>
                  <th className="px-1 py-2 text-center border w-10" title="土日追切（前週土・日）場所">場所</th>
                  <th className="px-1 py-2 text-center border w-10" title="土日追切スピード（◎=好タイム）">速</th>
                  <th className="px-1 py-2 text-center border w-12" title="土日追切ラップ分類">ラップ</th>
                  <th className="px-1 py-2 text-center border w-10" title="一週前追切（前週水・木）場所">場所</th>
                  <th className="px-1 py-2 text-center border w-10" title="一週前追切スピード（◎=好タイム）">速</th>
                  <th className="px-1 py-2 text-center border w-12" title="一週前追切ラップ分類">ラップ</th>
                  {/* その他 */}
                  <th className="px-2 py-2 text-center border w-10" title="調教評価">評価</th>
                  <th className="px-2 py-2 text-left border min-w-24">調教短評</th>
                  <th className="px-2 py-2 text-left border min-w-48">攻め馬解説</th>
                </tr>
                {/* サブヘッダー: 最終 → 土日 → 一週前 */}
                <tr className="bg-gray-50 dark:bg-gray-800/50 text-xs text-muted-foreground">
                  <th colSpan={4} className="border"></th>
                  <th colSpan={3} className="border text-center">最終</th>
                  <th colSpan={3} className="border text-center">土日</th>
                  <th colSpan={3} className="border text-center">一週前</th>
                  <th colSpan={3} className="border"></th>
                </tr>
              </thead>
              <tbody>
                {sortedEntries.map((entry) => (
                  <TrainingAnalysisRow 
                    key={entry.horse_number} 
                    entry={entry} 
                    trainingSummary={trainingSummaryMap[entry.horse_name]}
                  />
                ))}
              </tbody>
            </table>
          </div>
          
          {/* 凡例 */}
          <div className="p-3 border-t bg-gray-50 dark:bg-gray-800/50 text-xs text-gray-600 dark:text-gray-400">
            <div className="flex flex-wrap gap-4">
              <span><strong>場所:</strong> 坂=坂路 / コ=コース</span>
              <span><strong>速:</strong> ◎=好タイム</span>
              <span><strong>ラップ:</strong> SS～D（終い重点度）、+ 加速 / = 同 / - 減速</span>
            </div>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}

interface TrainingAnalysisRowProps {
  entry: HorseEntry;
  trainingSummary?: TrainingSummaryData;
}

function TrainingAnalysisRow({ entry, trainingSummary }: TrainingAnalysisRowProps) {
  const { entry_data, training_data } = entry;
  const wakuColorClass = getWakuColor(entry_data.waku);

  // 調教矢印の色（プラス＝緑、マイナス＝赤）
  const getArrowColor = (arrow: string) => {
    switch (arrow) {
      case '↗': return POSITIVE_TEXT;
      case '↘': return 'text-red-600 dark:text-red-400 font-bold';
      default: return 'text-gray-500';
    }
  };

  // 場所は色分けしない（坂/コとも同じ表示）
  const getLocationBgColor = (_location?: string) => '';

  // 好タイム◎はプラス色で統一
  const getSpeedColor = (speed?: string) => (speed === '◎' ? POSITIVE_TEXT : '');

  // ラップ S+ S= A+ A= のみプラス色で強調
  const getLapRankBgColor = (rank?: string) => {
    if (!rank) return '';
    if (rank === 'S+' || rank === 'S=') return POSITIVE_BG;
    if (rank === 'A+' || rank === 'A=') return POSITIVE_BG_MUTED;
    return '';
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
      <td className="px-2 py-1.5 border font-medium text-xs">
        {entry.horse_name}
      </td>
      
      {/* 調教師 */}
      <td className="px-2 py-1.5 border text-xs text-gray-700 dark:text-gray-300">
        {entry_data.trainer || '-'}
      </td>
      
      {/* 最終追切 - 場所 */}
      <td className={`px-1 py-1.5 text-center border font-bold ${getLocationBgColor(trainingSummary?.finalLocation)}`}>
        {trainingSummary?.finalLocation || '-'}
      </td>
      
      {/* 最終追切 - スピード */}
      <td className={`px-1 py-1.5 text-center border ${getSpeedColor(trainingSummary?.finalSpeed)}`}>
        {trainingSummary?.finalSpeed || '-'}
      </td>
      
      {/* 最終追切 - ラップ */}
      <td className={`px-1 py-1.5 text-center border font-bold ${getLapRankBgColor(trainingSummary?.finalLap)}`}>
        {trainingSummary?.finalLap || '-'}
      </td>
      
      {/* 土日追切 - 場所 */}
      <td className={`px-1 py-1.5 text-center border font-bold ${getLocationBgColor(trainingSummary?.weekendLocation)}`}>
        {trainingSummary?.weekendLocation || '-'}
      </td>
      
      {/* 土日追切 - スピード */}
      <td className={`px-1 py-1.5 text-center border ${getSpeedColor(trainingSummary?.weekendSpeed)}`}>
        {trainingSummary?.weekendSpeed || '-'}
      </td>
      
      {/* 土日追切 - ラップ */}
      <td className={`px-1 py-1.5 text-center border font-bold ${getLapRankBgColor(trainingSummary?.weekendLap)}`}>
        {trainingSummary?.weekendLap || '-'}
      </td>
      
      {/* 一週前追切 - 場所 */}
      <td className={`px-1 py-1.5 text-center border font-bold ${getLocationBgColor(trainingSummary?.weekAgoLocation)}`}>
        {trainingSummary?.weekAgoLocation || '-'}
      </td>
      
      {/* 一週前追切 - スピード */}
      <td className={`px-1 py-1.5 text-center border ${getSpeedColor(trainingSummary?.weekAgoSpeed)}`}>
        {trainingSummary?.weekAgoSpeed || '-'}
      </td>
      
      {/* 一週前追切 - ラップ */}
      <td className={`px-1 py-1.5 text-center border font-bold ${getLapRankBgColor(trainingSummary?.weekAgoLap)}`}>
        {trainingSummary?.weekAgoLap || '-'}
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
