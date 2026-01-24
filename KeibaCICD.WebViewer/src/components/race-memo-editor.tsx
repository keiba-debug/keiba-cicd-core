'use client';

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Pencil, Save, Loader2, X } from 'lucide-react';

interface RaceMemoEditorProps {
  date: string;
  raceId: string;
}

interface RaceNotes {
  raceMemo?: string;
  horses?: Record<string, string>;
  updatedAt?: string;
}

export function RaceMemoEditor({ date, raceId }: RaceMemoEditorProps) {
  const [memo, setMemo] = useState('');
  const [originalMemo, setOriginalMemo] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState<string | null>(null);

  // メモを読み込み
  useEffect(() => {
    const fetchNotes = async () => {
      try {
        const response = await fetch(`/api/notes?date=${date}&raceId=${raceId}`);
        if (response.ok) {
          const notes: RaceNotes = await response.json();
          setMemo(notes.raceMemo || '');
          setOriginalMemo(notes.raceMemo || '');
          if (notes.updatedAt) {
            setLastSaved(notes.updatedAt);
          }
        }
      } catch (error) {
        console.error('Failed to fetch notes:', error);
      }
    };
    fetchNotes();
  }, [date, raceId]);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const response = await fetch('/api/notes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ date, raceId, raceMemo: memo }),
      });

      if (response.ok) {
        const result = await response.json();
        setOriginalMemo(memo);
        setIsEditing(false);
        if (result.notes?.updatedAt) {
          setLastSaved(result.notes.updatedAt);
        }
      } else {
        alert('保存に失敗しました');
      }
    } catch (error) {
      console.error('Failed to save memo:', error);
      alert('保存に失敗しました');
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    setMemo(originalMemo);
    setIsEditing(false);
  };

  const hasChanges = memo !== originalMemo;

  const formatDate = (isoString: string) => {
    const date = new Date(isoString);
    return date.toLocaleString('ja-JP', {
      month: 'numeric',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="mb-6 p-4 bg-card rounded-lg border">
      {/* セクションヘッダー - 左ボーダースタイル */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-bold border-l-4 border-primary pl-3">
          予想メモ
        </h2>
        <div className="flex items-center gap-2">
          {lastSaved && !isEditing && (
            <span className="text-xs text-muted-foreground">
              保存: {formatDate(lastSaved)}
            </span>
          )}
          {!isEditing ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsEditing(true)}
              className="rounded-lg"
            >
              <Pencil className="w-4 h-4 mr-1" />
              編集
            </Button>
          ) : (
            <div className="flex gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={handleCancel}
                disabled={isSaving}
                className="rounded-lg"
              >
                <X className="w-4 h-4 mr-1" />
                キャンセル
              </Button>
              <Button
                size="sm"
                onClick={handleSave}
                disabled={isSaving || !hasChanges}
                className="rounded-lg bg-primary text-primary-foreground hover:bg-primary/90"
              >
                {isSaving ? (
                  <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                ) : (
                  <Save className="w-4 h-4 mr-1" />
                )}
                保存
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* コンテンツ */}
      {isEditing ? (
        <textarea
          value={memo}
          onChange={(e) => setMemo(e.target.value)}
          placeholder="予想メモを入力..."
          className="w-full min-h-[120px] p-3 border rounded-lg text-sm resize-y focus:outline-none focus:ring-2 focus:ring-ring"
          autoFocus
        />
      ) : (
        <div className="min-h-[40px] text-sm">
          {memo ? (
            <p className="whitespace-pre-wrap">{memo}</p>
          ) : (
            <p className="text-muted-foreground italic">
              メモはありません。「編集」をクリックして追加できます。
            </p>
          )}
        </div>
      )}
    </div>
  );
}
