'use client';

/**
 * TARGET馬印入力モーダル
 * 
 * レース詳細画面から呼び出し、TARGETの馬印を編集・保存
 */

import { useState, useEffect, useCallback } from 'react';
import { X, Save, RefreshCw, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { getWakuColor } from '@/types/race-data';
import { cn } from '@/lib/utils';

// 印の定義
const MARK_OPTIONS = [
  { value: '◎', label: '◎', color: 'bg-red-500 hover:bg-red-600 text-white' },
  { value: '○', label: '○', color: 'bg-blue-500 hover:bg-blue-600 text-white' },
  { value: '▲', label: '▲', color: 'bg-yellow-500 hover:bg-yellow-600 text-white' },
  { value: '△', label: '△', color: 'bg-gray-400 hover:bg-gray-500 text-white' },
  { value: '★', label: '★', color: 'bg-purple-500 hover:bg-purple-600 text-white' },
  { value: '穴', label: '穴', color: 'bg-pink-500 hover:bg-pink-600 text-white' },
  { value: '', label: '消', color: 'bg-gray-200 hover:bg-gray-300 text-gray-700' },
] as const;

interface HorseEntry {
  horse_number: number;
  horse_name: string;
  entry_data: {
    waku?: number;
  };
}

/** 保存後に返されるデータ */
export interface TargetMarksSavedData {
  markSet: number;
  horseMarks: Record<number, string>;
}

interface TargetMarkInputModalProps {
  /** レース情報 */
  raceInfo: {
    venue: string;
    year: string;
    kai: number;
    nichi: number;
    raceNumber: number;
    raceName?: string;
  };
  /** 出走馬リスト */
  entries: HorseEntry[];
  /** モーダルを開くトリガー */
  trigger?: React.ReactNode;
  /** 保存後のコールバック（保存されたmarkSetとmarksを受け取る） */
  onSaved?: (data: TargetMarksSavedData) => void;
}

export function TargetMarkInputModal({
  raceInfo,
  entries,
  trigger,
  onSaved,
}: TargetMarkInputModalProps) {
  const [open, setOpen] = useState(false);
  const [markSet, setMarkSet] = useState(1);
  const [marks, setMarks] = useState<Record<number, string>>({});
  const [originalMarks, setOriginalMarks] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // 印データを取得
  const fetchMarks = useCallback(async () => {
    if (!raceInfo.venue || !raceInfo.kai || !raceInfo.nichi) return;
    
    setLoading(true);
    try {
      const params = new URLSearchParams({
        year: raceInfo.year,
        kai: String(raceInfo.kai),
        nichi: String(raceInfo.nichi),
        raceNumber: String(raceInfo.raceNumber),
        venue: raceInfo.venue,
        markSet: String(markSet),
      });
      
      const res = await fetch(`/api/target-marks?${params}`);
      if (res.ok) {
        const data = await res.json();
        setMarks(data.data.horseMarks || {});
        setOriginalMarks(data.data.horseMarks || {});
      }
    } catch (error) {
      console.error('Failed to fetch marks:', error);
    } finally {
      setLoading(false);
    }
  }, [raceInfo, markSet]);

  // モーダルを開いた時にデータ取得
  useEffect(() => {
    if (open) {
      fetchMarks();
      setSaved(false);
    }
  }, [open, fetchMarks]);

  // 印セット変更時にデータ再取得
  useEffect(() => {
    if (open) {
      fetchMarks();
    }
  }, [markSet, open, fetchMarks]);

  // 印を変更
  const handleMarkChange = (horseNumber: number, mark: string) => {
    setMarks(prev => ({
      ...prev,
      [horseNumber]: mark,
    }));
    setSaved(false);
  };

  // 保存
  const handleSave = async () => {
    setSaving(true);
    try {
      // 変更があった印のみ送信
      const changedMarks: Record<number, string> = {};
      for (const [horseNum, mark] of Object.entries(marks)) {
        const num = parseInt(horseNum, 10);
        if (originalMarks[num] !== mark) {
          changedMarks[num] = mark;
        }
      }
      // 削除された印も含める
      for (const horseNum of Object.keys(originalMarks)) {
        const num = parseInt(horseNum, 10);
        if (!(num in marks) || marks[num] === '') {
          changedMarks[num] = '';
        }
      }

      if (Object.keys(changedMarks).length === 0) {
        setSaved(true);
        return;
      }

      const res = await fetch('/api/target-marks', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          year: parseInt(raceInfo.year, 10),
          kai: raceInfo.kai,
          nichi: raceInfo.nichi,
          raceNumber: raceInfo.raceNumber,
          venue: raceInfo.venue,
          marks: changedMarks,
          markSet,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        const updatedMarks = data.data.horseMarks || {};
        setMarks(updatedMarks);
        setOriginalMarks(updatedMarks);
        setSaved(true);
        onSaved?.({ markSet, horseMarks: updatedMarks });
      }
    } catch (error) {
      console.error('Failed to save marks:', error);
    } finally {
      setSaving(false);
    }
  };

  // 変更があるかチェック
  const hasChanges = JSON.stringify(marks) !== JSON.stringify(originalMarks);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger || (
          <Button variant="outline" size="sm" className="gap-1">
            🎯 印入力
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-hidden flex flex-col">
        <DialogHeader className="flex-shrink-0">
          <DialogTitle className="flex items-center gap-2">
            🎯 TARGET印入力
            <Badge variant="outline" className="ml-2">
              {raceInfo.venue}{raceInfo.raceNumber}R
            </Badge>
            {raceInfo.raceName && (
              <span className="text-sm font-normal text-muted-foreground">
                {raceInfo.raceName}
              </span>
            )}
          </DialogTitle>
        </DialogHeader>

        {/* 印セット選択 */}
        <div className="flex items-center gap-4 py-2 border-b flex-shrink-0">
          <span className="text-sm font-medium">印セット:</span>
          <Select
            value={String(markSet)}
            onValueChange={(v) => setMarkSet(parseInt(v, 10))}
          >
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1">馬印1</SelectItem>
              <SelectItem value="2">馬印2</SelectItem>
              <SelectItem value="3">馬印3</SelectItem>
              <SelectItem value="4">馬印4</SelectItem>
              <SelectItem value="5">馬印5</SelectItem>
              <SelectItem value="6">馬印6</SelectItem>
              <SelectItem value="7">馬印7</SelectItem>
              <SelectItem value="8">馬印8</SelectItem>
            </SelectContent>
          </Select>
          <Button
            variant="ghost"
            size="sm"
            onClick={fetchMarks}
            disabled={loading}
          >
            <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
          </Button>
        </div>

        {/* 馬リスト */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="py-8 text-center text-muted-foreground">
              <RefreshCw className="h-6 w-6 mx-auto animate-spin" />
              <p className="mt-2">読み込み中...</p>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-background border-b">
                <tr>
                  <th className="px-2 py-2 text-center w-10">枠</th>
                  <th className="px-2 py-2 text-center w-12">馬番</th>
                  <th className="px-2 py-2 text-left">馬名</th>
                  <th className="px-2 py-2 text-center">印</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => {
                  const currentMark = marks[entry.horse_number] || '';
                  const wakuColorClass = entry.entry_data.waku
                    ? getWakuColor(entry.entry_data.waku)
                    : '';

                  return (
                    <tr
                      key={entry.horse_number}
                      className="border-b hover:bg-muted/30"
                    >
                      <td className={cn("px-2 py-2 text-center font-bold", wakuColorClass)}>
                        {entry.entry_data.waku || '-'}
                      </td>
                      <td className="px-2 py-2 text-center font-bold">
                        {entry.horse_number}
                      </td>
                      <td className="px-2 py-2">{entry.horse_name}</td>
                      <td className="px-2 py-2">
                        <div className="flex gap-1 justify-center flex-wrap">
                          {MARK_OPTIONS.map((opt) => (
                            <Button
                              key={opt.value}
                              size="sm"
                              variant={currentMark === opt.value ? 'default' : 'outline'}
                              className={cn(
                                "w-8 h-8 p-0 text-sm font-bold",
                                currentMark === opt.value && opt.color
                              )}
                              onClick={() => handleMarkChange(entry.horse_number, opt.value)}
                            >
                              {opt.label}
                            </Button>
                          ))}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* フッター */}
        <div className="flex items-center justify-between pt-4 border-t flex-shrink-0">
          <div className="text-sm text-muted-foreground">
            {hasChanges && !saved && (
              <span className="text-orange-500">未保存の変更があります</span>
            )}
            {saved && (
              <span className="text-green-500 flex items-center gap-1">
                <Check className="h-4 w-4" />
                保存しました
              </span>
            )}
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setOpen(false)}>
              閉じる
            </Button>
            <Button
              onClick={handleSave}
              disabled={saving || !hasChanges}
              className="gap-1"
            >
              {saving ? (
                <>
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  保存中...
                </>
              ) : (
                <>
                  <Save className="h-4 w-4" />
                  TARGETに保存
                </>
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
