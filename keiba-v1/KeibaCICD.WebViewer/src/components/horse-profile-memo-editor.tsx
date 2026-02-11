'use client';

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface HorseProfileMemoEditorProps {
  horseId: string;
  horseName: string;
}

export function HorseProfileMemoEditor({ horseId, horseName }: HorseProfileMemoEditorProps) {
  const [memo, setMemo] = useState('');
  const [originalMemo, setOriginalMemo] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  // メモを読み込み
  useEffect(() => {
    const fetchMemo = async () => {
      setIsLoading(true);
      try {
        const response = await fetch(`/api/horse-memo?horseId=${horseId}`);
        if (response.ok) {
          const data = await response.json();
          setMemo(data.memo || '');
          setOriginalMemo(data.memo || '');
        }
      } catch (error) {
        console.error('Failed to fetch horse memo:', error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchMemo();
  }, [horseId]);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const response = await fetch('/api/horse-memo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ horseId, memo }),
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

  if (isLoading) {
    return (
      <Card className="mb-6">
        <CardHeader className="pb-2">
          <CardTitle className="text-lg flex items-center gap-2">
            📝 ユーザーメモ
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">読み込み中...</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="mb-6">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            📝 ユーザーメモ
          </CardTitle>
          <div className="flex items-center gap-2">
            {!isEditing ? (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsEditing(true)}
              >
                編集
              </Button>
            ) : (
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleCancel}
                  disabled={isSaving}
                >
                  キャンセル
                </Button>
                <Button
                  size="sm"
                  onClick={handleSave}
                  disabled={isSaving || !hasChanges}
                  className="bg-lime-400 hover:bg-lime-300 text-black font-bold px-5 shadow-md border-2 border-lime-500"
                >
                  {isSaving ? '⏳ 保存中...' : '💾 保存'}
                </Button>
              </div>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {isEditing ? (
          <textarea
            value={memo}
            onChange={(e) => setMemo(e.target.value)}
            placeholder={`${horseName}についてのメモ...`}
            className="w-full min-h-[150px] p-3 border rounded-md text-sm resize-y focus:outline-none focus:ring-2 focus:ring-ring"
            autoFocus
          />
        ) : (
          <div className="min-h-[60px] text-sm">
            {memo ? (
              <p className="whitespace-pre-wrap">{memo}</p>
            ) : (
              <p className="text-muted-foreground italic">
                メモはありません。「編集」をクリックして追加できます。
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
