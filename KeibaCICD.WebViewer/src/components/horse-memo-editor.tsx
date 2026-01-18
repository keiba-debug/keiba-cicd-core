'use client';

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';

interface HorseMemoEditorProps {
  date: string;
  raceId: string;
  horseNumber: string;
  horseName: string;
}

interface RaceNotes {
  raceMemo?: string;
  horses?: Record<string, string>;
  updatedAt?: string;
}

export function HorseMemoEditor({ date, raceId, horseNumber, horseName }: HorseMemoEditorProps) {
  const [memo, setMemo] = useState('');
  const [originalMemo, setOriginalMemo] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // メモを読み込み
  useEffect(() => {
    const fetchNotes = async () => {
      try {
        const response = await fetch(`/api/notes?date=${date}&raceId=${raceId}`);
        if (response.ok) {
          const notes: RaceNotes = await response.json();
          const horseMemo = notes.horses?.[horseNumber] || '';
          setMemo(horseMemo);
          setOriginalMemo(horseMemo);
        }
      } catch (error) {
        console.error('Failed to fetch horse memo:', error);
      }
    };
    fetchNotes();
  }, [date, raceId, horseNumber]);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const response = await fetch('/api/notes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          date, 
          raceId, 
          horseNumber, 
          horseMemo: memo 
        }),
      });

      if (response.ok) {
        setOriginalMemo(memo);
        setIsEditing(false);
      } else {
        alert('保存に失敗しました');
      }
    } catch (error) {
      console.error('Failed to save horse memo:', error);
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

  // コンパクトな表示（編集ボタンのみ）
  if (!isEditing && !memo) {
    return (
      <Button
        variant="ghost"
        size="sm"
        className="h-6 px-2 text-xs text-muted-foreground hover:text-foreground"
        onClick={() => setIsEditing(true)}
      >
        ＋メモ
      </Button>
    );
  }

  // メモがある場合の表示
  if (!isEditing) {
    return (
      <div className="flex items-start gap-1 group">
        <span className="text-xs text-muted-foreground flex-1 whitespace-pre-wrap">
          📝 {memo}
        </span>
        <Button
          variant="ghost"
          size="sm"
          className="h-5 px-1 text-xs opacity-0 group-hover:opacity-100 transition-opacity"
          onClick={() => setIsEditing(true)}
        >
          ✏️
        </Button>
      </div>
    );
  }

  // 編集モード
  return (
    <div className="flex flex-col gap-1 mt-1">
      <input
        type="text"
        value={memo}
        onChange={(e) => setMemo(e.target.value)}
        placeholder={`${horseName}のメモ...`}
        className="w-full px-2 py-1 text-xs border rounded focus:outline-none focus:ring-1 focus:ring-ring"
        autoFocus
        onKeyDown={(e) => {
          if (e.key === 'Enter' && hasChanges && !isSaving) {
            handleSave();
          } else if (e.key === 'Escape') {
            handleCancel();
          }
        }}
      />
      <div className="flex gap-1 justify-end">
        <Button
          variant="ghost"
          size="sm"
          className="h-5 px-2 text-xs"
          onClick={handleCancel}
          disabled={isSaving}
        >
          キャンセル
        </Button>
        <Button
          size="sm"
          className="h-5 px-2 text-xs"
          onClick={handleSave}
          disabled={isSaving || !hasChanges}
        >
          {isSaving ? '...' : '保存'}
        </Button>
      </div>
    </div>
  );
}
