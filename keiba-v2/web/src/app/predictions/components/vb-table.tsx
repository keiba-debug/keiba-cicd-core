'use client';

import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { PredictionRace, PredictionEntry } from '@/lib/data/predictions-reader';
import type { BetRecommendation, OddsMap, DbResultsMap, SortState } from '../lib/types';
import {
  getWinOdds, getPlaceOddsMin, calcHeadRatio,
  getGapColor, getGapBg, getEvColor, getMarkColor, getRecBadgeClass,
  getTrackBadgeClass, getTrackLabel, getFinishColor, getPlaceLimit,
  getRaceLink, getKoukakuDetail, getRaceDanger, getCommentColor, getCommentTooltip, getRatingColor, SortTh,
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
            Value Bet 候補 ({filteredVBEntries.length}頭)
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
                <th className="px-2 py-2 text-center border" title="購入プラン推奨の券種">推奨</th>
                <th className="px-2 py-2 text-center border" title="競馬ブック本紙予想の印">本紙</th>
                <th className="px-2 py-2 text-center border" title="TARGET 馬印1（自分の印）">My</th>
                <SortTh sortKey="rank_v" sort={vbSort} setSort={setVbSort} className="px-2 py-2 text-center border" title="独自ランク — 好走 独自モデルによるレース内順位">VR</SortTh>
                <SortTh sortKey="odds_rank" sort={vbSort} setSort={setVbSort} className="px-2 py-2 text-center border" title="オッズ順人気">人気</SortTh>
                <SortTh sortKey="odds" sort={vbSort} setSort={setVbSort} className="px-2 py-2 text-center border" title="単勝オッズ（DB最新）">オッズ</SortTh>
                <SortTh sortKey="gap" sort={vbSort} setSort={setVbSort} className="px-2 py-2 text-center border" title="乖離度 — 人気順位 - VR。大きいほど市場が過小評価">Gap</SortTh>
                <SortTh sortKey="margin" sort={vbSort} setSort={setVbSort} className="px-2 py-2 text-center border bg-teal-50 dark:bg-teal-900/30" title="能力R — 能力レーティング。高いほど強い">能力R</SortTh>
                <SortTh sortKey="win_gap" sort={vbSort} setSort={setVbSort} className="px-2 py-2 text-center border bg-emerald-50 dark:bg-emerald-900/30" title="Win VB Gap：Win順位と人気の乖離">W-Gap</SortTh>
                <SortTh sortKey="ev" sort={vbSort} setSort={setVbSort} className="px-2 py-2 text-center border text-gray-400" title="WVモデルECE=0.12のため参考値">単EV*</SortTh>
                <SortTh sortKey="place_ev" sort={vbSort} setSort={setVbSort} className="px-2 py-2 text-center border bg-blue-50 dark:bg-blue-900/30" title="複勝EV = calibrated P(top3) × 複勝オッズ">複EV</SortTh>
                <SortTh sortKey="head_ratio" sort={vbSort} setSort={setVbSort} className="px-2 py-2 text-center border" title="頭向き度 = P(win)/P(top3)">頭%</SortTh>
                <SortTh sortKey="prob_v" sort={vbSort} setSort={setVbSort} className="px-2 py-2 text-center border" title="好走 独自モデルの3着内確率">V%</SortTh>
                <th className="px-2 py-2 text-center border" title="勝利 独自モデルの勝率予測">WV%</th>
                <th className="px-2 py-2 text-center border" title="競馬ブック調教評価の矢印">調教</th>
                <th className="px-2 py-2 text-center border" title="厩舎談話NLPスコア（仕上がり度 -3〜+3）">談</th>
                {hasResults && <SortTh sortKey="finish" sort={vbSort} setSort={setVbSort} className="px-2 py-2 text-center border" title="確定着順">着順</SortTh>}
                {hasResults && <th className="px-2 py-2 text-center border" title="単勝払い戻し">単払</th>}
                {hasResults && <th className="px-2 py-2 text-center border" title="複勝払い戻し">複払</th>}
              </tr>
            </thead>
            <tbody>
              {sortedVBEntries.map(({ race, entry }) => {
                const winOdds = getWinOdds(oddsMap, race.race_id, entry.umaban, entry.odds);
                const placeOddsMin = entry.place_odds_min ?? getPlaceOddsMin(oddsMap, race.race_id, entry.umaban);
                const liveGap = getLiveGap(race.race_id, entry);
                const ev = entry.win_ev ?? null;
                const placeEv = entry.place_ev ?? null;
                const headRatio = calcHeadRatio(entry.pred_proba_wv, entry.pred_proba_v);
                const finishPos = getFinishPos(race.race_id, entry.umaban);
                const placeLimit = getPlaceLimit(race.num_runners);
                const isPlaceHit = finishPos > 0 && placeLimit > 0 && finishPos <= placeLimit;
                const dbEntry = dbResults[race.race_id]?.[entry.umaban];
                const winGap = entry.win_vb_gap;
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
                      {(() => { const dg = getRaceDanger(race.entries, 5); return dg.isDanger ? (
                        <span className="ml-0.5 text-[9px] text-orange-500" title={`危険: ${dg.dangerHorse?.horseName} (人気${dg.dangerHorse?.oddsRank}→V${dg.dangerHorse?.rankV})`}>!</span>
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
                      {(entry.koukaku_rote_count ?? 0) > 0 && (
                        <span className="ml-1 text-[9px] px-1 py-0.5 rounded bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300" title={getKoukakuDetail(entry)}>
                          降格{(entry.koukaku_rote_count ?? 0) > 1 ? `×${entry.koukaku_rote_count}` : ''}
                        </span>
                      )}
                    </td>
                    <td className="px-2 py-1.5 border text-center">
                      {rec ? (
                        <span className={`px-1.5 py-0.5 rounded text-[10px] ${getRecBadgeClass(rec.betType, rec.strength)}`}>
                          {rec.betType}
                        </span>
                      ) : (
                        <span className="text-[10px] text-gray-300">-</span>
                      )}
                    </td>
                    <td className={`px-2 py-1.5 border text-center ${getMarkColor(entry.kb_mark)}`}>
                      {entry.kb_mark || '-'}
                    </td>
                    {(() => {
                      const myMark = targetMarks?.[race.race_id]?.[entry.umaban];
                      return (
                        <td className={`px-2 py-1.5 border text-center font-bold ${myMark ? 'text-purple-700 dark:text-purple-300' : 'text-gray-300'}`}>
                          {myMark || '-'}
                        </td>
                      );
                    })()}
                    <td className="px-2 py-1.5 border text-center font-mono font-bold text-blue-600">{entry.rank_v}</td>
                    <td className="px-2 py-1.5 border text-center font-mono">{entry.odds_rank || '-'}</td>
                    <td className="px-2 py-1.5 border text-center font-mono font-bold">
                      {winOdds ? winOdds.toFixed(1) : '-'}
                    </td>
                    <td className={`px-2 py-1.5 border text-center font-mono ${getGapColor(liveGap)}`}>
                      +{liveGap}
                    </td>
                    <td className={`px-2 py-1.5 border text-center font-mono text-xs bg-teal-50/30 dark:bg-teal-900/10 ${getRatingColor(margin)}`}>
                      {margin != null ? margin.toFixed(1) : '-'}
                    </td>
                    <td className={`px-2 py-1.5 border text-center font-mono ${winGap != null && winGap >= 3 ? getGapColor(winGap) : 'text-gray-400'} bg-emerald-50/30 dark:bg-emerald-900/10`}>
                      {winGap != null && winGap !== 0 ? (winGap > 0 ? `+${winGap}` : `${winGap}`) : '-'}
                    </td>
                    <td className="px-2 py-1.5 border text-center font-mono text-gray-400" title="WVモデルECE=0.12のため参考値">
                      {ev !== null ? ev.toFixed(2) : '-'}
                    </td>
                    <td className={`px-2 py-1.5 border text-center font-mono text-xs ${placeEv !== null && placeEv >= 1.0 ? 'text-blue-600 font-bold' : placeEv !== null ? 'text-blue-400' : 'text-gray-300'} bg-blue-50/30 dark:bg-blue-900/10`}>
                      {placeEv !== null ? placeEv.toFixed(2) : '-'}
                    </td>
                    <td className={`px-2 py-1.5 border text-center font-mono text-xs ${headRatio !== null && headRatio >= 0.35 ? 'text-red-600 font-bold' : headRatio !== null ? '' : 'text-gray-300'}`}>
                      {headRatio !== null ? `${(headRatio * 100).toFixed(0)}` : '-'}
                    </td>
                    <td className="px-2 py-1.5 border text-center font-mono text-xs">
                      {(entry.pred_proba_v * 100).toFixed(1)}
                    </td>
                    <td className="px-2 py-1.5 border text-center font-mono text-xs text-emerald-600">
                      {entry.pred_proba_wv != null ? (entry.pred_proba_wv * 100).toFixed(1) : '-'}
                    </td>
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
