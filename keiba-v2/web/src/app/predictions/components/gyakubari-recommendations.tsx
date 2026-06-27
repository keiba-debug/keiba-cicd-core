'use client';

/**
 * gyakubari-recommendations.tsx — 逆張り単（gap単勝）の推奨カード (Session 178)
 *
 * 自動投票の ★逆張り単スリーブ★ が拾う買い目を推奨画面に「一級の推奨」として表示する
 * （本命EV単カードと 1:1 で並べ、自動投票の2スリーブと画面を対応させる）。
 * 選定は表示専用の `selectGapTansho`（select_gap_tansho の TS 忠実移植）。amount は出さない
 * （自動投票では残高×比率で1点・サイジングはスリーブ側の責務）。
 */
import { useMemo } from 'react';
import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { PredictionRace, RaceResultsMap } from '@/lib/data/predictions-reader';
import type { OddsMap, DbResultsMap } from '../lib/types';
import { selectGapTansho, gapClassLabel, type GapTanshoPick } from '../lib/gap-tansho';
import { getWinOdds, getEvColor, getFinishColor, getPlaceLimit } from '../lib/helpers';

interface GyakubariRecommendationsProps {
  races: PredictionRace[];
  oddsMap: OddsMap;
  dbResults?: DbResultsMap;
  results?: RaceResultsMap;
}

interface GyakubariRow extends GapTanshoPick {
  race: PredictionRace;
}

export function GyakubariRecommendations({
  races, oddsMap, dbResults, results,
}: GyakubariRecommendationsProps) {
  const rows = useMemo<GyakubariRow[]>(() => {
    const out: GyakubariRow[] = [];
    for (const race of races) {
      for (const pick of selectGapTansho(race)) {
        out.push({ ...pick, race });
      }
    }
    // 信号強度(EV)降順
    out.sort((a, b) => b.winEv - a.winEv);
    return out;
  }, [races]);

  if (rows.length === 0) return null; // 候補なしの日はカード自体を出さない

  return (
    <Card id="section-gyakubari" className="mb-8 border-amber-200 dark:border-amber-800">
      <CardHeader className="pb-2 bg-gradient-to-r from-amber-50 to-yellow-50 dark:from-amber-950 dark:to-yellow-950">
        <CardTitle className="text-lg flex items-center gap-2 flex-wrap">
          <span className="px-2 py-0.5 rounded bg-amber-500 text-white text-sm font-bold">逆張り単</span>
          <span className="text-sm font-normal text-muted-foreground hidden sm:inline"
                title="市場が見限った(人気薄の)馬を、AIの勝率評価が上回る「過小評価」のときだけ単勝で買う高配狙い。gap≥5(AI上位なのに人気薄)を未勝利・条件・重賞に限定。自動投票の逆張り単スリーブと同条件。">
            AI評価＞人気の過小評価馬の単勝（高配狙い）
          </span>
          <span className="text-sm">({rows.length}件)</span>
          <Link href="/analysis/edge-validation" target="_blank"
                className="ml-auto text-xs text-amber-700 dark:text-amber-300 hover:underline">
            検証 →
          </Link>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-amber-50/50 dark:bg-amber-900/20 text-xs">
                <th className="px-2 py-1.5 text-left border-b">レース</th>
                <th className="px-2 py-1.5 text-center border-b w-12">クラス</th>
                <th className="px-2 py-1.5 text-left border-b min-w-[120px]">馬</th>
                <th className="px-2 py-1.5 text-center border-b w-12" title="gap = 人気順 - W順 (AI上位なのに人気薄)">gap</th>
                <th className="px-2 py-1.5 text-center border-b w-14" title="単勝オッズ(最新)">オッズ</th>
                <th className="px-2 py-1.5 text-center border-b w-14" title="単勝EV = P(win) × オッズ">EV</th>
                <th className="px-2 py-1.5 text-center border-b w-12">着順</th>
                <th className="px-2 py-1.5 text-center border-b w-16">単払</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const liveOdds = getWinOdds(oddsMap, r.race.race_id, r.umaban, r.odds);
                const dbEntry = dbResults?.[r.race.race_id]?.[r.umaban];
                const jsonEntry = results?.[r.race.race_id]?.[r.umaban];
                const finishPos = dbEntry?.finishPosition ?? jsonEntry?.finish_position ?? 0;
                const placeLimit = getPlaceLimit(r.race.num_runners);
                const isWin = finishPos === 1;
                return (
                  <tr key={`${r.race.race_id}-${r.umaban}`}
                      className={`border-b ${isWin ? 'bg-amber-50/60 dark:bg-amber-900/15'
                        : finishPos > 0 && finishPos <= placeLimit ? 'bg-green-50/30 dark:bg-green-900/5' : ''}`}>
                    <td className="px-2 py-1 whitespace-nowrap">
                      <Link href={`/odds-race/${r.race.race_id}`} target="_blank"
                            className="font-bold hover:text-amber-700 hover:underline">
                        {r.race.venue_name} {r.race.race_number}R
                      </Link>
                    </td>
                    <td className="px-2 py-1 text-center">
                      <Badge variant="outline" className="text-[10px] border-amber-400 text-amber-700 dark:text-amber-300">
                        {gapClassLabel(r.cls)}
                      </Badge>
                    </td>
                    <td className="px-2 py-1 font-bold text-xs">
                      <span className="font-mono mr-1">{r.umaban}</span>{r.horseName}
                    </td>
                    <td className="px-2 py-1 text-center font-mono text-xs font-bold text-amber-700 dark:text-amber-300">
                      +{r.gap}
                    </td>
                    <td className="px-2 py-1 text-center font-mono text-xs font-bold">
                      {liveOdds ? liveOdds.toFixed(1) : r.odds.toFixed(1)}
                    </td>
                    <td className={`px-2 py-1 text-center font-mono text-xs ${getEvColor(r.winEv)}`}>
                      {r.winEv.toFixed(2)}
                    </td>
                    <td className={`px-2 py-1 text-center font-mono text-xs ${finishPos > 0 ? getFinishColor(finishPos) : 'text-gray-300'}`}>
                      {finishPos > 0 ? finishPos : '-'}
                    </td>
                    <td className={`px-2 py-1 text-center font-mono text-xs ${isWin && dbEntry?.confirmedWinOdds ? 'text-red-600 font-bold' : ''}`}>
                      {isWin && dbEntry?.confirmedWinOdds ? `¥${Math.round(dbEntry.confirmedWinOdds * 100).toLocaleString()}` : ''}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="px-3 py-2 text-[11px] text-muted-foreground border-t">
          ※ 自動投票では各候補を「残高×比率」で1点ずつ購入します（金額はスリーブ側で決定）。
          本命EV単と同一レースで重なった場合は、レース合算上限を超える分だけ逆張り単を見送ります（案A 二段化）。
        </p>
      </CardContent>
    </Card>
  );
}
