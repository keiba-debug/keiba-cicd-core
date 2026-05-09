/**
 * /specialist/[raceId] ヘッダー (Server Component)
 *
 * レース基本情報 + 関連画面への横断リンク。
 */

import Link from 'next/link';
import type { RaceMetaForSpecialist } from '@/lib/data/specialist-reader';

interface Props {
  meta: RaceMetaForSpecialist;
}

export function SpecialistRaceHeader({ meta }: Props) {
  const dateForLink = meta.date;
  const venueForLink = encodeURIComponent(meta.venueName);

  return (
    <header className="rounded-2xl border-2 border-indigo-200 bg-gradient-to-br from-indigo-50 via-blue-50 to-white overflow-hidden">
      <div className="px-6 py-4">
        <div className="flex items-start justify-between flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-700">
                Specialist Prediction
              </span>
              {meta.appliedModels.map((m) => (
                <span
                  key={m.id}
                  className="text-[10px] font-bold px-2 py-0.5 rounded bg-indigo-600 text-white"
                >
                  {m.label}
                </span>
              ))}
            </div>
            <h1 className="text-2xl font-bold mt-1">
              {meta.venueName} {meta.raceNumber}R
              {meta.raceName && (
                <span className="text-base font-medium text-gray-600 ml-2">{meta.raceName}</span>
              )}
            </h1>
            <p className="text-sm text-gray-600 mt-1">
              {meta.date}・{meta.trackType}{meta.distance}m
              {meta.grade && ` ${meta.grade}`}・{meta.numRunners}頭
            </p>
          </div>
          <div className="flex flex-wrap gap-1.5 text-xs">
            <Link
              href={`/races-v2/${dateForLink}/${venueForLink}/${meta.raceId}`}
              className="px-2.5 py-1.5 rounded-lg bg-white border border-gray-300 text-gray-700 hover:bg-gray-50"
            >
              出走表 →
            </Link>
            <Link
              href={`/odds-race/${meta.raceId}`}
              className="px-2.5 py-1.5 rounded-lg bg-white border border-gray-300 text-gray-700 hover:bg-gray-50"
            >
              オッズ画面 →
            </Link>
            {meta.appliedModels[0]?.encyclopediaUrl && (
              <Link
                href={meta.appliedModels[0].encyclopediaUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="px-2.5 py-1.5 rounded-lg bg-white border border-indigo-300 text-indigo-700 hover:bg-indigo-50"
              >
                コース事典 ↗
              </Link>
            )}
            {meta.appliedModels[0]?.dashboardUrl && (
              <Link
                href={meta.appliedModels[0].dashboardUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="px-2.5 py-1.5 rounded-lg bg-white border border-indigo-300 text-indigo-700 hover:bg-indigo-50"
              >
                全データ ↗
              </Link>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
