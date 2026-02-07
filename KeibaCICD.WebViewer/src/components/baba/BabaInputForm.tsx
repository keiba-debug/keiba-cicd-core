'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Pencil, Loader2, Check, AlertCircle } from 'lucide-react';
import type { VenueBabaSummary } from '@/lib/data/baba-reader';

interface BabaInputFormProps {
  date: string;
  track: string;
  kai?: number;
  nichi?: number;
  babaSummary?: VenueBabaSummary | null;
}

interface BabaFormData {
  cushion: string;
  moistureGTurf: string;
  moistureGDirt: string;
  moisture4Turf: string;
  moisture4Dirt: string;
}

type SaveStatus = 'idle' | 'saving' | 'success' | 'error';

export function BabaInputForm({ date, track, kai, nichi, babaSummary }: BabaInputFormProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [status, setStatus] = useState<SaveStatus>('idle');
  const [errorMessage, setErrorMessage] = useState('');
  const [formData, setFormData] = useState<BabaFormData>({
    cushion: '',
    moistureGTurf: '',
    moistureGDirt: '',
    moisture4Turf: '',
    moisture4Dirt: '',
  });

  // 開催情報がない場合は表示しない
  if (!kai || !nichi) {
    return null;
  }

  const hasData = babaSummary?.hasData ?? false;

  const handleInputChange = (field: keyof BabaFormData, value: string) => {
    // 数値のみ許可（小数点含む）
    if (value !== '' && !/^\d*\.?\d*$/.test(value)) {
      return;
    }
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async () => {
    // 少なくとも1つの値が入力されているか確認
    const hasValue = Object.values(formData).some(v => v !== '');
    if (!hasValue) {
      setErrorMessage('少なくとも1つの値を入力してください');
      setStatus('error');
      return;
    }

    setStatus('saving');
    setErrorMessage('');

    try {
      const body: Record<string, unknown> = {
        date,
        track,
        kai,
        nichi,
      };

      // 入力された値のみ送信
      if (formData.cushion) body.cushion = parseFloat(formData.cushion);
      if (formData.moistureGTurf) body.moistureGTurf = parseFloat(formData.moistureGTurf);
      if (formData.moistureGDirt) body.moistureGDirt = parseFloat(formData.moistureGDirt);
      if (formData.moisture4Turf) body.moisture4Turf = parseFloat(formData.moisture4Turf);
      if (formData.moisture4Dirt) body.moisture4Dirt = parseFloat(formData.moisture4Dirt);

      const response = await fetch('/api/baba/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      const result = await response.json();

      if (result.ok) {
        setStatus('success');
        // 成功後は2秒後に閉じる
        setTimeout(() => {
          setIsOpen(false);
          setStatus('idle');
          // フォームをリセット
          setFormData({
            cushion: '',
            moistureGTurf: '',
            moistureGDirt: '',
            moisture4Turf: '',
            moisture4Dirt: '',
          });
        }, 1500);
      } else {
        setErrorMessage(result.error || '更新に失敗しました');
        setStatus('error');
      }
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : '通信エラー');
      setStatus('error');
    }
  };

  // トリガー: データがある場合はサマリーバッジ、ない場合は「馬場入力」ボタン
  const renderTrigger = () => {
    if (hasData && babaSummary) {
      // 入力済み: データサマリーをバッジ表示（クリックで編集）
      const cushion = babaSummary.turf?.cushion;
      const turfMoisture = babaSummary.turf?.moistureG;
      const dirtMoisture = babaSummary.dirt?.moistureG;

      return (
        <button
          className="inline-flex items-center gap-1.5 px-2 py-1 text-[11px] rounded border border-border/50 bg-muted/50 hover:bg-muted transition-colors cursor-pointer"
          title="クリックして馬場情報を編集"
        >
          {cushion != null && (
            <span className="font-medium text-green-700 dark:text-green-400">
              C{cushion.toFixed(1)}
            </span>
          )}
          {turfMoisture != null && (
            <span className="text-emerald-600 dark:text-emerald-400">
              芝{turfMoisture.toFixed(1)}%
            </span>
          )}
          {dirtMoisture != null && (
            <span className="text-amber-600 dark:text-amber-400">
              ダ{dirtMoisture.toFixed(1)}%
            </span>
          )}
          <Pencil className="h-2.5 w-2.5 text-muted-foreground/60" />
        </button>
      );
    }

    // 未入力: 入力を促すバッジ
    return (
      <button
        className="inline-flex items-center gap-1 px-2 py-1 text-[11px] rounded border border-dashed border-muted-foreground/30 text-muted-foreground hover:border-primary/50 hover:text-primary transition-colors cursor-pointer"
        title="馬場状態を入力"
      >
        馬場入力
      </button>
    );
  };

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        {renderTrigger()}
      </PopoverTrigger>
      <PopoverContent className="w-80" align="end">
        <div className="space-y-4">
          <div className="space-y-1">
            <h4 className="font-medium text-sm">馬場状態入力</h4>
            <p className="text-xs text-muted-foreground">
              {kai}回{track}{nichi}日目
            </p>
          </div>

          <div className="space-y-3">
            {/* クッション値（芝のみ） */}
            <div className="space-y-1.5">
              <Label className="text-xs font-medium">クッション値（芝）</Label>
              <Input
                type="text"
                inputMode="decimal"
                placeholder="例: 9.6"
                value={formData.cushion}
                onChange={(e) => handleInputChange('cushion', e.target.value)}
                className="h-8 text-sm"
              />
            </div>

            {/* 含水率テーブル（JRA公式準拠: 横=ゴール前/4コーナー、縦=芝/ダート） */}
            <div className="space-y-1.5">
              <Label className="text-xs font-medium">含水率</Label>
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr>
                    <th className="w-12"></th>
                    <th className="text-center text-[10px] text-muted-foreground font-medium pb-1">ゴール前 %</th>
                    <th className="text-center text-[10px] text-muted-foreground font-medium pb-1">4コーナー %</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td className="text-[10px] text-muted-foreground font-medium pr-1.5 py-0.5">芝</td>
                    <td className="px-0.5 py-0.5">
                      <Input
                        type="text"
                        inputMode="decimal"
                        placeholder="14.1"
                        value={formData.moistureGTurf}
                        onChange={(e) => handleInputChange('moistureGTurf', e.target.value)}
                        className="h-7 text-sm text-center"
                      />
                    </td>
                    <td className="px-0.5 py-0.5">
                      <Input
                        type="text"
                        inputMode="decimal"
                        placeholder="12.3"
                        value={formData.moisture4Turf}
                        onChange={(e) => handleInputChange('moisture4Turf', e.target.value)}
                        className="h-7 text-sm text-center"
                      />
                    </td>
                  </tr>
                  <tr>
                    <td className="text-[10px] text-muted-foreground font-medium pr-1.5 py-0.5">ダート</td>
                    <td className="px-0.5 py-0.5">
                      <Input
                        type="text"
                        inputMode="decimal"
                        placeholder="1.2"
                        value={formData.moistureGDirt}
                        onChange={(e) => handleInputChange('moistureGDirt', e.target.value)}
                        className="h-7 text-sm text-center"
                      />
                    </td>
                    <td className="px-0.5 py-0.5">
                      <Input
                        type="text"
                        inputMode="decimal"
                        placeholder="1.7"
                        value={formData.moisture4Dirt}
                        onChange={(e) => handleInputChange('moisture4Dirt', e.target.value)}
                        className="h-7 text-sm text-center"
                      />
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* エラーメッセージ */}
          {status === 'error' && errorMessage && (
            <div className="flex items-center gap-1.5 text-xs text-destructive">
              <AlertCircle className="h-3.5 w-3.5" />
              {errorMessage}
            </div>
          )}

          {/* 保存ボタン */}
          <Button
            onClick={handleSubmit}
            disabled={status === 'saving' || status === 'success'}
            className="w-full h-8 text-sm"
          >
            {status === 'saving' && (
              <>
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                保存中...
              </>
            )}
            {status === 'success' && (
              <>
                <Check className="mr-1.5 h-3.5 w-3.5" />
                保存しました
              </>
            )}
            {(status === 'idle' || status === 'error') && 'CSVに保存'}
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
