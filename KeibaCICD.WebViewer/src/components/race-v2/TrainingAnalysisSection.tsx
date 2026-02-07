'use client';

/**
 * 調教分析セクション
 *
 * - 最終追切: 当週の水曜か木曜（場所/スピード/ラップ）
 * - 土日追切: 前週の土曜か日曜、両方あればタイムが早いほう
 * - 一週前追切: 前週の水曜か木曜
 * - 調教評価（矢印）・攻め馬解説
 *
 * v3.1 パフォーマンス最適化:
 * - カラー関数をモジュールスコープに移動
 * - TrainingAnalysisRow を React.memo でラップ
 * - sortedEntries, entriesWithTraining を useMemo でキャッシュ
 */

import React, { useState, useMemo } from 'react';
import { HorseEntry, getWakuColor, formatTrainerName, normalizeHorseName } from '@/types/race-data';
import { POSITIVE_TEXT, POSITIVE_BG, POSITIVE_BG_MUTED } from '@/lib/positive-colors';
import { ChevronDown, ChevronUp, Dumbbell } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import type { TrainingSummaryData } from '@/lib/data/training-summary-reader';
import type { RecentFormData } from '@/lib/data/target-race-result-reader';

interface PreviousTrainingEntry {
  date: string;
  training: TrainingSummaryData;
}

interface TrainingAnalysisSectionProps {
  entries: HorseEntry[];
  trainingSummaryMap?: Record<string, TrainingSummaryData>;
  previousTrainingMap?: Record<string, PreviousTrainingEntry>;
  recentFormMap?: Record<number, RecentFormData[]>;
}

// =============================================================================
// モジュールスコープのヘルパー関数（純粋関数・レンダリングごとの再生成なし）
// =============================================================================

// 調教矢印の色（プラス＝緑、マイナス＝赤）
function getArrowColor(arrow: string): string {
  switch (arrow) {
    case '↗': return POSITIVE_TEXT;
    case '↘': return 'text-red-600 dark:text-red-400 font-bold';
    default: return 'text-gray-500';
  }
}

// ラップランクの色（S/A/B/C/Dで色分け、+/=/−で明度変更）
function getLapRankColor(rank?: string): string {
  if (!rank) return '';

  if (rank === 'SS') return 'text-yellow-600 dark:text-yellow-400 font-bold';

  if (rank === 'S+') return 'text-teal-500 dark:text-teal-300 font-bold';
  if (rank === 'S=') return 'text-teal-600 dark:text-teal-400 font-bold';
  if (rank === 'S-') return 'text-teal-700 dark:text-teal-500 font-medium';

  if (rank === 'A+') return 'text-cyan-500 dark:text-cyan-300 font-medium';
  if (rank === 'A=') return 'text-cyan-600 dark:text-cyan-400 font-medium';
  if (rank === 'A-') return 'text-cyan-700 dark:text-cyan-500';

  if (rank === 'B+') return 'text-blue-500 dark:text-blue-300';
  if (rank === 'B=') return 'text-blue-600 dark:text-blue-400';
  if (rank === 'B-') return 'text-blue-700 dark:text-blue-500';

  if (rank === 'C+') return 'text-orange-500 dark:text-orange-300';
  if (rank === 'C=') return 'text-orange-600 dark:text-orange-400';
  if (rank === 'C-') return 'text-orange-700 dark:text-orange-500';

  if (rank === 'D+') return 'text-red-500 dark:text-red-300';
  if (rank === 'D=') return 'text-red-600 dark:text-red-400';
  if (rank === 'D-') return 'text-red-700 dark:text-red-500';

  return 'text-gray-500 dark:text-gray-400';
}

// 加速アイコンを取得（+/=/−）
function getAccelerationIcon(rank?: string): string {
  if (!rank || rank === 'SS') return '';
  const lastChar = rank.slice(-1);
  if (lastChar === '+') return '↗';
  if (lastChar === '=') return '→';
  if (lastChar === '-') return '↘';
  return '';
}

// ラップランクの背景色（+は明るく、-は淡く）
function getLapRankBgColor(rank?: string): string {
  if (!rank) return '';

  if (rank === 'SS') return 'bg-yellow-50 dark:bg-yellow-900/30';

  if (rank === 'S+') return 'bg-teal-100 dark:bg-teal-900/30';
  if (rank === 'S=') return 'bg-teal-50 dark:bg-teal-900/20';
  if (rank === 'S-') return 'bg-teal-50/50 dark:bg-teal-900/10';

  if (rank === 'A+') return 'bg-cyan-100 dark:bg-cyan-900/30';
  if (rank === 'A=') return 'bg-cyan-50 dark:bg-cyan-900/20';
  if (rank === 'A-') return 'bg-cyan-50/50 dark:bg-cyan-900/10';

  if (rank === 'B+') return 'bg-blue-100 dark:bg-blue-900/30';
  if (rank === 'B=') return 'bg-blue-50 dark:bg-blue-900/20';
  if (rank === 'B-') return 'bg-blue-50/50 dark:bg-blue-900/10';

  if (rank === 'C+') return 'bg-orange-100 dark:bg-orange-900/30';
  if (rank === 'C=') return 'bg-orange-50 dark:bg-orange-900/20';
  if (rank === 'C-') return 'bg-orange-50/50 dark:bg-orange-900/10';

  if (rank === 'D+') return 'bg-red-100 dark:bg-red-900/30';
  if (rank === 'D=') return 'bg-red-50 dark:bg-red-900/20';
  if (rank === 'D-') return 'bg-red-50/50 dark:bg-red-900/10';

  return '';
}

// =============================================================================
// メモ化されたサブコンポーネント
// =============================================================================

const ExpandableText = React.memo(function ExpandableText({ text, maxLength }: { text: string | undefined; maxLength: number }) {
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
});

// detailをパースして行ごとに表示（最終/土日/1週前）
function formatTrainingDetail(
  detail?: string,
  finalLap?: string,
  weekendLap?: string,
  weekAgoLap?: string,
  finalSpeed?: string,
  weekendSpeed?: string,
  weekAgoSpeed?: string
) {
  if (!detail) return null;

  const parts = detail.split(' / ');

  return (
    <div className="space-y-0.5">
      {parts.map((part, idx) => {
        const colonIdx = part.indexOf(':');
        if (colonIdx === -1) return <div key={idx} className="text-xs">{part}</div>;

        const label = part.substring(0, colonIdx);
        const value = part.substring(colonIdx + 1);

        let lapRank = '';
        let isFastTime = false;
        if (label === '最終') {
          lapRank = finalLap || '';
          isFastTime = finalSpeed === '◎';
        } else if (label === '土日') {
          lapRank = weekendLap || '';
          isFastTime = weekendSpeed === '◎';
        } else if (label === '1週前') {
          lapRank = weekAgoLap || '';
          isFastTime = weekAgoSpeed === '◎';
        }

        const isGoodTime = isFastTime;
        const rowClass = isGoodTime
          ? 'text-xs flex items-center gap-1 text-green-700 dark:text-green-400 font-medium bg-green-50 dark:bg-green-900/30 px-1.5 py-0.5 rounded'
          : 'text-xs flex items-center gap-1 text-gray-700 dark:text-gray-300';

        const bgClass = !isGoodTime && lapRank ? getLapRankBgColor(lapRank) : '';
        const combinedRowClass = `${rowClass} ${bgClass}`.trim();

        return (
          <div key={idx} className={combinedRowClass}>
            <span className={isGoodTime ? 'w-10 shrink-0 font-semibold' : 'text-muted-foreground w-10 shrink-0'}>{label}:</span>
            <span className={`font-mono ${isGoodTime ? 'font-semibold' : ''}`}>{value}</span>
            {lapRank && (
              <span className={`ml-1 px-1.5 py-0.5 rounded text-xs font-medium ${getLapRankColor(lapRank)} ${isGoodTime ? 'bg-green-100 dark:bg-green-800/40' : ''}`}>
                {lapRank} {getAccelerationIcon(lapRank)}
              </span>
            )}
            {isGoodTime && (
              <span className="text-green-600 dark:text-green-400 font-bold ml-1" title="好タイム">◎</span>
            )}
          </div>
        );
      })}
    </div>
  );
}

interface TrainingAnalysisRowProps {
  entry: HorseEntry;
  trainingSummary?: TrainingSummaryData;
  previousTraining?: PreviousTrainingEntry;
  previousRaceForm?: RecentFormData;
}

const TrainingAnalysisRow = React.memo(function TrainingAnalysisRow({ entry, trainingSummary, previousTraining, previousRaceForm }: TrainingAnalysisRowProps) {
  const { entry_data, training_data } = entry;
  const wakuColorClass = getWakuColor(entry_data.waku);

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
      <td className="px-2 py-1.5 border text-xs text-gray-700 dark:text-gray-300 whitespace-nowrap">
        {formatTrainerName(entry_data.trainer, entry_data.trainer_tozai)}
      </td>

      {/* 今走調教タイム詳細 */}
      <td className="px-2 py-1.5 border">
        {formatTrainingDetail(
          trainingSummary?.detail,
          trainingSummary?.finalLap,
          trainingSummary?.weekendLap,
          trainingSummary?.weekAgoLap,
          trainingSummary?.finalSpeed,
          trainingSummary?.weekendSpeed,
          trainingSummary?.weekAgoSpeed
        ) || <span className="text-gray-400 text-xs">-</span>}
      </td>

      {/* 前走調教 */}
      <td className="px-2 py-1.5 border">
        {(previousTraining?.training?.detail || previousRaceForm) ? (
          <div className="space-y-0.5">
            {(previousTraining?.date || previousRaceForm) && (
              <div className="text-xs text-muted-foreground mb-1 flex items-center gap-1.5">
                {previousTraining?.date && <span>{previousTraining.date}</span>}
                {previousRaceForm && (
                  <>
                    <span className={`font-bold ${
                      previousRaceForm.finishPosition === 1 ? 'text-red-600 dark:text-red-400'
                        : previousRaceForm.finishPosition === 2 ? 'text-blue-600 dark:text-blue-400'
                        : previousRaceForm.finishPosition === 3 ? 'text-green-600 dark:text-green-400'
                        : ''
                    }`}>
                      {previousRaceForm.finishPosition}着
                    </span>
                    <span>{previousRaceForm.venue}{previousRaceForm.raceNumber}R</span>
                  </>
                )}
              </div>
            )}
            {previousTraining?.training?.detail && formatTrainingDetail(
              previousTraining.training.detail,
              previousTraining.training.finalLap,
              previousTraining.training.weekendLap,
              previousTraining.training.weekAgoLap,
              previousTraining.training.finalSpeed,
              previousTraining.training.weekendSpeed,
              previousTraining.training.weekAgoSpeed
            )}
          </div>
        ) : (
          <span className="text-gray-400 text-xs">-</span>
        )}
      </td>

      {/* 調教評価 */}
      <td className={`px-2 py-1.5 text-center border ${getArrowColor(training_data?.training_arrow || '')}`}>
        {training_data?.training_arrow || training_data?.evaluation || '-'}
      </td>

      {/* 調教短評・解説（統合） */}
      <td className="px-2 py-1.5 border text-xs text-gray-700 dark:text-gray-300">
        {(training_data?.short_review || training_data?.attack_explanation) ? (
          <div className="space-y-1">
            {training_data?.short_review && (
              <div className="font-medium text-gray-800 dark:text-gray-200">
                {training_data.short_review}
              </div>
            )}
            {training_data?.attack_explanation && (
              <div className="text-gray-600 dark:text-gray-400">
                <ExpandableText
                  text={training_data.attack_explanation}
                  maxLength={80}
                />
              </div>
            )}
          </div>
        ) : (
          '-'
        )}
      </td>
    </tr>
  );
});

// =============================================================================
// メインコンポーネント
// =============================================================================

export default function TrainingAnalysisSection({
  entries,
  trainingSummaryMap = {},
  previousTrainingMap = {},
  recentFormMap = {}
}: TrainingAnalysisSectionProps) {
  const [isOpen, setIsOpen] = useState(true);

  // 馬番順にソート（useMemoでキャッシュ）
  const sortedEntries = useMemo(
    () => [...entries].sort((a, b) => a.horse_number - b.horse_number),
    [entries]
  );

  // 調教情報があるエントリーのみフィルター（useMemoでキャッシュ）
  const entriesWithTraining = useMemo(
    () => sortedEntries.filter(entry => {
      const normalizedName = normalizeHorseName(entry.horse_name);
      const trainingSummary = trainingSummaryMap[entry.horse_name] || trainingSummaryMap[normalizedName];
      return (
        entry.training_data?.attack_explanation ||
        entry.training_data?.short_review ||
        entry.training_data?.evaluation ||
        entry.training_data?.training_arrow ||
        trainingSummary?.finalLap ||
        trainingSummary?.weekendLap ||
        trainingSummary?.weekAgoLap ||
        trainingSummary?.timeRank
      );
    }),
    [sortedEntries, trainingSummaryMap]
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
                  <th className="px-2 py-2 text-left border min-w-24">調教師</th>
                  <th className="px-2 py-2 text-left border min-w-70" title="調教タイム詳細（最終/土日/1週前）">今走調教</th>
                  <th className="px-2 py-2 text-left border min-w-70" title="前走時の調教タイム">前走調教</th>
                  <th className="px-2 py-2 text-center border w-12" title="調教評価">評価</th>
                  <th className="px-2 py-2 text-left border min-w-60">調教短評・解説</th>
                </tr>
              </thead>
              <tbody>
                {sortedEntries.map((entry) => (
                  <TrainingAnalysisRow
                    key={entry.horse_number}
                    entry={entry}
                    trainingSummary={trainingSummaryMap[entry.horse_name] || trainingSummaryMap[normalizeHorseName(entry.horse_name)]}
                    previousTraining={previousTrainingMap[entry.horse_name] || previousTrainingMap[normalizeHorseName(entry.horse_name)]}
                    previousRaceForm={recentFormMap[entry.horse_number]?.[0]}
                  />
                ))}
              </tbody>
            </table>
          </div>

          {/* 凡例 */}
          <div className="p-3 border-t bg-gray-50 dark:bg-gray-800/50 text-xs text-gray-600 dark:text-gray-400">
            <div className="flex flex-wrap gap-4">
              <span><strong>今走/前走調教:</strong> 最終（当週水・木）/ 土日（前週土・日）/ 1週前（前週水・木）</span>
              <span><strong className="text-green-600">◎</strong>=好タイム（緑色表示）</span>
              <span><strong>ラップ:</strong> <strong className="text-yellow-600">SS</strong>=最高 / S=優秀 / A=良 / B=普通 / C=やや劣 / D=劣</span>
              <span><strong>加速:</strong> ↗=加速 / →=同タイム / ↘=減速</span>
            </div>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}
