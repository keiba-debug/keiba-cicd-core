'use client';

/**
 * 馬コメント編集コンポーネント
 * 
 * TARGETのUMA_COMに保存される馬コメントを編集・保存
 */

import React, { useState, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { MessageSquareText, Edit2, Save, X, Loader2 } from 'lucide-react';

interface HorseCommentEditorProps {
  kettoNum: string;        // 10桁のJRA-VAN馬ID
  horseName: string;       // 馬名（表示用）
  initialComment: string;  // 初期コメント
}

export function HorseCommentEditor({ 
  kettoNum, 
  horseName, 
  initialComment 
}: HorseCommentEditorProps) {
  const [comment, setComment] = useState(initialComment);
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState('');

  const handleSave = useCallback(async () => {
    if (!kettoNum || kettoNum.length !== 10) {
      setSaveStatus('error');
      setErrorMessage('馬ID(kettoNum)が無効です');
      return;
    }

    setIsSaving(true);
    setSaveStatus('idle');
    setErrorMessage('');

    try {
      const response = await fetch(`/api/horse-comment/${kettoNum}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ comment }),
      });

      if (response.ok) {
        setSaveStatus('success');
        setIsEditing(false);
        setTimeout(() => setSaveStatus('idle'), 3000);
      } else {
        const data = await response.json();
        setSaveStatus('error');
        setErrorMessage(data.error || '保存に失敗しました');
      }
    } catch (error) {
      setSaveStatus('error');
      setErrorMessage('ネットワークエラーが発生しました');
    } finally {
      setIsSaving(false);
    }
  }, [kettoNum, comment]);

  const handleCancel = useCallback(() => {
    setComment(initialComment);
    setIsEditing(false);
    setSaveStatus('idle');
    setErrorMessage('');
  }, [initialComment]);

  // kettoNumが無効な場合は編集不可として表示
  const isEditable = kettoNum && kettoNum.length === 10;

  return (
    <Card className="border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-950/20">
      <CardHeader className="py-2">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-sm">
            <MessageSquareText className="w-4 h-4 text-amber-600" />
            馬コメント
            {saveStatus === 'success' && (
              <span className="text-xs font-normal text-green-600 ml-2">✓ 保存しました</span>
            )}
          </CardTitle>
          
          {!isEditing && isEditable && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsEditing(true)}
              className="h-7 px-2 text-xs"
            >
              <Edit2 className="w-3 h-3 mr-1" />
              編集
            </Button>
          )}
        </div>
      </CardHeader>
      
      <CardContent className="pt-0 pb-3">
        {isEditing ? (
          <div className="space-y-2">
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder={`${horseName}に関するメモを入力...`}
              className="w-full h-28 px-3 py-2 text-sm border rounded-md bg-white dark:bg-gray-900 focus:outline-none focus:ring-2 focus:ring-amber-500 resize-y"
              autoFocus
            />
            
            <div className="flex items-center gap-2">
              <Button
                onClick={handleSave}
                disabled={isSaving}
                size="sm"
                className="h-7 px-3 text-xs bg-amber-600 hover:bg-amber-700"
              >
                {isSaving ? (
                  <>
                    <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                    保存中...
                  </>
                ) : (
                  <>
                    <Save className="w-3 h-3 mr-1" />
                    保存（TARGET）
                  </>
                )}
              </Button>
              
              <Button
                variant="outline"
                size="sm"
                onClick={handleCancel}
                className="h-7 px-3 text-xs"
                disabled={isSaving}
              >
                <X className="w-3 h-3 mr-1" />
                キャンセル
              </Button>
              
              {saveStatus === 'error' && errorMessage && (
                <span className="text-xs text-red-500">{errorMessage}</span>
              )}
            </div>
          </div>
        ) : (
          <div className="text-sm">
            {comment ? (
              <p className="whitespace-pre-wrap">{comment}</p>
            ) : (
              <p className="text-muted-foreground text-xs">
                {isEditable 
                  ? 'コメントはありません（編集ボタンで追加できます）' 
                  : '馬ID(kettoNum)が取得できないため編集できません'}
              </p>
            )}
          </div>
        )}
        
        {/* デバッグ情報（開発時のみ） */}
        {!isEditable && (
          <p className="text-xs text-muted-foreground mt-2">
            kettoNum: {kettoNum || '未設定'}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
