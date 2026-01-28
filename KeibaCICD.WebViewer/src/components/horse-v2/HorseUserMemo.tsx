'use client';

/**
 * 馬ユーザーメモコンポーネント（v2）
 */

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';

interface HorseUserMemoProps {
  horseId: string;
  horseName: string;
  initialMemo: string;
}

export function HorseUserMemo({ horseId, horseName, initialMemo }: HorseUserMemoProps) {
  const [memo, setMemo] = useState(initialMemo);
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');

  const handleSave = async () => {
    setIsSaving(true);
    setSaveMessage('');

    try {
      const response = await fetch('/api/horse-memo', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          horseId,
          horseName,
          memo,
        }),
      });

      if (response.ok) {
        setSaveMessage('保存しました');
        setIsEditing(false);
      } else {
        setSaveMessage('保存に失敗しました');
      }
    } catch (error) {
      setSaveMessage('エラーが発生しました');
    } finally {
      setIsSaving(false);
      setTimeout(() => setSaveMessage(''), 3000);
    }
  };

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg border p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold">📝 ユーザーメモ</h2>
        {!isEditing && (
          <Button 
            variant="outline" 
            size="sm"
            onClick={() => setIsEditing(true)}
          >
            編集
          </Button>
        )}
      </div>

      {isEditing ? (
        <div className="space-y-3">
          <textarea
            value={memo}
            onChange={(e) => setMemo(e.target.value)}
            placeholder="馬に関するメモを入力..."
            className="w-full h-32 px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-primary resize-y"
          />
          <div className="flex items-center gap-2">
            <Button 
              onClick={handleSave}
              disabled={isSaving}
              size="sm"
            >
              {isSaving ? '保存中...' : '保存'}
            </Button>
            <Button 
              variant="outline"
              size="sm"
              onClick={() => {
                setMemo(initialMemo);
                setIsEditing(false);
              }}
            >
              キャンセル
            </Button>
            {saveMessage && (
              <span className={`text-sm ${
                saveMessage.includes('失敗') || saveMessage.includes('エラー') 
                  ? 'text-red-500' 
                  : 'text-green-500'
              }`}>
                {saveMessage}
              </span>
            )}
          </div>
        </div>
      ) : (
        <div className="text-sm">
          {memo ? (
            <p className="whitespace-pre-wrap">{memo}</p>
          ) : (
            <p className="text-muted-foreground">メモはありません</p>
          )}
        </div>
      )}
    </div>
  );
}
