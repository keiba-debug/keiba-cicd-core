'use client';

import { useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import Image from 'next/image';
import { generateRaceUrl } from '@/lib/jra-viewer-url';
import type { RegistrationData, RegistrationRace, RegistrationEntry, RecentResult } from '@/lib/data/registration-reader';

interface Props {
  data: RegistrationData;
  availableDates: string[];
  currentDate: string;
}

const GRADE_COLORS: Record<string, string> = {
  G1: 'bg-yellow-500 text-white',
  G2: 'bg-red-500 text-white',
  G3: 'bg-green-600 text-white',
  Listed: 'bg-blue-500 text-white',
  OP: 'bg-gray-600 text-white',
};

function GradeBadge({ grade }: { grade: string }) {
  if (!grade) return null;
  const color = GRADE_COLORS[grade] || 'bg-gray-400 text-white';
  return (
    <span className={`px-2 py-0.5 text-xs font-bold rounded ${color}`}>
      {grade}
    </span>
  );
}

function FinishBadge({ finish }: { finish: number | null }) {
  if (finish == null) return <span className="text-gray-400 text-base">-</span>;
  const color =
    finish === 1 ? 'text-red-600 font-bold' :
    finish === 2 ? 'text-blue-600 font-bold' :
    finish === 3 ? 'text-green-600 font-bold' :
    finish <= 5 ? 'text-gray-700 dark:text-gray-300 font-medium' :
    'text-gray-400';
  return <span className={`text-base ${color}`}>{finish}</span>;
}

function getRaceDate(raceCode: string): string {
  return `${raceCode.slice(0, 4)}-${raceCode.slice(4, 6)}-${raceCode.slice(6, 8)}`;
}

/** race_code(16桁) → netkeiba race_id(10桁): year + venue + kai + nichi + race_no */
function toNetkeibaId(raceCode: string): string {
  return raceCode.slice(0, 4) + raceCode.slice(8);
}

/** race_code(16桁)からJRAレーシングビュアーURLを生成 */
function raceCodeToViewerUrl(raceCode: string, venueName: string): string | null {
  const year = parseInt(raceCode.slice(0, 4));
  const month = parseInt(raceCode.slice(4, 6));
  const day = parseInt(raceCode.slice(6, 8));
  const kai = parseInt(raceCode.slice(10, 12));
  const nichi = parseInt(raceCode.slice(12, 14));
  const raceNumber = parseInt(raceCode.slice(14, 16));
  return generateRaceUrl({ year, month, day, track: venueName, kai, nichi, raceNumber });
}

function RecentResultsRow({ results }: { results: RecentResult[] }) {
  if (!results.length) {
    return <span className="text-sm text-gray-400">初出走</span>;
  }
  return (
    <div className="flex gap-2 text-sm">
      {results.slice(0, 5).map((r, i) => {
        const raceDate = r.race_code ? getRaceDate(r.race_code) : r.date;
        const raceLink = r.race_code
          ? `/races-v2/${raceDate}/${r.venue}/${r.race_code}`
          : null;
        const netkeibaUrl = r.race_code
          ? `https://race.netkeiba.com/race/result.html?race_id=${toNetkeibaId(r.race_code)}`
          : null;
        const viewerUrl = r.race_code ? raceCodeToViewerUrl(r.race_code, r.venue) : null;
        return (
          <div key={i} className="flex flex-col items-center leading-tight min-w-[52px]">
            <Link
              href={raceLink || '#'}
              target="_blank"
              rel="noopener noreferrer"
              className="flex flex-col items-center hover:bg-muted/50 rounded px-1 py-0.5 transition-colors"
              title={r.race_name ? `${r.date} ${r.race_name}` : r.date}
            >
              <FinishBadge finish={r.finish} />
              <span className="text-xs text-muted-foreground">
                {r.venue}{r.track_type === '芝' ? '芝' : 'ダ'}{r.distance}
              </span>
            </Link>
            {r.race_code && (
              <div className="flex items-center gap-1 mt-0.5">
                {viewerUrl && (
                  <a href={viewerUrl} target="_blank" rel="noopener noreferrer" title="レース映像" className="hover:opacity-100 opacity-70">
                    <span className="text-sm text-green-600">▶</span>
                  </a>
                )}
                {netkeibaUrl && (
                  <a href={netkeibaUrl} target="_blank" rel="noopener noreferrer" title="netkeiba" className="hover:opacity-100 opacity-70">
                    <Image src="/netkeiba.png" alt="NK" width={16} height={16} />
                  </a>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function RaceCard({ race }: { race: RegistrationRace }) {
  const [expanded, setExpanded] = useState(true);
  const raceDate = getRaceDate(race.race_code);
  const raceLink = `/races-v2/${raceDate}/${race.venue_name}/${race.race_code}`;

  return (
    <div className="border rounded-lg overflow-hidden">
      {/* Race Header */}
      <div className="flex items-center gap-3 px-4 py-3 bg-muted/30">
        <span className="text-lg font-bold text-blue-600 dark:text-blue-400 min-w-[32px]">
          R{race.race_number}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <GradeBadge grade={race.grade} />
            <Link
              href={raceLink}
              target="_blank"
              rel="noopener noreferrer"
              className="font-bold truncate text-blue-600 dark:text-blue-400 hover:underline"
            >
              {race.race_name}
            </Link>
          </div>
          <div className="text-xs text-muted-foreground mt-0.5">
            {race.venue_name} {race.track_type}{race.distance}m / {race.registered_count}頭登録
          </div>
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-muted-foreground text-sm hover:text-foreground transition-colors px-2 py-1"
        >
          {expanded ? '▼' : '▶'}
        </button>
      </div>

      {/* Entries Table */}
      {expanded && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/20 text-xs text-muted-foreground">
                <th className="px-3 py-2 text-left w-8">#</th>
                <th className="px-3 py-2 text-left">馬名</th>
                <th className="px-3 py-2 text-center w-12">性齢</th>
                <th className="px-3 py-2 text-left">調教師</th>
                <th className="px-3 py-2 text-center w-14">斤量</th>
                <th className="px-3 py-2 text-left">近走成績</th>
              </tr>
            </thead>
            <tbody>
              {race.entries.map((entry) => (
                <tr key={entry.renban} className="border-b last:border-b-0 hover:bg-muted/10">
                  <td className="px-3 py-2 text-muted-foreground text-xs">{entry.renban}</td>
                  <td className="px-3 py-2 font-medium whitespace-nowrap">
                    <Link
                      href={`/horses/${entry.ketto_num}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 dark:text-blue-400 hover:underline"
                    >
                      {entry.horse_name}
                    </Link>
                  </td>
                  <td className="px-3 py-2 text-center text-xs whitespace-nowrap">
                    {entry.sex}{entry.age ?? '?'}
                  </td>
                  <td className="px-3 py-2 text-xs text-muted-foreground whitespace-nowrap">
                    {entry.tozai ? `[${entry.tozai}]` : ''}{entry.trainer_name}
                  </td>
                  <td className="px-3 py-2 text-center text-xs">{entry.weight_carried}kg</td>
                  <td className="px-3 py-2">
                    <RecentResultsRow results={entry.recent_results} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function RegistrationContent({ data, availableDates, currentDate }: Props) {
  const router = useRouter();
  const [venueFilter, setVenueFilter] = useState<string>('all');

  // Group races by venue
  const venues = useMemo(() => {
    const set = new Set(data.races.map(r => r.venue_name));
    return Array.from(set);
  }, [data.races]);

  const filteredRaces = useMemo(() => {
    if (venueFilter === 'all') return data.races;
    return data.races.filter(r => r.venue_name === venueFilter);
  }, [data.races, venueFilter]);

  // Group by venue for display
  const groupedRaces = useMemo(() => {
    const groups: Record<string, RegistrationRace[]> = {};
    for (const race of filteredRaces) {
      if (!groups[race.venue_name]) groups[race.venue_name] = [];
      groups[race.venue_name].push(race);
    }
    return groups;
  }, [filteredRaces]);

  const handleDateChange = (date: string) => {
    router.push(`/registration?date=${date}`);
  };

  const currentIdx = availableDates.indexOf(currentDate);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold">特別登録</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {data.total_races}レース / {data.total_entries}頭登録
            <span className="ml-2 text-xs">
              (生成: {new Date(data.created_at).toLocaleString('ja-JP')})
            </span>
          </p>
        </div>
      </div>

      {/* Date Navigation */}
      <div className="flex items-center gap-2 mb-4">
        <button
          onClick={() => currentIdx < availableDates.length - 1 && handleDateChange(availableDates[currentIdx + 1])}
          disabled={currentIdx >= availableDates.length - 1}
          className="px-3 py-1.5 text-sm border rounded-lg disabled:opacity-30 hover:bg-muted/50"
        >
          ← 前
        </button>

        <select
          value={currentDate}
          onChange={(e) => handleDateChange(e.target.value)}
          className="px-3 py-1.5 text-sm border rounded-lg bg-background"
        >
          {availableDates.map(d => {
            const dt = new Date(d + 'T00:00:00');
            const dow = ['日', '月', '火', '水', '木', '金', '土'][dt.getDay()];
            return (
              <option key={d} value={d}>
                {d} ({dow})
              </option>
            );
          })}
        </select>

        <button
          onClick={() => currentIdx > 0 && handleDateChange(availableDates[currentIdx - 1])}
          disabled={currentIdx <= 0}
          className="px-3 py-1.5 text-sm border rounded-lg disabled:opacity-30 hover:bg-muted/50"
        >
          次 →
        </button>
      </div>

      {/* Venue Filter */}
      {venues.length > 1 && (
        <div className="flex gap-1 mb-4">
          <button
            onClick={() => setVenueFilter('all')}
            className={`px-3 py-1.5 text-xs rounded-full transition-colors ${
              venueFilter === 'all'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
            }`}
          >
            全場
          </button>
          {venues.map(v => (
            <button
              key={v}
              onClick={() => setVenueFilter(v)}
              className={`px-3 py-1.5 text-xs rounded-full transition-colors ${
                venueFilter === v
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
              }`}
            >
              {v}
            </button>
          ))}
        </div>
      )}

      {/* Race Cards by Venue */}
      {Object.entries(groupedRaces).map(([venue, races]) => (
        <div key={venue} className="mb-6">
          <h2 className="text-lg font-bold mb-3 flex items-center gap-2">
            <span className="w-1.5 h-5 bg-blue-600 rounded-full inline-block" />
            {venue}
          </h2>
          <div className="space-y-3">
            {races.map(race => (
              <RaceCard key={race.race_code} race={race} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
