'use client';

import { useState, useMemo } from 'react';
import Link from 'next/link';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { PredictionRace, RaceResultsMap } from '@/lib/data/predictions-reader';
import type { OddsMap, DbResultsMap, SortState } from '../lib/types';
import {
  getWinOdds, calcWinEv, getGapColor, getGapBg, getEvColor, getMarkColor,
  getTrackBadgeClass, getTrackLabel, getFinishColor, getPlaceLimit,
  getRaceLink, getCommentColor, getCommentTooltip, getArColor, getArdColor, getGradeBadgeClass, SortTh,
} from '../lib/helpers';

interface RaceCardProps {
  race: PredictionRace;
  oddsMap: OddsMap;
  results?: RaceResultsMap;
  dbResults?: DbResultsMap;
  targetMarks?: Record<number, string>;
}

export function RaceCard({ race, oddsMap, results, dbResults, targetMarks }: RaceCardProps) {
  const dbRaceResult = dbResults?.[race.race_id];
  const jsonRaceResult = results?.[race.race_id];
  const hasResults = (dbRaceResult ? Object.keys(dbRaceResult).length > 0 : false) || (jsonRaceResult ? Object.keys(jsonRaceResult).length > 0 : false);
  const vbEntries = race.entries.filter(e => e.is_value_bet);

  const [sort, setSort] = useState<SortState>({ key: 'margin', dir: 'desc' });

  // リアルタイムオッズから人気順を再計算
  const liveRanking = useMemo(() => {
    const raceOdds = oddsMap[race.race_id];
    if (!raceOdds) return null;
    const sorted = race.entries
      .map(e => ({ umaban: e.umaban, odds: raceOdds[e.umaban]?.winOdds ?? e.odds ?? 999 }))
      .filter(e => e.odds > 0)
      .sort((a, b) => a.odds - b.odds);
    const ranking: Record<number, number> = {};
    sorted.forEach((e, i) => { ranking[e.umaban] = i + 1; });
    return ranking;
  }, [race, oddsMap]);

  /** リアルタイム人気順（フォールバック: predictions時点のodds_rank） */
  const getLiveOddsRank = (umaban: number, fallback: number) =>
    liveRanking?.[umaban] ?? fallback;

  /** リアルタイムGap = 人気順 - P順 */
  const getLiveGap = (entry: typeof race.entries[0]): number => {
    const oddsRank = getLiveOddsRank(entry.umaban, entry.odds_rank);
    if (oddsRank == null || entry.rank_p == null) return entry.vb_gap ?? 0;
    return oddsRank - entry.rank_p;
  };

  const sortedEntries = useMemo(() => {
    const arr = [...race.entries];
    const { key, dir } = sort;
    const mul = dir === 'asc' ? 1 : -1;
    arr.sort((a, b) => {
      let va: number, vb: number;
      switch (key) {
        case 'rank_p': va = a.rank_p; vb = b.rank_p; break;
        case 'odds_rank': va = getLiveOddsRank(a.umaban, a.odds_rank) || 999; vb = getLiveOddsRank(b.umaban, b.odds_rank) || 999; break;
        case 'odds': {
          va = getWinOdds(oddsMap, race.race_id, a.umaban, a.odds) ?? 9999;
          vb = getWinOdds(oddsMap, race.race_id, b.umaban, b.odds) ?? 9999;
          break;
        }
        case 'gap': va = getLiveGap(a); vb = getLiveGap(b); break;
        case 'margin': va = a.predicted_margin ?? 99; vb = b.predicted_margin ?? 99; break;
        case 'idm': va = a.jrdb_idm ?? -1; vb = b.jrdb_idm ?? -1; break;
        case 'ar_dev': va = a.ar_deviation ?? -99; vb = b.ar_deviation ?? -99; break;
        case 'ev': {
          va = calcWinEv(a, getWinOdds(oddsMap, race.race_id, a.umaban, a.odds)) ?? -1;
          vb = calcWinEv(b, getWinOdds(oddsMap, race.race_id, b.umaban, b.odds)) ?? -1;
          break;
        }
        case 'prob_p': va = a.pred_proba_p; vb = b.pred_proba_p; break;
        case 'prob_w': va = a.pred_proba_w ?? -1; vb = b.pred_proba_w ?? -1; break;
        case 'rating': va = a.kb_rating || 0; vb = b.kb_rating || 0; break;
        case 'finish': {
          const pa = dbRaceResult?.[a.umaban]?.finishPosition ?? jsonRaceResult?.[a.umaban]?.finish_position ?? 0;
          const pb = dbRaceResult?.[b.umaban]?.finishPosition ?? jsonRaceResult?.[b.umaban]?.finish_position ?? 0;
          va = pa > 0 ? pa : 999;
          vb = pb > 0 ? pb : 999;
          break;
        }
        default: /* umaban */ va = a.umaban; vb = b.umaban; break;
      }
      return (va - vb) * mul;
    });
    return arr;
  }, [race.entries, sort, oddsMap, race.race_id, dbRaceResult, jsonRaceResult]);

  return (
    <Card className="overflow-hidden">
      <CardHeader className="py-3 px-4 border-b bg-muted/30">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              href={getRaceLink(race)}
              target="_blank"
              className="text-lg font-bold hover:text-blue-600 hover:underline"
            >
              {race.race_number}R
            </Link>
            <Badge className={`text-[10px] ${getTrackBadgeClass(race.track_type)}`}>
              {getTrackLabel(race.track_type)}{race.distance}m
            </Badge>
            {race.grade && (
              <Badge variant="outline" className={`text-[10px] ${getGradeBadgeClass(race.grade)}`}>
                {race.grade}{race.age_class ? ` ${race.age_class}` : ''}
              </Badge>
            )}
            <span className="text-sm text-muted-foreground">{race.num_runners}頭</span>
          </div>
          <div className="flex items-center gap-2">
            {race.race_confidence != null && (
              <Badge variant="outline" className={`text-[10px] ${
                race.race_confidence >= 70 ? 'text-green-600 border-green-400 bg-green-50/50 dark:bg-green-900/20' :
                race.race_confidence >= 45 ? 'text-yellow-600 border-yellow-400 bg-yellow-50/50 dark:bg-yellow-900/20' :
                'text-red-600 border-red-400 bg-red-50/50 dark:bg-red-900/20'
              }`} title={`確信度: ${race.race_confidence.toFixed(1)} (P%差: ${((race.p_top1_gap ?? 0) * 100).toFixed(1)}pt, ARd幅: ${(race.ard_spread ?? 0).toFixed(1)})`}>
                {race.race_confidence >= 70 ? '◎' : race.race_confidence >= 45 ? '△' : '✕'}{race.race_confidence.toFixed(0)}
              </Badge>
            )}
            {race.closing_race_proba != null && race.closing_race_proba >= 0.10 && (
              <Badge variant="outline" className={`text-[10px] ${
                race.closing_race_proba >= 0.18 ? 'text-red-600 border-red-400 bg-red-50/50 dark:bg-red-900/20' :
                race.closing_race_proba >= 0.13 ? 'text-orange-600 border-orange-300 bg-orange-50/50 dark:bg-orange-900/20' :
                'text-sky-600 border-sky-300'
              }`} title={`差し決着度: ${(race.closing_race_proba * 100).toFixed(1)}%`}>
                差し {(race.closing_race_proba * 100).toFixed(0)}%
              </Badge>
            )}
            {vbEntries.length > 0 && (
              <Badge variant="outline" className="text-amber-600 border-amber-300">
                VB {vbEntries.length}頭
              </Badge>
            )}
            <Link
              href={getRaceLink(race)}
              target="_blank"
              className="text-xs text-blue-600 hover:underline"
            >
              詳細 →
            </Link>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-gray-50 dark:bg-gray-800/50 text-xs">
                <SortTh sortKey="umaban" sort={sort} setSort={setSort} className="px-2 py-1.5 text-center border-b w-10">番</SortTh>
                <th className="px-2 py-1.5 text-left border-b min-w-[100px]">馬名</th>
                <th className="px-2 py-1.5 text-center border-b w-10" title="競馬ブック本紙予想の印">本紙</th>
                <th className="px-2 py-1.5 text-center border-b w-8" title="TARGET 馬印1（自分の印）">My</th>
                <SortTh sortKey="rank_p" sort={sort} setSort={setSort} className="px-2 py-1.5 text-center border-b w-12" title="好走モデル(P)の順位">P順</SortTh>
                <SortTh sortKey="odds_rank" sort={sort} setSort={setSort} className="px-2 py-1.5 text-center border-b w-10" title="オッズ順人気">人</SortTh>
                <SortTh sortKey="odds" sort={sort} setSort={setSort} className="px-2 py-1.5 text-center border-b w-14" title="単勝オッズ（DB最新）">オッズ</SortTh>
                <SortTh sortKey="gap" sort={sort} setSort={setSort} className="px-2 py-1.5 text-center border-b w-12 bg-amber-50/50 dark:bg-amber-900/20 font-bold" title="Gap（主軸） = 人気順位 - VR。VB判定の主フィルター">Gap</SortTh>
                <SortTh sortKey="ev" sort={sort} setSort={setSort} className="px-2 py-1.5 text-center border-b w-14" title="単勝EV = calibrated P(win) × 単勝オッズ">EV</SortTh>
                <SortTh sortKey="margin" sort={sort} setSort={setSort} className="px-2 py-1.5 text-center border-b w-14 bg-teal-50/50 dark:bg-teal-900/20" title="AR (Aura Rating) — グレード補正済みの絶対能力指数（IDMスケール）">AR</SortTh>
                <SortTh sortKey="idm" sort={sort} setSort={setSort} className="px-2 py-1.5 text-center border-b w-14 bg-teal-50/30 dark:bg-teal-900/10" title="JRDB 事前IDM — 今回レースのJRDB予測値">IDM</SortTh>
                <SortTh sortKey="ar_dev" sort={sort} setSort={setSort} className="px-2 py-1.5 text-center border-b w-12 bg-teal-50/30 dark:bg-teal-900/10" title="AR偏差値 — レース内相対評価（mean=50, std=10）">ARd</SortTh>
                <SortTh sortKey="prob_p" sort={sort} setSort={setSort} className="px-2 py-1.5 text-center border-b w-14" title="好走モデル(P)の3着内確率（%）">P%</SortTh>
                <SortTh sortKey="prob_w" sort={sort} setSort={setSort} className="px-2 py-1.5 text-center border-b w-14 bg-emerald-50/50 dark:bg-emerald-900/20" title="勝利モデル(W)の勝率予測（%）">W%</SortTh>
                <SortTh sortKey="rating" sort={sort} setSort={setSort} className="px-2 py-1.5 text-center border-b w-14" title="BR (Book Rating) — 競馬ブックレイティング">BR</SortTh>
                <th className="px-2 py-1.5 text-center border-b w-10" title="競馬ブック調教評価">調</th>
                <th className="px-2 py-1.5 text-center border-b w-10" title="厩舎談話NLPスコア（仕上がり度 -3〜+3）">談</th>
                {hasResults && <SortTh sortKey="finish" sort={sort} setSort={setSort} className="px-2 py-1.5 text-center border-b w-12" title="確定着順">着順</SortTh>}
                {hasResults && <th className="px-2 py-1.5 text-center border-b w-16" title="単勝払い戻し">単払</th>}
                {hasResults && <th className="px-2 py-1.5 text-center border-b w-16" title="複勝払い戻し">複払</th>}
              </tr>
            </thead>
            <tbody>
              {sortedEntries.map((entry) => {
                const isVB = entry.is_value_bet;
                const winOdds = getWinOdds(oddsMap, race.race_id, entry.umaban, entry.odds);
                const ev = calcWinEv(entry, winOdds);
                const dbEntry = dbRaceResult?.[entry.umaban];
                const jsonEntry = jsonRaceResult?.[entry.umaban];
                const finishPos = dbEntry?.finishPosition ?? jsonEntry?.finish_position ?? 0;
                return (
                  <tr
                    key={entry.umaban}
                    className={`border-b transition-colors ${
                      hasResults && finishPos === 1 ? 'bg-amber-50/60 dark:bg-amber-900/15' :
                      hasResults && finishPos > 0 && finishPos <= 3 ? 'bg-green-50/30 dark:bg-green-900/5' :
                      isVB ? getGapBg(getLiveGap(entry)) : ''
                    } hover:bg-blue-50/50 dark:hover:bg-blue-900/10`}
                  >
                    <td className="px-2 py-1 text-center font-mono text-xs">{entry.umaban}</td>
                    <td className="px-2 py-1 font-bold text-xs">
                      {entry.horse_name}
                      {isVB && <span className="ml-1 text-amber-500 text-[10px]">VB</span>}
                    </td>
                    <td className={`px-2 py-1 text-center ${getMarkColor(entry.kb_mark)}`}>
                      {entry.kb_mark || '-'}
                    </td>
                    {(() => {
                      const myMark = targetMarks?.[entry.umaban];
                      return (
                        <td className={`px-2 py-1 text-center font-bold text-xs ${myMark ? 'text-purple-700 dark:text-purple-300' : 'text-gray-300'}`}>
                          {myMark || '-'}
                        </td>
                      );
                    })()}
                    <td className={`px-2 py-1 text-center font-mono text-xs ${entry.rank_p <= 3 ? 'font-bold text-purple-600' : ''}`}>
                      {entry.rank_p}
                    </td>
                    <td className="px-2 py-1 text-center font-mono text-xs">{getLiveOddsRank(entry.umaban, entry.odds_rank) || '-'}</td>
                    <td className="px-2 py-1 text-center font-mono text-xs font-bold">
                      {winOdds ? winOdds.toFixed(1) : '-'}
                    </td>
                    {(() => {
                      const liveGap = getLiveGap(entry);
                      return (
                        <td className={`px-2 py-1 text-center font-mono text-xs font-bold bg-amber-50/30 dark:bg-amber-900/10 ${getGapColor(liveGap)}`} title="Gap（主軸）">
                          {Number.isNaN(liveGap) ? '-' : liveGap > 0 ? `+${liveGap}` : liveGap === 0 ? '0' : liveGap}
                        </td>
                      );
                    })()}
                    <td className={`px-2 py-1 text-center font-mono text-xs ${getEvColor(ev)}`}>
                      {ev !== null ? ev.toFixed(2) : '-'}
                    </td>
                    <td className={`px-2 py-1 text-center font-mono text-xs bg-teal-50/30 dark:bg-teal-900/10 ${getArColor(entry.predicted_margin)}`}>
                      {entry.predicted_margin != null ? entry.predicted_margin.toFixed(1) : '-'}
                    </td>
                    <td className={`px-2 py-1 text-center font-mono text-xs bg-teal-50/20 dark:bg-teal-900/5 ${getArColor(entry.jrdb_idm != null && entry.jrdb_idm > 0 ? entry.jrdb_idm : null)}`} title="JRDB 事前IDM">
                      {entry.jrdb_idm != null && entry.jrdb_idm > 0 ? entry.jrdb_idm.toFixed(1) : '-'}
                    </td>
                    <td className={`px-2 py-1 text-center font-mono text-xs bg-teal-50/20 dark:bg-teal-900/5 ${getArdColor(entry.ar_deviation)}`} title="AR偏差値">
                      {entry.ar_deviation != null ? entry.ar_deviation.toFixed(0) : '-'}
                    </td>
                    <td className="px-2 py-1 text-center font-mono text-xs">{(entry.pred_proba_p * 100).toFixed(1)}</td>
                    <td className={`px-2 py-1 text-center font-mono text-xs bg-emerald-50/30 dark:bg-emerald-900/10 ${entry.rank_w != null && entry.rank_w <= 3 ? 'font-bold text-emerald-600' : ''}`}>
                      {entry.pred_proba_w != null ? (entry.pred_proba_w * 100).toFixed(1) : '-'}
                    </td>
                    <td className="px-2 py-1 text-center font-mono text-xs">{entry.kb_rating > 0 ? entry.kb_rating.toFixed(1) : '-'}</td>
                    <td className="px-2 py-1 text-center text-xs">{entry.kb_training_arrow}</td>
                    <td className={`px-2 py-1 text-center font-mono text-xs ${entry.comment_has_stable ? getCommentColor(entry.comment_stable_condition ?? 0) : 'text-gray-300'}`} title={getCommentTooltip(entry)}>
                      {entry.comment_has_stable ? (entry.comment_stable_condition ?? 0) > 0 ? `+${entry.comment_stable_condition}` : `${entry.comment_stable_condition ?? 0}` : '-'}
                    </td>
                    {hasResults && (
                      <td className={`px-2 py-1 text-center font-mono text-xs ${finishPos > 0 ? getFinishColor(finishPos) : 'text-gray-300'}`}>
                        {finishPos > 0 ? finishPos : '-'}
                      </td>
                    )}
                    {hasResults && (() => {
                      const isWin = finishPos === 1 && dbEntry?.confirmedWinOdds;
                      return (
                        <td className={`px-2 py-1 text-center font-mono text-xs ${isWin ? 'text-red-600 font-bold' : ''}`}>
                          {isWin ? `¥${Math.round(dbEntry!.confirmedWinOdds * 100).toLocaleString()}` : ''}
                        </td>
                      );
                    })()}
                    {hasResults && (() => {
                      const placeLimit = getPlaceLimit(race.num_runners);
                      const isPlaceHit = finishPos > 0 && placeLimit > 0 && finishPos <= placeLimit;
                      const hasPlaceOdds = isPlaceHit && dbEntry?.confirmedPlaceOddsMin;
                      return (
                        <td className={`px-2 py-1 text-center font-mono text-xs ${hasPlaceOdds ? 'text-blue-600 font-bold' : ''}`}>
                          {hasPlaceOdds ? `¥${Math.round(dbEntry!.confirmedPlaceOddsMin! * 100).toLocaleString()}` : ''}
                        </td>
                      );
                    })()}
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
