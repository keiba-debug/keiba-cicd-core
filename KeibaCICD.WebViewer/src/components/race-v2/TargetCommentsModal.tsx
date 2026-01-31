'use client';

/**
 * TARGETコメント一覧モーダル
 * 
 * レース出走馬のTARGETコメントを一覧表示
 * - 予想コメント（YOS_COM）: 青系
 * - 結果コメント（KEK_COM）: オレンジ系
 * - 馬コメント（UMA_COM）: 緑系
 */

import { useState, useMemo } from 'react';
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
import { MessageSquareText, List } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { RaceHorseComment, HorseComment } from '@/lib/data/target-comment-reader';
import type { HorseEntry } from '@/types/race-data';

interface TargetCommentsModalProps {
  entries: HorseEntry[];
  targetComments?: {
    predictions: Record<number, RaceHorseComment>;
    results: Record<number, RaceHorseComment>;
    horseComments?: Record<number, HorseComment>;
  };
}

interface CommentRowData {
  horseNumber: number;
  horseName: string;
  prediction?: RaceHorseComment;
  result?: RaceHorseComment;
  horse?: HorseComment;
  hasComment: boolean;
}

export function TargetCommentsModal({ entries, targetComments }: TargetCommentsModalProps) {
  const [showOnlyWithComments, setShowOnlyWithComments] = useState(true);

  // 全馬のコメント情報を整理
  const commentRows: CommentRowData[] = useMemo(() => {
    const sortedEntries = [...entries].sort((a, b) => a.horse_number - b.horse_number);
    
    return sortedEntries.map((entry) => ({
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
    }));
  }, [entries, targetComments]);

  // 表示する行をフィルタリング
  const displayRows = useMemo(() => {
    if (showOnlyWithComments) {
      return commentRows.filter((row) => row.hasComment);
    }
    return commentRows;
  }, [commentRows, showOnlyWithComments]);

  // コメントがある馬の数
  const commentCount = commentRows.filter((row) => row.hasComment).length;

  // コメントがない場合はボタンを非活性
  if (commentCount === 0) {
    return (
      <Button variant="outline" size="sm" disabled className="gap-1.5">
        <List className="w-4 h-4" />
        コメント一覧
        <Badge variant="secondary" className="ml-1">0</Badge>
      </Button>
    );
  }

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-1.5">
          <List className="w-4 h-4" />
          コメント一覧
          <Badge variant="default" className="ml-1 bg-blue-500">
            {commentCount}
          </Badge>
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <MessageSquareText className="w-5 h-5" />
            TARGETコメント一覧
          </DialogTitle>
        </DialogHeader>

        {/* フィルター */}
        <div className="flex items-center gap-2 py-2 border-b">
          <Switch
            id="show-only-comments"
            checked={showOnlyWithComments}
            onCheckedChange={setShowOnlyWithComments}
          />
          <Label htmlFor="show-only-comments" className="text-sm cursor-pointer">
            コメントありのみ表示
          </Label>
          <span className="text-xs text-muted-foreground ml-2">
            ({displayRows.length}/{entries.length}頭)
          </span>
        </div>

        {/* コメント一覧テーブル */}
        <div className="flex-1 overflow-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-background border-b">
              <tr>
                <th className="px-2 py-2 text-center w-12">馬番</th>
                <th className="px-2 py-2 text-left w-28">馬名</th>
                <th className="px-2 py-2 text-left">コメント</th>
              </tr>
            </thead>
            <tbody>
              {displayRows.length === 0 ? (
                <tr>
                  <td colSpan={3} className="px-4 py-8 text-center text-muted-foreground">
                    コメントがありません
                  </td>
                </tr>
              ) : (
                displayRows.map((row) => (
                  <tr
                    key={row.horseNumber}
                    className={cn(
                      "border-b hover:bg-muted/50",
                      !row.hasComment && "opacity-50"
                    )}
                  >
                    <td className="px-2 py-2 text-center font-bold">
                      {row.horseNumber}
                    </td>
                    <td className="px-2 py-2 font-medium text-xs">
                      {row.horseName}
                    </td>
                    <td className="px-2 py-2">
                      {row.hasComment ? (
                        <div className="space-y-1">
                          {row.horse && (
                            <div className="flex items-start gap-2">
                              <Badge
                                variant="outline"
                                className="shrink-0 text-xs bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-300 dark:border-emerald-800"
                              >
                                馬
                              </Badge>
                              <span className="text-sm whitespace-pre-wrap">
                                {row.horse.comment}
                              </span>
                            </div>
                          )}
                          {row.prediction && (
                            <div className="flex items-start gap-2">
                              <Badge
                                variant="outline"
                                className="shrink-0 text-xs bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950 dark:text-blue-300 dark:border-blue-800"
                              >
                                予想
                              </Badge>
                              <span className="text-sm whitespace-pre-wrap">
                                {row.prediction.comment}
                              </span>
                            </div>
                          )}
                          {row.result && (
                            <div className="flex items-start gap-2">
                              <Badge
                                variant="outline"
                                className="shrink-0 text-xs bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-950 dark:text-orange-300 dark:border-orange-800"
                              >
                                結果
                              </Badge>
                              <span className="text-sm whitespace-pre-wrap">
                                {row.result.comment}
                              </span>
                            </div>
                          )}
                        </div>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </td>
                  </tr>
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
            <span>UMA_COM</span>
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
        </div>
      </DialogContent>
    </Dialog>
  );
}
