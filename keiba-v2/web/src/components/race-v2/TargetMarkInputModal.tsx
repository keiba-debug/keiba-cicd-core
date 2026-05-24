'use client';

/**
 * TARGET馬印入力モーダル
 * 
 * レース詳細画面から呼び出し、TARGETの馬印を編集・保存
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
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

/** モーダル内部で実際に必要な最小限のフィールドのみ要求 */
export type TargetMarkEntry = {
  horse_number: number;
  horse_name: string;
  entry_data: { waku?: number | string | null };
};

// 印の定義
// '消' は内部値も '消' (文字列) で扱う。
// 物理層 (TARGET DAT) には書かず、my_marks_v2/{raceId}.json の explicit_erase に保存する。
// markSet=1 + raceId 指定時のみ表示される。
const MARK_OPTIONS_BASE = [
  { value: '◎', label: '◎', color: 'bg-red-500 hover:bg-red-600 text-white' },
  { value: '○', label: '○', color: 'bg-blue-500 hover:bg-blue-600 text-white' },
  { value: '▲', label: '▲', color: 'bg-yellow-500 hover:bg-yellow-600 text-white' },
  { value: '△', label: '△', color: 'bg-gray-400 hover:bg-gray-500 text-white' },
  { value: 'Ⅲ', label: 'Ⅲ', color: 'bg-purple-500 hover:bg-purple-600 text-white' },
  { value: '穴', label: '穴', color: 'bg-pink-500 hover:bg-pink-600 text-white' },
  { value: '', label: '無', color: 'bg-gray-100 hover:bg-gray-200 text-gray-500' },
] as const;
const ERASE_OPTION = {
  value: '消',
  label: '消',
  color: 'bg-gray-300 hover:bg-gray-400 text-gray-800 line-through',
} as const;

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
  /** 出走馬リスト（最小限: horse_number, horse_name, entry_data.waku のみ参照） */
  entries: TargetMarkEntry[];
  /**
   * 16桁 raceId (YYYYMMDDJJKKNNRR)。
   * 指定時のみ markSet=1 で '消' ボタンが有効化される (my_marks_v2 への保存)。
   */
  raceId?: string;
  /** モーダルを開くトリガー */
  trigger?: React.ReactNode;
  /** 保存後のコールバック（保存されたmarkSetとmarksを受け取る） */
  onSaved?: (data: TargetMarksSavedData) => void;
}

export function TargetMarkInputModal({
  raceInfo,
  entries,
  raceId,
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
  const [saveError, setSaveError] = useState<string | null>(null);

  // markSet=1 + raceId 指定時のみ「消」ボタンが有効になる (v2 ファイル経由)
  const eraseEnabled = markSet === 1 && !!raceId && /^\d{16}$/.test(raceId);
  const markOptions = useMemo(
    () => (eraseEnabled ? [...MARK_OPTIONS_BASE, ERASE_OPTION] : MARK_OPTIONS_BASE),
    [eraseEnabled]
  );

  // 印データを取得 (markSet=1 + raceId 指定時は v2 explicit_erase も合成)
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

      const fetches: Promise<Response>[] = [fetch(`/api/target-marks?${params}`)];
      if (eraseEnabled && raceId) {
        fetches.push(fetch(`/api/my-marks-v2/${raceId}`));
      }

      const [datRes, v2Res] = await Promise.all(fetches);

      let merged: Record<number, string> = {};
      if (datRes.ok) {
        const datJson = await datRes.json();
        merged = { ...(datJson.data.horseMarks || {}) };
      }
      if (v2Res && v2Res.ok) {
        const v2Json = await v2Res.json();
        const explicitErase: number[] = Array.isArray(v2Json?.data?.explicit_erase)
          ? v2Json.data.explicit_erase
          : [];
        for (const uma of explicitErase) {
          merged[uma] = '消';
        }
      }

      setMarks(merged);
      setOriginalMarks(merged);
    } catch (error) {
      console.error('Failed to fetch marks:', error);
    } finally {
      setLoading(false);
    }
  }, [raceInfo, markSet, eraseEnabled, raceId]);

  // モーダルを開いた時にデータ取得
  useEffect(() => {
    if (open) {
      fetchMarks();
      setSaved(false);
      setSaveError(null);
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
    setSaveError(null);
  };

  // 保存
  // markSet=1 + raceId 指定時:
  //  - '消' の馬番は v2 API (PUT /api/my-marks-v2/{raceId}) に explicit_erase として送る
  //  - DAT には '消' の馬番に '' (空文字) を書いて元印を取り除く
  //  - DAT には '◎○▲△Ⅲ穴' をそのまま書く
  // それ以外 (markSet >= 2 or raceId 無し):
  //  - 従来通り DAT への PUT のみ
  const putDatMarks = async (marksToWrite: Record<number, string>) => {
    return fetch('/api/target-marks', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        year: parseInt(raceInfo.year, 10),
        kai: raceInfo.kai,
        nichi: raceInfo.nichi,
        raceNumber: raceInfo.raceNumber,
        venue: raceInfo.venue,
        marks: marksToWrite,
        markSet,
      }),
    });
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveError(null);
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

      // DAT に書き込む印 — '消' は空文字に変換 (DAT 上では未入力扱い)
      const datMarks: Record<number, string> = {};
      for (const [horseNum, mark] of Object.entries(changedMarks)) {
        datMarks[parseInt(horseNum, 10)] = mark === '消' ? '' : mark;
      }

      // DAT 書き込み
      const datRes = await putDatMarks(datMarks);

      if (!datRes.ok) {
        const errText = await datRes.text();
        console.error('DAT write failed', errText);
        setSaveError(`TARGET DAT 保存に失敗: ${errText}`);
        return;
      }
      const datJson = await datRes.json();
      const updatedMarks: Record<number, string> = datJson.data.horseMarks || {};

      // v2 への書き込み (markSet=1 + raceId 指定時のみ)
      if (eraseEnabled && raceId) {
        const explicitErase = Object.entries(marks)
          .filter(([, m]) => m === '消')
          .map(([n]) => parseInt(n, 10))
          .filter((n) => Number.isInteger(n));

        let v2Res: Response;
        try {
          v2Res = await fetch(`/api/my-marks-v2/${raceId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ explicit_erase: explicitErase, source: 'manual' }),
          });
        } catch (netErr) {
          console.error('v2 write network error', netErr);
          await rollbackDat(changedMarks);
          return;
        }

        if (v2Res.ok) {
          // 表示用の合成: DAT 反映後の marks に explicit_erase を上書き
          for (const uma of explicitErase) {
            updatedMarks[uma] = '消';
          }
        } else {
          const errText = await v2Res.text();
          console.error('v2 write failed', errText);
          await rollbackDat(changedMarks, errText);
          return;
        }
      }

      setMarks(updatedMarks);
      setOriginalMarks(updatedMarks);
      setSaved(true);
      onSaved?.({ markSet, horseMarks: updatedMarks });
    } catch (error) {
      console.error('Failed to save marks:', error);
      setSaveError(`保存処理で予期しないエラー: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setSaving(false);
    }
  };

  // v2 失敗時の rollback: DAT 上の変更分を originalMarks の値で書き戻す
  // 失敗の不整合 (DAT 反映済 + v2 反映なし) を残さない
  const rollbackDat = async (changedMarks: Record<number, string>, v2ErrText?: string) => {
    const rollbackMarks: Record<number, string> = {};
    for (const horseNum of Object.keys(changedMarks)) {
      const num = parseInt(horseNum, 10);
      // 元印が無ければ空文字を送って消す
      rollbackMarks[num] = originalMarks[num] ?? '';
    }

    try {
      const rbRes = await putDatMarks(rollbackMarks);
      if (rbRes.ok) {
        // 表示も rollback 後の状態に戻す
        setMarks(originalMarks);
        setSaveError(
          `My印v2 保存に失敗したため、TARGET DAT の変更を元に戻しました。${v2ErrText ? ` (詳細: ${v2ErrText})` : ''}`
        );
      } else {
        const rbErr = await rbRes.text();
        console.error('DAT rollback failed', rbErr);
        setSaveError(
          `🚨 My印v2 保存に失敗し、TARGET DAT のロールバックも失敗しました。手動で TARGET 側を確認してください。 (v2: ${v2ErrText ?? 'network'} / rollback: ${rbErr})`
        );
      }
    } catch (rbNetErr) {
      console.error('DAT rollback network error', rbNetErr);
      setSaveError(
        `🚨 My印v2 保存に失敗し、TARGET DAT のロールバックも通信エラーで失敗。手動で TARGET 側を確認してください。`
      );
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
                {[...entries].sort((a, b) => a.horse_number - b.horse_number).map((entry) => {
                  const currentMark = marks[entry.horse_number] || '';
                  const wakuRaw = entry.entry_data.waku;
                  const wakuNum =
                    typeof wakuRaw === 'number'
                      ? wakuRaw
                      : typeof wakuRaw === 'string'
                        ? parseInt(wakuRaw, 10)
                        : null;
                  const wakuColorClass =
                    wakuNum != null && !isNaN(wakuNum) ? getWakuColor(wakuNum) : '';

                  return (
                    <tr
                      key={entry.horse_number}
                      className="border-b hover:bg-muted/30"
                    >
                      <td className={cn("px-2 py-2 text-center font-bold", wakuColorClass)}>
                        {wakuNum != null && !isNaN(wakuNum) ? wakuNum : '-'}
                      </td>
                      <td className="px-2 py-2 text-center font-bold">
                        {entry.horse_number}
                      </td>
                      <td className="px-2 py-2">{entry.horse_name}</td>
                      <td className="px-2 py-2">
                        <div className="flex gap-1 justify-center flex-wrap">
                          {markOptions.map((opt) => (
                            <Button
                              key={opt.value || '__erase__'}
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
        {saveError && (
          <div className="px-3 py-2 mt-2 bg-red-50 border border-red-300 rounded text-sm text-red-700 flex-shrink-0">
            {saveError}
          </div>
        )}
        <div className="flex items-center justify-between pt-4 border-t flex-shrink-0">
          <div className="text-sm text-muted-foreground">
            {hasChanges && !saved && !saveError && (
              <span className="text-orange-500">未保存の変更があります</span>
            )}
            {saved && !saveError && (
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
