'use client';

/**
 * 出走表コンポーネント（可視化強化版）
 * JSON → 直接レンダリング
 *
 * 改善点:
 * - レイティングにミニバーグラフ追加
 * - オッズ人気にヒートマップカラーリング
 * - AI指数のランク別ハイライト強化
 *
 * v3.1 パフォーマンス最適化:
 * - カラー関数をモジュールスコープに移動（関数オブジェクト再生成防止）
 * - HorseEntryRow を React.memo でラップ（不要な再レンダリング防止）
 * - レイティング・AI指数計算を useMemo でキャッシュ
 * - RatingCell, RatingMiniBar を React.memo でラップ
 */

import React, { useMemo, useState, useEffect } from 'react';
import Link from 'next/link';
import useSWR from 'swr';
import {
  HorseEntry,
  getWakuColor,
  toCircleNumber,
  TRAINING_ARROW_LABELS,
  normalizeHorseName,
} from '@/types/race-data';
import { POSITIVE_TEXT, POSITIVE_BG, POSITIVE_BG_MUTED, RATING_TOP, RATING_HIGH, RATING_MID_HIGH, RATING_MID, getRatingColor } from '@/lib/positive-colors';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { MessageSquareText } from 'lucide-react';
import { TrendIndicator, StreakBadge, calculateStreak, type RecentFormEntry } from '@/components/ui/visualization';
import type { TrainingSummaryData } from '@/lib/data/training-summary-reader';
import type { RaceHorseComment, HorseComment } from '@/lib/data/target-comment-reader';
import type { RecentFormData } from '@/lib/data/target-race-result-reader';

/** TARGETコメント（馬番→コメント） */
interface TargetCommentsMap {
  predictions: Record<number, RaceHorseComment>;
  results: Record<number, RaceHorseComment>;
  horseComments?: Record<number, HorseComment>;
}

/** TARGET馬印（馬番→印） */
export interface TargetMarksMap {
  horseMarks: Record<number, string>;  // 馬番 → 印（◎, ○, ▲, △, ★, 穴）
  horseMarks2?: Record<number, string>;  // 馬印2
}

/** ML予測データ（馬単位） */
export interface MlPredictionEntry {
  horse_number: number;
  pred_proba_accuracy: number;
  pred_proba_value: number;
  value_rank: number;
  odds_rank: number | null;
  gap: number | null;
  is_value_bet: boolean;
}

/** DB odds レスポンス型 */
interface DbHorseOdds {
  umaban: number;
  winOdds: number | null;
  placeOddsMin: number | null;
  placeOddsMax: number | null;
  ninki: number | null;
  firstWinOdds: number | null;
  oddsTrend: 'up' | 'down' | 'stable' | null;
}

interface DbOddsResponse {
  raceId: string;
  source: 'timeseries' | 'final' | 'none';
  snapshotTime: string | null;
  snapshotCount: number;
  horses: DbHorseOdds[];
}

const swrFetcher = (url: string) => fetch(url).then((r) => r.json());

function formatSnapshotTime(raw: string | null): string {
  if (!raw || raw.length < 8) return '';
  const hh = raw.slice(4, 6);
  const mm = raw.slice(6, 8);
  return `${hh}:${mm}`;
}

interface HorseEntryTableProps {
  entries: HorseEntry[];
  showResult?: boolean;
  trainingSummaryMap?: Record<string, TrainingSummaryData>;
  /** TARGETコメント */
  targetComments?: TargetCommentsMap;
  /** TARGET馬印（My印） */
  targetMarks?: TargetMarksMap;
  /** 直近戦績（馬番→RecentFormData[]） */
  recentFormMap?: Record<number, RecentFormData[]>;
  /** ML予測（馬番→予測データ） */
  mlPredictions?: Record<number, MlPredictionEntry>;
  /** 16桁レースID（DB odds取得用） */
  raceId?: string;
}

// =============================================================================
// モジュールスコープのヘルパー関数（純粋関数・レンダリングごとの再生成なし）
// =============================================================================

// RecentFormData → RecentFormEntry 変換（リンク+ツールチップ付き着順ドット用）
function toRecentFormEntries(forms: RecentFormData[]): RecentFormEntry[] {
  return forms.map(f => {
    const result = f.finishPosition === 1 ? '1st'
      : f.finishPosition === 2 ? '2nd'
      : f.finishPosition === 3 ? '3rd'
      : f.finishPosition === 4 ? '4th'
      : f.finishPosition === 5 ? '5th'
      : 'out' as const;
    const d = f.raceDate;
    const dateLabel = `${d.slice(4, 6)}/${d.slice(6, 8)}`;
    return {
      result,
      href: f.href,
      label: `${f.finishPosition}着 ${f.venue}${f.raceNumber}R (${dateLabel})`,
      raceTrend: f.raceTrend,
    };
  });
}

// レイティング文字列を数値に変換するヘルパー
function parseRating(rating: string | number | undefined | null): number {
  if (rating === undefined || rating === null || rating === '') return 0;
  if (typeof rating === 'number') return isNaN(rating) ? 0 : rating;
  const parsed = parseFloat(String(rating));
  return isNaN(parsed) ? 0 : parsed;
}

// AI指数の値を数値に変換するヘルパー
function parseAiIndex(aiIndex?: string | number): number {
  if (!aiIndex || aiIndex === '' || aiIndex === '-') return 0;
  if (typeof aiIndex === 'number') return isNaN(aiIndex) ? 0 : aiIndex;
  const parsed = parseFloat(String(aiIndex));
  return isNaN(parsed) ? 0 : parsed;
}

// 印の背景色（本紙）
function getMarkBgColor(mark: string): string {
  switch (mark) {
    case '◎': return 'bg-red-100 dark:bg-red-900/30';
    case '○': return 'bg-blue-100 dark:bg-blue-900/30';
    case '▲': return 'bg-yellow-100 dark:bg-yellow-900/30';
    case '△': return 'bg-gray-100 dark:bg-gray-700/30';
    default: return '';
  }
}

// My印の背景色（紫系でTarget印と区別）
function getMyMarkBgColor(mark?: string): string {
  if (!mark) return '';
  switch (mark) {
    case '◎': return 'bg-purple-200 dark:bg-purple-900/40 text-purple-900 dark:text-purple-200';
    case '○': return 'bg-purple-100 dark:bg-purple-800/30 text-purple-800 dark:text-purple-300';
    case '▲': return 'bg-violet-100 dark:bg-violet-800/30 text-violet-800 dark:text-violet-300';
    case '△': return 'bg-violet-50 dark:bg-violet-700/20 text-violet-700 dark:text-violet-400';
    case '★': return 'bg-fuchsia-100 dark:bg-fuchsia-800/30 text-fuchsia-800 dark:text-fuchsia-300';
    case '穴': return 'bg-pink-100 dark:bg-pink-800/30 text-pink-800 dark:text-pink-300';
    default: return '';
  }
}

// My印2の背景色（緑系で区別）
function getMyMark2BgColor(mark?: string): string {
  if (!mark) return '';
  switch (mark) {
    case '◎': return 'bg-teal-200 dark:bg-teal-900/40 text-teal-900 dark:text-teal-200';
    case '○': return 'bg-teal-100 dark:bg-teal-800/30 text-teal-800 dark:text-teal-300';
    case '▲': return 'bg-cyan-100 dark:bg-cyan-800/30 text-cyan-800 dark:text-cyan-300';
    case '△': return 'bg-cyan-50 dark:bg-cyan-700/20 text-cyan-700 dark:text-cyan-400';
    case '★': return 'bg-emerald-100 dark:bg-emerald-800/30 text-emerald-800 dark:text-emerald-300';
    case '穴': return 'bg-green-100 dark:bg-green-800/30 text-green-800 dark:text-green-300';
    default: return '';
  }
}

// パドック評価マークの正規化（全角→半角・前後空白除去）
function normalizePaddockMark(mark?: string): string {
  if (!mark || typeof mark !== 'string') return '';
  const t = mark.trim();
  if (!t) return '';
  // 全角英数・スペースを半角に（Ａ→A, Ｂ→B など）
  const half = t.replace(/[Ａ-Ｚａ-ｚ０-９]/g, (ch) =>
    String.fromCharCode(ch.charCodeAt(0) - 0xfee0)
  ).trim();
  return half || t;
}

// パドック評価の背景色・文字色（S/A/B/穴 + ◎○▲△）— 目立つように濃いめ・枠付き
function getPaddockMarkBgColor(mark?: string): string {
  const m = normalizePaddockMark(mark);
  if (!m) return '';
  switch (m) {
    case 'S': return 'bg-amber-200 text-amber-900 border-2 border-amber-400 dark:bg-amber-500/50 dark:text-amber-950 dark:border-amber-400';
    case 'A': return 'bg-emerald-200 text-emerald-900 border-2 border-emerald-500 dark:bg-emerald-500/50 dark:text-emerald-950 dark:border-emerald-400';
    case 'B': return 'bg-sky-200 text-sky-900 border-2 border-sky-500 dark:bg-sky-500/50 dark:text-sky-950 dark:border-sky-400';
    case '穴': return 'bg-violet-200 text-violet-900 border-2 border-violet-500 dark:bg-violet-500/50 dark:text-violet-950 dark:border-violet-400';
    case '◎': return 'bg-green-200 text-green-900 border-2 border-green-500 dark:bg-green-500/50 dark:text-green-950 dark:border-green-400';
    case '○': return 'bg-teal-200 text-teal-900 border-2 border-teal-500 dark:bg-teal-500/50 dark:text-teal-950 dark:border-teal-400';
    case '▲': return 'bg-amber-200 text-amber-900 border-2 border-amber-500 dark:bg-amber-500/50 dark:text-amber-950 dark:border-amber-400';
    case '△': return 'bg-gray-200 text-gray-800 border-2 border-gray-400 dark:bg-gray-500/50 dark:text-gray-100 dark:border-gray-400';
    default: return 'bg-gray-200 text-gray-800 border-2 border-gray-400 dark:bg-gray-500/50 dark:text-gray-100 dark:border-gray-400';
  }
}


// AI指数ランクのセル背景色（レース内順位ベース）
function getAiIndexColor(aiIndex: string | number | undefined, rank: number, secondValue: number, totalCount: number): string {
  if (!aiIndex || aiIndex === '' || aiIndex === '-' || rank === 0) return '';

  const value = parseAiIndex(aiIndex);
  if (value === 0) return '';

  // 特別抜けている場合（1位で2位との差が15%以上）: 赤色
  if (rank === 1 && secondValue > 0) {
    const diffPercent = ((value - secondValue) / secondValue) * 100;
    if (diffPercent >= 15) {
      return 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-200 font-bold';
    }
  }

  // 1位: 黄色系
  if (rank === 1) return 'bg-amber-50 dark:bg-amber-900/20 text-amber-800 dark:text-amber-200 font-semibold';
  // 2-3位: 青系
  if (rank <= 3) return 'bg-blue-50 dark:bg-blue-900/20 text-blue-800 dark:text-blue-200 font-medium';
  // 上位30%: 緑系
  if (rank <= Math.ceil(totalCount * 0.3)) return 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-800 dark:text-emerald-200';

  return '';
}

// 総合ポイントに基づく背景色（プラス色で統一）
function getPointBgColor(point: number): string {
  if (point >= 30) return `${POSITIVE_BG} font-bold`;
  if (point >= 20) return POSITIVE_BG_MUTED;
  if (point >= 10) return 'bg-emerald-50 dark:bg-emerald-900/10 text-emerald-700 dark:text-emerald-300';
  return '';
}

// レイティング順位に応じた背景色
function getRatingBgColor(rank: number, totalCount: number): string {
  if (rank === 1) return "bg-amber-50 dark:bg-amber-900/10";
  if (rank <= 3) return "bg-blue-50 dark:bg-blue-900/10";
  if (rank <= Math.ceil(totalCount * 0.3)) return "bg-emerald-50 dark:bg-emerald-900/10";
  return "";
}

// ミニバーの色（順位ベース）
function getBarColor(rank: number, totalCount: number, isHighlighted?: boolean): string {
  if (isHighlighted) return 'bg-gradient-to-r from-red-600 to-red-400';
  if (rank === 1) return 'bg-gradient-to-r from-yellow-500 to-amber-400';
  if (rank === 2) return 'bg-gradient-to-r from-blue-600 to-blue-400';
  if (rank === 3) return 'bg-gradient-to-r from-blue-500 to-blue-300';
  if (rank <= Math.ceil(totalCount * 0.3)) return 'bg-gradient-to-r from-emerald-500 to-emerald-400';
  if (rank <= Math.ceil(totalCount * 0.5)) return 'bg-gradient-to-r from-green-400 to-green-300';
  return 'bg-gradient-to-r from-gray-400 to-gray-300 dark:from-gray-500 dark:to-gray-400';
}

// テキスト色（順位ベース）
function getRatingTextColor(rank: number, totalCount: number, isHighlighted?: boolean): string {
  if (isHighlighted) return "text-red-600 dark:text-red-400 font-bold";
  if (rank === 1) return "text-amber-600 dark:text-amber-400 font-bold";
  if (rank <= 3) return "text-blue-600 dark:text-blue-400 font-bold";
  if (rank <= Math.ceil(totalCount * 0.3)) return "text-emerald-600 dark:text-emerald-400";
  return "text-gray-600 dark:text-gray-400";
}

// 順位アイコン
function getRankIcon(rank: number): string | null {
  if (rank === 1) return '🥇';
  if (rank === 2) return '🥈';
  if (rank === 3) return '🥉';
  return null;
}

// =============================================================================
// メモ化されたサブコンポーネント
// =============================================================================

// レイティングセルコンポーネント（レース内相対表示版）
interface RatingCellProps {
  rating: string | number | undefined;
  minRating: number;
  maxRating: number;
  rank: number;
  totalCount: number;
}

const RatingCell = React.memo(function RatingCell({ rating, minRating, maxRating, rank, totalCount }: RatingCellProps) {
  const ratingNum = parseRating(rating);

  if (ratingNum > 0 && rank > 0) {
    return (
      <td className={cn("px-2 py-1.5 text-center border", getRatingBgColor(rank, totalCount))}>
        <RatingMiniBar
          rating={ratingNum}
          minRating={minRating}
          maxRating={maxRating}
          rank={rank}
          totalCount={totalCount}
        />
      </td>
    );
  }

  return (
    <td className={cn(
      "px-2 py-1.5 text-center border font-mono",
      getRatingColor(rating as string)
    )}>
      {rating || '-'}
    </td>
  );
});

// レイティングのミニバーコンポーネント（レース内相対表示版）
interface RatingMiniBarProps {
  rating: number;
  minRating: number;
  maxRating: number;
  rank: number;
  totalCount: number;
  isHighlighted?: boolean;
}

const RatingMiniBar = React.memo(function RatingMiniBar({ rating, minRating, maxRating, rank, totalCount, isHighlighted }: RatingMiniBarProps) {
  const range = maxRating - minRating;
  const percentage = range > 0
    ? 20 + ((rating - minRating) / range) * 80
    : 50;

  return (
    <div className="flex flex-col items-center gap-0.5">
      <div className="flex items-center gap-1">
        <span className={cn("font-mono text-sm", getRatingTextColor(rank, totalCount, isHighlighted))}>
          {rating.toFixed(1)}
        </span>
        {rank <= 3 && (
          <span className="text-sm">{getRankIcon(rank)}</span>
        )}
      </div>
      <div className="w-14 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all duration-500", getBarColor(rank, totalCount, isHighlighted))}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
});

// オッズ人気バッジ
const OddsRankBadge = React.memo(function OddsRankBadge({ rank, odds }: { rank: number; odds: string }) {
  const validRank = isNaN(rank) ? 0 : rank;

  const getBadgeStyle = () => {
    if (validRank === 1) return 'bg-gradient-to-r from-red-500 to-red-400 text-white font-bold shadow-sm';
    if (validRank === 2) return 'bg-gradient-to-r from-blue-500 to-blue-400 text-white';
    if (validRank === 3) return 'bg-gradient-to-r from-emerald-500 to-emerald-400 text-white';
    if (validRank <= 5 && validRank > 0) return 'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300';
    return 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-500';
  };

  return (
    <div className="flex flex-col items-end gap-0.5">
      <span className={cn(
        "font-bold",
        validRank === 1 && "text-red-600 dark:text-red-400",
        validRank === 2 && "text-blue-600 dark:text-blue-400",
        validRank === 3 && "text-emerald-600 dark:text-emerald-400"
      )}>
        {odds || '-'}
      </span>
      <span className={cn(
        "inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold",
        getBadgeStyle()
      )}>
        {validRank > 0 ? validRank : '-'}
      </span>
    </div>
  );
});

// 着順バッジ
const FinishPositionBadge = React.memo(function FinishPositionBadge({ position }: { position: string }) {
  const pos = parseInt(position, 10);

  let bgColor = 'bg-gray-100 text-gray-800';
  if (pos === 1) bgColor = 'bg-yellow-400 text-yellow-900';
  else if (pos === 2) bgColor = 'bg-gray-300 text-gray-800';
  else if (pos === 3) bgColor = 'bg-amber-600 text-white';
  else if (pos <= 5) bgColor = 'bg-blue-100 text-blue-800';

  return (
    <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-sm font-bold ${bgColor}`}>
      {position}
    </span>
  );
});

// =============================================================================
// メインコンポーネント
// =============================================================================

interface HorseEntryRowProps {
  entry: HorseEntry;
  showResult: boolean;
  trainingSummary?: TrainingSummaryData;
  minRating: number;
  maxRating: number;
  ratingRank: number;
  ratingTotalCount: number;
  aiIndexRank: number;
  secondAiIndex: number;
  aiIndexTotalCount: number;
  predictionComment?: RaceHorseComment;
  resultComment?: RaceHorseComment;
  horseComment?: HorseComment;
  myMark?: string;
  myMark2?: string;
  recentForm?: RecentFormData[];
  mlPrediction?: MlPredictionEntry;
  dbOdds?: DbHorseOdds;
  hasDbOdds?: boolean;
}

const HorseEntryRow = React.memo(function HorseEntryRow({
  entry,
  showResult,
  trainingSummary,
  minRating,
  maxRating,
  ratingRank,
  ratingTotalCount,
  aiIndexRank,
  secondAiIndex,
  aiIndexTotalCount,
  predictionComment,
  resultComment,
  horseComment,
  myMark,
  myMark2,
  recentForm,
  mlPrediction,
  dbOdds,
  hasDbOdds,
}: HorseEntryRowProps) {
  const { entry_data, training_data, result } = entry;
  const wakuColorClass = getWakuColor(entry_data.waku);

  // DB odds優先: オッズ・人気を決定
  const displayOdds = dbOdds?.winOdds != null ? String(dbOdds.winOdds.toFixed(1)) : entry_data.odds;
  const displayNinki = dbOdds?.ninki ?? parseInt(entry_data.odds_rank, 10);
  const oddsRankRaw = dbOdds?.ninki ?? parseInt(entry_data.odds_rank, 10);
  const oddsRank = isNaN(oddsRankRaw) ? 0 : oddsRankRaw;
  const rowBgClass = oddsRank === 1
    ? 'bg-amber-50 dark:bg-amber-900/10'
    : oddsRank <= 3
      ? 'bg-blue-50/50 dark:bg-blue-900/5'
      : '';

  return (
    <tr className={`hover:bg-gray-50 dark:hover:bg-gray-800/50 ${rowBgClass}`}>
      {/* 枠番 */}
      <td className={`px-2 py-1.5 text-center border ${wakuColorClass}`}>
        {entry_data.waku}
      </td>

      {/* 馬番 */}
      <td className="px-2 py-1.5 text-center border font-bold">
        {entry.horse_number}
      </td>

      {/* 本紙印 */}
      <td className={`px-2 py-1.5 text-center border text-lg font-bold ${getMarkBgColor(entry_data.honshi_mark)}`}>
        {entry_data.honshi_mark || '-'}
      </td>

      {/* My印（TARGET馬印1） */}
      <td className={`px-2 py-1.5 text-center border text-lg font-bold ${getMyMarkBgColor(myMark)}`}>
        {myMark || '-'}
      </td>

      {/* My印2（TARGET馬印2） */}
      <td className={`px-2 py-1.5 text-center border text-lg font-bold ${getMyMark2BgColor(myMark2)}`}>
        {myMark2 || '-'}
      </td>

      {/* ML Value Bet */}
      {mlPrediction !== undefined && (
        <td className={cn(
          "px-1 py-1.5 text-center border",
          mlPrediction.is_value_bet && "bg-amber-50 dark:bg-amber-900/20"
        )}>
          <div className="flex flex-col items-center gap-0.5">
            {mlPrediction.is_value_bet ? (
              <span className={cn(
                "inline-flex items-center justify-center px-1.5 py-0.5 rounded text-[10px] font-bold",
                mlPrediction.gap !== null && mlPrediction.gap >= 5
                  ? "bg-gradient-to-r from-red-500 to-red-400 text-white"
                  : mlPrediction.gap !== null && mlPrediction.gap >= 4
                    ? "bg-gradient-to-r from-amber-500 to-amber-400 text-white"
                    : "bg-gradient-to-r from-emerald-500 to-emerald-400 text-white"
              )}
                title={`VR${mlPrediction.value_rank} 人気${mlPrediction.odds_rank ?? '-'} Gap${mlPrediction.gap ?? '-'}\nModel A: ${(mlPrediction.pred_proba_accuracy * 100).toFixed(1)}%\nModel B: ${(mlPrediction.pred_proba_value * 100).toFixed(1)}%`}
              >
                VB
              </span>
            ) : (
              <span className="text-[10px] text-gray-400">-</span>
            )}
            {mlPrediction.value_rank <= 3 && (
              <span className="text-[9px] text-gray-500 dark:text-gray-400">
                VR{mlPrediction.value_rank}
              </span>
            )}
          </div>
        </td>
      )}

      {/* 馬名 + TARGETコメント + 直近戦績ドット（連勝/連敗バッジは着順セルに表示） */}
      <td className="px-2 py-1.5 border min-w-[10rem]">
        <div className="flex flex-col gap-0.5">
          <div className="flex items-center gap-1 flex-nowrap min-w-0">
            <Link
              href={`/horses-v2/${entry.horse_id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 dark:text-blue-400 hover:underline font-medium truncate"
            >
              {entry.horse_name}
            </Link>
            {/* TARGETコメントアイコン */}
            {(horseComment || predictionComment || resultComment) && (
              <span
                className={cn(
                  "inline-flex items-center justify-center w-4 h-4 rounded cursor-help flex-shrink-0",
                  resultComment
                    ? "text-orange-500 hover:text-orange-600"
                    : horseComment
                      ? "text-emerald-500 hover:text-emerald-600"
                      : "text-blue-500 hover:text-blue-600"
                )}
                title={[
                  horseComment && `【馬】${horseComment.comment}`,
                  predictionComment && `【予想】${predictionComment.comment}`,
                  resultComment && `【結果】${resultComment.comment}`,
                ].filter(Boolean).join('\n')}
              >
                <MessageSquareText className="w-3.5 h-3.5" />
              </span>
            )}
          </div>
          {recentForm && recentForm.length > 0 && (
            <TrendIndicator
              results={[]}
              entries={toRecentFormEntries(recentForm)}
              size="sm"
              className="mt-0"
              hideStreak
            />
          )}
        </div>
      </td>

      {/* 性齢 */}
      <td className="px-2 py-1.5 text-center border text-gray-600 dark:text-gray-400">
        {entry_data.age}
      </td>

      {/* 騎手 */}
      <td className="px-2 py-1.5 border">
        {entry_data.jockey}
      </td>

      {/* 斤量 */}
      <td className="px-2 py-1.5 text-center border">
        {entry_data.weight}
        {entry_data.weight_diff && (
          <span className={`text-xs ml-0.5 ${
            entry_data.weight_diff.startsWith('+')
              ? 'text-red-500'
              : entry_data.weight_diff.startsWith('-')
                ? 'text-blue-500'
                : ''
          }`}>
            {entry_data.weight_diff}
          </span>
        )}
      </td>

      {/* オッズ */}
      <td className={cn(
        "px-2 py-1.5 border",
        oddsRank === 1 && "bg-red-50 dark:bg-red-900/10",
        oddsRank === 2 && "bg-blue-50 dark:bg-blue-900/10",
        oddsRank === 3 && "bg-emerald-50 dark:bg-emerald-900/10"
      )}>
        <div className="flex items-center justify-end gap-1">
          {dbOdds?.oddsTrend && (
            <span className={cn(
              "text-[10px]",
              dbOdds.oddsTrend === 'down' ? 'text-red-500' :
              dbOdds.oddsTrend === 'up' ? 'text-blue-500' : 'text-gray-400'
            )}>
              {dbOdds.oddsTrend === 'down' ? '\u25BC' : dbOdds.oddsTrend === 'up' ? '\u25B2' : '-'}
            </span>
          )}
          <OddsRankBadge rank={oddsRank} odds={displayOdds} />
        </div>
      </td>
      {/* 複勝オッズ（DB取得時のみ表示） */}
      {hasDbOdds && (
        <td className="px-2 py-1.5 text-right border font-mono text-xs text-gray-500">
          {dbOdds?.placeOddsMin != null ? (
            dbOdds.placeOddsMin === dbOdds.placeOddsMax
              ? dbOdds.placeOddsMin.toFixed(1)
              : `${dbOdds.placeOddsMin.toFixed(1)}-${dbOdds.placeOddsMax!.toFixed(1)}`
          ) : '-'}
        </td>
      )}

      {/* AI指数 */}
      <td className={cn(
        "px-2 py-1.5 text-center border font-mono",
        getAiIndexColor(entry_data.ai_index, aiIndexRank, secondAiIndex, aiIndexTotalCount)
      )}>
        {entry_data.ai_index || '-'}
        {entry_data.ai_rank && (
          <Badge variant="outline" className="ml-1 text-xs px-1">
            {entry_data.ai_rank}
          </Badge>
        )}
      </td>

      {/* レイティング */}
      <RatingCell
        rating={entry_data.rating}
        minRating={minRating}
        maxRating={maxRating}
        rank={ratingRank}
        totalCount={ratingTotalCount}
      />

      {/* 総合ポイント */}
      <td className={`px-2 py-1.5 text-center border ${getPointBgColor(entry_data.aggregate_mark_point)}`}>
        {entry_data.aggregate_mark_point > 0 ? entry_data.aggregate_mark_point : '-'}
      </td>

      {/* 短評 */}
      <td className="px-2 py-1.5 border text-xs text-gray-700 dark:text-gray-300">
        {entry_data.short_comment || '-'}
      </td>



      {/* パドック評価・コメント（1列）：評価を上段・色付き、コメントを下段で改行表示 */}
      <td className="px-2 py-1.5 border text-xs text-gray-700 dark:text-gray-300">
        {entry.paddock_info?.mark || entry.paddock_info?.comment ? (
          <div className="flex flex-col gap-0.5 min-w-0">
            <span className={cn(
              "flex-shrink-0 w-fit inline-flex items-center justify-center min-w-[1.5rem] h-6 px-1.5 rounded text-sm font-extrabold shadow-sm",
              getPaddockMarkBgColor(entry.paddock_info?.mark)
            )}>
              {entry.paddock_info?.mark || '－'}
            </span>
            {entry.paddock_info?.comment && (
              <span className="leading-tight break-words line-clamp-2" title={entry.paddock_info.comment}>
                {entry.paddock_info.comment}
              </span>
            )}
          </div>
        ) : (
          <span className="text-gray-400">－</span>
        )}
      </td>

      {/* 結果（オプション）：着順の横に連勝/連敗バッジを表示 */}
      {showResult && result && (
        <>
          <td className="px-2 py-1.5 text-center border font-bold">
            <div className="flex items-center justify-center gap-1 flex-wrap">
              <FinishPositionBadge position={result.finish_position} />
              {recentForm && recentForm.length > 0 && (() => {
                const formEntries = toRecentFormEntries(recentForm);
                const results = formEntries.map(e => e.result);
                const streak = calculateStreak(results);
                return streak ? <StreakBadge streak={streak} /> : null;
              })()}
            </div>
          </td>
          <td className="px-2 py-1.5 text-center border font-mono">
            {result.time}
          </td>
          <td className="px-2 py-1.5 text-center border font-mono">
            {result.last_3f}
          </td>
        </>
      )}
      {showResult && !result && (
        <>
          <td className="px-2 py-1.5 text-center border">
            <div className="flex items-center justify-center gap-1 flex-wrap">
              <span>-</span>
              {recentForm && recentForm.length > 0 && (() => {
                const formEntries = toRecentFormEntries(recentForm);
                const results = formEntries.map(e => e.result);
                const streak = calculateStreak(results);
                return streak ? <StreakBadge streak={streak} /> : null;
              })()}
            </div>
          </td>
          <td className="px-2 py-1.5 text-center border">-</td>
          <td className="px-2 py-1.5 text-center border">-</td>
        </>
      )}
    </tr>
  );
});

export default function HorseEntryTable({
  entries,
  showResult = false,
  trainingSummaryMap = {},
  targetComments,
  targetMarks,
  recentFormMap,
  mlPredictions,
  raceId,
}: HorseEntryTableProps) {
  const hasMlPredictions = mlPredictions && Object.keys(mlPredictions).length > 0;

  // DB odds取得（SWR: 当日は30秒ポーリング）
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);

  const today = new Date();
  const todayStr = `${today.getFullYear()}${String(today.getMonth() + 1).padStart(2, '0')}${String(today.getDate()).padStart(2, '0')}`;
  const isToday = raceId ? raceId.startsWith(todayStr) : false;

  const { data: dbOdds } = useSWR<DbOddsResponse>(
    mounted && raceId && raceId.length === 16 ? `/api/odds/db-latest?raceId=${raceId}` : null,
    swrFetcher,
    {
      refreshInterval: isToday ? 30000 : 0,
      revalidateOnFocus: isToday,
      dedupingInterval: 10000,
    }
  );

  const hasDbOdds = !!(dbOdds && dbOdds.source !== 'none' && dbOdds.horses.length > 0);
  const dbOddsMap = useMemo(() => {
    const map = new Map<number, DbHorseOdds>();
    if (hasDbOdds) {
      for (const h of dbOdds.horses) {
        map.set(h.umaban, h);
      }
    }
    return map;
  }, [dbOdds, hasDbOdds]);

  // 馬番順にソート（useMemoでキャッシュ）
  const sortedEntries = useMemo(
    () => [...entries].sort((a, b) => a.horse_number - b.horse_number),
    [entries]
  );

  // レイティング・AI指数の統計計算（useMemoでキャッシュ）
  // entries が変わらない限り再計算しない（O(n log n)の計算を節約）
  const { maxRating, minRating, ratingRankMap, ratingCount, aiIndexRankMap, aiIndexCount, secondAiIndex } = useMemo(() => {
    // レイティング統計
    const ratings = entries
      .map(e => ({ horseNumber: e.horse_number, rating: parseRating(e.entry_data.rating) }))
      .filter(r => r.rating > 0);
    const ratingValues = ratings.map(r => r.rating);
    const maxR = ratingValues.length > 0 ? Math.max(...ratingValues) : 50;
    const minR = ratingValues.length > 0 ? Math.min(...ratingValues) : 40;

    const sortedRatings = [...ratings].sort((a, b) => b.rating - a.rating);
    const rankMap = new Map<number, number>();
    sortedRatings.forEach((r, idx) => {
      rankMap.set(r.horseNumber, idx + 1);
    });

    // AI指数統計
    const aiIndices = entries
      .map(e => ({ horseNumber: e.horse_number, aiIndex: parseAiIndex(e.entry_data.ai_index) }))
      .filter(a => a.aiIndex > 0);
    const sortedAi = [...aiIndices].sort((a, b) => b.aiIndex - a.aiIndex);
    const aiRankMap = new Map<number, number>();
    sortedAi.forEach((a, idx) => {
      aiRankMap.set(a.horseNumber, idx + 1);
    });
    const second = sortedAi.length > 1 ? sortedAi[1].aiIndex : 0;

    return {
      maxRating: maxR,
      minRating: minR,
      ratingRankMap: rankMap,
      ratingCount: ratings.length,
      aiIndexRankMap: aiRankMap,
      aiIndexCount: aiIndices.length,
      secondAiIndex: second,
    };
  }, [entries]);

  return (
    <div className="overflow-x-auto">
      {/* DB odds情報バー */}
      {hasDbOdds && (
        <div className="flex items-center gap-2 text-xs text-gray-500 mb-1 px-1">
          {dbOdds.source === 'timeseries' && dbOdds.snapshotTime && (
            <>
              <span className="inline-block w-2 h-2 rounded-full bg-green-400 animate-pulse" />
              <span>{formatSnapshotTime(dbOdds.snapshotTime)}更新</span>
              <span className="text-gray-400">({dbOdds.snapshotCount}回)</span>
            </>
          )}
          {dbOdds.source === 'final' && (
            <span className="text-yellow-600">確定オッズ</span>
          )}
        </div>
      )}
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-gray-100 dark:bg-gray-800">
            <th className="px-2 py-2 text-center border w-10">枠</th>
            <th className="px-2 py-2 text-center border w-10">馬番</th>
            <th className="px-2 py-2 text-center border w-10">本紙</th>
            <th className="px-2 py-2 text-center border w-10">My印</th>
            <th className="px-2 py-2 text-center border w-10">My2</th>
            {hasMlPredictions && (
              <th className="px-1 py-2 text-center border w-10" title="ML Value Bet">VB</th>
            )}
            <th className="px-2 py-2 text-left border min-w-32">馬名</th>
            <th className="px-2 py-2 text-center border w-16">性齢</th>
            <th className="px-2 py-2 text-left border min-w-20">騎手</th>
            <th className="px-2 py-2 text-center border w-12">斤量</th>
            <th className="px-2 py-2 text-right border w-16">単勝</th>
            {hasDbOdds && (
              <th className="px-2 py-2 text-right border w-24">複勝</th>
            )}
            <th className="px-2 py-2 text-center border w-16">AI指数</th>
            <th className="px-2 py-2 text-center border w-12">レート</th>
            <th className="px-2 py-2 text-center border w-10">P</th>
            <th className="px-2 py-2 text-left border min-w-24">短評</th>
            <th className="px-2 py-2 text-left border min-w-20" title="パドック評価・コメント">パ</th>
            {showResult && (
              <>
                <th className="px-2 py-2 text-center border w-10">着</th>
                <th className="px-2 py-2 text-center border w-16">タイム</th>
                <th className="px-2 py-2 text-center border w-12">上り</th>
              </>
            )}
          </tr>
        </thead>
        <tbody>
          {sortedEntries.map((entry) => (
            <HorseEntryRow
              key={entry.horse_number}
              entry={entry}
              showResult={showResult}
              trainingSummary={trainingSummaryMap[entry.horse_name] || trainingSummaryMap[normalizeHorseName(entry.horse_name)]}
              minRating={minRating}
              maxRating={maxRating}
              ratingRank={ratingRankMap.get(entry.horse_number) || 0}
              ratingTotalCount={ratingCount}
              aiIndexRank={aiIndexRankMap.get(entry.horse_number) || 0}
              secondAiIndex={secondAiIndex}
              aiIndexTotalCount={aiIndexCount}
              predictionComment={targetComments?.predictions[entry.horse_number]}
              resultComment={targetComments?.results[entry.horse_number]}
              horseComment={targetComments?.horseComments?.[entry.horse_number]}
              myMark={targetMarks?.horseMarks[entry.horse_number]}
              myMark2={targetMarks?.horseMarks2?.[entry.horse_number]}
              recentForm={recentFormMap?.[entry.horse_number]}
              mlPrediction={hasMlPredictions ? mlPredictions[entry.horse_number] : undefined}
              dbOdds={dbOddsMap.get(entry.horse_number)}
              hasDbOdds={hasDbOdds}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}
