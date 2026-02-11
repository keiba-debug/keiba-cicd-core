'use client';

/**
 * 展開予想コンポーネント（新方式）
 */

import React from 'react';
import { TenkaiData, HorseEntry, toCircleNumber } from '@/types/race-data';
import { Badge } from '@/components/ui/badge';
import { Flame, Timer, Turtle } from 'lucide-react';

interface TenkaiSectionProps {
  tenkaiData: TenkaiData | null;
  entries: HorseEntry[];
}

export default function TenkaiSection({ tenkaiData, entries }: TenkaiSectionProps) {
  if (!tenkaiData) return null;

  const pace = tenkaiData.pace || 'M';
  const description = tenkaiData.description;
  // positions が欠けているデータがあるため安全にフォールバック
  const positions = (tenkaiData.positions ?? {}) as TenkaiData['positions'];

  // 馬番から馬名を取得するマップ
  const horseNameMap = new Map<string, string>();
  entries.forEach(e => {
    horseNameMap.set(String(e.horse_number), e.horse_name);
  });

  return (
    <div className="border rounded-lg p-4">
      <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
        🏃 展開予想
      </h3>

      {/* ペース予想 */}
      <div className="mb-4">
        <PaceBadge pace={pace} />
      </div>

      {/* 展開ポジション表 */}
      <div className="grid grid-cols-4 gap-2 mb-4">
        <PositionCard 
          label="逃げ" 
          horseNumbers={positions.逃げ || []} 
          horseNameMap={horseNameMap}
          color="bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800"
        />
        <PositionCard 
          label="好位" 
          horseNumbers={positions.好位 || []} 
          horseNameMap={horseNameMap}
          color="bg-orange-50 dark:bg-orange-900/20 border-orange-200 dark:border-orange-800"
        />
        <PositionCard 
          label="中位" 
          horseNumbers={positions.中位 || []} 
          horseNameMap={horseNameMap}
          color="bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800"
        />
        <PositionCard 
          label="後方" 
          horseNumbers={positions.後方 || []} 
          horseNameMap={horseNameMap}
          color="bg-gray-50 dark:bg-gray-800/50 border-gray-200 dark:border-gray-700"
        />
      </div>

      {/* 展開解説 */}
      {description && (
        <div className="mt-4 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
          <div className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
            💭 展開解説
          </div>
          <p className="text-sm text-gray-800 dark:text-gray-200">
            {description}
          </p>
        </div>
      )}

      {/* ビジュアル展開図 */}
      <TenkaiVisual 
        positions={positions} 
        horseNameMap={horseNameMap}
      />
    </div>
  );
}

interface PaceBadgeProps {
  pace: string;
}

function PaceBadge({ pace }: PaceBadgeProps) {
  const paceInfo: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
    'H': { 
      label: 'ハイペース', 
      icon: <Flame className="w-4 h-4" />, 
      color: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300' 
    },
    'M-H': { 
      label: 'ややハイ', 
      icon: <Flame className="w-4 h-4" />, 
      color: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300' 
    },
    'M': { 
      label: '平均ペース', 
      icon: <Timer className="w-4 h-4" />, 
      color: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300' 
    },
    'M-S': { 
      label: 'ややスロー', 
      icon: <Turtle className="w-4 h-4" />, 
      color: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300' 
    },
    'S': { 
      label: 'スローペース', 
      icon: <Turtle className="w-4 h-4" />, 
      color: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300' 
    },
  };

  const info = paceInfo[pace] || paceInfo['M'];

  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full ${info.color}`}>
      {info.icon}
      <span className="font-medium">{info.label}</span>
      <span className="text-xs opacity-70">({pace})</span>
    </div>
  );
}

interface PositionCardProps {
  label: string;
  horseNumbers: string[];
  horseNameMap: Map<string, string>;
  color: string;
}

function PositionCard({ label, horseNumbers, horseNameMap, color }: PositionCardProps) {
  return (
    <div className={`border rounded-lg p-3 ${color}`}>
      <div className="text-sm font-medium mb-2 text-center">{label}</div>
      <div className="flex flex-wrap justify-center gap-1">
        {horseNumbers.length > 0 ? (
          horseNumbers.map((num) => (
            <span 
              key={num}
              className="inline-flex items-center justify-center w-7 h-7 bg-white dark:bg-gray-900 rounded-full text-sm font-bold border"
              title={horseNameMap.get(num) || ''}
            >
              {toCircleNumber(parseInt(num, 10))}
            </span>
          ))
        ) : (
          <span className="text-xs text-gray-400">-</span>
        )}
      </div>
    </div>
  );
}

interface TenkaiVisualProps {
  positions?: TenkaiData['positions'] | null;
  horseNameMap: Map<string, string>;
}

function TenkaiVisual({ positions, horseNameMap }: TenkaiVisualProps) {
  const safePositions = (positions ?? {}) as TenkaiData['positions'];
  // 位置ごとの馬を取得
  const nige = safePositions.逃げ || [];
  const koi = safePositions.好位 || [];
  const chui = safePositions.中位 || [];
  const koho = safePositions.後方 || [];

  if (nige.length === 0 && koi.length === 0 && chui.length === 0 && koho.length === 0) {
    return null;
  }

  return (
    <div className="mt-4">
      <div className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">
        📊 予想隊列図
      </div>
      <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 font-mono text-sm">
        {/* ゴール方向 */}
        <div className="text-center text-xs text-gray-500 mb-2">
          ← ゴール
        </div>
        
        {/* 隊列 */}
        <div className="flex items-start gap-4 justify-center overflow-x-auto pb-2">
          {/* 逃げ */}
          {nige.length > 0 && (
            <div className="text-center">
              <div className="text-xs text-red-600 mb-1">逃げ</div>
              <div className="flex flex-col gap-1">
                {nige.map(num => (
                  <HorseMarker key={num} num={num} name={horseNameMap.get(num)} />
                ))}
              </div>
            </div>
          )}
          
          {/* 好位 */}
          {koi.length > 0 && (
            <div className="text-center">
              <div className="text-xs text-orange-600 mb-1">好位</div>
              <div className="flex flex-col gap-1">
                {koi.map(num => (
                  <HorseMarker key={num} num={num} name={horseNameMap.get(num)} />
                ))}
              </div>
            </div>
          )}
          
          {/* 中位 */}
          {chui.length > 0 && (
            <div className="text-center">
              <div className="text-xs text-blue-600 mb-1">中位</div>
              <div className="flex flex-col gap-1">
                {chui.map(num => (
                  <HorseMarker key={num} num={num} name={horseNameMap.get(num)} />
                ))}
              </div>
            </div>
          )}
          
          {/* 後方 */}
          {koho.length > 0 && (
            <div className="text-center">
              <div className="text-xs text-gray-600 mb-1">後方</div>
              <div className="flex flex-col gap-1">
                {koho.map(num => (
                  <HorseMarker key={num} num={num} name={horseNameMap.get(num)} />
                ))}
              </div>
            </div>
          )}
        </div>
        
        {/* スタート方向 */}
        <div className="text-center text-xs text-gray-500 mt-2">
          スタート →
        </div>
      </div>
    </div>
  );
}

function HorseMarker({ num, name }: { num: string; name?: string }) {
  const circleNum = toCircleNumber(parseInt(num, 10));
  
  return (
    <div 
      className="inline-flex items-center gap-1 px-2 py-0.5 bg-white dark:bg-gray-900 rounded border text-xs"
      title={name}
    >
      <span className="font-bold">{circleNum}</span>
      {name && <span className="text-gray-600 dark:text-gray-400 truncate max-w-16">{name}</span>}
    </div>
  );
}
