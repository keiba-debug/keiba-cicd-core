'use client';

import { useState, useMemo } from 'react';
import Link from 'next/link';
import { Card, CardContent } from '@/components/ui/card';
import type { DangerHorseEntry, SortState } from '../lib/types';
import { getFinishColor, getPlaceLimit, getTrackBadgeClass, getTrackLabel, getRaceLink, getArdColor, SortTh } from '../lib/helpers';

interface DangerResultsProps {
  dangerHorses: DangerHorseEntry[];
  getFinishPos: (raceId: string, umaban: number) => number;
}

type Verdict = 'correct' | 'incorrect' | 'pending';

function getVerdict(finishPos: number, numRunners: number): Verdict {
  if (finishPos <= 0) return 'pending';
  const placeLimit = getPlaceLimit(numRunners);
  return finishPos <= placeLimit ? 'incorrect' : 'correct';
}

export function DangerResults({ dangerHorses, getFinishPos }: DangerResultsProps) {
  const [sort, setSort] = useState<SortState>({ key: 'race_number', dir: 'asc' });

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

  const sorted = useMemo(() => {
    const arr = [...dangerHorses];
    const dir = sort.dir === 'asc' ? 1 : -1;
    arr.sort((a, b) => {
      let cmp = 0;
      switch (sort.key) {
        case 'race':
          cmp = a.race.race_id.localeCompare(b.race.race_id);
          break;
        case 'race_number':
          cmp = a.race.race_number - b.race.race_number || a.race.race_id.localeCompare(b.race.race_id);
          break;
        case 'umaban':
          cmp = a.entry.umaban - b.entry.umaban;
          break;
        case 'odds_rank':
          cmp = a.oddsRank - b.oddsRank;
          break;
        case 'ar_dev':
          cmp = a.ard - b.ard;
          break;
        case 'prob_v':
          cmp = a.predV - b.predV;
          break;
        case 'odds':
          cmp = a.odds - b.odds;
          break;
        case 'finish': {
          const fA = getFinishPos(a.race.race_id, a.entry.umaban) || 99;
          const fB = getFinishPos(b.race.race_id, b.entry.umaban) || 99;
          cmp = fA - fB;
          break;
        }
        case 'verdict': {
          const order = { correct: 0, incorrect: 1, pending: 2 };
          const vA = getVerdict(getFinishPos(a.race.race_id, a.entry.umaban), a.race.num_runners);
          const vB = getVerdict(getFinishPos(b.race.race_id, b.entry.umaban), b.race.num_runners);
          cmp = order[vA] - order[vB];
          break;
        }
      }
      return cmp * dir;
    });
    return arr;
  }, [dangerHorses, sort, getFinishPos]);

  if (dangerHorses.length === 0) return null;

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
                  <SortTh sortKey="race" sort={sort} setSort={setSort} className="px-2 py-2 text-left border">場</SortTh>
                  <SortTh sortKey="race_number" sort={sort} setSort={setSort} className="px-2 py-2 text-center border">R</SortTh>
                  <th className="px-2 py-2 text-center border">馬場</th>
                  <SortTh sortKey="umaban" sort={sort} setSort={setSort} className="px-2 py-2 text-center border">馬番</SortTh>
                  <th className="px-2 py-2 text-left border">馬名</th>
                  <SortTh sortKey="odds_rank" sort={sort} setSort={setSort} className="px-2 py-2 text-center border">人気</SortTh>
                  <SortTh sortKey="odds" sort={sort} setSort={setSort} className="px-2 py-2 text-center border bg-amber-50/50 dark:bg-amber-900/20" title="単勝オッズ (≤8.0)">オッズ</SortTh>
                  <SortTh sortKey="ar_dev" sort={sort} setSort={setSort} className="px-2 py-2 text-center border bg-teal-50/50 dark:bg-teal-900/20" title="AR偏差値 (<50)">ARd</SortTh>
                  <SortTh sortKey="prob_v" sort={sort} setSort={setSort} className="px-2 py-2 text-center border bg-red-50/50 dark:bg-red-900/20" title="好走確率 V% (<15%)">V%</SortTh>
                  <SortTh sortKey="finish" sort={sort} setSort={setSort} className="px-2 py-2 text-center border">着順</SortTh>
                  <SortTh sortKey="verdict" sort={sort} setSort={setSort} className="px-2 py-2 text-center border">判定</SortTh>
                </tr>
              </thead>
              <tbody>
                {sorted.map((dh) => {
                  const finishPos = getFinishPos(dh.race.race_id, dh.entry.umaban);
                  const verdict = getVerdict(finishPos, dh.race.num_runners);

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
                      <td className="px-2 py-1.5 border text-center font-mono text-orange-600 font-bold">{dh.oddsRank > 0 ? dh.oddsRank : '-'}</td>
                      <td className="px-2 py-1.5 border text-center font-mono text-xs font-bold">{dh.odds.toFixed(1)}</td>
                      <td className={`px-2 py-1.5 border text-center font-mono text-xs ${getArdColor(dh.ard)}`}>
                        {dh.ard.toFixed(0)}
                      </td>
                      <td className="px-2 py-1.5 border text-center font-mono text-xs text-red-500 font-bold">
                        {(dh.predV * 100).toFixed(1)}
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
