/**
 * レースの馬名取得
 *
 * race_info.json + shutsuba/integrated JSON から馬番→馬名のマップを取得
 * JRA 16桁 race_id を keibabook race_id にマッピングしてshutsubaを読み込む
 */

import fs from 'fs';
import path from 'path';
import { DATA3_ROOT } from '../config';

const JRA_TRACK_CODES: Record<string, string> = {
  '01': '札幌',
  '02': '函館',
  '03': '福島',
  '04': '新潟',
  '05': '東京',
  '06': '中山',
  '07': '中京',
  '08': '京都',
  '09': '阪神',
  '10': '小倉',
};

/**
 * JRA 16桁 race_id から keibabook race_id を解決
 * race_info.kaisai_data のキー "N回競馬場N日目" と race_no でマッチ
 */
export function resolveKeibabookRaceId(
  jraRaceId: string,
  dayPath: string
): string | null {
  if (jraRaceId.length !== 16) return null;

  const trackCode = jraRaceId.substring(8, 10);
  const kai = parseInt(jraRaceId.substring(10, 12), 10);
  const nichi = parseInt(jraRaceId.substring(12, 14), 10);
  const raceNum = parseInt(jraRaceId.substring(14, 16), 10);
  const trackName = JRA_TRACK_CODES[trackCode];
  if (!trackName) return null;

  const raceInfoPath = path.join(dayPath, 'race_info.json');
  if (!fs.existsSync(raceInfoPath)) return null;

  try {
    const data = JSON.parse(fs.readFileSync(raceInfoPath, 'utf-8'));
    const kaisaiData = data.kaisai_data as Record<
      string,
      Array<{ race_no: string; race_id: string }>
    >;
    if (!kaisaiData) return null;

    for (const [key, races] of Object.entries(kaisaiData)) {
      const m = key.match(/(\d+)回([^\d]+)(\d+)日/);
      if (!m) continue;
      const keyKai = parseInt(m[1], 10);
      const keyTrack = m[2];
      const keyNichi = parseInt(m[3], 10);
      if (keyTrack !== trackName || keyKai !== kai || keyNichi !== nichi)
        continue;

      const target = races.find((r) => {
        const n = parseInt((r.race_no || '').replace('R', ''), 10);
        return n === raceNum;
      });
      if (target?.race_id) return target.race_id;
    }
  } catch {
    // ignore
  }
  return null;
}

/** 馬番ごとの詳細情報 */
export interface HorseInfo {
  horseName: string;
  waku?: string;
  /** 本紙印（◎○▲△×など） */
  honshiMark?: string;
  /** 騎手名 */
  jockey?: string;
  /** AI指数 */
  aiIndex?: number;
  /** レイティング */
  rating?: number;
  /** 前走着順 */
  lastResult?: string;
  /** 確定着順（結果が出ている場合） */
  finishPosition?: string;
  /** 確定タイム */
  finishTime?: string;
  /** 確定単勝オッズ */
  finalOdds?: number;
  /** 確定単勝人気 */
  finalNinki?: number;
}

/** レース条件情報 */
export interface RaceConditionInfo {
  raceCondition?: string;  // "3歳未勝利 牝" など
  track?: string;          // "芝" | "ダ" | "ダート"
  distance?: number;
}

/**
 * shutsuba または integrated JSON から馬番→詳細情報を取得
 * 2つの形式をサポート:
 * - 旧形式: data.horses (shutsuba)
 * - 新形式: data.entries (integrated v2)
 */
function loadHorseInfoFromTemp(
  dayPath: string,
  keibabookRaceId: string
): Record<string, HorseInfo> {
  const tempDir = path.join(dayPath, 'temp');
  if (!fs.existsSync(tempDir)) return {};

  // integrated を優先（結果情報を含む）
  const candidates = [
    `integrated_${keibabookRaceId}.json`,
    `shutsuba_${keibabookRaceId}.json`,
  ];

  for (const fname of candidates) {
    const fp = path.join(tempDir, fname);
    if (!fs.existsSync(fp)) continue;

    try {
      const data = JSON.parse(fs.readFileSync(fp, 'utf-8'));
      const map: Record<string, HorseInfo> = {};
      
      // 新形式: entries 配列（integrated v2）
      if (Array.isArray(data.entries)) {
        for (const entry of data.entries) {
          const ub = String(entry.horse_number || '').trim();
          const name = (entry.horse_name || '').replace(/\★/g, '').trim();
          if (!ub || !name) continue;
          
          const entryData = entry.entry_data || {};
          const result = entry.result || {};
          
          const aiIdx = entryData.ai_index ? parseFloat(entryData.ai_index) : undefined;
          const rating = entryData.rating ? parseFloat(entryData.rating) : undefined;
          const finishPosition = result.finish_position || undefined;
          const finishTime = result.time || undefined;
          // 確定オッズは raw_data または直接 result から
          const finalOddsStr = result.raw_data?.単勝オッズ || result.odds;
          const finalNinkiStr = result.raw_data?.単人気 || result.popularity;
          const finalOdds = finalOddsStr ? parseFloat(String(finalOddsStr)) : undefined;
          const finalNinki = finalNinkiStr ? parseInt(String(finalNinkiStr), 10) : undefined;
          
          map[ub] = {
            horseName: name,
            waku: entryData.waku ? String(entryData.waku).trim() : undefined,
            honshiMark: entryData.honshi_mark || entryData.marks_by_person?.本紙 || undefined,
            jockey: entryData.jockey || undefined,
            aiIndex: !isNaN(aiIdx as number) ? aiIdx : undefined,
            rating: !isNaN(rating as number) ? rating : undefined,
            lastResult: undefined, // entries形式では前走情報の取得方法が異なる
            finishPosition: finishPosition,
            finishTime: finishTime,
            finalOdds: !isNaN(finalOdds as number) ? finalOdds : undefined,
            finalNinki: !isNaN(finalNinki as number) ? finalNinki : undefined,
          };
        }
        if (Object.keys(map).length > 0) return map;
      }
      
      // 旧形式: horses 配列（shutsuba）
      const horses = data.horses as Array<{
        馬番?: string;
        馬名?: string;
        馬名_clean?: string;
        枠番?: string;
        本紙?: string;
        騎手?: string;
        AI指数?: string;
        レイティング?: string;
        前走?: string;
        result?: {
          finish_position?: string;
          time?: string;
          raw_data?: {
            単人気?: string;
            単勝オッズ?: string;
          };
        };
      }>;
      if (!Array.isArray(horses)) continue;

      for (const h of horses) {
        const ub = String(h.馬番 || '').trim();
        const name = (h.馬名 || h.馬名_clean || '').replace(/\★/g, '').trim();
        if (ub && name) {
          const aiIdx = h.AI指数 ? parseFloat(h.AI指数) : undefined;
          const rating = h.レイティング ? parseFloat(h.レイティング) : undefined;
          
          // 結果情報を取得
          const result = h.result;
          const finishPosition = result?.finish_position || undefined;
          const finishTime = result?.time || undefined;
          const finalOddsStr = result?.raw_data?.単勝オッズ;
          const finalNinkiStr = result?.raw_data?.単人気;
          const finalOdds = finalOddsStr ? parseFloat(finalOddsStr) : undefined;
          const finalNinki = finalNinkiStr ? parseInt(finalNinkiStr, 10) : undefined;
          
          map[ub] = {
            horseName: name,
            waku: h.枠番 ? String(h.枠番).trim() : undefined,
            honshiMark: h.本紙 || undefined,
            jockey: h.騎手 || undefined,
            aiIndex: !isNaN(aiIdx as number) ? aiIdx : undefined,
            rating: !isNaN(rating as number) ? rating : undefined,
            lastResult: h.前走 || undefined,
            finishPosition: finishPosition,
            finishTime: finishTime,
            finalOdds: !isNaN(finalOdds as number) ? finalOdds : undefined,
            finalNinki: !isNaN(finalNinki as number) ? finalNinki : undefined,
          };
        }
      }
      if (Object.keys(map).length > 0) return map;
    } catch {
      continue;
    }
  }
  return {};
}

/**
 * shutsuba または integrated JSON から馬番→馬名を取得（後方互換）
 */
function loadHorseNamesFromTemp(
  dayPath: string,
  keibabookRaceId: string
): Record<string, string> {
  const info = loadHorseInfoFromTemp(dayPath, keibabookRaceId);
  const map: Record<string, string> = {};
  for (const [ub, data] of Object.entries(info)) {
    map[ub] = data.horseName;
  }
  return map;
}

/**
 * v4レースJSONから馬番→HorseInfoマップを取得
 */
function loadHorseInfoFromV4(jraRaceId: string): Record<string, HorseInfo> {
  const year = jraRaceId.substring(0, 4);
  const month = jraRaceId.substring(4, 6);
  const day = jraRaceId.substring(6, 8);
  const filePath = path.join(DATA3_ROOT, 'races', year, month, day, `race_${jraRaceId}.json`);

  if (!fs.existsSync(filePath)) return {};

  try {
    const data = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    const map: Record<string, HorseInfo> = {};
    for (const entry of data.entries || []) {
      const ub = String(entry.umaban || '');
      if (!ub || !entry.horse_name) continue;
      map[ub] = {
        horseName: entry.horse_name,
        waku: String(entry.wakuban || ''),
        jockey: entry.jockey_name || undefined,
        finishPosition: entry.finish_position > 0 ? String(entry.finish_position) : undefined,
        finishTime: entry.time || undefined,
        finalOdds: entry.odds > 0 ? entry.odds : undefined,
        finalNinki: entry.popularity > 0 ? entry.popularity : undefined,
      };
    }
    return map;
  } catch {
    return {};
  }
}

/**
 * JRA 16桁 race_id から馬番→馬名マップを取得
 */
export function getHorseNamesByUmaban(jraRaceId: string): Record<string, string> {
  if (jraRaceId.length !== 16) return {};

  // v4 race JSONから直接取得
  const info = loadHorseInfoFromV4(jraRaceId);
  if (Object.keys(info).length > 0) {
    const map: Record<string, string> = {};
    for (const [ub, data] of Object.entries(info)) {
      map[ub] = data.horseName;
    }
    return map;
  }

  // レガシーフォールバック（data2）
  const year = jraRaceId.substring(0, 4);
  const month = jraRaceId.substring(4, 6);
  const day = jraRaceId.substring(6, 8);
  const dayPath = path.join(DATA3_ROOT, 'races', year, month, day);

  const keibabookId = resolveKeibabookRaceId(jraRaceId, dayPath);
  if (!keibabookId) return {};

  return loadHorseNamesFromTemp(dayPath, keibabookId);
}

/**
 * 馬番の表記ゆれを吸収して馬名を取得
 * shutsuba は "8","10"、RT は "08","10" など混在するため
 */
export function lookupHorseName(
  horseNames: Record<string, string>,
  umaban: string
): string | undefined {
  const u = String(umaban || '').trim();
  if (!u) return undefined;
  return (
    horseNames[u] ??
    horseNames[u.replace(/^0+/, '')] ??
    horseNames[u.padStart(2, '0')]
  );
}

/**
 * JRA 16桁 race_id から馬番→詳細情報マップを取得
 */
export function getHorseInfoByUmaban(jraRaceId: string): Record<string, HorseInfo> {
  if (jraRaceId.length !== 16) return {};

  // v4 race JSONから直接取得
  const v4Info = loadHorseInfoFromV4(jraRaceId);
  if (Object.keys(v4Info).length > 0) return v4Info;

  // レガシーフォールバック
  const year = jraRaceId.substring(0, 4);
  const month = jraRaceId.substring(4, 6);
  const day = jraRaceId.substring(6, 8);
  const dayPath = path.join(DATA3_ROOT, 'races', year, month, day);

  const keibabookId = resolveKeibabookRaceId(jraRaceId, dayPath);
  if (!keibabookId) return {};

  return loadHorseInfoFromTemp(dayPath, keibabookId);
}

/**
 * 馬番の表記ゆれを吸収して詳細情報を取得
 */
export function lookupHorseInfo(
  horseInfo: Record<string, HorseInfo>,
  umaban: string
): HorseInfo | undefined {
  const u = String(umaban || '').trim();
  if (!u) return undefined;
  return (
    horseInfo[u] ??
    horseInfo[u.replace(/^0+/, '')] ??
    horseInfo[u.padStart(2, '0')]
  );
}

/**
 * shutsuba/integrated JSON からレース条件情報を取得
 */
function loadRaceConditionFromTemp(
  dayPath: string,
  keibabookRaceId: string
): RaceConditionInfo | null {
  const tempDir = path.join(dayPath, 'temp');
  if (!fs.existsSync(tempDir)) return null;

  const candidates = [
    `shutsuba_${keibabookRaceId}.json`,
    `integrated_${keibabookRaceId}.json`,
  ];

  for (const fname of candidates) {
    const fp = path.join(tempDir, fname);
    if (!fs.existsSync(fp)) continue;

    try {
      const data = JSON.parse(fs.readFileSync(fp, 'utf-8'));
      const raceInfo = data.race_info as {
        race_condition?: string;
        track?: string;
        distance?: number;
      };
      if (!raceInfo) continue;

      return {
        raceCondition: raceInfo.race_condition,
        track: raceInfo.track,
        distance: raceInfo.distance,
      };
    } catch {
      continue;
    }
  }
  return null;
}

/**
 * JRA 16桁 race_id からレース条件情報を取得
 */
export function getRaceConditionInfo(jraRaceId: string): RaceConditionInfo | null {
  if (jraRaceId.length !== 16) return null;

  // v4 race JSONから直接取得
  const year = jraRaceId.substring(0, 4);
  const month = jraRaceId.substring(4, 6);
  const day = jraRaceId.substring(6, 8);
  const filePath = path.join(DATA3_ROOT, 'races', year, month, day, `race_${jraRaceId}.json`);

  if (fs.existsSync(filePath)) {
    try {
      const data = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
      const trackMap: Record<string, string> = { turf: '芝', dirt: 'ダ' };
      return {
        raceCondition: data.grade || '',
        track: trackMap[data.track_type] || data.track_type || '',
        distance: data.distance || 0,
      };
    } catch { /* fall through */ }
  }

  // レガシーフォールバック
  const dayPath = path.join(DATA3_ROOT, 'races', year, month, day);
  const keibabookId = resolveKeibabookRaceId(jraRaceId, dayPath);
  if (!keibabookId) return null;

  return loadRaceConditionFromTemp(dayPath, keibabookId);
}
