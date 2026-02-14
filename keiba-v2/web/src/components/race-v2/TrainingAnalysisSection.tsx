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
import type { TrainerPatternMatch } from '@/lib/data/trainer-patterns-reader';

interface PreviousTrainingEntry {
  date: string;
  training: TrainingSummaryData;
}

interface TrainingAnalysisSectionProps {
  entries: HorseEntry[];
  trainingSummaryMap?: Record<string, TrainingSummaryData>;
  previousTrainingMap?: Record<string, PreviousTrainingEntry>;
  recentFormMap?: Record<number, RecentFormData[]>;
  trainerPatternMatchMap?: Record<string, TrainerPatternMatch | null>;
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

// 脚色の表示ラベルと色
function getIntensityInfo(intensity?: string): { label: string; color: string } {
  if (!intensity) return { label: '-', color: 'text-gray-400' };
  if (intensity.includes('一杯')) return { label: '一杯', color: 'text-red-600 dark:text-red-400 font-bold' };
  if (intensity.includes('末強')) return { label: '末強', color: 'text-orange-600 dark:text-orange-400 font-bold' };
  if (intensity.includes('強め')) return { label: '強め', color: 'text-amber-600 dark:text-amber-400 font-medium' };
  if (intensity.includes('馬なり')) return { label: '馬なり', color: 'text-green-600 dark:text-green-400 font-medium' };
  if (intensity.includes('ゲート')) return { label: 'ゲート', color: 'text-gray-500' };
  return { label: intensity.length > 4 ? intensity.slice(0, 4) : intensity, color: 'text-gray-600 dark:text-gray-400' };
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

// detailからラップランクを抽出（例: "坂路B-(51.3)" → "B-"）
function extractLapRankFromValue(value: string): string {
  const m = value.match(/(SS|[SABCD][+=-])/);
  return m ? m[1] : '';
}

// detailから好タイム判定（カッコ内に数値がある = 好タイム表示）
function hasGoodTimeMarker(value: string): boolean {
  return /\(\d+\.\d+\)/.test(value);
}

// detailテキストからラップランクを除去（バッジで別表示するため重複排除）
// "坂路B+(53.2)" → "坂路(53.2)", "坂路D-,コースB+(52.3)" → "坂路,コース(52.3)"
function stripLapRanksFromValue(value: string): string {
  return value.replace(/(坂路|コース)(SS|[A-DS][+=-])/g, '$1');
}

// タイムレベルの色（5=金, 4=緑, 3=青, 2=灰, 1=薄灰）
function getTimeLevelColor(level: number): string {
  switch (level) {
    case 5: return 'text-yellow-600 dark:text-yellow-400 font-bold';
    case 4: return 'text-green-600 dark:text-green-400 font-bold';
    case 3: return 'text-blue-600 dark:text-blue-400 font-medium';
    case 2: return 'text-gray-500 dark:text-gray-400';
    case 1: return 'text-gray-400 dark:text-gray-500';
    default: return '';
  }
}

function getTimeLevelBgColor(level: number): string {
  switch (level) {
    case 5: return 'bg-yellow-50 dark:bg-yellow-900/30';
    case 4: return 'bg-green-50 dark:bg-green-900/30';
    case 3: return 'bg-blue-50 dark:bg-blue-900/20';
    default: return '';
  }
}

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

  // ラベル(最終/土日/1週前)の前で分割（スペース区切り・スラッシュ区切りの両方に対応）
  const parts = detail.split(/\s*\/\s*|\s+(?=最終:|土日:|1週前:)/).filter(Boolean);

  return (
    <div className="space-y-0.5">
      {parts.map((part, idx) => {
        const colonIdx = part.indexOf(':');
        if (colonIdx === -1) return <div key={idx} className="text-xs">{part}</div>;

        const label = part.substring(0, colonIdx);
        const value = part.substring(colonIdx + 1);

        // ラップランク: 引数優先、なければdetailテキストから抽出
        let lapRank = '';
        let timeLevel = 0;
        if (label === '最終') {
          lapRank = finalLap || extractLapRankFromValue(value);
          timeLevel = finalSpeed ? parseInt(finalSpeed, 10) || 0 : (hasGoodTimeMarker(value) ? 4 : 0);
        } else if (label === '土日') {
          lapRank = weekendLap || extractLapRankFromValue(value);
          timeLevel = weekendSpeed ? parseInt(weekendSpeed, 10) || 0 : (hasGoodTimeMarker(value) ? 4 : 0);
        } else if (label === '1週前') {
          lapRank = weekAgoLap || extractLapRankFromValue(value);
          timeLevel = weekAgoSpeed ? parseInt(weekAgoSpeed, 10) || 0 : (hasGoodTimeMarker(value) ? 4 : 0);
        }

        const isHighLevel = timeLevel >= 4;
        const rowBgClass = isHighLevel
          ? getTimeLevelBgColor(timeLevel)
          : (lapRank ? getLapRankBgColor(lapRank) : '');
        const rowClass = `text-xs flex items-center gap-1 ${isHighLevel ? 'font-medium' : ''} text-gray-700 dark:text-gray-300 ${rowBgClass} ${isHighLevel ? 'px-1.5 py-0.5 rounded' : ''}`.trim();

        // ランクをバッジに集約するため、detailテキストからは除去
        const cleanValue = stripLapRanksFromValue(value);

        return (
          <div key={idx} className={rowClass}>
            <span className={isHighLevel ? 'w-10 shrink-0 font-semibold' : 'text-muted-foreground w-10 shrink-0'}>{label}:</span>
            <span className={`font-mono ${isHighLevel ? 'font-semibold' : ''}`}>{cleanValue}</span>
            {lapRank && (
              <span className={`ml-1 px-1.5 py-0.5 rounded text-xs font-medium ${getLapRankColor(lapRank)}`}>
                {lapRank} {getAccelerationIcon(lapRank)}
              </span>
            )}
            {timeLevel >= 1 && (
              <span className={`ml-1 px-1 py-0.5 rounded text-xs font-bold ${getTimeLevelColor(timeLevel)}`} title={`タイムレベル ${timeLevel}/5`}>
                Lv{timeLevel}
              </span>
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
  patternMatch?: TrainerPatternMatch | null;
}

const TrainingAnalysisRow = React.memo(function TrainingAnalysisRow({ entry, trainingSummary, previousTraining, previousRaceForm, patternMatch }: TrainingAnalysisRowProps) {
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
      <td className="px-2 py-1.5 border text-xs text-gray-700 dark:text-gray-300">
        <div className="whitespace-nowrap">{formatTrainerName(entry_data.trainer, entry_data.trainer_tozai)}</div>
        {patternMatch && patternMatch.matchScore > 0.3 && (
          <div
            className="mt-0.5 text-[10px] leading-tight text-amber-700 dark:text-amber-400 font-medium whitespace-nowrap"
            title={`${patternMatch.description}\n好走率: ${(patternMatch.stats.top3_rate * 100).toFixed(0)}% (${patternMatch.stats.sample_size}走)\n勝率: ${(patternMatch.stats.win_rate * 100).toFixed(0)}%`}
          >
            <span className="text-amber-500">★</span>
            {patternMatch.humanLabel
              ? `${patternMatch.humanLabel.length > 12 ? patternMatch.humanLabel.slice(0, 12) + '…' : patternMatch.humanLabel}`
              : `${patternMatch.description.length > 12 ? patternMatch.description.slice(0, 12) + '…' : patternMatch.description}`}
            <span className="text-[9px] ml-0.5 opacity-80">
              ({(patternMatch.stats.top3_rate * 100).toFixed(0)}%)
            </span>
          </div>
        )}
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

      {/* 脚色 */}
      {(() => {
        const oikiri = entry.oikiri_summary;
        const info = getIntensityInfo(oikiri?.intensity);
        return (
          <td className={`px-1 py-1.5 text-center border text-xs ${info.color}`} title={oikiri?.intensity || ''}>
            {oikiri ? (
              <div>
                <div>{info.label}</div>
                {oikiri.condition && (oikiri.condition === '重' || oikiri.condition === '不') && (
                  <div className="text-[10px] text-gray-500" title={`馬場: ${oikiri.condition}`}>{oikiri.condition}</div>
                )}
              </div>
            ) : '-'}
          </td>
        );
      })()}

      {/* 併せ馬 */}
      <td className="px-1 py-1.5 text-center border text-xs">
        {entry.oikiri_summary?.hasAwase ? (
          <span
            className="text-blue-600 dark:text-blue-400 font-bold cursor-help"
            title={entry.oikiri_summary.awaseText || '併せ馬あり'}
          >
            併
          </span>
        ) : (
          <span className="text-gray-400">-</span>
        )}
      </td>

      {/* 前走調教 */}
      <td className="px-2 py-1.5 border">
        {(previousTraining?.training?.detail || previousRaceForm) ? (
          <div className="space-y-0.5">
            {(previousTraining?.date || previousRaceForm) && (
              <div className="text-xs text-muted-foreground mb-1 flex items-center gap-1.5">
                {previousTraining?.date && <span>{(() => {
                  const parts = previousTraining.date.split('-');
                  return parts.length === 3 ? `${parseInt(parts[1])}/${parseInt(parts[2])}` : previousTraining.date;
                })()}</span>}
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
  recentFormMap = {},
  trainerPatternMatchMap = {},
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
                  <th className="px-2 py-2 text-center border w-14" title="追い切り脚色">脚色</th>
                  <th className="px-2 py-2 text-center border w-10" title="併せ馬">併</th>
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
                    patternMatch={trainerPatternMatchMap[entry.horse_name] || trainerPatternMatchMap[normalizeHorseName(entry.horse_name)]}
                  />
                ))}
              </tbody>
            </table>
          </div>

          {/* 凡例 */}
          <div className="p-3 border-t bg-gray-50 dark:bg-gray-800/50 text-xs text-gray-600 dark:text-gray-400">
            <div className="flex flex-wrap gap-4">
              <span><strong>今走/前走調教:</strong> 最終（当週水・木）/ 土日（前週土・日）/ 1週前（前週水・木）</span>
              <span><strong>タイム:</strong> <strong className="text-yellow-600">Lv5</strong>=top5% / <strong className="text-green-600">Lv4</strong>=top20% / <strong className="text-blue-600">Lv3</strong>=中央 / Lv2=やや遅 / <span className="text-gray-400">Lv1</span>=軽め</span>
              <span><strong>ラップ:</strong> <strong className="text-yellow-600">SS</strong>=最高 / S=優秀 / A=良 / B=普通 / C=やや劣 / D=劣</span>
              <span><strong>加速:</strong> ↗=加速 / →=同タイム / ↘=減速</span>
              <span><strong>脚色:</strong> <span className="text-green-600">馬なり</span>=余裕 / <span className="text-amber-600">強め</span> / <span className="text-orange-600">末強</span> / <span className="text-red-600">一杯</span>=全力</span>
              <span><strong className="text-blue-600">併</strong>=併せ馬あり（ツールチップで詳細）</span>
              <span><strong className="text-amber-500">★</strong>=調教師勝負パターン一致</span>
            </div>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}
