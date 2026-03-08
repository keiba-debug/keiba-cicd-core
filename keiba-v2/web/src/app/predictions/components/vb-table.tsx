'use client';

import { useState, useMemo } from 'react';
import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { PredictionRace, PredictionEntry } from '@/lib/data/predictions-reader';
import type { BetRecommendation, OddsMap, DbResultsMap } from '../lib/types';
import {
  getEvColor, getRecBadgeClass, getWinOdds,
  getTrackBadgeClass, getTrackLabel, getFinishColor, getPlaceLimit,
  getRaceLink, getArdColor,
} from '../lib/helpers';
import type { RaceResultsMap } from '@/lib/data/predictions-reader';

// --- 市場シグナル バッジ色 ---
function getSignalBadge(signal: string | null | undefined) {
  if (!signal) return null;
  const cls =
    signal === '鉄板' ? 'bg-gradient-to-r from-red-600 to-red-500 text-white' :
    signal === '軸向き' ? 'bg-gradient-to-r from-orange-500 to-orange-400 text-white' :
    signal === '妙味' ? 'bg-gradient-to-r from-blue-600 to-blue-500 text-white' :
    signal === 'やや妙味' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300' :
    signal === '想定通り' ? 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300' :
    signal === '人気しすぎ' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300' :
    signal === '穴注目' ? 'bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300' :
    'bg-gray-100 text-gray-600';
  return (
    <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-bold whitespace-nowrap ${cls}`}>
      {signal}
    </span>
  );
}

// --- 自信度バッジ ---
function getConfidenceBadge(conf: number | null | undefined) {
  if (conf == null) return null;
  const label = conf >= 70 ? '◎' : conf >= 45 ? '△' : '✕';
  const cls =
    conf >= 70 ? 'text-green-600 border-green-400 bg-green-50/50 dark:bg-green-900/20 dark:text-green-400' :
    conf >= 45 ? 'text-yellow-600 border-yellow-400 bg-yellow-50/50 dark:bg-yellow-900/20 dark:text-yellow-400' :
    'text-red-500 border-red-300 bg-red-50/50 dark:bg-red-900/20 dark:text-red-400';
  return (
    <span className={`inline-block px-1 py-0.5 rounded border text-[10px] font-bold ${cls}`} title={`確信度: ${conf.toFixed(1)}`}>
      {label}{conf.toFixed(0)}
    </span>
  );
}

export type FeaturedEntry = {
  race: PredictionRace;
  entry: PredictionEntry;
  category: 'pick' | 'value';  // pick=評価馬, value=穴注目
};

// ソートキー
type SortKey = 'confidence' | 'race' | 'prob_p' | 'prob_w' | 'ard' | 'odds' | 'ev' | 'finish';

interface VBTableProps {
  featuredEntries: FeaturedEntry[];
  oddsMap: OddsMap;
  dbResults: DbResultsMap;
  results?: RaceResultsMap;
  hasResults: boolean;
  getFinishPos: (raceId: string, umaban: number) => number;
  syncVbMarks: () => Promise<void>;
  markSyncing: boolean;
  markResult: { marks: Record<string, number>; markedHorses: number } | null;
  betRecMap: Map<string, BetRecommendation>;
}

export function VBTable({
  featuredEntries, oddsMap, dbResults, hasResults,
  getFinishPos,
  syncVbMarks, markSyncing, markResult,
  betRecMap,
}: VBTableProps) {
  if (featuredEntries.length === 0) return null;

  const picks = featuredEntries.filter(e => e.category === 'pick');
  const values = featuredEntries.filter(e => e.category === 'value');

  return (
    <Card id="section-vb" className="mb-8 border-amber-200 dark:border-amber-800">
      <CardHeader className="pb-2 bg-gradient-to-r from-amber-50 to-orange-50 dark:from-amber-950 dark:to-orange-950">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            注目馬リスト
            <span className="text-sm font-normal text-muted-foreground">
              評価馬{picks.length} + 穴注目{values.length}
            </span>
          </CardTitle>
          <div className="flex items-center gap-2">
            {markResult && (
              <span className="text-xs text-green-700 dark:text-green-400">
                {markResult.markedHorses}頭 反映完了
              </span>
            )}
            <button
              onClick={syncVbMarks}
              disabled={markSyncing}
              className="px-3 py-1 text-xs font-medium rounded border bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 border-amber-300 dark:border-amber-700 disabled:opacity-50"
              title="注目馬の印をTARGET馬印2に一括書込み"
            >
              {markSyncing ? '反映中...' : '印→馬印2'}
            </button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-4 space-y-4">
        {/* 評価馬セクション */}
        <div>
          <h3 className="text-sm font-bold mb-2 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-teal-500 inline-block" />
            評価馬
            <span className="text-xs font-normal text-muted-foreground">各レースのモデル Top1（自信度順）</span>
          </h3>
          <HorseTable
            entries={picks}
            oddsMap={oddsMap}
            dbResults={dbResults}
            hasResults={hasResults}
            getFinishPos={getFinishPos}
            betRecMap={betRecMap}
            defaultSort="confidence"
            defaultDir="desc"
          />
        </div>

        {/* 穴注目セクション */}
        {values.length > 0 && (
          <div>
            <h3 className="text-sm font-bold mb-2 flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-purple-500 inline-block" />
              穴注目
              <span className="text-xs font-normal text-muted-foreground">オッズ妙味 or スマートマネー検知</span>
            </h3>
            <HorseTable
              entries={values}
              oddsMap={oddsMap}
              dbResults={dbResults}
              hasResults={hasResults}
              getFinishPos={getFinishPos}
              betRecMap={betRecMap}
              defaultSort="ard"
              defaultDir="desc"
            />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// --- ソート可能ヘッダー ---
function SortTh({
  sortKey, currentKey, currentDir, onSort, children, className, title,
}: {
  sortKey: SortKey;
  currentKey: SortKey;
  currentDir: 'asc' | 'desc';
  onSort: (key: SortKey) => void;
  children: React.ReactNode;
  className?: string;
  title?: string;
}) {
  const isActive = currentKey === sortKey;
  return (
    <th
      onClick={() => onSort(sortKey)}
      className={`cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors select-none ${className || ''}`}
      title={title}
    >
      {children}
      {isActive && <span className="ml-0.5">{currentDir === 'desc' ? '▼' : '▲'}</span>}
    </th>
  );
}

// --- 共通テーブル ---
function HorseTable({
  entries, oddsMap, dbResults, hasResults, getFinishPos, betRecMap,
  defaultSort, defaultDir,
}: {
  entries: FeaturedEntry[];
  oddsMap: OddsMap;
  dbResults: DbResultsMap;
  hasResults: boolean;
  getFinishPos: (raceId: string, umaban: number) => number;
  betRecMap: Map<string, BetRecommendation>;
  defaultSort: SortKey;
  defaultDir: 'asc' | 'desc';
}) {
  const [sortKey, setSortKey] = useState<SortKey>(defaultSort);
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>(defaultDir);

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      // デフォルトは大きい順（desc）、ただしrace/oddsは小さい順
      setSortDir(key === 'race' || key === 'odds' ? 'asc' : 'desc');
    }
  };

  const sorted = useMemo(() => {
    const arr = [...entries];
    const mul = sortDir === 'asc' ? 1 : -1;
    arr.sort((a, b) => {
      let va: number, vb: number;
      switch (sortKey) {
        case 'confidence':
          va = a.race.race_confidence ?? -1;
          vb = b.race.race_confidence ?? -1;
          break;
        case 'race': {
          // 場名→R番
          const vn = a.race.venue_name.localeCompare(b.race.venue_name);
          if (vn !== 0) return vn * mul;
          va = a.race.race_number;
          vb = b.race.race_number;
          break;
        }
        case 'prob_p':
          va = a.entry.pred_proba_p ?? -1;
          vb = b.entry.pred_proba_p ?? -1;
          break;
        case 'prob_w':
          va = a.entry.pred_proba_w ?? -1;
          vb = b.entry.pred_proba_w ?? -1;
          break;
        case 'ard':
          va = a.entry.ar_deviation ?? -1;
          vb = b.entry.ar_deviation ?? -1;
          break;
        case 'odds':
          va = getWinOdds(oddsMap, a.race.race_id, a.entry.umaban, a.entry.odds) ?? 9999;
          vb = getWinOdds(oddsMap, b.race.race_id, b.entry.umaban, b.entry.odds) ?? 9999;
          break;
        case 'ev':
          va = a.entry.win_ev ?? -1;
          vb = b.entry.win_ev ?? -1;
          break;
        case 'finish':
          va = getFinishPos(a.race.race_id, a.entry.umaban) || 999;
          vb = getFinishPos(b.race.race_id, b.entry.umaban) || 999;
          break;
        default:
          va = 0; vb = 0;
      }
      return (va - vb) * mul;
    });
    return arr;
  }, [entries, sortKey, sortDir, oddsMap, getFinishPos]);

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-gray-100 dark:bg-gray-800 text-xs">
            <SortTh sortKey="race" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="px-2 py-1.5 text-left border">場R</SortTh>
            <th className="px-2 py-1.5 text-center border" title="芝/ダート">馬場</th>
            <SortTh sortKey="confidence" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="px-2 py-1.5 text-center border" title="レース確信度">自信</SortTh>
            <th className="px-2 py-1.5 text-center border">番</th>
            <th className="px-2 py-1.5 text-left border">馬名</th>
            <SortTh sortKey="prob_p" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="px-2 py-1.5 text-center border" title="好走モデル(P) 3着内確率">P%</SortTh>
            <SortTh sortKey="prob_w" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="px-2 py-1.5 text-center border" title="勝利モデル(W) 勝率予測">W%</SortTh>
            <SortTh sortKey="ard" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="px-2 py-1.5 text-center border" title="AR偏差値 — レース内相対評価">ARd</SortTh>
            <SortTh sortKey="odds" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="px-2 py-1.5 text-center border" title="単勝オッズ">オッズ</SortTh>
            <SortTh sortKey="ev" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="px-2 py-1.5 text-center border" title="単勝EV = calibrated P(win) × 単勝オッズ">EV</SortTh>
            <th className="px-2 py-1.5 text-center border" title="基準オッズとの乖離シグナル">市場</th>
            {hasResults && <SortTh sortKey="finish" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} className="px-2 py-1.5 text-center border">着順</SortTh>}
            {hasResults && <th className="px-2 py-1.5 text-center border">単払</th>}
            {hasResults && <th className="px-2 py-1.5 text-center border">複払</th>}
          </tr>
        </thead>
        <tbody>
          {sorted.map(({ race, entry }) => {
            const ev = entry.win_ev ?? null;
            const finishPos = getFinishPos(race.race_id, entry.umaban);
            const placeLimit = getPlaceLimit(race.num_runners);
            const isPlaceHit = finishPos > 0 && placeLimit > 0 && finishPos <= placeLimit;
            const dbEntry = dbResults[race.race_id]?.[entry.umaban];
            const rec = betRecMap.get(`${race.race_id}-${entry.umaban}`);
            const odds = getWinOdds(oddsMap, race.race_id, entry.umaban, entry.odds);
            return (
              <tr
                key={`${race.race_id}-${entry.umaban}`}
                className={`border-b hover:bg-blue-50/50 dark:hover:bg-blue-900/10 ${
                  finishPos === 1 ? 'bg-amber-50/60 dark:bg-amber-900/15' :
                  isPlaceHit ? 'bg-green-50/40 dark:bg-green-900/10' : ''
                }`}
              >
                <td className="px-2 py-1.5 border text-xs whitespace-nowrap">
                  <Link href={getRaceLink(race)} target="_blank" className="hover:text-blue-600 hover:underline">
                    {race.venue_name}{race.race_number}R
                  </Link>
                </td>
                <td className="px-2 py-1.5 border text-center">
                  <span className={`px-1 py-0.5 rounded text-[10px] ${getTrackBadgeClass(race.track_type)}`}>
                    {getTrackLabel(race.track_type)}{race.distance}
                  </span>
                </td>
                <td className="px-2 py-1.5 border text-center">
                  {getConfidenceBadge(race.race_confidence)}
                </td>
                <td className="px-2 py-1.5 border text-center font-mono font-bold">{entry.umaban}</td>
                <td className="px-2 py-1.5 border font-bold whitespace-nowrap">
                  {entry.horse_name}
                  {rec && (
                    <>
                      <span className={`ml-1 px-1 py-0.5 rounded text-[9px] ${getRecBadgeClass(rec.betType, rec.strength)}`}>
                        {rec.betType}
                      </span>
                      {rec.strength === 'strong' && (
                        <span className="ml-0.5 px-0.5 py-0.5 rounded text-[8px] bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300 font-bold">S</span>
                      )}
                    </>
                  )}
                </td>
                <td className="px-2 py-1.5 border text-center font-mono text-xs">
                  {(entry.pred_proba_p * 100).toFixed(1)}
                </td>
                <td className="px-2 py-1.5 border text-center font-mono text-xs text-emerald-600">
                  {entry.pred_proba_w != null ? (entry.pred_proba_w * 100).toFixed(1) : '-'}
                </td>
                <td className={`px-2 py-1.5 border text-center font-mono text-xs font-bold ${getArdColor(entry.ar_deviation)}`}>
                  {entry.ar_deviation != null ? entry.ar_deviation.toFixed(0) : '-'}
                </td>
                <td className="px-2 py-1.5 border text-center font-mono text-xs">
                  {odds ? odds.toFixed(1) : '-'}
                </td>
                <td className={`px-2 py-1.5 border text-center font-mono text-xs ${getEvColor(ev)}`}>
                  {ev !== null ? ev.toFixed(2) : '-'}
                </td>
                <td className="px-2 py-1.5 border text-center">
                  {getSignalBadge(entry.market_signal)}
                </td>
                {hasResults && (
                  <td className={`px-2 py-1.5 border text-center font-mono ${finishPos > 0 ? getFinishColor(finishPos) : 'text-gray-300'}`}>
                    {finishPos > 0 ? `${finishPos}着` : '-'}
                  </td>
                )}
                {hasResults && (
                  <td className={`px-2 py-1.5 border text-center font-mono text-xs ${finishPos === 1 && dbEntry?.confirmedWinOdds ? 'text-red-600 font-bold' : 'text-gray-300'}`}>
                    {finishPos === 1 && dbEntry?.confirmedWinOdds
                      ? `¥${Math.round(dbEntry.confirmedWinOdds * 100).toLocaleString()}`
                      : ''}
                  </td>
                )}
                {hasResults && (
                  <td className={`px-2 py-1.5 border text-center font-mono text-xs ${isPlaceHit && dbEntry?.confirmedPlaceOddsMin ? 'text-blue-600 font-bold' : 'text-gray-300'}`}>
                    {isPlaceHit && dbEntry?.confirmedPlaceOddsMin
                      ? `¥${Math.round(dbEntry.confirmedPlaceOddsMin * 100).toLocaleString()}`
                      : ''}
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
