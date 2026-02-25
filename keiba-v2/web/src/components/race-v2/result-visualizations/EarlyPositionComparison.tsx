'use client';

/**
 * 序盤位置取り比較（予想vs実際）
 * 展開予想と実際の1コーナー通過順位を比較表示
 * 内外は枠番と4角位置から推定
 * スタートメモ機能付き
 */

import React, { useState, useEffect, useCallback } from 'react';
import { HorseEntry, TenkaiData, toCircleNumber, getWakuColor, parseFinishPosition } from '@/types/race-data';
import { ChevronDown, ChevronUp, GitCompare, CheckCircle2, XCircle, Edit2, Check, X } from 'lucide-react';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

// スタートメモのプリセット
const START_MEMO_PRESETS = [
  '押してハナ',
  'スタート◎',
  'スタート〇',
  'スタート△',
  '二の足で先団',
  '出遅れ',
  'ダッシュ◎',
  'ダッシュ〇',
  'ダッシュ△',
] as const;

interface EarlyPositionComparisonProps {
  entries: HorseEntry[];
  tenkaiData: TenkaiData | null;
  defaultOpen?: boolean;
  raceId?: string;
  raceDate?: string;
  raceName?: string;
}

interface StartMemoEntry {
  horseNumber: number;
  horseName: string;
  memo: string;
  updatedAt: string;
}

interface HorsePositionData {
  horseNumber: number;
  horseName: string;
  jockeyName: string;
  waku: number;
  firstCornerPos: number; // 1コーナー通過順
  lastCornerPos: number;  // 4角位置
  finishPos: number;      // 着順
  first3f: string;        // 前3Fタイム
  passingOrdersFormatted: string; // 通過順（ハイフン区切り）
  predictedPosition: '逃げ' | '好位' | '中位' | '後方' | null; // 予想での位置
  actualGroup: '逃げ' | '好位' | '中位' | '後方'; // 実際の位置グループ
  innerOuter: '内' | '中' | '外'; // 内外推定
  isSlowStart: boolean; // 出遅れフラグ
}

// 丸数字を数値に変換するマップ
const circleNumMap: Record<string, number> = {
  '①': 1, '②': 2, '③': 3, '④': 4, '⑤': 5,
  '⑥': 6, '⑦': 7, '⑧': 8, '⑨': 9, '⑩': 10,
  '⑪': 11, '⑫': 12, '⑬': 13, '⑭': 14, '⑮': 15,
  '⑯': 16, '⑰': 17, '⑱': 18, '⑲': 19, '⑳': 20,
};

/**
 * 通過順位文字列をパースして数値配列に変換
 * @param raw - 通過順位の生文字列 (例: "5555", "⑫1213", "3-2-3-1")
 * @param totalHorses - 出走頭数（2桁判定に使用）
 * @returns 通過順位の数値配列
 */
function parsePassingOrders(raw: string, totalHorses: number): number[] {
  if (!raw) return [];
  
  // ハイフン区切りの場合
  if (raw.includes('-')) {
    return raw.split('-').map(p => parseInt(p.trim())).filter(n => !isNaN(n) && n > 0);
  }
  
  const positions: number[] = [];
  let remaining = raw;
  
  // 頭数が10頭以上の場合、2桁数字を考慮
  const hasTwoDigitNumbers = totalHorses >= 10;
  
  while (remaining.length > 0) {
    let matched = false;
    
    // まず丸数字をチェック
    for (const [circle, num] of Object.entries(circleNumMap)) {
      if (remaining.startsWith(circle)) {
        positions.push(num);
        remaining = remaining.slice(circle.length);
        matched = true;
        break;
      }
    }
    
    if (matched) continue;
    
    // 2桁数字をチェック（10頭以上のレースの場合）
    if (hasTwoDigitNumbers && remaining.length >= 2) {
      const twoDigit = remaining.slice(0, 2);
      const twoDigitNum = parseInt(twoDigit);
      // 10-18（または頭数まで）の範囲なら2桁として解釈
      if (!isNaN(twoDigitNum) && twoDigitNum >= 10 && twoDigitNum <= Math.max(totalHorses, 18)) {
        positions.push(twoDigitNum);
        remaining = remaining.slice(2);
        continue;
      }
    }
    
    // 1桁数字をチェック
    const oneDigit = remaining.slice(0, 1);
    const oneDigitNum = parseInt(oneDigit);
    if (!isNaN(oneDigitNum) && oneDigitNum > 0) {
      positions.push(oneDigitNum);
      remaining = remaining.slice(1);
      continue;
    }
    
    // マッチしない文字はスキップ
    remaining = remaining.slice(1);
  }
  
  return positions;
}

export default function EarlyPositionComparison({ 
  entries, 
  tenkaiData,
  defaultOpen = true,
  raceId,
  raceDate,
  raceName,
}: EarlyPositionComparisonProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const [startMemos, setStartMemos] = useState<Map<number, string>>(new Map());
  const [editingHorse, setEditingHorse] = useState<number | null>(null);
  const [editValue, setEditValue] = useState('');
  const [isCustomInput, setIsCustomInput] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // スタートメモを取得
  useEffect(() => {
    if (!raceId) return;
    
    fetch(`/api/start-memo?raceId=${encodeURIComponent(raceId)}`)
      .then(res => res.json())
      .then(data => {
        if (data.memos?.entries) {
          const memoMap = new Map<number, string>();
          data.memos.entries.forEach((entry: StartMemoEntry) => {
            memoMap.set(entry.horseNumber, entry.memo);
          });
          setStartMemos(memoMap);
        }
      })
      .catch(err => console.error('Failed to load start memos:', err));
  }, [raceId]);

  // スタートメモを保存
  const saveStartMemo = useCallback(async (horseNumber: number, horseName: string, memo: string) => {
    if (!raceId) return;
    
    setIsSaving(true);
    try {
      const res = await fetch('/api/start-memo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          raceId,
          raceDate,
          raceName,
          horseNumber,
          horseName,
          memo,
        }),
      });
      
      if (res.ok) {
        setStartMemos(prev => {
          const newMap = new Map(prev);
          if (memo) {
            newMap.set(horseNumber, memo);
          } else {
            newMap.delete(horseNumber);
          }
          return newMap;
        });
      }
    } catch (err) {
      console.error('Failed to save start memo:', err);
    } finally {
      setIsSaving(false);
      setEditingHorse(null);
      setEditValue('');
      setIsCustomInput(false);
    }
  }, [raceId, raceDate, raceName]);

  // 編集開始
  const startEdit = (horseNumber: number, currentMemo: string) => {
    setEditingHorse(horseNumber);
    setEditValue(currentMemo);
    setIsCustomInput(!START_MEMO_PRESETS.includes(currentMemo as typeof START_MEMO_PRESETS[number]) && currentMemo !== '');
  };

  // 編集キャンセル
  const cancelEdit = () => {
    setEditingHorse(null);
    setEditValue('');
    setIsCustomInput(false);
  };

  // 展開予想データから馬番→位置のマップを作成
  const predictedPositionMap = new Map<number, '逃げ' | '好位' | '中位' | '後方'>();
  if (tenkaiData?.positions) {
    for (const num of (tenkaiData.positions.逃げ || [])) {
      predictedPositionMap.set(parseInt(num), '逃げ');
    }
    for (const num of (tenkaiData.positions.好位 || [])) {
      predictedPositionMap.set(parseInt(num), '好位');
    }
    for (const num of (tenkaiData.positions.中位 || [])) {
      predictedPositionMap.set(parseInt(num), '中位');
    }
    for (const num of (tenkaiData.positions.後方 || [])) {
      predictedPositionMap.set(parseInt(num), '後方');
    }
  }

  // 馬のデータを抽出
  const horseData: HorsePositionData[] = entries
    .filter(e => e.result?.finish_position)
    .map(e => {
      // 通過順位を解析
      const passingOrdersRaw = e.result?.passing_orders || '';
      const positions = parsePassingOrders(passingOrdersRaw, entries.length);
      const firstCornerPos = positions[0] || parseFinishPosition(e.result?.finish_position || '99');
      
      const finishPos = parseFinishPosition(e.result?.finish_position || '99');
      const waku = parseInt(e.entry_data.waku) || 1;
      
      // last_corner_position はテキスト形式（"最内", "内", "中", "外"）の場合がある
      const cornerPosRaw = e.result?.last_corner_position || '';
      let innerOuter: '内' | '中' | '外' = '中';
      
      // テキスト形式の場合
      if (cornerPosRaw.includes('最内') || cornerPosRaw.includes('内')) {
        innerOuter = '内';
      } else if (cornerPosRaw.includes('外')) {
        innerOuter = '外';
      } else if (cornerPosRaw.includes('中')) {
        innerOuter = '中';
      } else {
        // 数値の場合または不明な場合は枠番から推定
        if (waku <= 2) {
          innerOuter = '内';
        } else if (waku >= 7) {
          innerOuter = '外';
        }
      }

      // 通過順をハイフン区切りでフォーマット
      const passingOrdersFormatted = positions.length > 0 ? positions.join('-') : '-';

      return {
        horseNumber: e.horse_number,
        horseName: e.horse_name,
        jockeyName: e.entry_data?.jockey ?? '',
        waku,
        firstCornerPos,
        lastCornerPos: positions[positions.length - 1] || firstCornerPos,
        finishPos,
        first3f: e.result?.first_3f || '-',
        passingOrdersFormatted,
        predictedPosition: predictedPositionMap.get(e.horse_number) || null,
        actualGroup: getPositionGroup(firstCornerPos, entries.length),
        innerOuter,
        isSlowStart: e.is_slow_start || false,
      };
    })
    // ソート: 内外順（内→中→外）を第一キー、馬番を第二キー
    .sort((a, b) => {
      const innerOuterOrder = { '内': 0, '中': 1, '外': 2 };
      const orderA = innerOuterOrder[a.innerOuter];
      const orderB = innerOuterOrder[b.innerOuter];
      if (orderA !== orderB) return orderA - orderB;
      return a.horseNumber - b.horseNumber;
    });

  if (horseData.length === 0) {
    return null;
  }

  // 位置グループ別にグループ化
  const actualGroups = {
    逃げ: horseData.filter(d => d.actualGroup === '逃げ'),
    好位: horseData.filter(d => d.actualGroup === '好位'),
    中位: horseData.filter(d => d.actualGroup === '中位'),
    後方: horseData.filter(d => d.actualGroup === '後方'),
  };

  // 予想との一致率を計算
  const matchCount = horseData.filter(d => d.predictedPosition === d.actualGroup).length;
  const totalPredicted = horseData.filter(d => d.predictedPosition).length;
  const matchRate = totalPredicted > 0 ? Math.round((matchCount / totalPredicted) * 100) : 0;

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <div className="border rounded-lg">
        <CollapsibleTrigger asChild>
          <Button
            variant="ghost"
            className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-gray-800"
          >
            <span className="text-lg font-semibold flex items-center gap-2">
              <GitCompare className="w-5 h-5 text-purple-500" />
              序盤位置取り比較
              <span className="text-sm font-normal text-gray-500">
                (予想vs実際)
              </span>
            </span>
            {isOpen ? (
              <ChevronUp className="w-5 h-5" />
            ) : (
              <ChevronDown className="w-5 h-5" />
            )}
          </Button>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <div className="p-4 space-y-4">
            {/* 予想一致率 */}
            {totalPredicted > 0 && (
              <div className="flex items-center gap-4 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-600 dark:text-gray-400">予想的中率:</span>
                  <span className={`text-lg font-bold ${
                    matchRate >= 70 ? 'text-green-600' : 
                    matchRate >= 50 ? 'text-yellow-600' : 'text-red-600'
                  }`}>
                    {matchRate}%
                  </span>
                  <span className="text-xs text-gray-500">
                    ({matchCount}/{totalPredicted})
                  </span>
                </div>
              </div>
            )}

            {/* 並列比較表示 */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* 予想隊列 */}
              {tenkaiData?.positions && (
                <div className="border rounded-lg p-3">
                  <div className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-3 flex items-center gap-2">
                    📊 予想隊列
                  </div>
                  <PositionDiagram 
                    groups={{
                      逃げ: (tenkaiData.positions.逃げ || []).map(n => horseData.find(h => h.horseNumber === parseInt(n))),
                      好位: (tenkaiData.positions.好位 || []).map(n => horseData.find(h => h.horseNumber === parseInt(n))),
                      中位: (tenkaiData.positions.中位 || []).map(n => horseData.find(h => h.horseNumber === parseInt(n))),
                      後方: (tenkaiData.positions.後方 || []).map(n => horseData.find(h => h.horseNumber === parseInt(n))),
                    }}
                    showInnerOuter={false}
                    type="predicted"
                  />
                </div>
              )}

              {/* 実際の1コーナー隊列 */}
              <div className="border rounded-lg p-3">
                <div className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-3 flex items-center gap-2">
                  🏁 実際の1コーナー通過
                </div>
                <PositionDiagram 
                  groups={actualGroups}
                  showInnerOuter={true}
                  type="actual"
                />
              </div>
            </div>

            {/* 詳細テーブル */}
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-gray-50 dark:bg-gray-800">
                    <th className="px-2 py-2 text-center w-8">枠</th>
                    <th className="px-2 py-2 text-center w-10">馬番</th>
                    <th className="px-2 py-2 text-left">馬名</th>
                    <th className="px-2 py-2 text-center w-10">内外</th>
                    <th className="px-2 py-2 text-center w-16">予想</th>
                    <th className="px-2 py-2 text-center w-8"></th>
                    <th className="px-2 py-2 text-center w-16">実際</th>
                    <th className="px-2 py-2 text-center w-12">1C順</th>
                    <th className="px-2 py-2 text-center w-20">通過順</th>
                    <th className="px-2 py-2 text-center w-14">前3F</th>
                    <th className="px-2 py-2 text-center w-10">着順</th>
                    <th className="px-2 py-2 text-left w-14">騎手</th>
                    <th className="px-2 py-2 text-center min-w-28">スタートメモ</th>
                  </tr>
                </thead>
                <tbody>
                  {horseData.map((horse) => {
                    const isMatch = horse.predictedPosition === horse.actualGroup;
                    return (
                      <tr 
                        key={horse.horseNumber}
                        className="border-b hover:bg-gray-50 dark:hover:bg-gray-800/50"
                      >
                        {/* 枠番（色付き） */}
                        <td className="px-2 py-2 text-center">
                          <span 
                            className={`inline-flex items-center justify-center w-6 h-6 rounded text-xs font-bold ${getWakuColor(horse.waku)}`}
                          >
                            {horse.waku}
                          </span>
                        </td>

                        {/* 馬番 */}
                        <td className="px-2 py-2 text-center font-bold">
                          {horse.horseNumber}
                        </td>

                        {/* 馬名（短縮表示） */}
                        <td className="px-1 py-2 font-medium text-xs max-w-20" title={horse.horseName}>
                          <span className="flex items-center gap-0.5">
                            <span className="truncate">{horse.horseName.slice(0, 5)}</span>
                            {horse.isSlowStart && (
                              <span className="inline-flex items-center justify-center w-3.5 h-3.5 rounded-sm bg-red-100 dark:bg-red-900/40 text-red-600 dark:text-red-400 text-[9px] font-bold shrink-0" title="出遅れ">
                                遅
                              </span>
                            )}
                          </span>
                        </td>

                        {/* 内外 */}
                        <td className="px-2 py-2 text-center">
                          <InnerOuterBadge position={horse.innerOuter} />
                        </td>

                        {/* 予想位置 */}
                        <td className="px-2 py-2 text-center">
                          {horse.predictedPosition ? (
                            <PositionBadge position={horse.predictedPosition} />
                          ) : (
                            <span className="text-gray-400">-</span>
                          )}
                        </td>

                        {/* 矢印 + 一致判定 */}
                        <td className="px-2 py-2 text-center">
                          {horse.predictedPosition && (
                            isMatch ? (
                              <CheckCircle2 className="w-4 h-4 text-green-500 mx-auto" />
                            ) : (
                              <XCircle className="w-4 h-4 text-red-400 mx-auto" />
                            )
                          )}
                        </td>

                        {/* 実際位置 */}
                        <td className="px-2 py-2 text-center">
                          <PositionBadge position={horse.actualGroup} />
                        </td>

                        {/* 1コーナー順位 */}
                        <td className="px-2 py-2 text-center font-mono text-gray-600 dark:text-gray-400">
                          {horse.firstCornerPos}
                        </td>

                        {/* 通過順 */}
                        <td className="px-2 py-2 text-center font-mono text-xs text-gray-600 dark:text-gray-400">
                          {horse.passingOrdersFormatted}
                        </td>

                        {/* 前3F */}
                        <td className="px-2 py-2 text-center font-mono text-gray-600 dark:text-gray-400">
                          {horse.first3f}
                        </td>

                        {/* 着順 */}
                        <td className="px-2 py-2 text-center">
                          <span className={`${horse.finishPos <= 3 ? 'font-bold text-yellow-600' : 'text-gray-500'}`}>
                            {horse.finishPos}着
                          </span>
                        </td>

                        {/* 騎手 */}
                        <td className="px-1 py-2 text-gray-600 dark:text-gray-400 truncate max-w-14 text-xs">
                          {horse.jockeyName || '-'}
                        </td>

                        {/* スタートメモ */}
                        <td className="px-1 py-1 text-center">
                          {editingHorse === horse.horseNumber ? (
                            <div className="flex items-center gap-1">
                              {isCustomInput ? (
                                <Input
                                  value={editValue}
                                  onChange={(e) => setEditValue(e.target.value)}
                                  className="h-6 w-20 text-xs"
                                  placeholder="自由入力"
                                  autoFocus
                                />
                              ) : (
                                <Select
                                  value={editValue}
                                  onValueChange={(val) => {
                                    if (val === '__custom__') {
                                      setIsCustomInput(true);
                                      setEditValue('');
                                    } else if (val === '__clear__') {
                                      saveStartMemo(horse.horseNumber, horse.horseName, '');
                                    } else {
                                      setEditValue(val);
                                    }
                                  }}
                                >
                                  <SelectTrigger className="h-6 w-24 text-xs">
                                    <SelectValue placeholder="選択" />
                                  </SelectTrigger>
                                  <SelectContent>
                                    {START_MEMO_PRESETS.map((preset) => (
                                      <SelectItem key={preset} value={preset} className="text-xs">
                                        {preset}
                                      </SelectItem>
                                    ))}
                                    <SelectItem value="__custom__" className="text-xs text-blue-600">
                                      自由入力...
                                    </SelectItem>
                                    {startMemos.get(horse.horseNumber) && (
                                      <SelectItem value="__clear__" className="text-xs text-red-600">
                                        クリア
                                      </SelectItem>
                                    )}
                                  </SelectContent>
                                </Select>
                              )}
                              <Button
                                size="sm"
                                variant="ghost"
                                className="h-5 w-5 p-0"
                                onClick={() => saveStartMemo(horse.horseNumber, horse.horseName, editValue)}
                                disabled={isSaving}
                              >
                                <Check className="h-3 w-3 text-green-600" />
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                className="h-5 w-5 p-0"
                                onClick={cancelEdit}
                              >
                                <X className="h-3 w-3 text-red-500" />
                              </Button>
                            </div>
                          ) : (
                            <div 
                              className="flex items-center justify-center gap-1 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800 rounded px-1 py-0.5"
                              onClick={() => raceId && startEdit(horse.horseNumber, startMemos.get(horse.horseNumber) || '')}
                            >
                              {startMemos.get(horse.horseNumber) ? (
                                <span className="text-xs font-medium text-blue-600 dark:text-blue-400">
                                  {startMemos.get(horse.horseNumber)}
                                </span>
                              ) : (
                                <span className="text-xs text-gray-400">
                                  {raceId ? '-' : '(N/A)'}
                                </span>
                              )}
                              {raceId && (
                                <Edit2 className="h-3 w-3 text-gray-400 hover:text-gray-600" />
                              )}
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* 凡例 */}
            <div className="text-xs text-gray-500 pt-2 border-t">
              <p>※ 内外は枠番と4角位置から推定。1コーナー通過順位は通過順データの最初の値を使用。</p>
            </div>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}

// 位置グループを決定
function getPositionGroup(pos: number, totalHorses: number): '逃げ' | '好位' | '中位' | '後方' {
  const ratio = pos / totalHorses;
  if (pos <= 2) return '逃げ';
  if (ratio <= 0.35) return '好位';
  if (ratio <= 0.65) return '中位';
  return '後方';
}

// 位置グループバッジ
function PositionBadge({ position }: { position: '逃げ' | '好位' | '中位' | '後方' }) {
  const styles: Record<string, string> = {
    逃げ: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    好位: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
    中位: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
    後方: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
  };
  
  return (
    <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${styles[position]}`}>
      {position}
    </span>
  );
}

// 内外バッジ
function InnerOuterBadge({ position }: { position: '内' | '中' | '外' }) {
  const styles: Record<string, string> = {
    内: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    中: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400',
    外: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
  };
  
  return (
    <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${styles[position]}`}>
      {position}
    </span>
  );
}

// 隊列図
interface PositionDiagramProps {
  groups: {
    逃げ: (HorsePositionData | undefined)[];
    好位: (HorsePositionData | undefined)[];
    中位: (HorsePositionData | undefined)[];
    後方: (HorsePositionData | undefined)[];
  };
  showInnerOuter: boolean;
  type: 'predicted' | 'actual';
}

function PositionDiagram({ groups, showInnerOuter, type }: PositionDiagramProps) {
  const groupColors = {
    逃げ: 'text-red-600',
    好位: 'text-orange-600',
    中位: 'text-blue-600',
    後方: 'text-gray-600',
  };

  const groupBgColors = {
    逃げ: 'bg-red-50 dark:bg-red-900/10 border-red-200 dark:border-red-800',
    好位: 'bg-orange-50 dark:bg-orange-900/10 border-orange-200 dark:border-orange-800',
    中位: 'bg-blue-50 dark:bg-blue-900/10 border-blue-200 dark:border-blue-800',
    後方: 'bg-gray-50 dark:bg-gray-800/50 border-gray-200 dark:border-gray-700',
  };

  return (
    <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3">
      {/* ゴール方向 */}
      <div className="text-center text-[10px] text-gray-400 mb-2">
        ← ゴール
      </div>
      
      {/* 隊列 */}
      <div className="flex items-start gap-2 justify-center overflow-x-auto pb-2">
        {(['逃げ', '好位', '中位', '後方'] as const).map((groupName) => {
          const horses = groups[groupName].filter(Boolean) as HorsePositionData[];
          if (horses.length === 0) return null;
          
          return (
            <div key={groupName} className={`text-center min-w-16 border rounded p-2 ${groupBgColors[groupName]}`}>
              <div className={`text-[10px] font-medium mb-1 ${groupColors[groupName]}`}>
                {groupName}
              </div>
              <div className="flex flex-col gap-1">
                {horses.map(horse => (
                  <HorseMarkerWithInnerOuter 
                    key={horse.horseNumber} 
                    horse={horse} 
                    showInnerOuter={showInnerOuter}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>
      
      {/* スタート方向 */}
      <div className="text-center text-[10px] text-gray-400 mt-2">
        スタート →
      </div>
    </div>
  );
}

// 馬マーカー（内外表示付き）
function HorseMarkerWithInnerOuter({
  horse,
  showInnerOuter
}: {
  horse: HorsePositionData;
  showInnerOuter: boolean;
}) {
  const circleNum = toCircleNumber(horse.horseNumber);

  return (
    <div
      className={cn(
        "inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-xs",
        horse.isSlowStart
          ? "bg-red-50 dark:bg-red-900/20 border-red-300 dark:border-red-700"
          : "bg-white dark:bg-gray-900"
      )}
      title={`${horse.horseName} (${horse.waku}枠)${horse.isSlowStart ? ' 出遅れ' : ''}`}
    >
      <span className="font-bold">{circleNum}</span>
      <span className={cn(
        "truncate max-w-12 text-[10px]",
        horse.isSlowStart ? "text-red-600 dark:text-red-400" : "text-gray-500"
      )}>
        {horse.horseName.slice(0, 4)}
      </span>
      {horse.isSlowStart && (
        <span className="text-[9px] px-0.5 rounded bg-red-200 dark:bg-red-800 text-red-700 dark:text-red-300 font-bold">
          遅
        </span>
      )}
      {showInnerOuter && (
        <span className={`text-[9px] px-1 rounded ${
          horse.innerOuter === '内' ? 'bg-green-200 text-green-700' :
          horse.innerOuter === '外' ? 'bg-purple-200 text-purple-700' :
          'bg-gray-200 text-gray-600'
        }`}>
          {horse.innerOuter}
        </span>
      )}
    </div>
  );
}
