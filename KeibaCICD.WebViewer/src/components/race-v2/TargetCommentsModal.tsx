'use client';

/**
 * TARGETコメント一覧モーダル（編集機能付き）
 * 
 * レース出走馬のTARGETコメントを一覧表示・編集
 * - 予想コメント（YOS_COM）: 青系
 * - 結果コメント（KEK_COM）: オレンジ系
 * - 馬コメント（UMA_COM）: 緑系（読み取り専用）
 */

import React, { useState, useMemo, useCallback } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { MessageSquareText, List, Save, Loader2, Pencil, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { RaceHorseComment, HorseComment } from '@/lib/data/target-comment-reader';
import type { HorseEntry } from '@/types/race-data';

/** レース情報（書き込みに必要） */
interface RaceInfo {
  venue: string;
  year: string;
  kai: number;
  nichi: number;
  raceNumber: number;
}

interface TargetCommentsModalProps {
  entries: HorseEntry[];
  targetComments?: {
    predictions: Record<number, RaceHorseComment>;
    results: Record<number, RaceHorseComment>;
    horseComments?: Record<number, HorseComment>;
  };
  /** 編集機能に必要なレース情報 */
  raceInfo?: RaceInfo;
  /** trainingSummaryMapからkettoNumを取得するため */
  trainingSummaryMap?: Record<string, { kettoNum?: string }>;
}

interface CommentRowData {
  horseNumber: number;
  horseName: string;
  prediction?: RaceHorseComment;
  result?: RaceHorseComment;
  horse?: HorseComment;
  hasComment: boolean;
  kettoNum?: string;
}

/** 編集中のコメント */
interface EditingComment {
  horseNumber: number;
  type: 'prediction' | 'result';
  value: string;
}

export function TargetCommentsModal({ 
  entries, 
  targetComments, 
  raceInfo,
  trainingSummaryMap = {},
}: TargetCommentsModalProps) {
  const [showOnlyWithComments, setShowOnlyWithComments] = useState(false); // 編集時は全馬表示がデフォルト
  const [isEditMode, setIsEditMode] = useState(false);
  const [editingComments, setEditingComments] = useState<Map<string, string>>(new Map());
  const [savingKeys, setSavingKeys] = useState<Set<string>>(new Set());
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  // 全馬のコメント情報を整理
  const commentRows: CommentRowData[] = useMemo(() => {
    const sortedEntries = [...entries].sort((a, b) => a.horse_number - b.horse_number);
    
    return sortedEntries.map((entry) => {
      // trainingSummaryMapからkettoNumを取得
      const normalized = entry.horse_name.replace(/^[\(（][外地父市][）\)]/g, '');
      const summary = trainingSummaryMap[entry.horse_name] || trainingSummaryMap[normalized];
      
      return {
        horseNumber: entry.horse_number,
        horseName: entry.horse_name,
        prediction: targetComments?.predictions[entry.horse_number],
        result: targetComments?.results[entry.horse_number],
        horse: targetComments?.horseComments?.[entry.horse_number],
        hasComment: !!(
          targetComments?.predictions[entry.horse_number] ||
          targetComments?.results[entry.horse_number] ||
          targetComments?.horseComments?.[entry.horse_number]
        ),
        kettoNum: summary?.kettoNum,
      };
    });
  }, [entries, targetComments, trainingSummaryMap]);

  // 表示する行をフィルタリング
  const displayRows = useMemo(() => {
    if (showOnlyWithComments && !isEditMode) {
      return commentRows.filter((row) => row.hasComment);
    }
    return commentRows;
  }, [commentRows, showOnlyWithComments, isEditMode]);

  // コメントがある馬の数
  const commentCount = commentRows.filter((row) => row.hasComment).length;

  // 編集キーを生成
  const getEditKey = (horseNumber: number, type: 'prediction' | 'result') => 
    `${horseNumber}-${type}`;

  // 編集中の値を取得
  const getEditingValue = (horseNumber: number, type: 'prediction' | 'result', original?: string) => {
    const key = getEditKey(horseNumber, type);
    if (editingComments.has(key)) {
      return editingComments.get(key) || '';
    }
    return original || '';
  };

  // 編集値を更新
  const setEditingValue = (horseNumber: number, type: 'prediction' | 'result', value: string) => {
    const key = getEditKey(horseNumber, type);
    setEditingComments(prev => {
      const next = new Map(prev);
      next.set(key, value);
      return next;
    });
  };

  // 変更があるかチェック
  const hasChanges = (horseNumber: number, type: 'prediction' | 'result', original?: string) => {
    const key = getEditKey(horseNumber, type);
    if (!editingComments.has(key)) return false;
    return editingComments.get(key) !== (original || '');
  };

  // コメントを保存
  const saveComment = useCallback(async (horseNumber: number, type: 'prediction' | 'result') => {
    if (!raceInfo) {
      setSaveMessage('レース情報がありません');
      return;
    }

    const key = getEditKey(horseNumber, type);
    const value = editingComments.get(key);
    if (value === undefined) return;

    setSavingKeys(prev => new Set(prev).add(key));
    setSaveMessage(null);

    try {
      const response = await fetch('/api/target-comments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: 'race',
          commentType: type,
          venue: raceInfo.venue,
          year: raceInfo.year,
          kai: raceInfo.kai,
          nichi: raceInfo.nichi,
          raceNumber: raceInfo.raceNumber,
          horseNumber,
          comment: value,
        }),
      });

      const result = await response.json();
      if (result.success) {
        setSaveMessage(`${horseNumber}番: ${result.message}`);
        // 保存成功後、編集状態をクリア
        setEditingComments(prev => {
          const next = new Map(prev);
          next.delete(key);
          return next;
        });
      } else {
        setSaveMessage(`エラー: ${result.message}`);
      }
    } catch (error) {
      setSaveMessage(`保存エラー: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setSavingKeys(prev => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    }
  }, [raceInfo, editingComments]);

  // 編集モード終了時にリセット
  const handleEditModeChange = (enabled: boolean) => {
    setIsEditMode(enabled);
    if (!enabled) {
      setEditingComments(new Map());
      setSaveMessage(null);
    }
  };

  // 編集可能かどうか
  const canEdit = !!raceInfo;

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-1.5">
          <List className="w-4 h-4" />
          コメント一覧
          {commentCount > 0 && (
            <Badge variant="default" className="ml-1 bg-blue-500">
              {commentCount}
            </Badge>
          )}
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-3xl max-h-[85vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <MessageSquareText className="w-5 h-5" />
            TARGETコメント一覧
            {isEditMode && (
              <Badge variant="outline" className="ml-2">
                編集モード
              </Badge>
            )}
          </DialogTitle>
        </DialogHeader>

        {/* フィルター＆編集モード切替 */}
        <div className="flex items-center justify-between py-2 border-b">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Switch
                id="show-only-comments"
                checked={showOnlyWithComments}
                onCheckedChange={setShowOnlyWithComments}
                disabled={isEditMode}
              />
              <Label htmlFor="show-only-comments" className="text-sm cursor-pointer">
                コメントありのみ
              </Label>
            </div>
            <span className="text-xs text-muted-foreground">
              ({displayRows.length}/{entries.length}頭)
            </span>
          </div>
          
          {canEdit && (
            <Button
              variant={isEditMode ? "default" : "outline"}
              size="sm"
              onClick={() => handleEditModeChange(!isEditMode)}
              className="gap-1.5"
            >
              {isEditMode ? (
                <>
                  <X className="w-4 h-4" />
                  編集終了
                </>
              ) : (
                <>
                  <Pencil className="w-4 h-4" />
                  編集
                </>
              )}
            </Button>
          )}
        </div>

        {/* 保存メッセージ */}
        {saveMessage && (
          <div className={cn(
            "px-3 py-2 rounded-md text-sm",
            saveMessage.startsWith('エラー') 
              ? "bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300"
              : "bg-green-50 text-green-700 dark:bg-green-950 dark:text-green-300"
          )}>
            {saveMessage}
          </div>
        )}

        {/* コメント一覧テーブル */}
        <div className="flex-1 overflow-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-background border-b z-10">
              <tr>
                <th className="px-2 py-2 text-center w-12">馬番</th>
                <th className="px-2 py-2 text-left w-28">馬名</th>
                <th className="px-2 py-2 text-left">予想</th>
                <th className="px-2 py-2 text-left">結果</th>
              </tr>
            </thead>
            <tbody>
              {displayRows.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-muted-foreground">
                    表示するデータがありません
                  </td>
                </tr>
              ) : (
                displayRows.map((row) => (
                  <React.Fragment key={row.horseNumber}>
                    {/* 1段目: 予想・結果 */}
                    <tr
                      className={cn(
                        "hover:bg-muted/50",
                        !row.hasComment && !isEditMode && "opacity-50",
                        !row.horse && "border-b"
                      )}
                    >
                      <td className="px-2 py-2 text-center font-bold align-top" rowSpan={row.horse ? 2 : 1}>
                        {row.horseNumber}
                      </td>
                      <td className="px-2 py-2 font-medium text-xs align-top" rowSpan={row.horse ? 2 : 1}>
                        {row.horseName}
                      </td>
                      
                      {/* 予想コメント */}
                      <td className="px-2 py-2 align-top">
                        {isEditMode ? (
                          <div className="space-y-1">
                            <Textarea
                              value={getEditingValue(row.horseNumber, 'prediction', row.prediction?.comment)}
                              onChange={(e) => setEditingValue(row.horseNumber, 'prediction', e.target.value)}
                              placeholder="予想コメントを入力..."
                              className="min-h-[50px] text-xs resize-none"
                            />
                            {hasChanges(row.horseNumber, 'prediction', row.prediction?.comment) && (
                              <Button
                                size="sm"
                                onClick={() => saveComment(row.horseNumber, 'prediction')}
                                disabled={savingKeys.has(getEditKey(row.horseNumber, 'prediction'))}
                                className="h-6 text-xs gap-1"
                              >
                                {savingKeys.has(getEditKey(row.horseNumber, 'prediction')) ? (
                                  <Loader2 className="w-3 h-3 animate-spin" />
                                ) : (
                                  <Save className="w-3 h-3" />
                                )}
                                保存
                              </Button>
                            )}
                          </div>
                        ) : (
                          <span className="text-sm whitespace-pre-wrap">
                            {row.prediction?.comment || '-'}
                          </span>
                        )}
                      </td>
                      
                      {/* 結果コメント */}
                      <td className="px-2 py-2 align-top">
                        {isEditMode ? (
                          <div className="space-y-1">
                            <Textarea
                              value={getEditingValue(row.horseNumber, 'result', row.result?.comment)}
                              onChange={(e) => setEditingValue(row.horseNumber, 'result', e.target.value)}
                              placeholder="結果コメントを入力..."
                              className="min-h-[50px] text-xs resize-none"
                            />
                            {hasChanges(row.horseNumber, 'result', row.result?.comment) && (
                              <Button
                                size="sm"
                                onClick={() => saveComment(row.horseNumber, 'result')}
                                disabled={savingKeys.has(getEditKey(row.horseNumber, 'result'))}
                                className="h-6 text-xs gap-1"
                              >
                                {savingKeys.has(getEditKey(row.horseNumber, 'result')) ? (
                                  <Loader2 className="w-3 h-3 animate-spin" />
                                ) : (
                                  <Save className="w-3 h-3" />
                                )}
                                保存
                              </Button>
                            )}
                          </div>
                        ) : (
                          <span className="text-sm whitespace-pre-wrap">
                            {row.result?.comment || '-'}
                          </span>
                        )}
                      </td>
                    </tr>
                    
                    {/* 2段目: 馬コメント（ある場合のみ） */}
                    {row.horse && (
                      <tr className="border-b bg-emerald-50/30 dark:bg-emerald-950/20">
                        <td colSpan={2} className="px-2 py-1.5">
                          <div className="flex items-start gap-2 text-xs">
                            <Badge 
                              variant="outline" 
                              className="shrink-0 text-[10px] px-1 py-0 bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-300 dark:border-emerald-800"
                            >
                              馬メモ
                            </Badge>
                            <span className="text-emerald-700 dark:text-emerald-300 whitespace-pre-wrap">
                              {row.horse.comment}
                            </span>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* 凡例 */}
        <div className="pt-2 border-t flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
          <div className="flex items-center gap-1">
            <Badge
              variant="outline"
              className="text-xs bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-300 dark:border-emerald-800"
            >
              馬
            </Badge>
            <span>UMA_COM（読み取り専用）</span>
          </div>
          <div className="flex items-center gap-1">
            <Badge
              variant="outline"
              className="text-xs bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950 dark:text-blue-300 dark:border-blue-800"
            >
              予想
            </Badge>
            <span>YOS_COM</span>
          </div>
          <div className="flex items-center gap-1">
            <Badge
              variant="outline"
              className="text-xs bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-950 dark:text-orange-300 dark:border-orange-800"
            >
              結果
            </Badge>
            <span>KEK_COM</span>
          </div>
          {!canEdit && (
            <span className="text-amber-600 dark:text-amber-400">
              ※ 編集にはレース情報が必要です
            </span>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
