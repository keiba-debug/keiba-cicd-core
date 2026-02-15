/**
 * レース日付インデックス
 * 
 * 利用可能な日付と各日の競馬場・レース情報を高速に取得するためのインデックス
 * JSONファイルに永続化してアプリ再起動時も高速検索を維持
 * リクエスト経路では非同期読み込みのみ使用し、readFileSync でイベントループをブロックしない
 */

import fs from 'fs';
import fsp from 'fs/promises';
import path from 'path';
import { TRACKS, DATA3_ROOT } from '../config';
import { getDbRaceInfoByDates, trackTypeToJapanese } from './db-race';

const INDEX_FILE = path.join(DATA3_ROOT, 'indexes', 'race_date_index.json');
const INDEX_META_FILE = path.join(DATA3_ROOT, 'indexes', 'race_date_index_meta.json');

// インメモリキャッシュ
let dateIndex: Map<string, DateIndexEntry> = new Map();
let availableDates: string[] = [];
let indexLoaded = false;
let indexLoadAttempted = false; // 非同期読み込みを1回試行済みか（sync にフォールバックしないため）
let indexBuildInProgress = false;

interface DateIndexEntry {
  date: string;
  displayDate: string;
  tracks: TrackIndexEntry[];
}

interface TrackIndexEntry {
  track: string;
  races: RaceIndexEntry[];
}

interface RaceIndexEntry {
  id: string;
  raceNumber: number;
  raceName: string;
  className: string;
  distance: string;
  startTime: string;
  kai?: number;
  nichi?: number;
  // ペース分析情報（レース結果から取得）
  paceType?: 'sprint' | 'average' | 'stamina';  // 瞬発/平均/持続
  winnerFirst3f?: number;  // 勝ち馬の前半3F
  winnerLast3f?: number;   // 勝ち馬の後半3F
  paceDiff?: number;       // 前半-後半の差（マイナス=瞬発戦）
  rpci?: number;           // RPCI値 (前半3F/後半3F)*50
}

// ペース分類タイプをエクスポート
export type PaceType = 'sprint' | 'average' | 'stamina';

/** インデックス形式バージョン。2=race_info.jsonのみ対応、3=ペース分析情報追加、4=RPCI比率方式に統一 */
const INDEX_VERSION = 4;

interface IndexMeta {
  builtAt: string;
  dateCount: number;
  raceCount: number;
  version?: number;
}

/**
 * インデックスをファイルから読み込み
 */
function loadIndexFromFile(): boolean {
  try {
    if (!fs.existsSync(INDEX_FILE)) {
      return false;
    }

    const data = JSON.parse(fs.readFileSync(INDEX_FILE, 'utf-8'));
    dateIndex = new Map(Object.entries(data).map(([k, v]) => [k, v as DateIndexEntry]));
    availableDates = Array.from(dateIndex.keys()).sort().reverse();

    if (fs.existsSync(INDEX_META_FILE)) {
      const meta: IndexMeta = JSON.parse(fs.readFileSync(INDEX_META_FILE, 'utf-8'));
      if ((meta.version ?? 1) < INDEX_VERSION) {
        console.log(`[RaceDateIndex] Cache version ${meta.version ?? 1} < ${INDEX_VERSION}, will rebuild (race_info-only support)`);
        dateIndex = new Map();
        availableDates = [];
        return false;
      }
      console.log(`[RaceDateIndex] Loaded from file: ${meta.dateCount} dates, ${meta.raceCount} races (built: ${meta.builtAt})`);
    }
    indexLoaded = true;
    return true;
  } catch (error) {
    console.error('[RaceDateIndex] Failed to load index:', error);
    return false;
  }
}

/**
 * インデックスを非同期でファイルから読み込み（リクエスト経路用・イベントループをブロックしない）
 */
async function loadIndexFromFileAsync(): Promise<boolean> {
  try {
    await fsp.access(INDEX_FILE);
  } catch {
    return false;
  }
  try {
    const content = await fsp.readFile(INDEX_FILE, 'utf-8');
    const data = JSON.parse(content);
    dateIndex = new Map(Object.entries(data).map(([k, v]) => [k, v as DateIndexEntry]));
    availableDates = Array.from(dateIndex.keys()).sort().reverse();

    try {
      const metaContent = await fsp.readFile(INDEX_META_FILE, 'utf-8');
      const meta: IndexMeta = JSON.parse(metaContent);
      if ((meta.version ?? 1) < INDEX_VERSION) {
        console.log(`[RaceDateIndex] Cache version ${meta.version ?? 1} < ${INDEX_VERSION}, will rebuild`);
        dateIndex = new Map();
        availableDates = [];
        return false;
      }
      console.log(`[RaceDateIndex] Loaded from file (async): ${meta.dateCount} dates, ${meta.raceCount} races`);
    } catch {
      // meta が無くてもインデックスは使う
    }
    indexLoaded = true;
    return true;
  } catch (error) {
    console.error('[RaceDateIndex] Failed to load index (async):', error);
    return false;
  }
}

/**
 * リクエスト経路で必ず先に呼ぶ。インデックスが未読み込みなら非同期で1回だけ読み込む。
 * これにより isRaceIndexAvailable / getAvailableDatesFromIndex は sync 読みをせずメモリだけ参照する。
 */
export async function ensureRaceDateIndexLoaded(): Promise<void> {
  if (indexLoaded || indexLoadAttempted) return;
  indexLoadAttempted = true;
  await loadIndexFromFileAsync();
}

/**
 * インデックスをファイルに保存
 */
function saveIndexToFile(raceCount: number): void {
  try {
    const cacheDir = path.dirname(INDEX_FILE);
    if (!fs.existsSync(cacheDir)) {
      fs.mkdirSync(cacheDir, { recursive: true });
    }

    const data = Object.fromEntries(dateIndex);
    fs.writeFileSync(INDEX_FILE, JSON.stringify(data), 'utf-8');

    const meta: IndexMeta = {
      builtAt: new Date().toISOString(),
      dateCount: dateIndex.size,
      raceCount,
      version: INDEX_VERSION,
    };
    fs.writeFileSync(INDEX_META_FILE, JSON.stringify(meta, null, 2), 'utf-8');

    console.log(`[RaceDateIndex] Saved to file: ${meta.dateCount} dates, ${raceCount} races`);
  } catch (error) {
    console.error('[RaceDateIndex] Failed to save index:', error);
  }
}

// JRA-VAN venue_code → 競馬場名
const VENUE_CODE_MAP: Record<string, string> = {
  '01': '札幌', '02': '函館', '03': '福島', '04': '新潟', '05': '東京',
  '06': '中山', '07': '中京', '08': '京都', '09': '阪神', '10': '小倉',
};

// track_type → 表示用（JRA-VAN英語 + keibabook日本語の両方に対応）
const TRACK_TYPE_MAP: Record<string, string> = {
  turf: '芝',
  dirt: 'ダ',
  '芝': '芝',
  'ダ': 'ダ',
  '障': '障',
};

/**
 * 全角英数・記号を半角に正規化（G２→G2, 雲雀Ｓ→雲雀S など）
 */
function normalizeForClass(str: string): string {
  return str.replace(/[ＧGg]/g, 'G').replace(/[１２３]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0xfee0))
    .replace(/[ＳSs]/g, 'S').replace(/[０-９]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0xfee0));
}

/**
 * race_nameからクラス名を抽出（gradeが空の場合のフォールバック）
 * 特別レース（G1/G2/G3、〇〇S、〇〇特別）も判定する
 */
function extractClassName(raceName: string): string {
  const normalized = normalizeForClass(raceName);
  // G1/G2/G3（全角G3なども正規化済み）
  const gMatch = normalized.match(/G[123]/);
  if (gMatch) return gMatch[0];
  // オープン・リステッド系
  if (/オープン|Listed|L\s/i.test(raceName)) return raceName.match(/オープン/) ? 'オープン' : 'L';
  // 特別（春日特別、北山特別など）
  if (/特別/.test(raceName)) return '特別';
  // 〇〇S / 〇〇Ｓ（雲雀Ｓ、バレンタインSなどステークス）
  if (/[ＳS]$/.test(raceName) || /\S[ＳS]$/.test(raceName)) return 'S';
  // 3勝/2勝/1勝クラス、未勝利、新馬、障害
  const patterns = [/3勝クラス/, /2勝クラス/, /1勝クラス/, /未勝利/, /新馬/, /障害未勝利/, /障害[^\s]*/];
  for (const p of patterns) {
    const m = raceName.match(p);
    if (m) return m[0];
  }
  // "4歳以上1勝クラス" → "1勝クラス" など
  const classMatch = raceName.match(/(\d勝クラス)/);
  if (classMatch) return classMatch[1];
  return '';
}

/**
 * v4レースJSONからRaceIndexEntryを構築
 */
function buildRaceEntryFromV4(raceData: {
  race_id: string;
  race_number: number;
  race_name?: string;
  grade?: string;
  distance?: number;
  track_type?: string;
  kai?: number;
  nichi?: number;
  pace?: { rpci?: number; s3?: number; l3?: number } | null;
  entries?: Array<{ finish_position: number; last_3f: number }>;
}): RaceIndexEntry {
  const raceNumber = raceData.race_number;
  const raceName = raceData.race_name || `${raceNumber}R`;
  const grade = raceData.grade || extractClassName(raceName);
  const trackType = TRACK_TYPE_MAP[raceData.track_type || ''] || '';
  const distance = raceData.distance
    ? `${trackType}${raceData.distance}m`
    : '';

  // ペース情報（v4のpaceフィールドから）
  let paceType: PaceType | undefined;
  let winnerFirst3f: number | undefined;
  let winnerLast3f: number | undefined;
  let paceDiff: number | undefined;
  let rpci: number | undefined;

  if (raceData.pace?.rpci != null) {
    rpci = raceData.pace.rpci;
    if (rpci >= 51) paceType = 'sprint';
    else if (rpci <= 48) paceType = 'stamina';
    else paceType = 'average';

    if (raceData.pace.s3 != null && raceData.pace.l3 != null) {
      winnerFirst3f = raceData.pace.s3;
      winnerLast3f = raceData.pace.l3;
      paceDiff = Math.round((raceData.pace.s3 - raceData.pace.l3) * 10) / 10;
    }
  }

  return {
    id: raceData.race_id,
    raceNumber,
    raceName,
    className: grade,
    distance,
    startTime: '',
    kai: raceData.kai,
    nichi: raceData.nichi,
    paceType,
    winnerFirst3f,
    winnerLast3f,
    paceDiff,
    rpci,
  };
}

/**
 * インデックスを構築（data3/races のv4 JSONから）
 */
export async function buildRaceDateIndex(): Promise<void> {
  if (indexBuildInProgress) {
    console.log('[RaceDateIndex] Build already in progress, skipping');
    return;
  }

  // 既存のインデックスがあれば読み込み
  if (!indexLoaded && loadIndexFromFile()) {
    return;
  }

  indexBuildInProgress = true;
  const startTime = Date.now();
  let raceCount = 0;

  try {
    const racesPath = path.join(DATA3_ROOT, 'races');
    if (!fs.existsSync(racesPath)) {
      console.log('[RaceDateIndex] Races directory not found:', racesPath);
      return;
    }

    const years = fs.readdirSync(racesPath)
      .filter(f => /^\d{4}$/.test(f))
      .sort((a, b) => parseInt(b) - parseInt(a));

    for (const year of years) {
      const yearPath = path.join(racesPath, year);
      const months = fs.readdirSync(yearPath)
        .filter(f => /^\d{2}$/.test(f));

      for (const month of months) {
        const monthPath = path.join(yearPath, month);
        const days = fs.readdirSync(monthPath)
          .filter(f => /^\d{2}$/.test(f));

        for (const day of days) {
          const dayPath = path.join(monthPath, day);
          const dateStr = `${year}-${month}-${day}`;

          // race_*.json ファイルを読み込み
          let raceFiles: string[];
          try {
            raceFiles = fs.readdirSync(dayPath)
              .filter(f => f.startsWith('race_') && f.endsWith('.json') && f !== 'race_info.json');
          } catch {
            continue;
          }

          // race_info.json からレース名・発走時刻・kaisai情報を取得（存在する場合）
          type RaceInfoItem = { raceName?: string; startTime?: string; course?: string; kai?: number; nichi?: number; track?: string };
          const raceInfoMap = new Map<string, RaceInfoItem>();
          const raceInfoByTrack = new Map<string, { entries: RaceInfoItem[]; kai?: number; nichi?: number }>();
          const raceInfoPath = path.join(dayPath, 'race_info.json');
          if (fs.existsSync(raceInfoPath)) {
            try {
              const infoContent = fs.readFileSync(raceInfoPath, 'utf-8');
              const infoData = JSON.parse(infoContent) as {
                kaisai_data?: Record<string, Array<{ race_id?: string; race_id_16?: string; race_no?: string; race_name?: string; start_time?: string; course?: string }>>;
              };
              for (const [kaisaiKey, raceList] of Object.entries(infoData.kaisai_data || {})) {
                const kaisaiMatch = kaisaiKey.match(/(\d+)回([^\d]+)(\d+)日/);
                const kai = kaisaiMatch ? parseInt(kaisaiMatch[1]) : undefined;
                const trackName = kaisaiMatch ? kaisaiMatch[2] : undefined;
                const nichi = kaisaiMatch ? parseInt(kaisaiMatch[3]) : undefined;

                for (const race of raceList) {
                  const item: RaceInfoItem = { raceName: race.race_name, startTime: race.start_time, course: race.course, kai, nichi, track: trackName };
                  if (race.race_id_16) raceInfoMap.set(race.race_id_16, item);
                  if (race.race_id) raceInfoMap.set(race.race_id, item);
                }

                if (trackName && (TRACKS as readonly string[]).includes(trackName)) {
                  if (!raceInfoByTrack.has(trackName)) {
                    raceInfoByTrack.set(trackName, { entries: [], kai, nichi });
                  }
                  for (const race of raceList) {
                    if (!race.race_id) continue;
                    const raceNo = parseInt((race.race_no || '0').replace('R', ''));
                    raceInfoByTrack.get(trackName)!.entries.push({
                      raceName: race.race_name,
                      startTime: race.start_time,
                      course: race.course,
                      kai, nichi, track: trackName,
                    });
                    // race_id_16がある場合はそちらをIDとして使用
                    const id = race.race_id_16 || race.race_id;
                    raceInfoMap.set(`_entry_${trackName}_${raceNo}`, { ...raceInfoMap.get(id)!, raceName: race.race_name });
                  }
                }
              }
            } catch { /* ignore */ }
          }

          // race_*.jsonがなくてもrace_info.jsonだけでインデックスを構築できる
          if (raceFiles.length === 0 && raceInfoByTrack.size === 0) continue;

          // 競馬場ごとにグループ化
          const trackMap = new Map<string, RaceIndexEntry[]>();

          for (const file of raceFiles) {
            try {
              const content = fs.readFileSync(path.join(dayPath, file), 'utf-8');
              const raceData = JSON.parse(content);
              const venueName = raceData.venue_name || VENUE_CODE_MAP[raceData.venue_code] || '';
              if (!venueName || !(TRACKS as readonly string[]).includes(venueName)) continue;

              if (!trackMap.has(venueName)) trackMap.set(venueName, []);
              const entry = buildRaceEntryFromV4(raceData);
              // race_info.jsonからレース名・発走時刻を補完
              const raceInfo = raceInfoMap.get(raceData.race_id);
              if (raceInfo) {
                if (raceInfo.raceName && entry.raceName === `${entry.raceNumber}R`) {
                  entry.raceName = raceInfo.raceName;
                }
                if (raceInfo.startTime && !entry.startTime) {
                  entry.startTime = raceInfo.startTime;
                }
                if (raceInfo.kai && !entry.kai) entry.kai = raceInfo.kai;
                if (raceInfo.nichi && !entry.nichi) entry.nichi = raceInfo.nichi;
              }
              trackMap.get(venueName)!.push(entry);
              raceCount++;
            } catch {
              // skip unreadable files
            }
          }

          // race_info.jsonのみでv4 JSONがないレースを追加（未来レース対応）
          if (raceInfoByTrack.size > 0) {
            for (const [kaisaiKey, raceList] of Object.entries(
              (JSON.parse(fs.readFileSync(raceInfoPath, 'utf-8')) as { kaisai_data?: Record<string, Array<{ race_id?: string; race_id_16?: string; race_no?: string; race_name?: string; start_time?: string; course?: string }>> }).kaisai_data || {}
            )) {
              const kaisaiMatch = kaisaiKey.match(/(\d+)回([^\d]+)(\d+)日/);
              if (!kaisaiMatch) continue;
              const trackName = kaisaiMatch[2];
              if (!(TRACKS as readonly string[]).includes(trackName)) continue;
              const kai = parseInt(kaisaiMatch[1]);
              const nichi = parseInt(kaisaiMatch[3]);

              if (!trackMap.has(trackName)) trackMap.set(trackName, []);
              const existing = trackMap.get(trackName)!;
              const existingIds = new Set(existing.map(e => e.id));

              for (const race of raceList) {
                const raceId = race.race_id_16 || race.race_id || '';
                if (!raceId || existingIds.has(raceId)) continue;
                const raceNumber = parseInt((race.race_no || '0').replace('R', ''));
                if (raceNumber === 0) continue;

                let distance = race.course || '';
                // course が空のとき、v4 の race_*.json があれば距離を補完
                if (!distance) {
                  const v4Path = path.join(dayPath, `race_${raceId}.json`);
                  try {
                    if (fs.existsSync(v4Path)) {
                      const raceData = JSON.parse(fs.readFileSync(v4Path, 'utf-8'));
                      const trackType = TRACK_TYPE_MAP[raceData.track_type || ''] || '';
                      if (raceData.distance) {
                        distance = `${trackType}${raceData.distance}m`;
                      }
                    }
                  } catch { /* 無視 */ }
                }

                existing.push({
                  id: raceId,
                  raceNumber,
                  raceName: race.race_name || `${raceNumber}R`,
                  className: extractClassName(race.race_name || ''),
                  distance,
                  startTime: race.start_time || '',
                  kai,
                  nichi,
                });
                raceCount++;
              }
            }
          }

          if (trackMap.size === 0) continue;

          const trackEntries: TrackIndexEntry[] = [];
          for (const [track, races] of trackMap) {
            races.sort((a, b) => a.raceNumber - b.raceNumber);
            trackEntries.push({ track, races });
          }
          trackEntries.sort((a, b) => {
            const indexA = TRACKS.indexOf(a.track as (typeof TRACKS)[number]);
            const indexB = TRACKS.indexOf(b.track as (typeof TRACKS)[number]);
            return indexA - indexB;
          });

          const displayDate = `${year}年${parseInt(month)}月${parseInt(day)}日`;
          dateIndex.set(dateStr, { date: dateStr, displayDate, tracks: trackEntries });
        }
      }
    }

    availableDates = Array.from(dateIndex.keys()).sort().reverse();
    indexLoaded = true;

    // DB enrichment: fill missing track/distance from RACE_SHOSAI
    await enrichMissingFromDb(dateIndex);

    saveIndexToFile(raceCount);

    const elapsed = Date.now() - startTime;
    console.log(`[RaceDateIndex] Built: ${dateIndex.size} dates, ${raceCount} races in ${elapsed}ms`);
  } catch (error) {
    console.error('[RaceDateIndex] Build error:', error);
  } finally {
    indexBuildInProgress = false;
  }
}

/**
 * DB (RACE_SHOSAI) からtrack/distance/startTimeが欠落しているレースを補完
 * mykeibadbにデータがある日のみ実行される
 */
async function enrichMissingFromDb(index: Map<string, DateIndexEntry>): Promise<void> {
  // Collect dates that have races with missing distance
  const datesToEnrich: string[] = [];
  for (const [date, entry] of index) {
    for (const track of entry.tracks) {
      if (track.races.some(r => !r.distance)) {
        datesToEnrich.push(date.replace(/-/g, ''));
        break;
      }
    }
  }

  if (datesToEnrich.length === 0) return;

  try {
    const dbInfo = await getDbRaceInfoByDates(datesToEnrich);
    if (dbInfo.size === 0) return;

    let enriched = 0;
    for (const [, entry] of index) {
      for (const track of entry.tracks) {
        for (const race of track.races) {
          const info = dbInfo.get(race.id);
          if (!info) continue;

          // Fill missing distance
          if (!race.distance && info.distance > 0) {
            const trackTypeJp = trackTypeToJapanese(info.trackType);
            race.distance = `${trackTypeJp}${info.distance}m`;
            enriched++;
          }

          // Fill missing startTime
          if (!race.startTime && info.hassoJikoku.length === 4) {
            race.startTime = `${info.hassoJikoku.substring(0, 2)}:${info.hassoJikoku.substring(2, 4)}`;
          }
        }
      }
    }

    if (enriched > 0) {
      console.log(`[RaceDateIndex] DB enrichment: ${enriched} races updated from ${datesToEnrich.length} dates`);
    }
  } catch (error) {
    console.error('[RaceDateIndex] DB enrichment failed (non-fatal):', error);
  }
}

/**
 * 利用可能な日付一覧を取得（高速）
 * 必ず ensureRaceDateIndexLoaded() を await した後に呼ぶこと。未読み込み時は空配列。
 */
export function getAvailableDatesFromIndex(): string[] {
  if (!indexLoaded) return [];
  return availableDates;
}

/**
 * 指定日のレース一覧を取得（高速）
 * 必ず ensureRaceDateIndexLoaded() を await した後に呼ぶこと。未読み込み時は null。
 */
export function getRacesByDateFromIndex(date: string): DateIndexEntry | null {
  if (!indexLoaded) return null;
  return dateIndex.get(date) || null;
}

/**
 * インデックスが利用可能か（メモリに読み込み済みかつ中身あり）
 * 必ず ensureRaceDateIndexLoaded() を await した後に呼ぶこと。
 */
export function isRaceIndexAvailable(): boolean {
  return indexLoaded && dateIndex.size > 0;
}

/**
 * インデックスをクリア（再構築用）
 */
export function clearRaceDateIndex(): void {
  dateIndex.clear();
  availableDates = [];
  indexLoaded = false;
  indexLoadAttempted = false;

  try {
    if (fs.existsSync(INDEX_FILE)) {
      fs.unlinkSync(INDEX_FILE);
    }
    if (fs.existsSync(INDEX_META_FILE)) {
      fs.unlinkSync(INDEX_META_FILE);
    }
  } catch (e) {
    // ignore
  }
}
