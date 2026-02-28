'use client';

import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { PredictionRace, PredictionEntry } from '@/lib/data/predictions-reader';
import type { BetRecommendation, OddsMap, DbResultsMap, SortState } from '../lib/types';
import {
  getGapColor, getGapBg, getEvColor, getRecBadgeClass, getWinOdds,
  getTrackBadgeClass, getTrackLabel, getFinishColor, getPlaceLimit,
  getRaceLink, getRaceDanger, getCommentColor, getCommentTooltip, getArColor, getArdColor, SortTh,
} from '../lib/helpers';
import type { RaceResultsMap } from '@/lib/data/predictions-reader';

interface VBTableProps {
  sortedVBEntries: Array<{ race: PredictionRace; entry: PredictionEntry }>;
  filteredVBEntries: Array<{ race: PredictionRace; entry: PredictionEntry }>;
  oddsMap: OddsMap;
  dbResults: DbResultsMap;
  results?: RaceResultsMap;
  hasResults: boolean;
  getFinishPos: (raceId: string, umaban: number) => number;
  getLiveGap: (raceId: string, entry: PredictionEntry) => number;
  vbSort: SortState;
  setVbSort: (s: SortState) => void;
  syncVbMarks: () => Promise<void>;
  markSyncing: boolean;
  markResult: { marks: Record<string, number>; markedHorses: number } | null;
  betRecMap: Map<string, BetRecommendation>;
  targetMarks?: Record<string, Record<number, string>>;
}

export function VBTable({
  sortedVBEntries, filteredVBEntries, oddsMap, dbResults, results, hasResults,
  getFinishPos, getLiveGap, vbSort, setVbSort,
  syncVbMarks, markSyncing, markResult,
  betRecMap, targetMarks,
}: VBTableProps) {
  if (filteredVBEntries.length === 0) return null;

  return (
    <Card id="section-vb" className="mb-8 border-amber-200 dark:border-amber-800">
      <CardHeader className="pb-2 bg-gradient-to-r from-amber-50 to-orange-50 dark:from-amber-950 dark:to-orange-950">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            Value Bet 対象馬 ({filteredVBEntries.length}頭)
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
              title="VB候補の印をTARGET馬印2に一括書込み"
            >
              {markSyncing ? '反映中...' : 'VB印→馬印2'}
            </button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-4">
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-gray-100 dark:bg-gray-800 text-xs">
                <th className="px-2 py-2 text-left border">場</th>
                <SortTh sortKey="race" sort={vbSort} setSort={setVbSort} className="px-2 py-2 text-center border">R</SortTh>
                <th className="px-2 py-2 text-center border" title="芝/ダート">馬場</th>
                <SortTh sortKey="umaban" sort={vbSort} setSort={setVbSort} className="px-2 py-2 text-center border">馬番</SortTh>
                <th className="px-2 py-2 text-left border">馬名</th>
                <SortTh sortKey="ev" sort={vbSort} setSort={setVbSort} className="px-2 py-2 text-center border bg-amber-50 dark:bg-amber-900/30" title="単勝EV = calibrated P(win) × 単勝オッズ">EV</SortTh>
                <SortTh sortKey="margin" sort={vbSort} setSort={setVbSort} className="px-2 py-2 text-center border bg-teal-50 dark:bg-teal-900/30" title="AR (Aura Rating) — グレード補正済みの絶対能力指数">AR</SortTh>
                <SortTh sortKey="ar_dev" sort={vbSort} setSort={setVbSort} className="px-2 py-2 text-center border bg-teal-50/50 dark:bg-teal-900/20" title="AR偏差値 — レース内相対評価（mean=50, std=10）">ARd</SortTh>
                <SortTh sortKey="gap" sort={vbSort} setSort={setVbSort} className="px-2 py-2 text-center border bg-amber-50/50 dark:bg-amber-900/20" title="Gap = 人気順位 - VR。参考指標">Gap</SortTh>
                <SortTh sortKey="odds" sort={vbSort} setSort={setVbSort} className="px-2 py-2 text-center border" title="単勝オッズ">オッズ</SortTh>
                <SortTh sortKey="prob_v" sort={vbSort} setSort={setVbSort} className="px-2 py-2 text-center border" title="好走 独自モデルの3着内確率">V%</SortTh>
                <th className="px-2 py-2 text-center border" title="勝利 独自モデルの勝率予測">WV%</th>
                <SortTh sortKey="rating" sort={vbSort} setSort={setVbSort} className="px-2 py-2 text-center border" title="BR (Book Rating) — 競馬ブックレイティング">BR</SortTh>
                <th className="px-2 py-2 text-center border" title="競馬ブック調教評価の矢印">調</th>
                <th className="px-2 py-2 text-center border" title="厩舎談話NLPスコア（仕上がり度 -3〜+3）">談</th>
                {hasResults && <SortTh sortKey="finish" sort={vbSort} setSort={setVbSort} className="px-2 py-2 text-center border" title="確定着順">着順</SortTh>}
                {hasResults && <th className="px-2 py-2 text-center border" title="単勝払い戻し">単払</th>}
                {hasResults && <th className="px-2 py-2 text-center border" title="複勝払い戻し">複払</th>}
              </tr>
            </thead>
            <tbody>
              {sortedVBEntries.map(({ race, entry }) => {
                const liveGap = getLiveGap(race.race_id, entry);
                const ev = entry.win_ev ?? null;
                const finishPos = getFinishPos(race.race_id, entry.umaban);
                const placeLimit = getPlaceLimit(race.num_runners);
                const isPlaceHit = finishPos > 0 && placeLimit > 0 && finishPos <= placeLimit;
                const dbEntry = dbResults[race.race_id]?.[entry.umaban];
                const margin = entry.predicted_margin;
                const rec = betRecMap.get(`${race.race_id}-${entry.umaban}`);
                return (
                  <tr
                    key={`${race.race_id}-${entry.umaban}`}
                    className={`border-b hover:bg-blue-50/50 dark:hover:bg-blue-900/10 ${
                      finishPos === 1 ? 'bg-amber-50/60 dark:bg-amber-900/15' :
                      isPlaceHit ? 'bg-green-50/40 dark:bg-green-900/10' :
                      getGapBg(liveGap)
                    }`}
                  >
                    <td className="px-2 py-1.5 border text-xs">
                      <Link href={getRaceLink(race)} target="_blank" className="hover:text-blue-600 hover:underline">
                        {race.venue_name}
                      </Link>
                      {(() => { const dg = getRaceDanger(race.entries); return dg.isDanger ? (
                        <span className="ml-0.5 text-[9px] text-orange-500" title={`危険: ${dg.dangerHorse?.horseName} (${dg.dangerHorse?.odds?.toFixed(1)}倍)`}>!</span>
                      ) : null; })()}
                    </td>
                    <td className="px-2 py-1.5 border text-center font-bold">
                      <Link href={getRaceLink(race)} target="_blank" className="hover:text-blue-600 hover:underline">
                        {race.race_number}
                      </Link>
                    </td>
                    <td className="px-2 py-1.5 border text-center">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] ${getTrackBadgeClass(race.track_type)}`}>
                        {getTrackLabel(race.track_type)}{race.distance}
                      </span>
                    </td>
                    <td className="px-2 py-1.5 border text-center font-mono">{entry.umaban}</td>
                    <td className="px-2 py-1.5 border font-bold">
                      {entry.horse_name}
                      {(() => {
                        // 購入プランに入っている場合はそのバッジを優先
                        if (rec) {
                          return (
                            <>
                              <span className={`ml-1 px-1 py-0.5 rounded text-[9px] ${getRecBadgeClass(rec.betType, rec.strength)}`}>
                                {rec.betType}
                              </span>
                              {rec.strength === 'strong' && (
                                <span className="ml-0.5 px-0.5 py-0.5 rounded text-[8px] bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300 font-bold" title="strong: 単勝重視配分">S</span>
                              )}
                            </>
                          );
                        }
                        // VB候補全体: 単勝/複勝適性バッジ
                        const headRatio = entry.pred_proba_wv && entry.pred_proba_v > 0
                          ? entry.pred_proba_wv / entry.pred_proba_v : 0;
                        const winSuited = (ev ?? 0) >= 1.0 && headRatio >= 0.30;
                        const placeSuited = (entry.place_ev ?? 0) >= 1.0;
                        if (winSuited && placeSuited) {
                          return <span className="ml-1 px-1 py-0.5 rounded text-[9px] bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300" title={`頭%=${(headRatio*100).toFixed(0)}% 単EV=${ev?.toFixed(2)} 複EV=${entry.place_ev?.toFixed(2)}`}>単複向</span>;
                        }
                        if (winSuited) {
                          return <span className="ml-1 px-1 py-0.5 rounded text-[9px] bg-red-50 text-red-600 dark:bg-red-900/20 dark:text-red-400" title={`頭%=${(headRatio*100).toFixed(0)}% 単EV=${ev?.toFixed(2)}`}>単勝向</span>;
                        }
                        if (placeSuited) {
                          return <span className="ml-1 px-1 py-0.5 rounded text-[9px] bg-blue-50 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400" title={`複EV=${entry.place_ev?.toFixed(2)}`}>複勝向</span>;
                        }
                        return null;
                      })()}
                    </td>
                    <td className={`px-2 py-1.5 border text-center font-mono text-xs bg-amber-50/30 dark:bg-amber-900/10 ${getEvColor(ev)}`}>
                      {ev !== null ? ev.toFixed(2) : '-'}
                    </td>
                    <td className={`px-2 py-1.5 border text-center font-mono text-xs bg-teal-50/30 dark:bg-teal-900/10 ${getArColor(margin)}`}>
                      {margin != null ? margin.toFixed(1) : '-'}
                    </td>
                    <td className={`px-2 py-1.5 border text-center font-mono text-xs bg-teal-50/20 dark:bg-teal-900/5 ${getArdColor(entry.ar_deviation)}`} title="AR偏差値">
                      {entry.ar_deviation != null ? entry.ar_deviation.toFixed(0) : '-'}
                    </td>
                    <td className={`px-2 py-1.5 border text-center font-mono font-bold bg-amber-50/20 dark:bg-amber-900/5 ${getGapColor(liveGap)}`} title="Gap">
                      +{liveGap}
                    </td>
                    <td className="px-2 py-1.5 border text-center font-mono text-xs">
                      {(() => { const wo = getWinOdds(oddsMap, race.race_id, entry.umaban, entry.odds); return wo ? wo.toFixed(1) : '-'; })()}
                    </td>
                    <td className="px-2 py-1.5 border text-center font-mono text-xs">
                      {(entry.pred_proba_v * 100).toFixed(1)}
                    </td>
                    <td className="px-2 py-1.5 border text-center font-mono text-xs text-emerald-600">
                      {entry.pred_proba_wv != null ? (entry.pred_proba_wv * 100).toFixed(1) : '-'}
                    </td>
                    <td className="px-2 py-1.5 border text-center font-mono text-xs">{entry.kb_rating > 0 ? entry.kb_rating.toFixed(1) : '-'}</td>
                    <td className="px-2 py-1.5 border text-center">{entry.kb_training_arrow}</td>
                    <td className={`px-2 py-1.5 border text-center font-mono text-xs ${entry.comment_has_stable ? getCommentColor(entry.comment_stable_condition ?? 0) : 'text-gray-300'}`} title={getCommentTooltip(entry)}>
                      {entry.comment_has_stable ? (entry.comment_stable_condition ?? 0) > 0 ? `+${entry.comment_stable_condition}` : `${entry.comment_stable_condition ?? 0}` : '-'}
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
      </CardContent>
    </Card>
  );
}
