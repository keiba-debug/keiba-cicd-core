'use client';

/**
 * レース展開ビジュアライゼーション
 * 残り600m地点とゴール地点の位置関係を視覚化
 * - 前半タイム = ゴールタイム - 上がり3F
 * - 残り600m地点での各馬の位置（タイム差で表現）
 * - ゴール地点での着差
 * - 1200m戦は前半600m地点 = 残り600m地点（同一地点）
 */

import React, { useState, useMemo } from 'react';
import { HorseEntry, parseFinishPosition, toCircleNumber, getWakuColor } from '@/types/race-data';
import { ChevronDown, ChevronUp, Flag, MapPin, Timer, ArrowRight } from 'lucide-react';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { Button } from '@/components/ui/button';

interface RaceProgressVisualizationProps {
  entries: HorseEntry[];
  distance: number; // レース距離（メートル）
  defaultOpen?: boolean;
}

interface HorseProgressData {
  horseNumber: number;
  horseName: string;
  waku: number;
  finishPosition: number;
  goalTimeSeconds: number;      // ゴールタイム（秒）
  last3fSeconds: number;        // 上がり3F（秒）
  firstHalfSeconds: number;     // 前半タイム（秒）
  marginFromWinner: number;     // 着差（秒換算）
  position600m: number;         // 残り600m地点での順位
  timeDiff600m: number;         // 残り600m地点でのタイム差
}

/**
 * タイム文字列を秒に変換
 * @param timeStr - "M.SS.T" or "SS.T" 形式
 * @returns 秒数
 */
function parseTimeToSeconds(timeStr: string): number {
  if (!timeStr) return 0;
  
  // 空白を除去
  const cleaned = timeStr.trim();
  
  // "M.SS.T" 形式 (例: "2.00.9", "1.46.3")
  const parts = cleaned.split('.');
  
  if (parts.length === 3) {
    const minutes = parseInt(parts[0]) || 0;
    const seconds = parseInt(parts[1]) || 0;
    const tenths = parseInt(parts[2]) || 0;
    return minutes * 60 + seconds + tenths / 10;
  }
  
  if (parts.length === 2) {
    // "SS.T" 形式 (例: "33.7")
    const seconds = parseInt(parts[0]) || 0;
    const tenths = parseInt(parts[1]) || 0;
    return seconds + tenths / 10;
  }
  
  return parseFloat(cleaned) || 0;
}

/**
 * 着差文字列を秒に変換（概算）
 * 1馬身 ≒ 0.17秒として計算
 */
function parseMarginToSeconds(margin: string): number {
  if (!margin || margin === '') return 0;
  
  const trimmed = margin.trim();
  
  // 特殊表記
  const specialMargins: Record<string, number> = {
    'ハナ': 0.02,
    'アタマ': 0.05,
    'クビ': 0.08,
    '大差': 3.0,
    '同着': 0,
  };
  
  if (specialMargins[trimmed] !== undefined) {
    return specialMargins[trimmed];
  }
  
  // 分数形式 "1 3/4" or "3/4"
  const fractionMatch = trimmed.match(/^(\d+)?\s*(\d+)\/(\d+)$/);
  if (fractionMatch) {
    const whole = parseInt(fractionMatch[1]) || 0;
    const numerator = parseInt(fractionMatch[2]) || 0;
    const denominator = parseInt(fractionMatch[3]) || 1;
    return (whole + numerator / denominator) * 0.17;
  }
  
  // 整数のみ
  const numMatch = trimmed.match(/^(\d+)$/);
  if (numMatch) {
    return parseInt(numMatch[1]) * 0.17;
  }
  
  return 0;
}

/**
 * 秒を表示用フォーマットに変換
 */
function formatTime(seconds: number): string {
  if (seconds === 0) return '-';
  const mins = Math.floor(seconds / 60);
  const secs = (seconds % 60).toFixed(1);
  if (mins > 0) {
    return `${mins}:${secs.padStart(4, '0')}`;
  }
  return secs;
}

export default function RaceProgressVisualization({ 
  entries, 
  distance,
  defaultOpen = true 
}: RaceProgressVisualizationProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const [viewMode, setViewMode] = useState<'diagram' | 'table'>('diagram');

  // 1200m戦かどうか
  const is1200m = distance === 1200;

  // 馬のデータを計算
  const horseData = useMemo(() => {
    const data: HorseProgressData[] = entries
      .filter(e => e.result?.finish_position && e.result?.time && e.result?.last_3f)
      .map(e => {
        const goalTimeSeconds = parseTimeToSeconds(e.result!.time);
        const last3fSeconds = parseTimeToSeconds(e.result!.last_3f);
        const firstHalfSeconds = goalTimeSeconds - last3fSeconds;
        const finishPosition = parseFinishPosition(e.result!.finish_position);
        
        return {
          horseNumber: e.horse_number,
          horseName: e.horse_name,
          waku: parseInt(e.entry_data.waku) || 1,
          finishPosition,
          goalTimeSeconds,
          last3fSeconds,
          firstHalfSeconds,
          marginFromWinner: 0, // 後で計算
          position600m: 0,     // 後で計算
          timeDiff600m: 0,     // 後で計算
        };
      })
      .filter(d => d.goalTimeSeconds > 0 && d.last3fSeconds > 0);

    if (data.length === 0) return [];

    // 残り600m地点での順位を計算（前半タイム順）
    const sortedByFirstHalf = [...data].sort((a, b) => a.firstHalfSeconds - b.firstHalfSeconds);
    const fastestFirstHalf = sortedByFirstHalf[0]?.firstHalfSeconds || 0;
    
    sortedByFirstHalf.forEach((horse, index) => {
      horse.position600m = index + 1;
      horse.timeDiff600m = horse.firstHalfSeconds - fastestFirstHalf;
    });

    // 着差を計算
    const winner = data.find(d => d.finishPosition === 1);
    if (winner) {
      data.forEach(horse => {
        horse.marginFromWinner = horse.goalTimeSeconds - winner.goalTimeSeconds;
      });
    }

    return data.sort((a, b) => a.finishPosition - b.finishPosition);
  }, [entries]);

  if (horseData.length === 0) {
    return null;
  }

  // 表示用の計算
  const maxTimeDiff600m = Math.max(...horseData.map(d => d.timeDiff600m), 0.1);
  const maxMarginFromWinner = Math.max(...horseData.map(d => d.marginFromWinner), 0.1);
  const maxScale = Math.max(maxTimeDiff600m, maxMarginFromWinner);

  // 図の幅計算用（残り600m〜ゴールまでを表現）
  const chartWidth = 100; // パーセント

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <div className="border rounded-lg bg-white shadow-sm">
        <CollapsibleTrigger asChild>
          <Button
            variant="ghost"
            className="w-full flex items-center justify-between p-4 hover:bg-gray-50"
          >
            <div className="flex items-center gap-2">
              <Timer className="h-5 w-5 text-green-600" />
              <span className="font-semibold">レース展開図（残600m → ゴール）</span>
              {is1200m && (
                <span className="text-xs bg-yellow-100 text-yellow-800 px-2 py-0.5 rounded">
                  1200m戦
                </span>
              )}
            </div>
            {isOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </Button>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <div className="p-4 border-t">
            {/* 表示モード切替 */}
            <div className="flex gap-2 mb-4">
              <Button
                size="sm"
                variant={viewMode === 'diagram' ? 'default' : 'outline'}
                onClick={() => setViewMode('diagram')}
              >
                展開図
              </Button>
              <Button
                size="sm"
                variant={viewMode === 'table' ? 'default' : 'outline'}
                onClick={() => setViewMode('table')}
              >
                詳細表
              </Button>
            </div>

            {viewMode === 'diagram' ? (
              <div className="space-y-4">
                {/* ヘッダー */}
                <div className="flex items-center justify-between text-sm text-gray-500 px-2">
                  <div className="flex items-center gap-1">
                    <Flag className="h-4 w-4 text-red-500" />
                    <span>← ゴール</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <MapPin className="h-4 w-4 text-orange-500" />
                    <span>{is1200m ? '前半600m / 残600m地点' : '残600m地点'}</span>
                  </div>
                </div>

                {/* 展開図 */}
                <div className="relative bg-gradient-to-r from-red-50 to-orange-50 rounded-lg p-4">
                  {/* グリッドライン */}
                  <div className="absolute inset-4 flex justify-between pointer-events-none">
                    <div className="border-l-2 border-red-300 border-dashed" />
                    <div className="border-l-2 border-gray-200 border-dashed" />
                    <div className="border-l-2 border-gray-200 border-dashed" />
                    <div className="border-l-2 border-orange-300 border-dashed" />
                  </div>

                  {/* 各馬の表示 */}
                  <div className="space-y-1 relative z-10">
                    {horseData.map((horse) => {
                      const waku = horse.waku;
                      const wakuColor = getWakuColor(waku);
                      
                      // ゴール地点での位置（左側: 1着が左端、着差があるほど右）
                      const goalPercent = (horse.marginFromWinner / maxScale) * 40;
                      
                      // 残り600m地点での位置（右側: 先頭馬が左寄り、後方馬が右端）
                      // timeDiff600mが大きい（後方）ほど右に表示
                      const pos600mPercent = 60 + (horse.timeDiff600m / maxScale) * 40;

                      return (
                        <div key={horse.horseNumber} className="flex items-center gap-1 h-8">
                          {/* 馬番 */}
                          <div 
                            className="w-6 h-6 rounded text-xs font-bold flex items-center justify-center flex-shrink-0"
                            style={{ 
                              backgroundColor: wakuColor.bg, 
                              color: wakuColor.text 
                            }}
                          >
                            {horse.horseNumber}
                          </div>

                          {/* 馬名 */}
                          <div className={`w-20 text-xs truncate flex-shrink-0 ${horse.finishPosition <= 3 ? 'font-bold text-gray-800' : 'text-gray-600'}`}>
                            {horse.horseName}
                          </div>

                          {/* 軌跡 */}
                          <div className="flex-1 relative h-6">
                            {/* 残600m地点のマーカー */}
                            <div 
                              className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-orange-400 border-2 border-white shadow-sm z-10"
                              style={{ left: `${pos600mPercent}%` }}
                              title={`残600m: ${horse.position600m}位 (+${horse.timeDiff600m.toFixed(1)}秒)`}
                            />
                            
                            {/* 軌跡線 */}
                            <svg className="absolute inset-0 w-full h-full overflow-visible">
                              <line
                                x1={`${pos600mPercent}%`}
                                y1="50%"
                                x2={`${goalPercent}%`}
                                y2="50%"
                                stroke={horse.finishPosition <= 3 ? '#10B981' : '#9CA3AF'}
                                strokeWidth={horse.finishPosition <= 3 ? 2 : 1}
                                strokeDasharray={horse.finishPosition <= 3 ? '' : '4 2'}
                              />
                            </svg>

                            {/* ゴール地点のマーカー */}
                            <div 
                              className={`absolute top-1/2 -translate-y-1/2 w-4 h-4 rounded-full border-2 border-white shadow-sm z-10
                                ${horse.finishPosition === 1 ? 'bg-yellow-400' : 
                                  horse.finishPosition === 2 ? 'bg-gray-300' : 
                                  horse.finishPosition === 3 ? 'bg-amber-600' : 'bg-red-400'}`}
                              style={{ left: `${goalPercent}%` }}
                              title={`ゴール: ${horse.finishPosition}着 (+${horse.marginFromWinner.toFixed(2)}秒)`}
                            />
                          </div>

                          {/* 着順 */}
                          <div className={`w-8 text-center text-sm font-bold flex-shrink-0
                            ${horse.finishPosition <= 3 ? 'text-green-600 dark:text-green-400' : 'text-gray-600'}`}
                          >
                            {horse.finishPosition}着
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* 凡例 */}
                <div className="flex items-center gap-4 text-xs text-gray-500 justify-center mt-2">
                  <div className="flex items-center gap-1">
                    <div className="w-4 h-4 rounded-full bg-yellow-400 border border-white" />
                    <span>ゴール（1着）</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="w-3 h-3 rounded-full bg-orange-400 border border-white" />
                    <span>残600m地点</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="w-6 h-0.5 bg-green-500" />
                    <span>3着以内</span>
                  </div>
                </div>
              </div>
            ) : (
              /* 詳細テーブル */
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-2 py-2 text-left">着順</th>
                      <th className="px-2 py-2 text-left">馬番</th>
                      <th className="px-2 py-2 text-left">馬名</th>
                      <th className="px-2 py-2 text-right">ゴールタイム</th>
                      <th className="px-2 py-2 text-right">前半</th>
                      <th className="px-2 py-2 text-right">上がり3F</th>
                      <th className="px-2 py-2 text-center">600m順位</th>
                      <th className="px-2 py-2 text-right">600m差</th>
                      <th className="px-2 py-2 text-right">着差</th>
                      <th className="px-2 py-2 text-center">変化</th>
                    </tr>
                  </thead>
                  <tbody>
                    {horseData.map((horse) => {
                      const posChange = horse.position600m - horse.finishPosition;
                      const waku = horse.waku;
                      const wakuColor = getWakuColor(waku);
                      
                      return (
                        <tr key={horse.horseNumber} className="border-t hover:bg-gray-50">
                          <td className={`px-2 py-2 font-bold
                            ${horse.finishPosition <= 3 ? 'text-green-600 dark:text-green-400' : ''}`}
                          >
                            {horse.finishPosition}
                          </td>
                          <td className="px-2 py-2">
                            <span 
                              className="inline-block w-6 h-6 rounded text-xs font-bold text-center leading-6"
                              style={{ 
                                backgroundColor: wakuColor.bg, 
                                color: wakuColor.text 
                              }}
                            >
                              {horse.horseNumber}
                            </span>
                          </td>
                          <td className="px-2 py-2 font-medium">{horse.horseName}</td>
                          <td className="px-2 py-2 text-right font-mono">
                            {formatTime(horse.goalTimeSeconds)}
                          </td>
                          <td className="px-2 py-2 text-right font-mono text-orange-600">
                            {formatTime(horse.firstHalfSeconds)}
                          </td>
                          <td className={`px-2 py-2 text-right font-mono font-bold ${horse.finishPosition <= 3 ? 'text-green-600 dark:text-green-400' : 'text-gray-600 dark:text-gray-400'}`}>
                            {horse.last3fSeconds.toFixed(1)}
                          </td>
                          <td className="px-2 py-2 text-center">
                            <span className={`font-bold ${horse.position600m <= 3 ? 'text-orange-500' : ''}`}>
                              {horse.position600m}位
                            </span>
                          </td>
                          <td className="px-2 py-2 text-right font-mono text-gray-500">
                            {horse.timeDiff600m > 0 ? `+${horse.timeDiff600m.toFixed(1)}` : '0.0'}
                          </td>
                          <td className="px-2 py-2 text-right font-mono">
                            {horse.marginFromWinner > 0 ? `+${horse.marginFromWinner.toFixed(2)}` : '-'}
                          </td>
                          <td className="px-2 py-2 text-center">
                            {posChange > 0 ? (
                              <span className="text-green-600 font-bold">↑{posChange}</span>
                            ) : posChange < 0 ? (
                              <span className="text-red-600 font-bold">↓{Math.abs(posChange)}</span>
                            ) : (
                              <span className="text-gray-400">→</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {/* 1200m戦の注釈 */}
            {is1200m && (
              <div className="mt-4 p-3 bg-yellow-50 rounded-lg text-sm text-yellow-800">
                <strong>※ 1200m戦</strong>：前半600m地点 = 残り600m地点のため、同一地点での比較となります。
              </div>
            )}
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}
