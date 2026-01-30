'use client';

/**
 * 調教分析セクション
 *
 * - 最終追切: 当週の水曜か木曜（場所/スピード/ラップ）
 * - 土日追切: 前週の土曜か日曜、両方あればタイムが早いほう
 * - 一週前追切: 前週の水曜か木曜
 * - 調教評価（矢印）・攻め馬解説
 */

import React, { useState, useRef } from 'react';
import { HorseEntry, getWakuColor, formatTrainerName } from '@/types/race-data';
import { POSITIVE_TEXT, POSITIVE_BG, POSITIVE_BG_MUTED } from '@/lib/positive-colors';
import { ChevronDown, ChevronUp, Dumbbell, MessageSquare, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import type { TrainingSummaryData } from '@/lib/data/training-summary-reader';

interface PreviousTrainingEntry {
  date: string;
  training: TrainingSummaryData;
}

interface TrainingAnalysisSectionProps {
  entries: HorseEntry[];
  trainingSummaryMap?: Record<string, TrainingSummaryData>;
  previousTrainingMap?: Record<string, PreviousTrainingEntry>;
}

export default function TrainingAnalysisSection({ 
  entries, 
  trainingSummaryMap = {},
  previousTrainingMap = {}
}: TrainingAnalysisSectionProps) {
  const [isOpen, setIsOpen] = useState(true);
  
  // 馬番順にソート
  const sortedEntries = [...entries].sort((a, b) => a.horse_number - b.horse_number);
  
  // 調教情報があるエントリーのみフィルター
  const entriesWithTraining = sortedEntries.filter(entry => 
    entry.training_data?.attack_explanation ||
    entry.training_data?.short_review ||
    entry.training_data?.evaluation ||
    entry.training_data?.training_arrow ||
    trainingSummaryMap[entry.horse_name]?.finalLap ||
    trainingSummaryMap[entry.horse_name]?.weekendLap ||
    trainingSummaryMap[entry.horse_name]?.weekAgoLap ||
    trainingSummaryMap[entry.horse_name]?.timeRank
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
                  {/* 調教タイム詳細 */}
                  <th className="px-2 py-2 text-left border min-w-64" title="調教タイム詳細（最終/土日/1週前）">今走調教</th>
                  {/* 前走調教 */}
                  <th className="px-2 py-2 text-left border min-w-56" title="前走時の調教タイム">前走調教</th>
                  {/* その他 */}
                  <th className="px-2 py-2 text-center border w-10" title="調教評価">評価</th>
                  <th className="px-2 py-2 text-left border min-w-24">調教短評</th>
                  <th className="px-2 py-2 text-left border min-w-48">攻め馬解説</th>
                </tr>
              </thead>
              <tbody>
          {sortedEntries.map((entry) => (
            <TrainingAnalysisRow 
              key={entry.horse_number} 
              entry={entry} 
              trainingSummary={trainingSummaryMap[entry.horse_name]}
              previousTraining={previousTrainingMap[entry.horse_name]}
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
              <span><strong>ラップ:</strong> S=終い重視 / A=やや終い / B=平均 / C=やや前傾 / D=前傾、+ 加速 / = 同 / - 減速</span>
            </div>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}

interface TrainingAnalysisRowProps {
  entry: HorseEntry;
  trainingSummary?: TrainingSummaryData;
  previousTraining?: PreviousTrainingEntry;
}

function TrainingAnalysisRow({ entry, trainingSummary, previousTraining }: TrainingAnalysisRowProps) {
  const { entry_data, training_data } = entry;
  const wakuColorClass = getWakuColor(entry_data.waku);

  // 調教矢印の色（プラス＝緑、マイナス＝赤）
  const getArrowColor = (arrow: string) => {
    switch (arrow) {
      case '↗': return POSITIVE_TEXT;
      case '↘': return 'text-red-600 dark:text-red-400 font-bold';
      default: return 'text-gray-500';
    }
  };

  // ラップランクの色（S/A/B/C/Dで色分け）
  const getLapRankColor = (rank?: string) => {
    if (!rank) return '';
    if (rank.startsWith('S')) return 'text-green-600 dark:text-green-400 font-bold';
    if (rank.startsWith('A')) return 'text-emerald-600 dark:text-emerald-400 font-medium';
    if (rank.startsWith('B')) return 'text-blue-600 dark:text-blue-400';
    if (rank.startsWith('C')) return 'text-orange-600 dark:text-orange-400';
    if (rank.startsWith('D')) return 'text-red-600 dark:text-red-400';
    return 'text-gray-500 dark:text-gray-400';
  };

  // ラップランクの背景色
  const getLapRankBgColor = (rank?: string) => {
    if (!rank) return '';
    if (rank.startsWith('S')) return 'bg-green-50 dark:bg-green-900/20';
    if (rank.startsWith('A')) return 'bg-emerald-50 dark:bg-emerald-900/20';
    if (rank.startsWith('B')) return 'bg-blue-50 dark:bg-blue-900/20';
    if (rank.startsWith('C')) return 'bg-orange-50 dark:bg-orange-900/20';
    if (rank.startsWith('D')) return 'bg-red-50 dark:bg-red-900/20';
    return '';
  };

  // detailをパースして行ごとに表示（最終/土日/1週前）
  const formatTrainingDetail = () => {
    if (!trainingSummary?.detail) return null;
    
    // "最終:坂路 4F47.0-13.9 / 土日:坂路 4F52.0-13.6 / 1週前:坂路 4F54.0-13.8" 形式をパース
    const parts = trainingSummary.detail.split(' / ');
    
    return (
      <div className="space-y-0.5">
        {parts.map((part, idx) => {
          // ラベル(最終/土日/1週前)と値を分離
          const colonIdx = part.indexOf(':');
          if (colonIdx === -1) return <div key={idx} className="text-xs">{part}</div>;
          
          const label = part.substring(0, colonIdx);
          const value = part.substring(colonIdx + 1);
          
          // 対応するラップランクとスピード（◎=好タイム）を取得
          let lapRank = '';
          let isFastTime = false;
          if (label === '最終') {
            lapRank = trainingSummary.finalLap || '';
            isFastTime = trainingSummary.finalSpeed === '◎';
          } else if (label === '土日') {
            lapRank = trainingSummary.weekendLap || '';
            isFastTime = trainingSummary.weekendSpeed === '◎';
          } else if (label === '1週前') {
            lapRank = trainingSummary.weekAgoLap || '';
            isFastTime = trainingSummary.weekAgoSpeed === '◎';
          }
          
          // 好タイムの場合は行全体を緑色で強調、背景も追加
          const isGoodTime = isFastTime;
          const rowClass = isGoodTime
            ? 'text-xs flex items-center gap-1 text-green-700 dark:text-green-400 font-medium bg-green-50 dark:bg-green-900/30 px-1.5 py-0.5 rounded'
            : 'text-xs flex items-center gap-1 text-gray-700 dark:text-gray-300';
          
          // ラップランクに応じた背景色を追加（好タイムでない場合）
          const bgClass = !isGoodTime && lapRank ? getLapRankBgColor(lapRank) : '';
          const combinedRowClass = `${rowClass} ${bgClass}`.trim();
          
          return (
            <div key={idx} className={combinedRowClass}>
              <span className={isGoodTime ? 'w-10 shrink-0 font-semibold' : 'text-muted-foreground w-10 shrink-0'}>{label}:</span>
              <span className={`font-mono ${isGoodTime ? 'font-semibold' : ''}`}>{value}</span>
              {isGoodTime && (
                <span className="text-green-600 dark:text-green-400 font-bold ml-1" title="好タイム">◎</span>
              )}
              {lapRank && (
                <span className={`ml-1 px-1.5 py-0.5 rounded text-xs font-medium ${getLapRankColor(lapRank)} ${isGoodTime ? 'bg-green-100 dark:bg-green-800/40' : ''}`}>
                  {lapRank}
                </span>
              )}
            </div>
          );
        })}
      </div>
    );
  };

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
        <div className="flex items-center gap-1">
          <span>{formatTrainerName(entry_data.trainer, entry_data.trainer_tozai)}</span>
          {(entry_data.trainer_comment || entry_data.trainer_id) && (
            <TrainerCommentButton 
              trainerName={formatTrainerName(entry_data.trainer, entry_data.trainer_tozai)}
              trainerId={entry_data.trainer_id}
              comment={entry_data.trainer_comment}
            />
          )}
        </div>
      </td>
      
      {/* 今走調教タイム詳細 */}
      <td className="px-2 py-1.5 border">
        {formatTrainingDetail() || <span className="text-gray-400 text-xs">-</span>}
      </td>
      
      {/* 前走調教 */}
      <td className="px-2 py-1.5 border">
        {previousTraining?.training?.detail ? (
          <div className="space-y-0.5">
            {previousTraining.date && (
              <div className="text-xs text-muted-foreground mb-0.5">
                {previousTraining.date}
              </div>
            )}
            <div className="text-xs font-mono">
              {previousTraining.training.detail.split(' / ').map((part, idx) => {
                const isFastTime = previousTraining.training.finalSpeed === '◎' && idx === 0;
                return (
                  <div key={idx} className={isFastTime ? 'text-green-700 dark:text-green-400 font-medium' : ''}>
                    {part}
                    {isFastTime && <span className="ml-1 text-green-600 font-bold">◎</span>}
                  </div>
                );
              })}
            </div>
            {previousTraining.training.lapRank && (
              <div className={`text-xs ${getLapRankColor(previousTraining.training.lapRank)}`}>
                ラップ: {previousTraining.training.lapRank}
              </div>
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
      
      {/* 調教短評 */}
      <td className="px-2 py-1.5 border text-xs text-gray-700 dark:text-gray-300">
        {training_data?.short_review || '-'}
      </td>
      
      {/* 攻め馬解説 */}
      <td className="px-2 py-1.5 border text-xs text-gray-700 dark:text-gray-300">
        <ExpandableText 
          text={training_data?.attack_explanation} 
          maxLength={60}
        />
      </td>
    </tr>
  );
}

interface ExpandableTextProps {
  text: string | undefined;
  maxLength: number;
}

function ExpandableText({ text, maxLength }: ExpandableTextProps) {
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
}

interface TrainerCommentButtonProps {
  trainerName: string;
  trainerId?: string;
  comment?: string;
}

function TrainerCommentButton({ trainerName, trainerId, comment: initialComment }: TrainerCommentButtonProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [comment, setComment] = useState<string | null>(initialComment || null);
  const [isLoading, setIsLoading] = useState(false);
  const hasFetchedRef = useRef<string | null>(null); // 取得済みのtrainerIdを記録

  // trainerIdが変更された時にコメントとhasFetchedRefをリセット
  React.useEffect(() => {
    if (hasFetchedRef.current !== trainerId) {
      hasFetchedRef.current = null;
      setComment(initialComment || null);
    }
  }, [trainerId, initialComment]);

  // コメントを取得（trainer_idがある場合、モーダルが開いた時のみ、初回のみ）
  React.useEffect(() => {
    // 既にコメントがある場合、またはtrainer_idがない場合、またはモーダルが閉じている場合、または既に取得済みの場合はスキップ
    if (comment || !trainerId || !isOpen || hasFetchedRef.current === trainerId) {
      return;
    }
    
    setIsLoading(true);
    hasFetchedRef.current = trainerId; // 取得開始をマーク
    
    const fetchComment = async () => {
      try {
        const response = await fetch(`/api/trainer/comment?trainer_id=${encodeURIComponent(trainerId)}`);
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.error) {
          console.error('調教師コメント取得エラー:', data.error, data.details);
          setComment(null);
        } else if (data.comment && typeof data.comment === 'string' && data.comment.trim().length > 3) {
          // 有効なコメントのみ設定（3文字以下や数字のみは除外）
          const trimmedComment = data.comment.trim();
          if (!/^\d+$/.test(trimmedComment)) {
            setComment(trimmedComment);
          } else {
            setComment(null);
          }
        } else {
          // コメントがない場合
          setComment(null);
        }
      } catch (err) {
        console.error('調教師コメント取得エラー:', err);
        setComment(null);
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchComment();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trainerId, isOpen]); // trainerIdとisOpenが変更された時のみ実行


  // ESCキーでモーダルを閉じる
  React.useEffect(() => {
    if (!isOpen) return;
    
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsOpen(false);
      }
    };
    
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [isOpen]);

  // モーダルが閉じた時にhasFetchedRefをリセット（次回開いた時に再取得可能にする）
  React.useEffect(() => {
    if (!isOpen) {
      hasFetchedRef.current = false;
    }
  }, [isOpen]);

  // コメントを整形（改行を保持）
  const formattedComment = comment
    ? comment.split('\n').map((line, idx) => (
        <React.Fragment key={idx}>
          {line}
          {idx < comment.split('\n').length - 1 && <br />}
        </React.Fragment>
      ))
    : null;

  return (
    <>
      <button
        onClick={(e) => {
          e.stopPropagation();
          setIsOpen(true);
        }}
        className="inline-flex items-center justify-center w-4 h-4 text-blue-500 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 transition-colors"
        title="調教師コメントを表示"
      >
        <MessageSquare className="w-3.5 h-3.5" />
      </button>

      {/* モーダル */}
      {isOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          onClick={() => setIsOpen(false)}
        >
          {/* 背景オーバーレイ */}
          <div className="absolute inset-0 bg-black/50 dark:bg-black/70" />
          
          {/* モーダルコンテンツ */}
          <div
            className="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] overflow-hidden flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            {/* ヘッダー */}
            <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
              <div className="flex items-center gap-2">
                <MessageSquare className="w-5 h-5 text-blue-500" />
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                  調教師コメント
                </h3>
              </div>
              <button
                onClick={() => setIsOpen(false)}
                className="p-1 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                title="閉じる (ESC)"
              >
                <X className="w-5 h-5 text-gray-500 dark:text-gray-400" />
              </button>
            </div>

            {/* コンテンツ */}
            <div className="p-6 overflow-y-auto flex-1">
              <div className="mb-4">
                <div className="text-sm text-gray-500 dark:text-gray-400 mb-1">調教師</div>
                <div className="text-base font-medium text-gray-900 dark:text-gray-100">
                  {trainerName}
                </div>
              </div>
              
              <div>
                <div className="text-sm text-gray-500 dark:text-gray-400 mb-2">コメント</div>
                {isLoading ? (
                  <div className="text-sm text-gray-500 dark:text-gray-400">読み込み中...</div>
                ) : comment ? (
                  <div className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap leading-relaxed">
                    {formattedComment}
                  </div>
                ) : (
                  <div className="text-sm text-gray-400 dark:text-gray-500">コメントがありません</div>
                )}
              </div>
            </div>

            {/* フッター */}
            <div className="p-4 border-t border-gray-200 dark:border-gray-700 flex justify-end">
              <Button
                variant="outline"
                onClick={() => setIsOpen(false)}
                className="text-sm"
              >
                閉じる
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
