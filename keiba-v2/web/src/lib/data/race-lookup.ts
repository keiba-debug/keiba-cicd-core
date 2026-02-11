/**
 * race_info.json 検索ユーティリティ
 * 
 * 日付 + 競馬場 + レース名 から race_info.json を検索して
 * レース番号や回次・日次情報を取得する
 */

import { promises as fs } from 'fs';
import path from 'path';
import { DATA_ROOT } from '../config';

export interface RaceInfoResult {
  date: string;           // YYYYMMDD
  track: string;          // 競馬場名
  raceNumber: number;     // レース番号
  raceId: string;         // レースID
  raceName: string;       // レース名
  kaisai: string;         // 回次・日次 (例: "5回中山1日目")
  kai: number;            // 回次
  nichi: number;          // 日次
}

export interface RaceLookupQuery {
  date: string;           // YYYY/MM/DD or YYYYMMDD
  track: string;          // 競馬場名（"東京", "中山" など）
  raceName?: string;      // レース名（部分一致検索）
  raceNumber?: number;    // レース番号（直接指定する場合）
  distance?: string;      // 距離（"芝1800" など）
}

/**
 * 競馬場名の正規化
 * "4東京11" -> "東京"
 * "東京" -> "東京"
 */
function normalizeTrackName(rawTrack: string): string {
  // 数字を除去して競馬場名だけを抽出
  const match = rawTrack.match(/[^\d]+/);
  if (match) {
    return match[0].trim();
  }
  return rawTrack.trim();
}

/**
 * 開催情報をパース
 * "4東京11" -> { kai: 4, track: "東京", nichi: 11 }
 */
export function parseKaisaiInfo(rawTrack: string): { kai: number; track: string; nichi: number } | null {
  const match = rawTrack.match(/^(\d+)([^\d]+)(\d+)$/);
  if (match) {
    return {
      kai: parseInt(match[1], 10),
      track: match[2],
      nichi: parseInt(match[3], 10),
    };
  }
  return null;
}

/**
 * 日付を正規化
 * "2025/11/02" -> { year: "2025", month: "11", day: "02", yyyymmdd: "20251102" }
 */
function normalizeDate(dateStr: string): { year: string; month: string; day: string; yyyymmdd: string } | null {
  // YYYY/MM/DD 形式
  let match = dateStr.match(/^(\d{4})\/(\d{1,2})\/(\d{1,2})$/);
  if (match) {
    const year = match[1];
    const month = match[2].padStart(2, '0');
    const day = match[3].padStart(2, '0');
    return { year, month, day, yyyymmdd: `${year}${month}${day}` };
  }
  
  // YYYYMMDD 形式
  match = dateStr.match(/^(\d{4})(\d{2})(\d{2})$/);
  if (match) {
    return { year: match[1], month: match[2], day: match[3], yyyymmdd: dateStr };
  }
  
  return null;
}

/**
 * race_info.json を読み込む
 */
async function loadRaceInfo(year: string, month: string, day: string): Promise<Record<string, unknown> | null> {
  const raceInfoPath = path.join(DATA_ROOT, 'races', year, month, day, 'race_info.json');
  
  try {
    const content = await fs.readFile(raceInfoPath, 'utf-8');
    return JSON.parse(content);
  } catch {
    return null;
  }
}

/**
 * kaisai_dataのキーから競馬場名を抽出
 * "4回東京11日目" -> "東京"
 */
function extractTrackFromKaisaiKey(kaisaiKey: string): string | null {
  const match = kaisaiKey.match(/\d+回([^\d]+)\d+日/);
  return match ? match[1] : null;
}

/**
 * 全角数字を半角に変換
 */
function fullWidthToHalfWidth(str: string): string {
  return str.replace(/[０-９]/g, (char) => 
    String.fromCharCode(char.charCodeAt(0) - 0xFEE0)
  );
}

/**
 * レース名を正規化（表記揺れ対応）
 * "3歳上1勝クラス" -> "3歳以上1勝クラス"
 * "４歳上２勝クラス" -> "4歳以上2勝クラス"
 */
function normalizeRaceName(raceName: string): string {
  const normalized = fullWidthToHalfWidth(raceName)
    .replace(/（/g, ' (')               // 全角括弧を半角に
    .replace(/）/g, ') ')
    .replace(/\s+/g, ' ')               // 連続スペースを1つに
    .replace(/Ｓ/g, 'S')
    .replace(/[ＧG]/g, 'G')
    .replace(/G\s*[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ0-9]+/g, '')
    .replace(/(\d)歳上/g, '$1歳以上')   // 「3歳上」→「3歳以上」
    .trim();

  const aliasMap: Record<string, string> = {
    'エ女王杯': 'エリザベス女王杯',
    'エリ女王杯': 'エリザベス女王杯',
    'クイーS': 'クイーンS',
  };

  for (const [alias, full] of Object.entries(aliasMap)) {
    if (normalized.includes(alias)) {
      return normalized.replace(alias, full).replace(/\s+/g, ' ').trim();
    }
  }

  return normalized;
}

/**
 * 距離表記を正規化（芝/ダ/障 + 数字）
 * "芝外・1800m" -> "芝1800"
 * "ダート1200" -> "ダ1200"
 */
function normalizeCourse(raw: string): string | null {
  const cleaned = fullWidthToHalfWidth(raw).replace(/\s+/g, '');
  if (!cleaned) return null;
  const surface = cleaned.includes('障')
    ? '障'
    : cleaned.includes('ダ')
    ? 'ダ'
    : cleaned.includes('芝')
    ? '芝'
    : null;
  const distanceMatch = cleaned.match(/(\d{3,4})/);
  if (!surface || !distanceMatch) return null;
  return `${surface}${distanceMatch[1]}`;
}

/**
 * 限定条件（牝、牡、混合など）を除去してベースのレース名を取得
 */
function getBaseRaceName(raceName: string): string {
  return raceName
    .replace(/\s*\(牝\)\s*/g, '')
    .replace(/\s*\(牡\)\s*/g, '')
    .replace(/\s*（牝）\s*/g, '')
    .replace(/\s*（牡）\s*/g, '')
    .replace(/\s*\[牝\]\s*/g, '')
    .replace(/\s*\[牡\]\s*/g, '')
    .trim();
}

/**
 * 2つのレース名が一致するか判定（正規化後に比較）
 */
function matchRaceNames(raceName1: string, raceName2: string): boolean {
  const n1 = normalizeRaceName(raceName1);
  const n2 = normalizeRaceName(raceName2);
  
  // 完全一致
  if (n1 === n2) return true;
  
  // 部分一致（片方がもう片方を含む）
  if (n1.includes(n2) || n2.includes(n1)) return true;
  
  // ベース名（限定条件を除く）で比較
  const base1 = getBaseRaceName(n1);
  const base2 = getBaseRaceName(n2);
  if (base1 === base2) return true;
  if (base1.includes(base2) || base2.includes(base1)) return true;
  
  return false;
}

/**
 * レース情報を検索
 */
export async function lookupRace(query: RaceLookupQuery): Promise<RaceInfoResult | null> {
  const dateInfo = normalizeDate(query.date);
  if (!dateInfo) {
    return null;
  }
  
  const raceInfo = await loadRaceInfo(dateInfo.year, dateInfo.month, dateInfo.day);
  if (!raceInfo) {
    return null;
  }
  
  const normalizedTrack = normalizeTrackName(query.track);
  
  // kaisai_data から競馬場に一致するエントリを探す
  // 構造: { "4回東京11日目": [ { race_no, race_name, course, race_id }, ... ] }
  const kaisaiData = raceInfo.kaisai_data as Record<string, Array<{ race_no: string; race_name: string; course: string; race_id: string }>> | undefined;
  
  if (!kaisaiData) {
    return null;
  }
  
  // 競馬場名に一致するキーを探す
  let targetKaisaiKey: string | null = null;
  let races: Array<{ race_no: string; race_name: string; course: string; race_id: string }> = [];
  
  for (const [key, raceList] of Object.entries(kaisaiData)) {
    const trackFromKey = extractTrackFromKaisaiKey(key);
    if (trackFromKey === normalizedTrack) {
      targetKaisaiKey = key;
      races = raceList;
      break;
    }
  }
  
  if (!targetKaisaiKey || races.length === 0) {
    return null;
  }
  
  // "4回東京11日目" -> kai=4, nichi=11
  const kaisaiMatch = targetKaisaiKey.match(/(\d+)回[^\d]+(\d+)日/);
  const kai = kaisaiMatch ? parseInt(kaisaiMatch[1], 10) : 0;
  const nichi = kaisaiMatch ? parseInt(kaisaiMatch[2], 10) : 0;
  
  let targetRace: { race_no: string; race_name: string; course: string; race_id: string } | undefined;
  const normalizedDistance = query.distance ? normalizeCourse(query.distance) : null;
  
  // レース番号で直接検索
  if (query.raceNumber !== undefined) {
    targetRace = races.find(r => {
      const raceNum = parseInt(r.race_no.replace('R', ''), 10);
      return raceNum === query.raceNumber;
    });
  }
  // レース名で検索（正規化後に比較）
  else if (query.raceName) {
    const normalizedQuery = normalizeRaceName(query.raceName);
    
    // 1. 正規化後の完全一致
    const exactMatches = races.filter(r => normalizeRaceName(r.race_name) === normalizedQuery);
    if (exactMatches.length === 1) {
      targetRace = exactMatches[0];
    } else if (exactMatches.length > 1 && normalizedDistance) {
      targetRace = exactMatches.find(r => normalizeCourse(r.course) === normalizedDistance);
    }
    
    if (!targetRace) {
      // 2. 正規化後の部分一致（(牝)などの限定条件を除いた比較）
      // ただし、同名レースが複数ある場合は最初のマッチのみ返す
      const nameMatches = races.filter(r => matchRaceNames(r.race_name, query.raceName!));
      if (nameMatches.length === 1) {
        targetRace = nameMatches[0];
      } else if (nameMatches.length > 1 && normalizedDistance) {
        targetRace = nameMatches.find(r => normalizeCourse(r.course) === normalizedDistance);
      }
    }
    
    if (!targetRace) {
      // 3. より緩い部分一致（レース名の主要キーワード）
      const searchTerms = normalizedQuery.replace(/[（）\(\)Ｇ\s]/g, '').split(/クラス|特別|賞|Ｓ/);
      const mainTerm = searchTerms[0]; // 主要部分（例: "3歳以上1勝"）
      if (mainTerm && mainTerm.length >= 3) {
        const looseMatches = races.filter(r => normalizeRaceName(r.race_name).includes(mainTerm));
        if (looseMatches.length === 1) {
          targetRace = looseMatches[0];
        } else if (looseMatches.length > 1 && normalizedDistance) {
          targetRace = looseMatches.find(r => normalizeCourse(r.course) === normalizedDistance);
        }
      }
    }
  } else if (normalizedDistance) {
    const distanceMatches = races.filter(r => normalizeCourse(r.course) === normalizedDistance);
    if (distanceMatches.length === 1) {
      targetRace = distanceMatches[0];
    }
  }
  
  if (!targetRace) {
    return null;
  }
  
  const raceNumber = parseInt(targetRace.race_no.replace('R', ''), 10);
  
  return {
    date: dateInfo.yyyymmdd,
    track: normalizedTrack,
    raceNumber,
    raceId: targetRace.race_id,
    raceName: targetRace.race_name,
    kaisai: targetKaisaiKey,
    kai,
    nichi,
  };
}

/**
 * 馬の過去成績から複数のレース情報を一括検索
 */
export async function lookupRaces(queries: RaceLookupQuery[]): Promise<(RaceInfoResult | null)[]> {
  return Promise.all(queries.map(q => lookupRace(q)));
}

/**
 * 指定日の全レース情報を取得
 */
export async function getAllRacesForDate(dateStr: string): Promise<RaceInfoResult[]> {
  const dateInfo = normalizeDate(dateStr);
  if (!dateInfo) {
    return [];
  }
  
  const raceInfo = await loadRaceInfo(dateInfo.year, dateInfo.month, dateInfo.day);
  if (!raceInfo) {
    return [];
  }
  
  const results: RaceInfoResult[] = [];
  const kaisaiData = raceInfo.kaisai_data as Record<string, Array<{ race_no: string; race_name: string; course: string; race_id: string }>> | undefined;
  
  if (!kaisaiData) {
    return [];
  }
  
  for (const [kaisaiKey, races] of Object.entries(kaisaiData)) {
    const track = extractTrackFromKaisaiKey(kaisaiKey);
    if (!track) continue;
    
    const kaisaiMatch = kaisaiKey.match(/(\d+)回[^\d]+(\d+)日/);
    const kai = kaisaiMatch ? parseInt(kaisaiMatch[1], 10) : 0;
    const nichi = kaisaiMatch ? parseInt(kaisaiMatch[2], 10) : 0;
    
    for (const race of races) {
      const raceNumber = parseInt(race.race_no.replace('R', ''), 10);
      results.push({
        date: dateInfo.yyyymmdd,
        track,
        raceNumber,
        raceId: race.race_id,
        raceName: race.race_name,
        kaisai: kaisaiKey,
        kai,
        nichi,
      });
    }
  }
  
  return results;
}
