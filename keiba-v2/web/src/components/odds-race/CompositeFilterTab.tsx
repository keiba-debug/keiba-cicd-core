'use client';

/**
 * 複合フィルタタブ
 *
 * AND条件のチップフィルタで馬を絞り込む。
 * 旧「フィルタ分析」タブ（4パネル並列）を置き換え。
 */

import { useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { X } from 'lucide-react';
import { getWakuColor } from '@/types/race-data';
import {
  getBuyZoneDisplay,
  getMyMarkColor,
  getMarketSignalDisplay,
  type EnrichedHorse,
} from './buy-zone';

interface CompositeFilterTabProps {
  horses: EnrichedHorse[];
  surgeMap?: Map<string, { level: 'hot' | 'warm' | 'cold' | 'stable' | 'unknown' }>;
  hasMl: boolean;
}

interface FilterState {
  oddsBand: 'any' | 'le2' | '2to5' | '5to10' | '10to30' | 'ge30';
  myMark1: 'any' | '◎' | '○' | '▲' | '△' | '★' | '穴' | 'has' | 'none';
  myMark2: 'any' | '◎' | '○' | '▲' | '△' | '★' | '穴' | 'has';
  mlJudge: 'any' | 'vb' | 'hot' | 'buy_plus' | 'ard55' | 'ard60';
  honshi: 'any' | '◎' | '○' | '▲' | 'has';
  surge: 'any' | 'hot' | 'warm_plus';
  aiTop: 'any' | 'top30' | 'top50';
}

const INITIAL: FilterState = {
  oddsBand: 'any',
  myMark1: 'any',
  myMark2: 'any',
  mlJudge: 'any',
  honshi: 'any',
  surge: 'any',
  aiTop: 'any',
};

function applyFilter(
  horses: EnrichedHorse[],
  state: FilterState,
  surgeMap?: CompositeFilterTabProps['surgeMap']
): EnrichedHorse[] {
  // AI上位判定用: AI指数のソート済み配列
  const aiSorted = horses
    .map((h) => h.aiIndex)
    .filter((v): v is number => v != null)
    .sort((a, b) => b - a);

  return horses.filter((h) => {
    // オッズ帯
    if (state.oddsBand !== 'any') {
      const o = h.winOdds;
      if (o == null) return false;
      if (state.oddsBand === 'le2' && !(o < 2)) return false;
      if (state.oddsBand === '2to5' && !(o >= 2 && o < 5)) return false;
      if (state.oddsBand === '5to10' && !(o >= 5 && o < 10)) return false;
      if (state.oddsBand === '10to30' && !(o >= 10 && o < 30)) return false;
      if (state.oddsBand === 'ge30' && !(o >= 30)) return false;
    }
    // My印1
    if (state.myMark1 !== 'any') {
      if (state.myMark1 === 'has' && !h.myMark1) return false;
      if (state.myMark1 === 'none' && h.myMark1) return false;
      if (state.myMark1 !== 'has' && state.myMark1 !== 'none' && h.myMark1 !== state.myMark1) return false;
    }
    // My印2
    if (state.myMark2 !== 'any') {
      if (state.myMark2 === 'has' && !h.myMark2) return false;
      if (state.myMark2 !== 'has' && h.myMark2 !== state.myMark2) return false;
    }
    // ML判定
    if (state.mlJudge !== 'any') {
      if (state.mlJudge === 'vb' && !h.isVb) return false;
      if (state.mlJudge === 'hot' && h.winZone !== 'hot') return false;
      if (state.mlJudge === 'buy_plus' && !(h.winZone === 'hot' || h.winZone === 'buy')) return false;
      if (state.mlJudge === 'ard55' && (h.arDeviation ?? 0) < 55) return false;
      if (state.mlJudge === 'ard60' && (h.arDeviation ?? 0) < 60) return false;
    }
    // 本紙印
    if (state.honshi !== 'any') {
      if (state.honshi === 'has' && !h.honshiMark) return false;
      if (state.honshi !== 'has' && h.honshiMark !== state.honshi) return false;
    }
    // 急騰
    if (state.surge !== 'any') {
      const s = surgeMap?.get(h.umaban) ?? surgeMap?.get(h.umaban.replace(/^0+/, ''));
      if (state.surge === 'hot' && s?.level !== 'hot') return false;
      if (state.surge === 'warm_plus' && !(s?.level === 'hot' || s?.level === 'warm')) return false;
    }
    // AI上位
    if (state.aiTop !== 'any' && aiSorted.length > 0) {
      if (h.aiIndex == null) return false;
      const cut = state.aiTop === 'top30' ? Math.ceil(aiSorted.length * 0.3) : Math.ceil(aiSorted.length * 0.5);
      const threshold = aiSorted[cut - 1] ?? -Infinity;
      if (h.aiIndex < threshold) return false;
    }
    return true;
  });
}

interface ChipGroupProps<K extends keyof FilterState> {
  label: string;
  field: K;
  state: FilterState;
  setState: (s: FilterState) => void;
  options: { value: FilterState[K]; label: string }[];
}

function ChipGroup<K extends keyof FilterState>({
  label,
  field,
  state,
  setState,
  options,
}: ChipGroupProps<K>) {
  return (
    <div className="flex items-start gap-2 flex-wrap">
      <span className="text-xs font-semibold text-muted-foreground min-w-[5rem] pt-1">{label}:</span>
      <div className="flex flex-wrap gap-1">
        {options.map((opt) => {
          const active = state[field] === opt.value;
          return (
            <Button
              key={String(opt.value)}
              size="sm"
              variant={active ? 'default' : 'outline'}
              onClick={() => setState({ ...state, [field]: opt.value })}
              className="h-7 text-[11px] px-2"
            >
              {opt.label}
            </Button>
          );
        })}
      </div>
    </div>
  );
}

export function CompositeFilterTab({ horses, surgeMap, hasMl }: CompositeFilterTabProps) {
  const [state, setState] = useState<FilterState>(INITIAL);

  const filtered = useMemo(
    () => applyFilter(horses, state, surgeMap),
    [horses, state, surgeMap]
  );

  const isEmpty = JSON.stringify(state) === JSON.stringify(INITIAL);

  const hasResults = useMemo(() => horses.some((h) => h.finishPosition), [horses]);

  return (
    <div className="space-y-4">
      {/* フィルタチップ */}
      <Card>
        <CardHeader className="py-3 px-4 border-b">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-bold">🔍 複合フィルタ (AND条件)</CardTitle>
            <div className="flex items-center gap-2">
              <Badge variant="outline">
                該当: <strong className="ml-1">{filtered.length}</strong> / {horses.length} 頭
              </Badge>
              {!isEmpty && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setState(INITIAL)}
                  className="h-7 text-xs"
                >
                  <X className="h-3 w-3 mr-1" />
                  リセット
                </Button>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-3 space-y-2">
          <ChipGroup
            label="My印1"
            field="myMark1"
            state={state}
            setState={setState}
            options={[
              { value: 'any', label: '全' },
              { value: '◎', label: '◎' },
              { value: '○', label: '○' },
              { value: '▲', label: '▲' },
              { value: '△', label: '△' },
              { value: '★', label: '★' },
              { value: '穴', label: '穴' },
              { value: 'has', label: '印あり' },
              { value: 'none', label: '印なし' },
            ]}
          />
          <ChipGroup
            label="My印2"
            field="myMark2"
            state={state}
            setState={setState}
            options={[
              { value: 'any', label: '全' },
              { value: '◎', label: '◎' },
              { value: '○', label: '○' },
              { value: '▲', label: '▲' },
              { value: '△', label: '△' },
              { value: '★', label: '★' },
              { value: '穴', label: '穴' },
              { value: 'has', label: '印あり' },
            ]}
          />
          {hasMl && (
            <ChipGroup
              label="ML判定"
              field="mlJudge"
              state={state}
              setState={setState}
              options={[
                { value: 'any', label: '全' },
                { value: 'vb', label: 'VB' },
                { value: 'hot', label: '🔥激アツ' },
                { value: 'buy_plus', label: '💰買い+' },
                { value: 'ard55', label: 'ARd≥55' },
                { value: 'ard60', label: 'ARd≥60' },
              ]}
            />
          )}
          <ChipGroup
            label="オッズ帯"
            field="oddsBand"
            state={state}
            setState={setState}
            options={[
              { value: 'any', label: '全' },
              { value: 'le2', label: '<2' },
              { value: '2to5', label: '2-5' },
              { value: '5to10', label: '5-10' },
              { value: '10to30', label: '10-30' },
              { value: 'ge30', label: '≥30' },
            ]}
          />
          <ChipGroup
            label="本紙印"
            field="honshi"
            state={state}
            setState={setState}
            options={[
              { value: 'any', label: '全' },
              { value: '◎', label: '◎' },
              { value: '○', label: '○' },
              { value: '▲', label: '▲' },
              { value: 'has', label: '印あり' },
            ]}
          />
          <ChipGroup
            label="直前変動"
            field="surge"
            state={state}
            setState={setState}
            options={[
              { value: 'any', label: '全' },
              { value: 'hot', label: '🔥hot' },
              { value: 'warm_plus', label: 'warm+' },
            ]}
          />
          <ChipGroup
            label="AI指数"
            field="aiTop"
            state={state}
            setState={setState}
            options={[
              { value: 'any', label: '全' },
              { value: 'top30', label: '上位30%' },
              { value: 'top50', label: '上位50%' },
            ]}
          />
        </CardContent>
      </Card>

      {/* 結果テーブル */}
      <Card>
        <CardHeader className="py-3 px-4 border-b">
          <CardTitle className="text-sm font-bold">絞り込み結果</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-1 py-1.5 text-center font-bold w-6">枠</th>
                  <th className="px-1 py-1.5 text-center font-bold w-8">番</th>
                  <th className="px-1 py-1.5 text-center font-bold w-8">My印</th>
                  <th className="px-1 py-1.5 text-center font-bold w-8">My2</th>
                  <th className="px-1 py-1.5 text-left font-bold min-w-[5rem]">馬名</th>
                  <th className="px-1 py-1.5 text-right font-bold w-12">単勝</th>
                  <th className="px-1 py-1.5 text-center font-bold w-8">人気</th>
                  {hasMl && (
                    <>
                      <th className="px-1 py-1.5 text-right font-bold w-12">単EV</th>
                      <th className="px-1 py-1.5 text-center font-bold w-20">単判定</th>
                      <th className="px-1 py-1.5 text-center font-bold w-8">VB</th>
                      <th className="px-1 py-1.5 text-center font-bold w-12">ARd</th>
                      <th className="px-1 py-1.5 text-center font-bold w-16">市場</th>
                    </>
                  )}
                  <th className="px-1 py-1.5 text-right font-bold w-10">AI</th>
                  <th className="px-1 py-1.5 text-center font-bold w-6">本紙</th>
                  {hasResults && <th className="px-1 py-1.5 text-center font-bold w-8">着</th>}
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={hasMl ? 14 : 9} className="py-6 text-center text-muted-foreground">
                      該当馬なし
                    </td>
                  </tr>
                ) : (
                  filtered.map((h) => {
                    const wakuNum = h.waku ? parseInt(h.waku, 10) : null;
                    const wakuColorClass = wakuNum ? getWakuColor(wakuNum) : 'bg-gray-100';
                    const signal = getMarketSignalDisplay(h.marketSignal);
                    const zone = getBuyZoneDisplay(h.winZone);
                    return (
                      <tr key={h.umaban} className="border-b hover:bg-muted/30">
                        <td className={`px-1 py-1 text-center text-[10px] font-bold border ${wakuColorClass}`}>
                          {h.waku || '-'}
                        </td>
                        <td className="px-1 py-1 text-center font-mono font-semibold">
                          {parseInt(h.umaban, 10)}
                        </td>
                        <td className="px-1 py-1 text-center text-base">
                          <span className={getMyMarkColor(h.myMark1)}>{h.myMark1 || '-'}</span>
                        </td>
                        <td className="px-1 py-1 text-center text-base">
                          <span className={getMyMarkColor(h.myMark2)}>{h.myMark2 || '-'}</span>
                        </td>
                        <td className="px-1 py-1 truncate max-w-[7rem]" title={h.horseName}>
                          {h.horseName || '-'}
                        </td>
                        <td className="px-1 py-1 text-right font-mono tabular-nums">
                          {h.winOdds != null ? h.winOdds.toFixed(1) : '-'}
                        </td>
                        <td className="px-1 py-1 text-center">
                          {h.ninki != null ? (
                            <Badge variant={h.ninki <= 3 ? 'default' : 'secondary'} className="text-[10px] px-1">
                              {h.ninki}
                            </Badge>
                          ) : (
                            '-'
                          )}
                        </td>
                        {hasMl && (
                          <>
                            <td className="px-1 py-1 text-right font-mono tabular-nums">
                              {h.winEv != null ? h.winEv.toFixed(2) : '-'}
                            </td>
                            <td className="px-1 py-1 text-center">
                              {h.winZone === 'unknown' ? (
                                <span className="text-gray-300">-</span>
                              ) : (
                                <span
                                  className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] ${zone.className}`}
                                >
                                  {zone.icon} {zone.label}
                                </span>
                              )}
                            </td>
                            <td className="px-1 py-1 text-center">
                              {h.isVb ? (
                                <span className="bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-400 px-1 py-0.5 rounded font-bold text-[10px]">
                                  VB
                                </span>
                              ) : (
                                '-'
                              )}
                            </td>
                            <td className="px-1 py-1 text-center font-mono tabular-nums text-[11px]">
                              {h.arDeviation != null ? h.arDeviation.toFixed(0) : '-'}
                            </td>
                            <td className="px-1 py-1 text-center">
                              {signal ? (
                                <span className={`px-1 py-0.5 rounded text-[10px] ${signal.className}`}>
                                  {signal.label}
                                </span>
                              ) : (
                                '-'
                              )}
                            </td>
                          </>
                        )}
                        <td className="px-1 py-1 text-right font-mono tabular-nums text-muted-foreground">
                          {h.aiIndex != null ? h.aiIndex.toFixed(0) : '-'}
                        </td>
                        <td className="px-1 py-1 text-center text-muted-foreground text-[11px]">
                          {h.honshiMark || '-'}
                        </td>
                        {hasResults && (
                          <td className="px-1 py-1 text-center font-mono">
                            {h.finishPosition || '-'}
                          </td>
                        )}
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
