'use client';

/**
 * レース結果コンポーネント（新方式）
 */

import React, { useState, useMemo } from 'react';
import { 
  HorseEntry, 
  PayoutEntry, 
  TenkaiData,
  getWakuColor, 
  toCircleNumber,
  parseFinishPosition,
} from '@/types/race-data';
import { Badge } from '@/components/ui/badge';
import { ChevronDown, ChevronUp, Trophy, Timer, TrendingUp, TrendingDown, Minus, Activity } from 'lucide-react';
import { calculateActualRpci, type CourseRpciInfo, type RaceRpciAnalysis } from '@/lib/data/rpci-utils';
import type { BabaCondition } from '@/lib/data/baba-reader';
import { POSITIVE_TEXT, getRatingColor } from '@/lib/positive-colors';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { Button } from '@/components/ui/button';

// 新しい可視化コンポーネント
import {
  Last3FComparisonChart,
  MarginVisualization,
  PositionGainIndicator,
  EarlyPositionComparison,
  RaceProgressVisualization,
} from './result-visualizations';

interface RaceResultSectionProps {
  entries: HorseEntry[];
  payouts?: PayoutEntry[] | null;
  tenkaiData?: TenkaiData | null;
  distance?: number; // レース距離（メートル）
  rpciInfo?: CourseRpciInfo | null; // RPCI基準値情報
  babaInfo?: BabaCondition | null; // 馬場コンディション（クッション値・含水率）
}

export default function RaceResultSection({ entries, payouts, tenkaiData, distance, rpciInfo, babaInfo }: RaceResultSectionProps) {
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

  // 実際のRPCI分析を計算
  const rpciAnalysis = useMemo(() => {
    return calculateActualRpci(entries, rpciInfo);
  }, [entries, rpciInfo]);

  return (
    <>
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
            {/* 馬場コンディション（上がり3F・走破タイムの解釈補助） */}
            {babaInfo && (
              <div
                className="text-sm text-muted-foreground py-2 px-3 rounded-md border bg-muted/30"
                title="JRA早見表に基づく目安です。馬場状態は含水率だけで決まるものではありません。"
              >
                <span className="font-medium text-foreground">このレースの馬場: </span>
                {babaInfo.cushion != null && (
                  <span>クッション {babaInfo.cushion.toFixed(1)}{babaInfo.cushionLabel ? `（${babaInfo.cushionLabel}）` : ''}</span>
                )}
                {(babaInfo.moistureG != null || babaInfo.moisture4 != null) && (
                  <span>
                    {babaInfo.cushion != null ? ' / ' : ''}
                    含水率 G前 {babaInfo.moistureG != null ? `${babaInfo.moistureG.toFixed(1)}%` : '—'}
                    {' / '}4C {babaInfo.moisture4 != null ? `${babaInfo.moisture4.toFixed(1)}%` : '—'}
                    {babaInfo.moistureConditionLabel ? `（${babaInfo.moistureConditionLabel}の目安）` : ''}
                  </span>
                )}
                {babaInfo.cushion == null && babaInfo.moistureG == null && babaInfo.moisture4 == null && (
                  <span>クッション・含水率: 計測なし</span>
                )}
                <span className="ml-1 text-xs">上がり3F・走破タイムの参考にしてください。</span>
              </div>
            )}

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
                    <th className="px-2 py-2 text-center border w-12">レート</th>
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

    {/* 視覚的分析セクション */}
    <div className="mt-4 space-y-4">
      {/* RPCI分析結果 */}
      {rpciAnalysis && (
        <RpciAnalysisCard 
          analysis={rpciAnalysis} 
          courseInfo={rpciInfo || undefined} 
        />
      )}

      {/* レース展開図（残600m → ゴール） */}
      <RaceProgressVisualization entries={entries} distance={distance || 0} defaultOpen={false} />

      {/* 序盤位置取り比較 */}
      <EarlyPositionComparison entries={entries} tenkaiData={tenkaiData || null} defaultOpen={false} />

      {/* 着差バー */}
      <MarginVisualization entries={entries} defaultOpen={false} />

      {/* 上り3F比較チャート */}
      <Last3FComparisonChart entries={entries} defaultOpen={false} />

      {/* 伸び脚インジケータ */}
      <PositionGainIndicator entries={entries} defaultOpen={false} />
    </div>
    </>
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
      
      {/* 上り3F（最速はプラス色で強調） */}
      <td className={`px-2 py-1.5 text-center border font-mono ${
        isFastestLast3f ? POSITIVE_TEXT : ''
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
      
      {/* レイティング */}
      <td className={`px-2 py-1.5 text-center border font-mono ${getRatingColor(entry_data.rating)}`}>
        {entry_data.rating || '-'}
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

/**
 * RPCI分析結果カード
 */
interface RpciAnalysisCardProps {
  analysis: RaceRpciAnalysis;
  courseInfo?: CourseRpciInfo;
}

function RpciAnalysisCard({ analysis, courseInfo }: RpciAnalysisCardProps) {
  // 傾向に応じたスタイル
  const getTrendStyle = (trend: 'instantaneous' | 'sustained' | 'neutral') => {
    switch (trend) {
      case 'instantaneous':
        return { 
          bg: 'bg-blue-50', 
          border: 'border-blue-200', 
          text: 'text-blue-700',
          icon: <TrendingUp className="w-5 h-5" />,
          label: '瞬発戦'
        };
      case 'sustained':
        return { 
          bg: 'bg-red-50', 
          border: 'border-red-200', 
          text: 'text-red-700',
          icon: <TrendingDown className="w-5 h-5" />,
          label: '持続戦'
        };
      default:
        return { 
          bg: 'bg-gray-50', 
          border: 'border-gray-200', 
          text: 'text-gray-700',
          icon: <Minus className="w-5 h-5" />,
          label: '平均的'
        };
    }
  };

  const style = getTrendStyle(analysis.actualTrend);
  
  // 基準値との比較
  const getComparisonStyle = (compared: 'faster' | 'slower' | 'typical') => {
    switch (compared) {
      case 'slower':
        return { color: 'text-blue-600', label: 'スロー' };
      case 'faster':
        return { color: 'text-red-600', label: 'ハイペース' };
      default:
        return { color: 'text-gray-600', label: '平均的' };
    }
  };

  const compStyle = getComparisonStyle(analysis.comparedToStandard);

  return (
    <div className={`rounded-lg border p-4 ${style.bg} ${style.border}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-full ${style.bg} ${style.text}`}>
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <div className="text-sm font-medium text-gray-600">このレースのペース分析</div>
            <div className={`text-lg font-bold flex items-center gap-2 ${style.text}`}>
              {style.icon}
              <span>{style.label}</span>
              <span className="text-base font-normal">(RPCI: {analysis.actualRpci.toFixed(1)})</span>
            </div>
          </div>
        </div>
        
        {/* 基準値との比較 */}
        {courseInfo && (
          <div className="text-right">
            <div className="text-xs text-gray-500">
              コース基準: {courseInfo.rpciMean.toFixed(1)}
            </div>
            <div className={`text-sm font-medium ${compStyle.color}`}>
              {analysis.deviation > 0 ? '+' : ''}{analysis.deviation.toFixed(1)} ({compStyle.label})
            </div>
            <div className="text-xs text-gray-400">
              {analysis.comparedToStandardLabel}
            </div>
          </div>
        )}
      </div>

      {/* 詳細情報 */}
      <div className="mt-3 pt-3 border-t border-gray-200 grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        <div>
          <div className="text-gray-500 text-xs">実測RPCI</div>
          <div className="font-mono font-bold">{analysis.actualRpci.toFixed(2)}</div>
        </div>
        {courseInfo && (
          <>
            <div>
              <div className="text-gray-500 text-xs">瞬発戦閾値</div>
              <div className="font-mono text-blue-600">&gt;{courseInfo.thresholds.instantaneous.toFixed(1)}</div>
            </div>
            <div>
              <div className="text-gray-500 text-xs">持続戦閾値</div>
              <div className="font-mono text-red-600">&lt;{courseInfo.thresholds.sustained.toFixed(1)}</div>
            </div>
          </>
        )}
        <div>
          <div className="text-gray-500 text-xs">算出馬数</div>
          <div className="font-mono">{analysis.sourceHorses}頭</div>
        </div>
      </div>
    </div>
  );
}
