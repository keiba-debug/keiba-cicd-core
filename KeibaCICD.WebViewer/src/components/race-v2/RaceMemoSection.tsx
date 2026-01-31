'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  StickyNote,
  ChevronDown,
  ChevronUp,
  Check,
  Loader2,
  Plus,
  Maximize2,
} from 'lucide-react';

interface Memo {
  type: 'pre' | 'post';
  text: string;
  created_at: string;
  updated_at: string;
}

interface MemoData {
  race_id: string;
  race_date: string;
  race_name: string;
  memos: Memo[];
}

interface RaceMemoSectionProps {
  raceId: string;
  raceDate: string; // YYYY-MM-DD 形式
  raceName: string;
  showResults?: boolean;
}

export function RaceMemoSection({
  raceId,
  raceDate,
  raceName,
  showResults = false,
}: RaceMemoSectionProps) {
  const [memoData, setMemoData] = useState<MemoData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [expanded, setExpanded] = useState(true);
  const [showPostMemo, setShowPostMemo] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // テキストエリアの値
  const [preText, setPreText] = useState('');
  const [postText, setPostText] = useState('');

  // Debounce用タイマー
  const saveTimerRef = useRef<NodeJS.Timeout | null>(null);

  // メモを取得
  const fetchMemo = useCallback(async () => {
    try {
      const res = await fetch(`/api/memos/${raceId}?date=${raceDate}`);
      if (res.ok) {
        const data: MemoData = await res.json();
        setMemoData(data);

        // テキストを設定
        const preMemo = data.memos.find((m) => m.type === 'pre');
        const postMemo = data.memos.find((m) => m.type === 'post');
        setPreText(preMemo?.text || '');
        setPostText(postMemo?.text || '');

        // 結果後メモが存在する場合は表示
        if (postMemo && postMemo.text) {
          setShowPostMemo(true);
        }
      }
    } catch (error) {
      console.error('メモ取得エラー:', error);
    } finally {
      setLoading(false);
    }
  }, [raceId, raceDate]);

  useEffect(() => {
    fetchMemo();
  }, [fetchMemo]);

  // メモを保存
  const saveMemo = useCallback(
    async (type: 'pre' | 'post', text: string) => {
      setSaving(true);
      setSaveSuccess(false);

      try {
        const res = await fetch(`/api/memos/${raceId}?date=${raceDate}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            type,
            text,
            race_name: raceName,
            race_date: raceDate.replace(/-/g, ''), // YYYYMMDD形式
          }),
        });

        if (res.ok) {
          const result = await res.json();
          setMemoData(result.data);
          setSaveSuccess(true);

          // 2秒後に成功表示をリセット
          setTimeout(() => setSaveSuccess(false), 2000);
        }
      } catch (error) {
        console.error('メモ保存エラー:', error);
      } finally {
        setSaving(false);
      }
    },
    [raceId, raceDate, raceName]
  );

  // Debounce付き自動保存
  const handleTextChange = useCallback(
    (type: 'pre' | 'post', text: string) => {
      if (type === 'pre') {
        setPreText(text);
      } else {
        setPostText(text);
      }

      // 既存のタイマーをクリア
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
      }

      // 1.5秒後に保存
      saveTimerRef.current = setTimeout(() => {
        saveMemo(type, text);
      }, 1500);
    },
    [saveMemo]
  );

  // クリーンアップ
  useEffect(() => {
    return () => {
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
      }
    };
  }, []);

  // 最終更新時刻を取得
  const getLastUpdated = (type: 'pre' | 'post'): string | null => {
    const memo = memoData?.memos.find((m) => m.type === type);
    return memo?.updated_at || null;
  };

  // 時刻をフォーマット
  const formatTime = (isoString: string): string => {
    const date = new Date(isoString);
    return date.toLocaleString('ja-JP', {
      month: 'numeric',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (loading) {
    return (
      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-base flex items-center gap-2">
            <StickyNote className="h-4 w-4" />
            予想メモ
          </CardTitle>
        </CardHeader>
        <CardContent className="py-4">
          <div className="flex items-center justify-center text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
            読み込み中...
          </div>
        </CardContent>
      </Card>
    );
  }

  const preUpdated = getLastUpdated('pre');
  const postUpdated = getLastUpdated('post');

  return (
    <Card>
      <Collapsible open={expanded} onOpenChange={setExpanded}>
        <CollapsibleTrigger asChild>
          <CardHeader className="py-3 cursor-pointer hover:bg-muted/50 transition-colors">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                <StickyNote className="h-4 w-4" />
                予想メモ
                {(preText || postText) && (
                  <span className="text-xs text-muted-foreground font-normal ml-2">
                    (記録あり)
                  </span>
                )}
              </CardTitle>
              <div className="flex items-center gap-2">
                {saving && (
                  <span className="text-xs text-muted-foreground flex items-center">
                    <Loader2 className="h-3 w-3 animate-spin mr-1" />
                    保存中...
                  </span>
                )}
                {saveSuccess && (
                  <span className="text-xs text-green-600 flex items-center">
                    <Check className="h-3 w-3 mr-1" />
                    保存しました
                  </span>
                )}
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 w-6 p-0"
                  onClick={(e) => {
                    e.stopPropagation();
                    setIsFullscreen(true);
                  }}
                  title="全画面表示"
                >
                  <Maximize2 className="h-4 w-4" />
                </Button>
                {expanded ? (
                  <ChevronUp className="h-4 w-4 text-muted-foreground" />
                ) : (
                  <ChevronDown className="h-4 w-4 text-muted-foreground" />
                )}
              </div>
            </div>
          </CardHeader>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <CardContent className="pt-0 pb-4 space-y-4">
            {/* 予想前メモ */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-muted-foreground">
                  予想メモ（レース前）
                </label>
                {preUpdated && (
                  <span className="text-xs text-muted-foreground">
                    最終保存: {formatTime(preUpdated)}
                  </span>
                )}
              </div>
              <textarea
                value={preText}
                onChange={(e) => handleTextChange('pre', e.target.value)}
                placeholder="予想の根拠、気になるポイントなどをメモ..."
                className="w-full min-h-[100px] p-3 text-sm border rounded-md resize-y bg-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
              />
            </div>

            {/* 結果後メモ（showResults=trueの場合のみ） */}
            {showResults && (
              <>
                {showPostMemo ? (
                  <div className="space-y-2 pt-2 border-t">
                    <div className="flex items-center justify-between">
                      <label className="text-sm font-medium text-muted-foreground">
                        振り返りメモ（レース後）
                      </label>
                      {postUpdated && (
                        <span className="text-xs text-muted-foreground">
                          最終保存: {formatTime(postUpdated)}
                        </span>
                      )}
                    </div>
                    <textarea
                      value={postText}
                      onChange={(e) => handleTextChange('post', e.target.value)}
                      placeholder="展開の読み、予想の精度、反省点などを振り返り..."
                      className="w-full min-h-[100px] p-3 text-sm border rounded-md resize-y bg-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                    />
                  </div>
                ) : (
                  <div className="pt-2 border-t">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setShowPostMemo(true)}
                      className="w-full"
                    >
                      <Plus className="h-4 w-4 mr-2" />
                      振り返りメモを追加
                    </Button>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </CollapsibleContent>
      </Collapsible>

      {/* 全画面表示モーダル */}
      <Dialog open={isFullscreen} onOpenChange={setIsFullscreen}>
        <DialogContent className="w-[95vw] max-w-[95vw] h-[95vh] max-h-[95vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <StickyNote className="h-5 w-5" />
              予想メモ - {raceName}
            </DialogTitle>
          </DialogHeader>
          <div className="flex-1 overflow-y-auto space-y-6 py-4">
            {/* 予想前メモ */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium">
                  予想メモ（レース前）
                </label>
                {preUpdated && (
                  <span className="text-xs text-muted-foreground">
                    最終保存: {formatTime(preUpdated)}
                  </span>
                )}
              </div>
              <textarea
                value={preText}
                onChange={(e) => handleTextChange('pre', e.target.value)}
                placeholder="予想の根拠、気になるポイントなどをメモ..."
                className="w-full flex-1 min-h-[300px] p-4 text-sm border rounded-md resize-none bg-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                style={{ height: showResults ? '35vh' : '70vh' }}
              />
            </div>

            {/* 振り返りメモ */}
            {showResults && (
              <div className="space-y-2 pt-4 border-t">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium">
                    振り返りメモ（レース後）
                  </label>
                  {postUpdated && (
                    <span className="text-xs text-muted-foreground">
                      最終保存: {formatTime(postUpdated)}
                    </span>
                  )}
                </div>
                <textarea
                  value={postText}
                  onChange={(e) => handleTextChange('post', e.target.value)}
                  placeholder="展開の読み、予想の精度、反省点などを振り返り..."
                  className="w-full min-h-[300px] p-4 text-sm border rounded-md resize-none bg-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                  style={{ height: '35vh' }}
                />
              </div>
            )}
          </div>

          {/* ステータス表示 */}
          <div className="flex items-center justify-end gap-2 pt-2 border-t">
            {saving && (
              <span className="text-sm text-muted-foreground flex items-center">
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
                保存中...
              </span>
            )}
            {saveSuccess && (
              <span className="text-sm text-green-600 flex items-center">
                <Check className="h-4 w-4 mr-2" />
                保存しました
              </span>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
