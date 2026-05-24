/**
 * My印（TARGET馬印）取得ユーティリティ
 *
 * raceId(16桁) → year/kai/nichi/raceNumber/venue 変換と、馬印1/2の取得を提供。
 *
 * v2 (明示消) の合成も担う:
 *  - /api/target-marks (TARGET DAT) と /api/my-marks-v2/{raceId} を並列 fetch
 *  - markSet=1 (主) のみ explicit_erase を '消' として上書き合成
 *  - markSet=2 (副) には v2 を適用しない (v2 は単一意思空間のため)
 */

import { getTrackNameFromRaceId } from '@/lib/data/rt-data-types';

export interface RaceInfoForMarks {
  year: string;
  kai: number;
  nichi: number;
  raceNumber: number;
  venue: string;
}

export interface MyMarksV2Slim {
  explicit_erase: number[];
  explicit_no_mark: number[];
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

/** my_marks_v2 (明示消) を取得 */
export async function fetchMyMarksV2(raceId: string): Promise<MyMarksV2Slim> {
  try {
    const res = await fetch(`/api/my-marks-v2/${raceId}`);
    if (!res.ok) return { explicit_erase: [], explicit_no_mark: [] };
    const json = await res.json();
    const d = json?.data;
    return {
      explicit_erase: Array.isArray(d?.explicit_erase) ? d.explicit_erase : [],
      explicit_no_mark: Array.isArray(d?.explicit_no_mark) ? d.explicit_no_mark : [],
    };
  } catch {
    return { explicit_erase: [], explicit_no_mark: [] };
  }
}

/** DAT 印に explicit_erase を '消' として上書き合成 (非破壊) */
export function mergeEraseIntoMarks(
  marks: Record<number, string>,
  v2: MyMarksV2Slim
): Record<number, string> {
  if (v2.explicit_erase.length === 0) return marks;
  const merged = { ...marks };
  for (const uma of v2.explicit_erase) {
    merged[uma] = '消';
  }
  return merged;
}

/**
 * 馬印1と馬印2を同時取得。
 * raceId が渡されたら v2 (明示消) も並列 fetch して markSet=1 に合成する。
 */
export async function fetchMyMarksBoth(
  info: RaceInfoForMarks,
  raceId?: string
): Promise<{
  marks1: Record<number, string>;
  marks2: Record<number, string>;
  v2: MyMarksV2Slim;
}> {
  if (raceId) {
    const [marks1, marks2, v2] = await Promise.all([
      fetchMyMarks(info, 1),
      fetchMyMarks(info, 2),
      fetchMyMarksV2(raceId),
    ]);
    return {
      marks1: mergeEraseIntoMarks(marks1, v2),
      marks2,
      v2,
    };
  }
  const [marks1, marks2] = await Promise.all([fetchMyMarks(info, 1), fetchMyMarks(info, 2)]);
  return { marks1, marks2, v2: { explicit_erase: [], explicit_no_mark: [] } };
}
