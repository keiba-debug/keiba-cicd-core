'use client';

/**
 * 馬プロフィールヘッダーコンポーネント（v2 - 可視化強化版）
 * 
 * 改善点:
 * - 直近成績のトレンドインジケーター追加
 * - 連勝/連敗状況の表示
 * - 通算成績のサマリー表示
 */

import React from 'react';
import { Badge } from '@/components/ui/badge';
import { TrendIndicator, type RaceResult } from '@/components/ui/visualization';
import type { HorseBasicInfo, HorseRaceResult } from '@/lib/data/integrated-horse-reader';

interface HorseHeaderProps {
  basic: HorseBasicInfo;
  recentRaces?: HorseRaceResult[]; // 直近レース（トレンド表示用）
}

/**
 * 着順からRaceResult型に変換
 */
function parseFinishPosition(position: string): RaceResult {
  const pos = parseInt(position, 10);
  if (isNaN(pos)) return 'out'; // 除外、中止など
  if (pos === 1) return '1st';
  if (pos === 2) return '2nd';
  if (pos === 3) return '3rd';
  if (pos === 4) return '4th';
  if (pos === 5) return '5th';
  return 'out';
}

/**
 * 直近成績から傾向を分析
 */
function analyzeRecentTrend(races: HorseRaceResult[]): {
  status: 'rising' | 'falling' | 'stable';
  message: string;
} | null {
  if (races.length < 3) return null;
  
  // 直近5戦の平均着順を前半と後半で比較
  const recentFive = races.slice(0, 5);
  const positions = recentFive.map(r => {
    const pos = parseInt(r.finishPosition, 10);
    return isNaN(pos) ? 10 : pos; // 無効な値は10として扱う
  });
  
  // 直近2戦 vs 3-5戦前
  const recent = (positions[0] + (positions[1] || positions[0])) / 2;
  const previous = positions.slice(2).reduce((a, b) => a + b, 0) / Math.max(1, positions.slice(2).length);
  
  const diff = previous - recent;
  
  if (diff >= 2) {
    return { status: 'rising', message: '上昇傾向' };
  } else if (diff <= -2) {
    return { status: 'falling', message: '下降傾向' };
  }
  return { status: 'stable', message: '安定' };
}

export function HorseHeader({ basic, recentRaces }: HorseHeaderProps) {
  // 直近成績をトレンド形式に変換
  const trendResults: RaceResult[] = recentRaces
    ? recentRaces.slice(0, 5).map(r => parseFinishPosition(r.finishPosition))
    : [];
  
  // 傾向分析
  const trend = recentRaces ? analyzeRecentTrend(recentRaces) : null;
  
  const trendStyles = {
    rising: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
    falling: 'bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400',
    stable: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
  };
  
  const trendIcons = {
    rising: '📈',
    falling: '📉',
    stable: '➡️',
  };

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg border p-6">
      <div className="flex items-start justify-between gap-4 mb-4">
        <div className="flex items-center gap-4">
          <span className="text-4xl">🐴</span>
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-3">
              {basic.name || `馬ID: ${basic.id}`}
              {basic.age && (
                <Badge variant="secondary" className="text-sm font-normal">
                  {basic.age}
                </Badge>
              )}
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              馬ID: {basic.id}
            </p>
          </div>
        </div>
        
        {/* 直近成績トレンド */}
        {trendResults.length > 0 && (
          <div className="flex flex-col items-end gap-2">
            <div className="text-xs text-muted-foreground">直近{trendResults.length}戦</div>
            <TrendIndicator results={trendResults} size="md" />
            {trend && (
              <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${trendStyles[trend.status]}`}>
                {trendIcons[trend.status]} {trend.message}
              </span>
            )}
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
        {basic.trainer && (
          <div>
            <span className="text-muted-foreground">調教師</span>
            <div className="flex items-center gap-2">
              <p className="font-medium">{basic.trainer}</p>
              {basic.trainerLink && (
                <a
                  href={basic.trainerLink}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-blue-600 hover:underline"
                  title="厩舎ページを見る"
                >
                  →厩舎
                </a>
              )}
            </div>
            {basic.trainerId && (
              <p className="text-[10px] text-muted-foreground">ID: {basic.trainerId}</p>
            )}
          </div>
        )}
        {basic.jockey && (
          <div>
            <span className="text-muted-foreground">直近騎手</span>
            <p className="font-medium">{basic.jockey}</p>
          </div>
        )}
        <div>
          <span className="text-muted-foreground">通算出走</span>
          <p className="font-medium">{basic.totalRaces}戦</p>
        </div>
        {basic.updatedAt && (
          <div>
            <span className="text-muted-foreground">最終更新</span>
            <p className="font-medium text-xs">{basic.updatedAt}</p>
          </div>
        )}
      </div>

      {/* 調教師コメント（勝負調教パターン） */}
      {basic.trainerComment && (
        <div className="mt-4 p-3 bg-amber-50 dark:bg-amber-900/20 rounded-lg border border-amber-200 dark:border-amber-800">
          <div className="flex items-start gap-2">
            <span className="text-amber-600 dark:text-amber-400 text-lg">📝</span>
            <div className="flex-1">
              <p className="text-xs font-medium text-amber-700 dark:text-amber-400 mb-1">
                厩舎コメント（勝負調教パターン）
              </p>
              <p className="text-sm text-amber-900 dark:text-amber-200 whitespace-pre-wrap leading-relaxed">
                {basic.trainerComment}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
