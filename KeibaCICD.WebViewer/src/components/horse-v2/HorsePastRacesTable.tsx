'use client';

/**
 * 馬過去レース成績テーブルコンポーネント（v2）
 */

import React, { useState } from 'react';
import Link from 'next/link';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { HorseRaceResult } from '@/lib/data/integrated-horse-reader';

interface HorsePastRacesTableProps {
  races: HorseRaceResult[];
}

// 着順バッジの色
function getPositionBadgeClass(position: string): string {
  const pos = parseInt(position, 10);
  if (pos === 1) return 'bg-yellow-400 text-yellow-900';
  if (pos === 2) return 'bg-gray-300 text-gray-800';
  if (pos === 3) return 'bg-amber-600 text-white';
  if (pos <= 5) return 'bg-blue-100 text-blue-800';
  return 'bg-gray-100 text-gray-800';
}

// 本誌印の背景色
function getMarkBgColor(mark: string): string {
  switch (mark) {
    case '◎': return 'bg-red-100 dark:bg-red-900/30';
    case '○': return 'bg-blue-100 dark:bg-blue-900/30';
    case '▲': return 'bg-yellow-100 dark:bg-yellow-900/30';
    case '△': return 'bg-gray-100 dark:bg-gray-700/30';
    default: return '';
  }
}

// コース種別バッジ
function getCourseBadgeClass(distance: string): string {
  if (distance.includes('芝')) {
    return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300';
  }
  if (distance.includes('ダ') || distance.includes('D')) {
    return 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300';
  }
  if (distance.includes('障')) {
    return 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300';
  }
  return 'bg-gray-100 text-gray-800';
}

// 枠番の色
function getFrameColor(frame: number): string {
  const colors: Record<number, string> = {
    1: 'bg-white text-gray-800 border border-gray-300',
    2: 'bg-black text-white',
    3: 'bg-red-500 text-white',
    4: 'bg-blue-500 text-white',
    5: 'bg-yellow-400 text-gray-800',
    6: 'bg-green-500 text-white',
    7: 'bg-orange-500 text-white',
    8: 'bg-pink-400 text-white',
  };
  return colors[frame] || 'bg-gray-200 text-gray-800';
}

function RaceRow({ race, isExpanded, onToggle }: { 
  race: HorseRaceResult; 
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const pos = parseInt(race.finishPosition, 10);
  const isGoodResult = !isNaN(pos) && pos <= 3;

  // レースリンク生成
  const raceLink = race.raceId 
    ? `/races-v2/${race.date.replace(/\//g, '-')}/${encodeURIComponent(race.track)}/${race.raceId}`
    : null;

  return (
    <>
      <tr 
        className={`hover:bg-gray-50 dark:hover:bg-gray-800/50 cursor-pointer ${
          isGoodResult ? 'bg-amber-50/50 dark:bg-amber-900/10' : ''
        }`}
        onClick={onToggle}
      >
        {/* 展開ボタン */}
        <td className="px-1 py-1.5 border text-center">
          {isExpanded ? (
            <ChevronUp className="w-3 h-3 inline text-gray-400" />
          ) : (
            <ChevronDown className="w-3 h-3 inline text-gray-400" />
          )}
        </td>

        {/* 日付 */}
        <td className="px-1 py-1.5 border whitespace-nowrap text-xs">
          {race.date}
        </td>

        {/* 競馬場 */}
        <td className="px-1 py-1.5 border text-center text-xs">
          {race.track}
        </td>

        {/* レース */}
        <td className="px-1 py-1.5 border text-xs">
          {raceLink ? (
            <Link 
              href={raceLink}
              className="text-blue-600 hover:underline"
              onClick={(e) => e.stopPropagation()}
            >
              {race.raceNumber}R
              {race.raceName && <span className="ml-0.5">{race.raceName.slice(0, 6)}</span>}
            </Link>
          ) : (
            <span>
              {race.raceNumber}R
              {race.raceName && <span className="ml-0.5">{race.raceName.slice(0, 6)}</span>}
            </span>
          )}
          {race.raceClass && (
            <div className="text-[10px] text-gray-500 truncate">{race.raceClass}</div>
          )}
        </td>

        {/* 距離 */}
        <td className="px-1 py-1.5 border text-center">
          {race.distance ? (
            <span className={`px-1 py-0.5 rounded text-xs ${getCourseBadgeClass(race.distance)}`}>
              {race.distance}
            </span>
          ) : '-'}
        </td>

        {/* 頭数 */}
        <td className="px-1 py-1.5 border text-center text-xs">
          {race.headCount > 0 ? race.headCount : '-'}
        </td>

        {/* 馬場 */}
        <td className="px-1 py-1.5 border text-center text-xs">
          {race.condition || '-'}
        </td>

        {/* 枠番 */}
        <td className="px-1 py-1.5 border text-center">
          <span className={`inline-flex items-center justify-center w-5 h-5 rounded text-[10px] font-bold ${getFrameColor(race.frameNumber)}`}>
            {race.frameNumber || '-'}
          </span>
        </td>

        {/* 馬番 */}
        <td className="px-1 py-1.5 border text-center text-xs">
          {race.horseNumber || '-'}
        </td>

        {/* 騎手 */}
        <td className="px-1 py-1.5 border text-xs truncate max-w-14">
          {race.jockey || '-'}
        </td>

        {/* 斤量 */}
        <td className="px-1 py-1.5 border text-center text-xs">
          {race.weight || '-'}
        </td>

        {/* 馬体重 */}
        <td className="px-1 py-1.5 border text-center text-xs whitespace-nowrap">
          {race.horseWeight ? (
            <span>
              {race.horseWeight}
              {race.horseWeightDiff && (
                <span className={`text-[10px] ${
                  race.horseWeightDiff.startsWith('+') ? 'text-red-500' : 
                  race.horseWeightDiff.startsWith('-') ? 'text-blue-500' : ''
                }`}>
                  ({race.horseWeightDiff})
                </span>
              )}
            </span>
          ) : '-'}
        </td>

        {/* 本誌印 */}
        <td className={`px-1 py-1.5 border text-center font-bold text-xs ${getMarkBgColor(race.honshiMark)}`}>
          {race.honshiMark || '-'}
        </td>

        {/* オッズ */}
        <td className="px-1 py-1.5 border text-center text-xs">
          {race.odds || '-'}
        </td>

        {/* 人気 */}
        <td className="px-1 py-1.5 border text-center text-xs">
          {race.popularity ? `${race.popularity}人` : '-'}
        </td>

        {/* 着順 */}
        <td className="px-1 py-1.5 border text-center">
          <span className={`inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold ${getPositionBadgeClass(race.finishPosition)}`}>
            {race.finishPosition || '-'}
          </span>
        </td>

        {/* タイム */}
        <td className="px-1 py-1.5 border text-center font-mono text-xs">
          {race.time || '-'}
        </td>

        {/* 前半3F */}
        <td className="px-1 py-1.5 border text-center font-mono text-xs">
          {race.first3f || '-'}
        </td>

        {/* 上がり3F */}
        <td className="px-1 py-1.5 border text-center font-mono text-xs">
          {race.last3f || '-'}
        </td>

        {/* 4角 */}
        <td className="px-1 py-1.5 border text-center text-xs">
          {race.corner4Pos || '-'}
        </td>

        {/* 通過 */}
        <td className="px-1 py-1.5 border text-center text-xs">
          {race.cornerPositions || '-'}
        </td>

        {/* 寸評 */}
        <td className="px-1 py-1.5 border text-xs truncate max-w-20" title={race.sunpyou}>
          {race.sunpyou || '-'}
        </td>
      </tr>

      {/* 展開時の詳細行 */}
      {isExpanded && (
        <tr className="bg-gray-50 dark:bg-gray-800/30">
          <td colSpan={22} className="px-4 py-3 border">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
              {race.sunpyou && (
                <div className="lg:col-span-3">
                  <span className="text-muted-foreground">寸評:</span>
                  <p className="mt-1">{race.sunpyou}</p>
                </div>
              )}
              {race.shortComment && (
                <div>
                  <span className="text-muted-foreground">短評:</span>
                  <p className="mt-1">{race.shortComment}</p>
                </div>
              )}
              {race.trainingDetail && (
                <div className="lg:col-span-2">
                  <span className="text-muted-foreground">調教タイム:</span>
                  <p className="mt-1 font-mono text-xs">
                    {race.trainingDetail.split(' / ').map((part, idx) => (
                      <span key={idx} className={`block ${race.trainingFinalSpeed === '◎' && idx === 0 ? 'text-green-600 font-medium' : ''}`}>
                        {part}
                        {race.trainingFinalSpeed === '◎' && idx === 0 && <span className="ml-1">◎</span>}
                      </span>
                    ))}
                    {race.trainingLapRank && <span className="text-muted-foreground ml-2">(ラップ: {race.trainingLapRank})</span>}
                  </p>
                </div>
              )}
              {race.trainingComment && (
                <div>
                  <span className="text-muted-foreground">調教短評:</span>
                  <p className="mt-1">
                    {race.trainingArrow && <span className="mr-1">{race.trainingArrow}</span>}
                    {race.trainingComment}
                  </p>
                </div>
              )}
              {race.attackExplanation && (
                <div>
                  <span className="text-muted-foreground">攻め馬解説:</span>
                  <p className="mt-1">{race.attackExplanation}</p>
                </div>
              )}
              {race.stableComment && (
                <div>
                  <span className="text-muted-foreground">厩舎談話:</span>
                  <p className="mt-1">{race.stableComment}</p>
                </div>
              )}
              {(race.paddockMark || race.paddockComment) && (
                <div>
                  <span className="text-muted-foreground">パドック:</span>
                  <p className="mt-1">
                    {race.paddockMark && <span className="mr-1 font-bold">{race.paddockMark}</span>}
                    {race.paddockComment}
                  </p>
                </div>
              )}
              {race.resultMemo && (
                <div>
                  <span className="text-muted-foreground">結果メモ:</span>
                  <p className="mt-1">{race.resultMemo}</p>
                </div>
              )}
              {race.resultComment && (
                <div>
                  <span className="text-muted-foreground">騎手コメント:</span>
                  <p className="mt-1">{race.resultComment}</p>
                </div>
              )}
              {race.timeDiff && (
                <div>
                  <span className="text-muted-foreground">着差:</span>
                  <span className="ml-1">{race.timeDiff}</span>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export function HorsePastRacesTable({ races }: HorsePastRacesTableProps) {
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());
  const [showAll, setShowAll] = useState(false);

  const toggleRow = (index: number) => {
    setExpandedRows(prev => {
      const newSet = new Set(prev);
      if (newSet.has(index)) {
        newSet.delete(index);
      } else {
        newSet.add(index);
      }
      return newSet;
    });
  };

  const displayRaces = showAll ? races : races.slice(0, 10);

  if (races.length === 0) {
    return (
      <div className="bg-white dark:bg-gray-900 rounded-lg border p-6">
        <h2 className="text-lg font-semibold mb-4">📋 過去レース成績</h2>
        <p className="text-muted-foreground">過去レースデータがありません</p>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg border p-4">
      <h2 className="text-lg font-semibold mb-4">📋 過去レース成績 ({races.length}戦)</h2>
      
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse min-w-[1300px]">
          <thead>
            <tr className="bg-gray-100 dark:bg-gray-800 text-[10px]">
              <th className="px-1 py-1.5 border w-5"></th>
              <th className="px-1 py-1.5 border text-center w-18">日付</th>
              <th className="px-1 py-1.5 border text-center w-8">場</th>
              <th className="px-1 py-1.5 border text-left w-24">レース</th>
              <th className="px-1 py-1.5 border text-center w-16">距離</th>
              <th className="px-1 py-1.5 border text-center w-6">頭</th>
              <th className="px-1 py-1.5 border text-center w-6">馬場</th>
              <th className="px-1 py-1.5 border text-center w-6">枠</th>
              <th className="px-1 py-1.5 border text-center w-6">番</th>
              <th className="px-1 py-1.5 border text-left w-12">騎手</th>
              <th className="px-1 py-1.5 border text-center w-8">斤量</th>
              <th className="px-1 py-1.5 border text-center w-16">馬体重</th>
              <th className="px-1 py-1.5 border text-center w-5">印</th>
              <th className="px-1 py-1.5 border text-center w-10">ｵｯｽﾞ</th>
              <th className="px-1 py-1.5 border text-center w-8">人気</th>
              <th className="px-1 py-1.5 border text-center w-5">着</th>
              <th className="px-1 py-1.5 border text-center w-12">ﾀｲﾑ</th>
              <th className="px-1 py-1.5 border text-center w-10">前3F</th>
              <th className="px-1 py-1.5 border text-center w-10">上3F</th>
              <th className="px-1 py-1.5 border text-center w-6">4角</th>
              <th className="px-1 py-1.5 border text-center w-14">通過</th>
              <th className="px-1 py-1.5 border text-center w-20">寸評</th>
            </tr>
          </thead>
          <tbody>
            {displayRaces.map((race, index) => (
              <RaceRow 
                key={`${race.raceId}-${index}`}
                race={race}
                isExpanded={expandedRows.has(index)}
                onToggle={() => toggleRow(index)}
              />
            ))}
          </tbody>
        </table>
      </div>

      {races.length > 10 && (
        <div className="mt-4 text-center">
          <Button 
            variant="outline" 
            size="sm"
            onClick={() => setShowAll(!showAll)}
          >
            {showAll ? '折りたたむ' : `すべて表示 (${races.length}戦)`}
          </Button>
        </div>
      )}
    </div>
  );
}
