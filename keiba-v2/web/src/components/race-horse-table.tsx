'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import useSWR from 'swr';
import { formatTrainerName } from '@/types/race-data';

// --- 型定義 ---

export interface HorseData {
  waku: number;
  umaban: number;
  name: string;
  sex: string;
  age: number;
  weight: number;      // 斤量
  jockey: string;
  trainer: string;
  odds: number;
  popularity: number;
  // v4 JSON追加フィールド（オプショナル）
  horseWeight?: number;      // 馬体重
  horseWeightDiff?: number | null; // 馬体重増減
  kettoNum?: string;         // horse_id (馬リンク用)
  finishPosition?: number;   // 着順
  time?: string;             // タイム
  last3f?: number;           // 上がり3F
}

interface DbHorseOdds {
  umaban: number;
  winOdds: number | null;
  placeOddsMin: number | null;
  placeOddsMax: number | null;
  ninki: number | null;
  firstWinOdds: number | null;
  oddsTrend: 'up' | 'down' | 'stable' | null;
}

interface DbOddsResponse {
  raceId: string;
  source: 'timeseries' | 'final' | 'none';
  snapshotTime: string | null;
  snapshotCount: number;
  horses: DbHorseOdds[];
}

// --- ヘルパー ---

const getWakuColor = (waku: number) => {
  const colors: Record<number, { bg: string; text: string; border: string }> = {
    1: { bg: 'bg-white', text: 'text-gray-900', border: 'border-gray-300' },
    2: { bg: 'bg-gray-900', text: 'text-white', border: 'border-gray-900' },
    3: { bg: 'bg-red-600', text: 'text-white', border: 'border-red-600' },
    4: { bg: 'bg-blue-600', text: 'text-white', border: 'border-blue-600' },
    5: { bg: 'bg-yellow-400', text: 'text-gray-900', border: 'border-yellow-400' },
    6: { bg: 'bg-green-600', text: 'text-white', border: 'border-green-600' },
    7: { bg: 'bg-orange-500', text: 'text-white', border: 'border-orange-500' },
    8: { bg: 'bg-pink-500', text: 'text-white', border: 'border-pink-500' },
  };
  return colors[waku] || colors[1];
};

function formatSnapshotTime(raw: string | null): string {
  if (!raw || raw.length < 8) return '';
  // HAPPYO_TSUKIHI_JIFUN format: "MMDDHHmm" (8桁)
  const hh = raw.slice(4, 6);
  const mm = raw.slice(6, 8);
  return `${hh}:${mm}`;
}

const fetcher = (url: string) => fetch(url).then((r) => r.json());

// --- コンポーネント ---

interface RaceHorseTableProps {
  horses: HorseData[];
  raceId: string;
  isToday?: boolean;
}

export function RaceHorseTable({ horses, raceId, isToday = false }: RaceHorseTableProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // DBオッズをSWRで取得（ポーリング: 当日は30秒、それ以外は無効）
  const { data: dbOdds } = useSWR<DbOddsResponse>(
    mounted ? `/api/odds/db-latest?raceId=${raceId}` : null,
    fetcher,
    {
      refreshInterval: isToday ? 30000 : 0,
      revalidateOnFocus: isToday,
      dedupingInterval: 10000,
    }
  );

  const hasDbOdds = dbOdds && dbOdds.source !== 'none' && dbOdds.horses.length > 0;

  // DBオッズをマップ化
  const dbOddsMap = new Map<number, DbHorseOdds>();
  if (hasDbOdds) {
    for (const h of dbOdds.horses) {
      dbOddsMap.set(h.umaban, h);
    }
  }

  // v4 JSON追加データの有無チェック
  const hasHorseWeight = horses.some(h => h.horseWeight && h.horseWeight > 0);
  const hasResult = horses.some(h => h.finishPosition && h.finishPosition > 0);

  return (
    <div className="bg-card rounded-lg border overflow-hidden mt-6 mb-6">
      <div className="bg-gradient-to-r from-gray-800 to-gray-700 text-white px-4 py-3 flex items-center justify-between">
        <h2 className="font-bold text-lg">出走馬一覧</h2>
        {hasDbOdds && (
          <div className="flex items-center gap-2 text-xs text-gray-300">
            {dbOdds.source === 'timeseries' && dbOdds.snapshotTime && (
              <>
                <span className="inline-block w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                <span>{formatSnapshotTime(dbOdds.snapshotTime)}更新</span>
                <span className="text-gray-500">({dbOdds.snapshotCount}回)</span>
              </>
            )}
            {dbOdds.source === 'final' && (
              <span className="text-yellow-300">確定オッズ</span>
            )}
          </div>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-100 border-b">
              <th className="px-2 py-2.5 text-center font-bold w-10">枠</th>
              <th className="px-2 py-2.5 text-center font-bold w-10">番</th>
              <th className="px-3 py-2.5 text-left font-bold min-w-[140px]">馬名</th>
              <th className="px-2 py-2.5 text-center font-bold w-14">性齢</th>
              <th className="px-2 py-2.5 text-center font-bold w-14">斤量</th>
              <th className="px-3 py-2.5 text-left font-bold min-w-[80px]">騎手</th>
              <th className="px-3 py-2.5 text-left font-bold min-w-[80px]">調教師</th>
              {hasHorseWeight && (
                <th className="px-2 py-2.5 text-center font-bold w-20">馬体重</th>
              )}
              <th className="px-2 py-2.5 text-right font-bold w-16">単勝</th>
              {hasDbOdds && (
                <th className="px-2 py-2.5 text-right font-bold w-24">複勝</th>
              )}
              <th className="px-2 py-2.5 text-center font-bold w-10">人</th>
              {hasResult && (
                <>
                  <th className="px-2 py-2.5 text-center font-bold w-10">着</th>
                  <th className="px-2 py-2.5 text-right font-bold w-16">タイム</th>
                  <th className="px-2 py-2.5 text-right font-bold w-14">上3F</th>
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {horses.map((horse, index) => {
              const wakuColor = getWakuColor(horse.waku);
              const db = dbOddsMap.get(horse.umaban);
              const displayOdds = db?.winOdds ?? horse.odds;
              const displayNinki = db?.ninki ?? horse.popularity;

              return (
                <tr
                  key={horse.umaban}
                  className={`border-b transition-colors hover:bg-blue-50/50 ${
                    index % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'
                  }`}
                >
                  {/* 枠番 */}
                  <td className="px-2 py-2 text-center">
                    <span
                      className={`inline-flex items-center justify-center w-7 h-7 rounded-sm text-xs font-bold border ${wakuColor.bg} ${wakuColor.text} ${wakuColor.border}`}
                    >
                      {horse.waku}
                    </span>
                  </td>
                  {/* 馬番 */}
                  <td className="px-2 py-2 text-center">
                    <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-white border-2 border-gray-300 text-xs font-bold">
                      {horse.umaban}
                    </span>
                  </td>
                  {/* 馬名 */}
                  <td className="px-3 py-2">
                    <Link
                      href={`/horses/${horse.kettoNum || horse.name}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-bold text-gray-900 hover:text-blue-600 hover:underline transition-colors"
                    >
                      {horse.name}
                    </Link>
                  </td>
                  {/* 性齢 */}
                  <td className="px-2 py-2 text-center text-gray-600">
                    {horse.sex}
                    {horse.age}
                  </td>
                  {/* 斤量 */}
                  <td className="px-2 py-2 text-center font-mono text-gray-700">
                    {horse.weight.toFixed(1)}
                  </td>
                  {/* 騎手 */}
                  <td className="px-3 py-2">
                    <Link
                      href={`/jockeys/${horse.jockey}`}
                      className="text-gray-700 hover:text-blue-600 hover:underline transition-colors"
                    >
                      {horse.jockey}
                    </Link>
                  </td>
                  {/* 調教師 */}
                  <td className="px-3 py-2 text-gray-600">{formatTrainerName(horse.trainer)}</td>
                  {/* 馬体重 */}
                  {hasHorseWeight && (
                    <td className="px-2 py-2 text-center font-mono text-xs">
                      {horse.horseWeight ? (
                        <span>
                          {horse.horseWeight}
                          {horse.horseWeightDiff != null && (
                            <span className={`ml-0.5 ${
                              horse.horseWeightDiff > 0 ? 'text-red-500' :
                              horse.horseWeightDiff < 0 ? 'text-blue-500' :
                              'text-gray-400'
                            }`}>
                              ({horse.horseWeightDiff > 0 ? '+' : ''}{horse.horseWeightDiff})
                            </span>
                          )}
                        </span>
                      ) : '-'}
                    </td>
                  )}
                  {/* 単勝オッズ */}
                  <td className="px-2 py-2 text-right font-mono">
                    <div className="flex items-center justify-end gap-1">
                      {db?.oddsTrend && (
                        <span
                          className={`text-[10px] ${
                            db.oddsTrend === 'down'
                              ? 'text-red-500'
                              : db.oddsTrend === 'up'
                                ? 'text-blue-500'
                                : 'text-gray-400'
                          }`}
                        >
                          {db.oddsTrend === 'down' ? '\u25BC' : db.oddsTrend === 'up' ? '\u25B2' : '-'}
                        </span>
                      )}
                      <span
                        className={`font-bold ${
                          displayOdds < 5
                            ? 'text-red-600'
                            : displayOdds < 10
                              ? 'text-orange-600'
                              : 'text-gray-700'
                        }`}
                      >
                        {displayOdds > 0 ? displayOdds.toFixed(1) : '-'}
                      </span>
                    </div>
                  </td>
                  {/* 複勝オッズ（DB取得時のみ表示） */}
                  {hasDbOdds && (
                    <td className="px-2 py-2 text-right font-mono text-xs text-gray-500">
                      {db?.placeOddsMin != null ? (
                        db.placeOddsMin === db.placeOddsMax
                          ? db.placeOddsMin.toFixed(1)
                          : `${db.placeOddsMin.toFixed(1)}-${db.placeOddsMax!.toFixed(1)}`
                      ) : (
                        '-'
                      )}
                    </td>
                  )}
                  {/* 人気 */}
                  <td className="px-2 py-2 text-center">
                    <span
                      className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold ${
                        displayNinki === 1
                          ? 'bg-red-500 text-white'
                          : displayNinki === 2
                            ? 'bg-blue-500 text-white'
                            : displayNinki === 3
                              ? 'bg-green-500 text-white'
                              : 'bg-gray-200 text-gray-700'
                      }`}
                    >
                      {displayNinki || '-'}
                    </span>
                  </td>
                  {/* 着順 */}
                  {hasResult && (
                    <>
                      <td className="px-2 py-2 text-center">
                        <span className={`inline-flex items-center justify-center w-6 h-6 rounded text-xs font-bold ${
                          horse.finishPosition === 1 ? 'bg-yellow-400 text-gray-900' :
                          horse.finishPosition === 2 ? 'bg-gray-300 text-gray-900' :
                          horse.finishPosition === 3 ? 'bg-orange-300 text-gray-900' :
                          'text-gray-600'
                        }`}>
                          {horse.finishPosition || '-'}
                        </span>
                      </td>
                      <td className="px-2 py-2 text-right font-mono text-xs text-gray-700">
                        {horse.time || '-'}
                      </td>
                      <td className="px-2 py-2 text-right font-mono text-xs text-gray-700">
                        {horse.last3f ? horse.last3f.toFixed(1) : '-'}
                      </td>
                    </>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
