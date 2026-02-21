'use client';

import Link from 'next/link';
import { Card, CardContent } from '@/components/ui/card';
import type { DangerHorseEntry, OddsMap, DbResultsMap } from '../lib/types';
import type { RaceResultsMap } from '@/lib/data/predictions-reader';
import { getWinOdds, getFinishColor, getPlaceLimit, getTrackBadgeClass, getTrackLabel, getRaceLink } from '../lib/helpers';

interface DangerResultsProps {
  dangerHorses: DangerHorseEntry[];
  oddsMap: OddsMap;
  dbResults: DbResultsMap;
  results?: RaceResultsMap;
  getFinishPos: (raceId: string, umaban: number) => number;
}

type Verdict = 'correct' | 'incorrect' | 'pending';

function getVerdict(finishPos: number, numRunners: number): Verdict {
  if (finishPos <= 0) return 'pending';
  const placeLimit = getPlaceLimit(numRunners);
  return finishPos <= placeLimit ? 'incorrect' : 'correct';
}

export function DangerResults({ dangerHorses, oddsMap, dbResults, results, getFinishPos }: DangerResultsProps) {
  if (dangerHorses.length === 0) return null;

  // サマリー集計
  let correct = 0, incorrect = 0, pending = 0;
  for (const dh of dangerHorses) {
    const v = getVerdict(getFinishPos(dh.race.race_id, dh.entry.umaban), dh.race.num_runners);
    if (v === 'correct') correct++;
    else if (v === 'incorrect') incorrect++;
    else pending++;
  }
  const finished = correct + incorrect;
  const accuracy = finished > 0 ? (correct / finished * 100) : null;
  const raceCount = new Set(dangerHorses.map(d => d.race.race_id)).size;

  return (
    <div id="section-danger" className="scroll-mt-28">
      <Card>
        <CardContent className="pt-6 pb-4">
          {/* ヘッダー */}
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-bold flex items-center gap-2">
              危険な人気馬
              <span className="text-sm font-normal text-muted-foreground">
                {dangerHorses.length}頭 ({raceCount}R中)
              </span>
            </h3>
            {finished > 0 && (
              <div className="flex items-center gap-3 text-sm">
                <span>
                  的中{' '}
                  <span className={`font-bold ${accuracy != null && accuracy >= 50 ? 'text-green-600' : 'text-red-500'}`}>
                    {correct}/{finished}
                  </span>
                </span>
                {accuracy != null && (
                  <span className={`font-bold text-lg ${accuracy >= 50 ? 'text-green-600' : 'text-red-500'}`}>
                    {accuracy.toFixed(0)}%
                  </span>
                )}
                {pending > 0 && (
                  <span className="text-muted-foreground text-xs">残{pending}頭</span>
                )}
              </div>
            )}
          </div>

          {/* テーブル */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-orange-50/60 dark:bg-orange-900/20 text-xs">
                  <th className="px-2 py-2 text-left border">場</th>
                  <th className="px-2 py-2 text-center border">R</th>
                  <th className="px-2 py-2 text-center border">馬場</th>
                  <th className="px-2 py-2 text-center border">馬番</th>
                  <th className="px-2 py-2 text-left border">馬名</th>
                  <th className="px-2 py-2 text-center border">人気</th>
                  <th className="px-2 py-2 text-center border">VR</th>
                  <th className="px-2 py-2 text-center border">Gap</th>
                  <th className="px-2 py-2 text-center border">オッズ</th>
                  <th className="px-2 py-2 text-center border">着順</th>
                  <th className="px-2 py-2 text-center border">判定</th>
                </tr>
              </thead>
              <tbody>
                {dangerHorses.map((dh) => {
                  const finishPos = getFinishPos(dh.race.race_id, dh.entry.umaban);
                  const verdict = getVerdict(finishPos, dh.race.num_runners);
                  const winOdds = getWinOdds(oddsMap, dh.race.race_id, dh.entry.umaban, dh.entry.odds);
                  const dbEntry = dbResults[dh.race.race_id]?.[dh.entry.umaban];

                  return (
                    <tr
                      key={`${dh.race.race_id}-${dh.entry.umaban}`}
                      className={`border-b ${
                        verdict === 'correct'
                          ? 'bg-green-50/50 dark:bg-green-900/10'
                          : verdict === 'incorrect'
                            ? 'bg-red-50/50 dark:bg-red-900/10'
                            : ''
                      }`}
                    >
                      <td className="px-2 py-1.5 border text-xs">
                        <Link href={getRaceLink(dh.race)} target="_blank" className="hover:text-blue-600 hover:underline">
                          {dh.race.venue_name}
                        </Link>
                      </td>
                      <td className="px-2 py-1.5 border text-center font-bold">{dh.race.race_number}</td>
                      <td className="px-2 py-1.5 border text-center">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] ${getTrackBadgeClass(dh.race.track_type)}`}>
                          {getTrackLabel(dh.race.track_type)}{dh.race.distance}
                        </span>
                      </td>
                      <td className="px-2 py-1.5 border text-center font-mono">{dh.entry.umaban}</td>
                      <td className="px-2 py-1.5 border font-bold text-xs">{dh.entry.horse_name}</td>
                      <td className="px-2 py-1.5 border text-center font-mono text-orange-600 font-bold">{dh.oddsRank}</td>
                      <td className="px-2 py-1.5 border text-center font-mono text-blue-600">{dh.rankV}</td>
                      <td className="px-2 py-1.5 border text-center font-mono text-red-600 font-bold">+{dh.dangerScore}</td>
                      <td className="px-2 py-1.5 border text-center font-mono text-xs">
                        {dbEntry ? dbEntry.confirmedWinOdds.toFixed(1) : winOdds ? winOdds.toFixed(1) : '-'}
                      </td>
                      <td className={`px-2 py-1.5 border text-center font-mono font-bold ${finishPos > 0 ? getFinishColor(finishPos) : 'text-gray-300'}`}>
                        {finishPos > 0 ? finishPos : '-'}
                      </td>
                      <td className="px-2 py-1.5 border text-center">
                        {verdict === 'correct' && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300">
                            圏外 ✓
                          </span>
                        )}
                        {verdict === 'incorrect' && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300">
                            複勝圏
                          </span>
                        )}
                        {verdict === 'pending' && (
                          <span className="px-2 py-0.5 rounded text-[10px] bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400">
                            未確定
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
