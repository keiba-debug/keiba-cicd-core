/**
 * My印（TARGET馬印）取得ユーティリティ
 *
 * raceId(16桁) → year/kai/nichi/raceNumber/venue 変換と、馬印1/2の取得を提供。
 */

import { getTrackNameFromRaceId } from '@/lib/data/rt-data-types';

export interface RaceInfoForMarks {
  year: string;
  kai: number;
  nichi: number;
  raceNumber: number;
  venue: string;
}

/** 16桁 raceId (YYYYMMDDJJKKNNRR) → TARGET API 用パラメータ */
export function parseRaceIdForMarks(raceId: string): RaceInfoForMarks | null {
  if (raceId.length !== 16) return null;
  const year = raceId.substring(0, 4);
  const kai = parseInt(raceId.substring(10, 12), 10);
  const nichi = parseInt(raceId.substring(12, 14), 10);
  const raceNumber = parseInt(raceId.substring(14, 16), 10);
  const venue = getTrackNameFromRaceId(raceId);
  if (!year || !kai || !nichi || !raceNumber || !venue) return null;
  return { year, kai, nichi, raceNumber, venue };
}

/** TARGET馬印を1セット取得 */
export async function fetchMyMarks(
  info: RaceInfoForMarks,
  markSet: number
): Promise<Record<number, string>> {
  const params = new URLSearchParams({
    year: info.year,
    kai: String(info.kai),
    nichi: String(info.nichi),
    raceNumber: String(info.raceNumber),
    venue: info.venue,
    markSet: String(markSet),
  });
  try {
    const res = await fetch(`/api/target-marks?${params}`);
    if (!res.ok) return {};
    const data = await res.json();
    return (data?.data?.horseMarks as Record<number, string>) || {};
  } catch {
    return {};
  }
}

/** 馬印1と馬印2を同時取得 */
export async function fetchMyMarksBoth(
  info: RaceInfoForMarks
): Promise<{ marks1: Record<number, string>; marks2: Record<number, string> }> {
  const [marks1, marks2] = await Promise.all([fetchMyMarks(info, 1), fetchMyMarks(info, 2)]);
  return { marks1, marks2 };
}
