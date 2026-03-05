'use client';

/**
 * レース展開ビジュアライゼーション
 * 残り600m地点とゴール地点の位置関係を視覚化
 * - 前半タイム = ゴールタイム - 上がり3F
 * - 残り600m地点での各馬の位置（タイム差で表現）
 * - ゴール地点での着差
 * - 1200m戦は前半600m地点 = 残り600m地点（同一地点）
 */

import React, { useState, useMemo, useCallback } from 'react';
import { HorseEntry, parseFinishPosition, toCircleNumber } from '@/types/race-data';
import { ChevronDown, ChevronUp, Flag, MapPin, Timer, ArrowRight, ArrowUpDown } from 'lucide-react';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { Button } from '@/components/ui/button';

/** Get waku color as RGB values for inline styles */
function getWakuColorRGB(waku: number): { bg: string; text: string } {
  const colors: Record<number, { bg: string; text: string }> = {
    1: { bg: '#ffffff', text: '#000000' },
    2: { bg: '#000000', text: '#ffffff' },
    3: { bg: '#ef4444', text: '#ffffff' },
    4: { bg: '#3b82f6', text: '#ffffff' },
    5: { bg: '#eab308', text: '#000000' },
    6: { bg: '#22c55e', text: '#000000' },
    7: { bg: '#f97316', text: '#ffffff' },
    8: { bg: '#ec4899', text: '#ffffff' },
  };
  return colors[waku] || { bg: '#9ca3af', text: '#ffffff' };
}

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

/** スロープグラフ: 残600m順位 → ゴール着順 の変動を視覚化 */
function SlopegraphDiagram({ horseData }: { horseData: HorseProgressData[] }) {
  const [hoveredHorse, setHoveredHorse] = useState<number | null>(null);

  if (horseData.length === 0) return null;

  const rowH = 30;
  const topPad = 8;
  const svgH = horseData.length * rowH + topPad * 2;
  const svgW = 720;
  const lineX1 = 175;
  const lineX2 = 540;

  const by600m = [...horseData].sort((a, b) => a.position600m - b.position600m);
  const byFinish = [...horseData].sort((a, b) => a.finishPosition - b.finishPosition);

  const leftY = new Map<number, number>();
  by600m.forEach((h, i) => leftY.set(h.horseNumber, topPad + i * rowH + rowH / 2));
  const rightY = new Map<number, number>();
  byFinish.forEach((h, i) => rightY.set(h.horseNumber, topPad + i * rowH + rowH / 2));

  const shortName = (name: string, max = 6) =>
    name.length > max ? name.slice(0, max - 1) + '…' : name;

  // 追い上げ秒数 = 600m地点差 - ゴール差（プラス=追い上げ）
  const timeGained = (h: HorseProgressData) => h.timeDiff600m - h.marginFromWinner;

  const lineColor = (h: HorseProgressData) => {
    const gain = timeGained(h);
    if (gain > 0.3) return '#16a34a';  // 追い上げ
    if (gain < -0.3) return '#dc2626'; // 後退
    return '#9ca3af';                  // 維持
  };

  // 線の太さ = 追い上げ/後退の秒数に比例
  const lineWidth = (h: HorseProgressData) => {
    const absGain = Math.abs(timeGained(h));
    if (absGain >= 1.5) return 4;
    if (absGain >= 0.8) return 3;
    if (absGain >= 0.3) return 2;
    return 1.5;
  };

  const lineOpacity = (h: HorseProgressData) => {
    if (hoveredHorse !== null) return hoveredHorse === h.horseNumber ? 1 : 0.1;
    return h.finishPosition <= 3 ? 0.85 : 0.35;
  };

  const labelOpacity = (num: number) => {
    if (hoveredHorse !== null) return hoveredHorse === num ? 1 : 0.25;
    return 1;
  };

  return (
    <div className="space-y-2">
      {/* Headers */}
      <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 px-1">
        <span className="flex items-center gap-1">
          <MapPin className="h-3.5 w-3.5 text-orange-500" />
          残600m順（差）
        </span>
        <span className="flex items-center gap-1">
          ゴール着順（差）
          <Flag className="h-3.5 w-3.5 text-red-500" />
        </span>
      </div>

      <div className="overflow-x-auto" onMouseLeave={() => setHoveredHorse(null)}>
        <svg
          viewBox={`0 0 ${svgW} ${svgH}`}
          className="w-full text-gray-700 dark:text-gray-300"
          style={{ minWidth: 520 }}
        >
          {/* Lines (worst finish first → best on top) */}
          {[...horseData]
            .sort((a, b) => b.finishPosition - a.finishPosition)
            .map(h => {
              const ly = leftY.get(h.horseNumber)!;
              const ry = rightY.get(h.horseNumber)!;
              return (
                <g key={`l-${h.horseNumber}`}>
                  <line x1={lineX1} y1={ly} x2={lineX2} y2={ry}
                    stroke="transparent" strokeWidth={16}
                    className="cursor-pointer"
                    onMouseEnter={() => setHoveredHorse(h.horseNumber)}
                  />
                  <line x1={lineX1} y1={ly} x2={lineX2} y2={ry}
                    stroke={lineColor(h)}
                    strokeWidth={lineWidth(h)}
                    opacity={lineOpacity(h)}
                    strokeLinecap="round"
                    style={{ transition: 'opacity 0.15s' }}
                  />
                </g>
              );
            })}

          {/* Left labels (残600m order) + タイム差 */}
          {by600m.map((h) => {
            const y = leftY.get(h.horseNumber)!;
            const wc = getWakuColorRGB(h.waku);
            return (
              <g key={`ll-${h.horseNumber}`}
                opacity={labelOpacity(h.horseNumber)}
                className="cursor-pointer"
                onMouseEnter={() => setHoveredHorse(h.horseNumber)}
                style={{ transition: 'opacity 0.15s' }}
              >
                <rect x={8} y={y - 9} width={18} height={18} rx={3}
                  fill={wc.bg} stroke="#d1d5db" strokeWidth={0.5} />
                <text x={17} y={y + 4} textAnchor="middle" fontSize={10}
                  fill={wc.text} fontWeight="bold">{h.horseNumber}</text>
                <text x={32} y={y + 4} fontSize={11} fill="currentColor"
                  fontWeight={h.finishPosition <= 3 ? 'bold' : 'normal'}>
                  {shortName(h.horseName)}
                </text>
                {/* 600m地点での先頭差 */}
                {h.timeDiff600m > 0 && (
                  <text x={lineX1 - 4} y={y + 4} textAnchor="end" fontSize={8.5}
                    fill="#9ca3af">
                    +{h.timeDiff600m.toFixed(1)}
                  </text>
                )}
              </g>
            );
          })}

          {/* Right labels (着順 order) + 着差 */}
          {byFinish.map((h) => {
            const y = rightY.get(h.horseNumber)!;
            const wc = getWakuColorRGB(h.waku);
            const isTop3 = h.finishPosition <= 3;
            return (
              <g key={`rl-${h.horseNumber}`}
                opacity={labelOpacity(h.horseNumber)}
                className="cursor-pointer"
                onMouseEnter={() => setHoveredHorse(h.horseNumber)}
                style={{ transition: 'opacity 0.15s' }}
              >
                {/* ゴール時点での着差 */}
                {h.marginFromWinner > 0 && (
                  <text x={lineX2 + 4} y={y + 4} fontSize={8.5}
                    fill="#9ca3af">
                    +{h.marginFromWinner.toFixed(1)}
                  </text>
                )}
                <text x={570} y={y + 4} fontSize={11} fill="currentColor"
                  fontWeight={isTop3 ? 'bold' : 'normal'}>
                  {shortName(h.horseName)}
                </text>
                <rect x={648} y={y - 9} width={18} height={18} rx={3}
                  fill={wc.bg} stroke="#d1d5db" strokeWidth={0.5} />
                <text x={657} y={y + 4} textAnchor="middle" fontSize={10}
                  fill={wc.text} fontWeight="bold">{h.horseNumber}</text>
                <text x={712} y={y + 4} textAnchor="end" fontSize={11}
                  fill={isTop3 ? '#16a34a' : 'currentColor'}
                  fontWeight="bold">
                  {h.finishPosition}着
                </text>
              </g>
            );
          })}

          {/* Hover tooltip — 追い上げ秒数表示 */}
          {hoveredHorse !== null && (() => {
            const h = horseData.find(d => d.horseNumber === hoveredHorse);
            if (!h) return null;
            const ly = leftY.get(h.horseNumber)!;
            const ry = rightY.get(h.horseNumber)!;
            const mx = (lineX1 + lineX2) / 2;
            const my = (ly + ry) / 2;
            const gain = timeGained(h);
            const posChange = h.position600m - h.finishPosition;
            const posArrow = posChange > 0 ? `↑${posChange}` : posChange < 0 ? `↓${Math.abs(posChange)}` : '→';
            const gainLabel = gain > 0.05 ? `${gain.toFixed(1)}s短縮` : gain < -0.05 ? `${Math.abs(gain).toFixed(1)}s拡大` : '差維持';
            const line1 = `${h.position600m}位→${h.finishPosition}着 ${posArrow}`;
            const line2 = `3F ${h.last3fSeconds.toFixed(1)} / ${gainLabel}`;
            const tw = Math.max(line1.length, line2.length) * 7.5 + 20;
            return (
              <g style={{ pointerEvents: 'none' }}>
                <rect x={mx - tw / 2} y={my - 18} width={tw} height={32} rx={4}
                  fill="white" stroke="#e5e7eb" />
                <text x={mx} y={my - 4} textAnchor="middle" fontSize={10}
                  fill="#374151" fontWeight="bold">{line1}</text>
                <text x={mx} y={my + 9} textAnchor="middle" fontSize={9}
                  fill={gain > 0.05 ? '#16a34a' : gain < -0.05 ? '#dc2626' : '#6b7280'}>
                  {line2}
                </text>
              </g>
            );
          })()}
        </svg>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400 justify-center">
        <span className="inline-flex items-center gap-1">
          <span className="inline-block w-6 h-1 bg-green-600 rounded" />
          追い上げ（太=大）
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="inline-block w-6 h-1 bg-red-600 rounded" />
          後退（太=大）
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="inline-block w-5 h-0.5 bg-gray-400 rounded" />
          維持
        </span>
      </div>
    </div>
  );
}


type SortKey = 'finish' | 'number' | 'goal' | 'firstHalf' | 'last3f' | 'margin' | 'change';

/** ソート可能ヘッダー */
function SortableHeader({ label, sortKey, current, onSort, className = '' }: {
  label: React.ReactNode;
  sortKey: SortKey;
  current: { key: SortKey; asc: boolean };
  onSort: (key: SortKey) => void;
  className?: string;
}) {
  const active = current.key === sortKey;
  return (
    <th
      className={`px-2 py-2 cursor-pointer select-none hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors ${className}`}
      onClick={() => onSort(sortKey)}
    >
      <span className="inline-flex items-center gap-0.5">
        {label}
        {active ? (
          current.asc
            ? <ChevronUp className="h-3 w-3 text-blue-500" />
            : <ChevronDown className="h-3 w-3 text-blue-500" />
        ) : (
          <ArrowUpDown className="h-3 w-3 text-gray-300" />
        )}
      </span>
    </th>
  );
}

export default function RaceProgressVisualization({
  entries,
  distance,
  defaultOpen = true
}: RaceProgressVisualizationProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const [viewMode, setViewMode] = useState<'diagram' | 'table'>('diagram');
  const [sortState, setSortState] = useState<{ key: SortKey; asc: boolean }>({ key: 'finish', asc: true });

  const handleSort = useCallback((key: SortKey) => {
    setSortState(prev => prev.key === key ? { key, asc: !prev.asc } : { key, asc: true });
  }, []);

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

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <div className="border rounded-lg bg-white dark:bg-gray-900 shadow-sm">
        <CollapsibleTrigger asChild>
          <Button
            variant="ghost"
            className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-gray-800"
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
              <SlopegraphDiagram horseData={horseData} />
            ) : (
              /* 詳細テーブル */
              <div className="overflow-x-auto">
                {/* 前半タイムの説明 */}
                <div className="mb-2 text-xs text-gray-500 flex items-center gap-2">
                  <span className="bg-orange-100 text-orange-700 px-2 py-0.5 rounded">
                    〜残600m = ゴールタイム − 上がり3F（スタートから残600m地点までのタイム）
                  </span>
                </div>
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 dark:bg-gray-800">
                    <tr>
                      <SortableHeader label="着順" sortKey="finish" current={sortState} onSort={handleSort} className="text-left" />
                      <SortableHeader label="馬番" sortKey="number" current={sortState} onSort={handleSort} className="text-left" />
                      <th className="px-2 py-2 text-left">馬名</th>
                      <SortableHeader label="ゴール" sortKey="goal" current={sortState} onSort={handleSort} className="text-right" />
                      <SortableHeader sortKey="firstHalf" current={sortState} onSort={handleSort} className="text-center" label={
                        <div className="flex flex-col items-center">
                          <span>〜残600m</span>
                          <span className="text-[10px] text-gray-400 font-normal">タイム / 順位</span>
                        </div>
                      } />
                      <SortableHeader label="上がり3F" sortKey="last3f" current={sortState} onSort={handleSort} className="text-right" />
                      <SortableHeader label="着差" sortKey="margin" current={sortState} onSort={handleSort} className="text-right" />
                      <SortableHeader label="変化" sortKey="change" current={sortState} onSort={handleSort} className="text-center" />
                    </tr>
                  </thead>
                  <tbody>
                    {[...horseData].sort((a, b) => {
                      const getValue = (h: HorseProgressData): number => {
                        switch (sortState.key) {
                          case 'finish': return h.finishPosition;
                          case 'number': return h.horseNumber;
                          case 'goal': return h.goalTimeSeconds;
                          case 'firstHalf': return h.firstHalfSeconds;
                          case 'last3f': return h.last3fSeconds;
                          case 'margin': return h.marginFromWinner;
                          case 'change': return h.position600m - h.finishPosition;
                        }
                      };
                      const diff = getValue(a) - getValue(b);
                      return sortState.asc ? diff : -diff;
                    }).map((horse) => {
                      const posChange = horse.position600m - horse.finishPosition;
                      const waku = horse.waku;
                      const wakuColor = getWakuColorRGB(waku);
                      
                      // 前半タイムの順位に応じた色分け（黄色→青→緑ルール）
                      const getFirstHalfStyle = () => {
                        if (horse.position600m === 1) return { bg: 'bg-amber-50', text: 'text-amber-600 font-bold', icon: '🥇' };
                        if (horse.position600m === 2) return { bg: 'bg-blue-50', text: 'text-blue-600 font-bold', icon: '🥈' };
                        if (horse.position600m === 3) return { bg: 'bg-blue-50', text: 'text-blue-500 font-bold', icon: '🥉' };
                        if (horse.position600m <= Math.ceil(horseData.length * 0.3)) return { bg: 'bg-emerald-50', text: 'text-emerald-600', icon: '' };
                        return { bg: '', text: 'text-gray-600', icon: '' };
                      };
                      const firstHalfStyle = getFirstHalfStyle();
                      
                      // 前半タイムのバー幅（相対位置）
                      const fastestFirstHalf = Math.min(...horseData.map(h => h.firstHalfSeconds));
                      const slowestFirstHalf = Math.max(...horseData.map(h => h.firstHalfSeconds));
                      const firstHalfRange = slowestFirstHalf - fastestFirstHalf;
                      const firstHalfPercent = firstHalfRange > 0 
                        ? 100 - ((horse.firstHalfSeconds - fastestFirstHalf) / firstHalfRange) * 80
                        : 100;
                      
                      return (
                        <tr key={horse.horseNumber} className={`border-t hover:bg-gray-50 ${horse.finishPosition <= 3 ? 'bg-green-50/30' : ''}`}>
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
                          {/* 前半タイム（ビジュアライズ強化） */}
                          <td className={`px-2 py-2 ${firstHalfStyle.bg}`}>
                            <div className="flex flex-col items-center gap-0.5">
                              <div className="flex items-center gap-1">
                                <span className={`font-mono text-xs ${firstHalfStyle.text}`}>
                                  {formatTime(horse.firstHalfSeconds)}
                                </span>
                                {firstHalfStyle.icon && <span className="text-xs">{firstHalfStyle.icon}</span>}
                              </div>
                              {/* ミニバー */}
                              <div className="w-12 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                                <div 
                                  className="h-full rounded-full bg-gradient-to-r from-orange-400 to-orange-300"
                                  style={{ width: `${firstHalfPercent}%` }}
                                />
                              </div>
                              {/* 600m地点での差 */}
                              <span className="text-[10px] text-gray-400">
                                {horse.position600m}位 {horse.timeDiff600m > 0 ? `(+${horse.timeDiff600m.toFixed(1)})` : ''}
                              </span>
                            </div>
                          </td>
                          <td className={`px-2 py-2 text-right font-mono font-bold ${horse.finishPosition <= 3 ? 'text-green-600 dark:text-green-400' : 'text-gray-600 dark:text-gray-400'}`}>
                            {horse.last3fSeconds.toFixed(1)}
                          </td>
                          <td className="px-2 py-2 text-right font-mono">
                            {horse.marginFromWinner > 0 ? `+${horse.marginFromWinner.toFixed(2)}` : '-'}
                          </td>
                          <td className="px-2 py-2 text-center">
                            {posChange > 0 ? (
                              <span className="inline-flex items-center gap-0.5 text-green-600 font-bold bg-green-100 px-1.5 py-0.5 rounded">
                                ↑{posChange}
                              </span>
                            ) : posChange < 0 ? (
                              <span className="inline-flex items-center gap-0.5 text-red-600 font-bold bg-red-100 px-1.5 py-0.5 rounded">
                                ↓{Math.abs(posChange)}
                              </span>
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
