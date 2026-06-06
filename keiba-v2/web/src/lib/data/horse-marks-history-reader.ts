/**
 * 馬別 印履歴リーダー (My印 markSet=1 / AI印 markSet=6)
 *
 * 1頭の過去レースを横断し、各レースでその馬 (umaban) に付いていた
 * My印 (TARGET markSet=1, 明示消を合成) と AI印 (markSet=6) を時系列で集める。
 * 着順と並べることで「AI印が当たっているか」を目視評価できる。
 *
 * - 表示専用 (書込なし)。 markSet=6 (AI印) は読むだけ。
 * - My印には my_marks_v2 の explicit_erase を '消' として合成する
 *   (markSet=6 には合成しない。 v2 は markSet=1 の単一意思空間のため)。
 * - DAT を毎レース読むため、 結果は ketto_num 単位で in-memory キャッシュ (TTL付き)。
 */

import { getRaceMarks } from './target-mark-reader';
import { readMyMarksV2, mergeWithEraseMarks, ERASE_MARK } from './my-marks-v2-reader';

// race_id[8:10] (JV 場コード) → 場名 (target-mark-reader の venue 名と一致させる)
const JV_CODE_TO_VENUE: Record<string, string> = {
  '01': '札幌', '02': '函館', '03': '福島', '04': '新潟', '05': '東京',
  '06': '中山', '07': '中京', '08': '京都', '09': '阪神', '10': '小倉',
};

// 推奨印 (◎○▲△Ⅲ穴)。 '消' / '' は除外して信頼性集計する。
const POSITIVE_MARKS = new Set(['◎', '○', '▲', '△', 'Ⅲ', '穴']);

/** getHorseMarksHistory が受け付ける過去レースの最小形 (HorseRaceResult が満たす) */
export interface HorseRaceLike {
  raceId?: string;       // 16桁 (enrich 済) または 12桁 (SE) または ''
  targetRaceId?: string; // SE 由来 (12桁)
  date: string;          // "YYYY/MM/DD"
  track: string;         // 場名
  raceNumber: number;
  raceName?: string;
  distance?: string;
  horseNumber: number;   // umaban
  finishPosition: string;
}

export interface HorseMarkHistoryEntry {
  raceId: string;        // 16桁 (可能なら)
  date: string;          // "YYYY/MM/DD"
  track: string;
  raceNumber: number;
  raceName: string;
  distance: string;
  umaban: number;
  finishPosition: string;
  finishNum: number;     // 数値化した着順 (0=取消/中止/不明)
  myMark: string;        // markSet=1 (+ 明示消合成)。 無印は ''
  aiMark: string;        // markSet=6。 無印は ''
}

export interface HorseMarksReliability {
  races: number;         // 正の印が付いたレース数
  top3: number;          // うち3着内
  win: number;           // うち1着
}

export interface HorseMarksHistory {
  entries: HorseMarkHistoryEntry[]; // My印 or AI印 のあるレースのみ。 新しい順
  my: HorseMarksReliability;        // My印 (推奨印) の信頼性
  ai: HorseMarksReliability;        // AI印 (推奨印) の信頼性
}

interface DerivedParams {
  year: number;
  kai: number;
  nichi: number;
  raceNumber: number;
  venue: string;
  raceId16: string;
}

/**
 * 過去レース 1件から TARGET 印読み出しに必要なパラメータを導出する。
 * year は date から (raceId の桁数揺れに頑健)、 kai/nichi は raceId から取る。
 */
function deriveParams(race: HorseRaceLike): DerivedParams | null {
  const dm = (race.date || '').match(/(\d{4})\D?(\d{1,2})\D?(\d{1,2})/);
  if (!dm) return null;
  const year = parseInt(dm[1], 10);
  const ymd = `${dm[1]}${dm[2].padStart(2, '0')}${dm[3].padStart(2, '0')}`;

  const pick = (len: number) =>
    race.raceId && race.raceId.length === len ? race.raceId
      : race.targetRaceId && race.targetRaceId.length === len ? race.targetRaceId
        : '';

  let kai = 0;
  let nichi = 0;
  let venueCode = '';
  let raceNumber = race.raceNumber || 0;
  let raceId16 = '';

  const rid16 = pick(16);
  const rid12 = pick(12);

  if (rid16) {
    // YYYYMMDD + VV + KK + NN + RR
    venueCode = rid16.slice(8, 10);
    kai = parseInt(rid16.slice(10, 12), 10);
    nichi = parseInt(rid16.slice(12, 14), 10);
    if (!raceNumber) raceNumber = parseInt(rid16.slice(14, 16), 10);
    raceId16 = rid16;
  } else if (rid12) {
    // SE: YYYY + KK + VV + NN + RR
    kai = parseInt(rid12.slice(4, 6), 10);
    venueCode = rid12.slice(6, 8);
    nichi = parseInt(rid12.slice(8, 10), 10);
    if (!raceNumber) raceNumber = parseInt(rid12.slice(10, 12), 10);
    // v2 (明示消) 参照用に 16桁を date から再構成
    raceId16 = `${ymd}${venueCode}${rid12.slice(4, 6)}${rid12.slice(8, 10)}${rid12.slice(10, 12)}`;
  } else {
    return null;
  }

  const venue = race.track || JV_CODE_TO_VENUE[venueCode] || '';
  if (!year || !kai || !nichi || !raceNumber || !venue) return null;
  return { year, kai, nichi, raceNumber, venue, raceId16 };
}

// ---------------------------------------------------------------------------
// キャッシュ (ketto_num 単位)。 当日の印は更新されうるので短めの TTL。
// ---------------------------------------------------------------------------
const cache = new Map<string, { data: HorseMarksHistory; ts: number }>();
const CACHE_TTL = 5 * 60 * 1000; // 5分

const EMPTY: HorseMarksHistory = {
  entries: [],
  my: { races: 0, top3: 0, win: 0 },
  ai: { races: 0, top3: 0, win: 0 },
};

/**
 * 1頭の印履歴を集計する。
 * @param kettoNum 10桁 ketto_num (キャッシュキー)
 * @param pastRaces その馬の過去レース (HorseRaceResult[] でよい)
 */
export function getHorseMarksHistory(
  kettoNum: string,
  pastRaces: HorseRaceLike[],
): HorseMarksHistory {
  if (!kettoNum || pastRaces.length === 0) return EMPTY;

  const cached = cache.get(kettoNum);
  if (cached && Date.now() - cached.ts < CACHE_TTL) return cached.data;

  const entries: HorseMarkHistoryEntry[] = [];
  const my: HorseMarksReliability = { races: 0, top3: 0, win: 0 };
  const ai: HorseMarksReliability = { races: 0, top3: 0, win: 0 };

  for (const race of pastRaces) {
    const p = deriveParams(race);
    if (!p) continue;

    // My印 (markSet=1) + 明示消合成
    let myMark = '';
    const raw1 = getRaceMarks(p.year, p.kai, p.nichi, p.raceNumber, p.venue, 1);
    if (raw1 || p.raceId16) {
      const v2 = p.raceId16 ? readMyMarksV2(p.raceId16) : null;
      const merged = mergeWithEraseMarks(raw1?.horseMarks ?? {}, v2);
      myMark = merged[race.horseNumber] ?? '';
    }

    // AI印 (markSet=6) — 読むだけ、 v2 合成なし
    const raw6 = getRaceMarks(p.year, p.kai, p.nichi, p.raceNumber, p.venue, 6);
    const aiMark = raw6?.horseMarks[race.horseNumber] ?? '';

    // どちらの印も無ければスキップ ('消' は意味があるので残す)
    if (!myMark && !aiMark) continue;

    const finishNum = parseInt(race.finishPosition, 10);
    const finish = Number.isNaN(finishNum) ? 0 : finishNum;

    entries.push({
      raceId: p.raceId16,
      date: race.date,
      track: race.track,
      raceNumber: p.raceNumber,
      raceName: race.raceName || '',
      distance: race.distance || '',
      umaban: race.horseNumber,
      finishPosition: race.finishPosition,
      finishNum: finish,
      myMark,
      aiMark,
    });

    // 信頼性集計 (推奨印が付いた走のみ。 '消'/'' は対象外)
    if (POSITIVE_MARKS.has(myMark)) {
      my.races += 1;
      if (finish >= 1 && finish <= 3) my.top3 += 1;
      if (finish === 1) my.win += 1;
    }
    if (POSITIVE_MARKS.has(aiMark)) {
      ai.races += 1;
      if (finish >= 1 && finish <= 3) ai.top3 += 1;
      if (finish === 1) ai.win += 1;
    }
  }

  // 新しい順 (date 降順)。 pastRaces は降順想定だが念のため整列。
  entries.sort((a, b) => b.date.localeCompare(a.date));

  const data: HorseMarksHistory = { entries, my, ai };
  cache.set(kettoNum, { data, ts: Date.now() });
  return data;
}

/** '消' を判定するヘルパ (UI 用に再エクスポート) */
export const isEraseMark = (mark: string): boolean => mark === ERASE_MARK;
