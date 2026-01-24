'use client';

/**
 * レース結果コンポーネント（新方式）
 */

import React, { useState } from 'react';
import { 
  HorseEntry, 
  PayoutEntry, 
  getWakuColor, 
  toCircleNumber,
  parseFinishPosition,
} from '@/types/race-data';
import { Badge } from '@/components/ui/badge';
import { ChevronDown, ChevronUp, Trophy, Timer, TrendingUp } from 'lucide-react';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { Button } from '@/components/ui/button';

interface RaceResultSectionProps {
  entries: HorseEntry[];
  payouts?: PayoutEntry[] | null;
}

export default function RaceResultSection({ entries, payouts }: RaceResultSectionProps) {
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

  return (
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
                    <th className="px-2 py-2 text-left border min-w-32">寸評</th>
                  </tr>
                </thead>
                <tbody>
                  {resultsEntries.slice(0, 12).map((entry) => (
                    <ResultRow 
                      key={entry.horse_number} 
                      entry={entry}
                      isFastestLast3f={entry.horse_number === fastestLast3f?.horse_number}
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
  );
}

interface ResultRowProps {
  entry: HorseEntry;
  isFastestLast3f: boolean;
}

function ResultRow({ entry, isFastestLast3f }: ResultRowProps) {
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
      
      {/* 上り3F */}
      <td className={`px-2 py-1.5 text-center border font-mono ${
        isFastestLast3f ? 'text-red-600 dark:text-red-400 font-bold' : ''
      }`}>
        {result.last_3f}
        {isFastestLast3f && <span className="ml-0.5">🏃</span>}
      </td>
      
      {/* 通過順 */}
      <td className="px-2 py-1.5 text-center border text-gray-600 dark:text-gray-400">
        {result.passing_orders || '-'}
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
      
      {/* 寸評 */}
      <td className="px-2 py-1.5 border text-xs text-gray-700 dark:text-gray-300">
        {sunpyo || '-'}
      </td>
    </tr>
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
