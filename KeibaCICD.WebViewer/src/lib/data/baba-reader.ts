/**
 * BABAデータ（クッション値・ゴール前含水率・4コーナー含水率）読み込み
 * DATA_ROOT/baba 以下の CSV を参照する。
 */

import fs from 'fs';
import path from 'path';
import { BABA_DATA_PATH } from '../config';
import { getCushionLabel, getMoistureConditionLabel } from './baba-utils';

/** BABA ルート（参照するディレクトリ） */
function getEffectiveBabaPath(): string {
  return path.normalize(BABA_DATA_PATH);
}

/** デバッグ用: BABA 参照パスと存在有無 */
export function getBabaPathForDebug(): { path: string; exists: boolean } {
  const p = getEffectiveBabaPath();
  return { path: p, exists: fs.existsSync(p) && fs.statSync(p).isDirectory() };
}

/** デバッグ用: 指定年のCSVに含まれる先頭数件の RX_ID を返す */
export function getSampleRxIdsFromBaba(year: number, limit: number = 5): string[] {
  const cushionMap = getCushionMap(year);
  const keys = Array.from(cushionMap.keys());
  return keys.slice(0, limit);
}

/** デバッグ用: 指定年のクッションCSVの RX_ID 件数 */
export function getBabaCushionMapSize(year: number): number {
  return getCushionMap(year).size;
}

/** デバッグ用: 候補RX_IDがマップに存在するか + CSVに含まれる場コード一覧（2桁） */
export function getBabaDebugCandidatesAndVenues(
  year: number,
  candidateIds: string[]
): { candidateInMap: Record<string, boolean>; venueCodesInCsv: string[] } {
  const cushionMap = getCushionMap(year);
  const candidateInMap: Record<string, boolean> = {};
  for (const id of candidateIds) {
    candidateInMap[id] = cushionMap.has(id);
  }
  const venueCodes = new Set<string>();
  for (const rxId of cushionMap.keys()) {
    if (rxId.length >= 4 && rxId.startsWith('RX')) {
      venueCodes.add(rxId.substring(2, 4));
    }
  }
  return {
    candidateInMap,
    venueCodesInCsv: Array.from(venueCodes).sort(),
  };
}

export type Surface = 'turf' | 'dirt';

export interface BabaValues {
  cushion?: number;
  moistureG?: number;
  moisture4?: number;
}

/** 馬場コンディション（数値＋解釈ラベル） */
export interface BabaCondition extends BabaValues {
  /** 芝 or ダート */
  surface: Surface;
  cushionLabel?: string;
  moistureConditionLabel?: string;
}

// 競馬場名 → RX_ID用の場コード2桁（race_id の場コードと食い違う場合に URL/kaisaiInfo の競馬場を優先する）
const TRACK_TO_VENUE2: Record<string, string> = {
  '札幌': '01', '函館': '02', '福島': '03', '新潟': '04', '東京': '05',
  '中山': '06', '中京': '07', '京都': '08', '阪神': '09', '小倉': '10',
};

// RX_ID → 芝/ダート別の値
type BabaMap = Map<string, { turf?: number; dirt?: number }>;

const SURFACE_TURF = '00';
const SURFACE_DIRT = '0D';

/**
 * BABAの3列目（値）をパース: "00 9.4" or "0D10.7" → surface + number
 */
function parseBabaValue(col: string): { surface: Surface; value: number } | null {
  const s = (col || '').trim();
  if (s.length < 3) return null;
  const prefix = s.substring(0, 2);
  const rest = s.substring(2).trim().replace(/,/g, '');
  const value = parseFloat(rest);
  if (Number.isNaN(value)) return null;
  if (prefix === SURFACE_TURF) return { surface: 'turf', value };
  if (prefix === SURFACE_DIRT) return { surface: 'dirt', value };
  return null;
}

/**
 * CSV 1行をパース（列: ラベル, RX_ID, 値）
 * 値が空でも RX_ID があれば返す（行をマップに登録するため）
 */
function parseRow(line: string): { rxId: string; surface?: Surface; value?: number } | null {
  const parts = line.split(',').map((p) => p.replace(/^"|"$/g, '').trim());
  if (parts.length < 2) return null;
  const rxId = parts[1];
  if (!rxId) return null;
  const parsed = parseBabaValue(parts[2] ?? '');
  if (parsed) return { rxId, surface: parsed.surface, value: parsed.value };
  return { rxId };
}

/**
 * 指定年のクッション値CSVを読み込む
 */
function loadCushionYear(year: number): BabaMap {
  const map: BabaMap = new Map();
  const baseDir = getEffectiveBabaPath();
  const file = path.join(baseDir, `cushion${year}.csv`);
  if (!fs.existsSync(file)) return map;

  const encodings: (BufferEncoding | 'cp932')[] = ['utf-8', 'utf8', 'cp932'];
  let content: string | null = null;
  for (const enc of encodings) {
    try {
      content = fs.readFileSync(file, enc as BufferEncoding);
      break;
    } catch {
      continue;
    }
  }
  if (!content) return map;

  const lines = content.split(/\r?\n/).filter((l) => l.trim());
  for (const line of lines) {
    const row = parseRow(line);
    if (!row) continue;
    let entry = map.get(row.rxId);
    if (!entry) {
      entry = {};
      map.set(row.rxId, entry);
    }
    if (row.surface != null && row.value != null) {
      if (row.surface === 'turf') entry.turf = row.value;
      else entry.dirt = row.value;
    }
  }
  return map;
}

/**
 * 指定年の含水率CSV（moistureG または moisture4）を読み込む
 * 同一RX_IDで芝・ダート2行ある場合あり
 */
function loadMoistureYear(year: number, kind: 'G' | '4'): BabaMap {
  const map: BabaMap = new Map();
  const baseDir = getEffectiveBabaPath();
  const file = path.join(baseDir, `moisture${kind}_${year}.csv`);
  if (!fs.existsSync(file)) return map;

  const encodings: (BufferEncoding | 'cp932')[] = ['utf-8', 'utf8', 'cp932'];
  let content: string | null = null;
  for (const enc of encodings) {
    try {
      content = fs.readFileSync(file, enc as BufferEncoding);
      break;
    } catch {
      continue;
    }
  }
  if (!content) return map;

  const lines = content.split(/\r?\n/).filter((l) => l.trim());
  for (const line of lines) {
    const row = parseRow(line);
    if (!row) continue;
    let entry = map.get(row.rxId);
    if (!entry) {
      entry = {};
      map.set(row.rxId, entry);
    }
    if (row.surface != null && row.value != null) {
      if (row.surface === 'turf') entry.turf = row.value;
      else entry.dirt = row.value;
    }
  }
  return map;
}

// 年ごとのキャッシュ（同一リクエスト内で再利用）
const cacheCushion: Map<number, BabaMap> = new Map();
const cacheMoistureG: Map<number, BabaMap> = new Map();
const cacheMoisture4: Map<number, BabaMap> = new Map();

function getCushionMap(year: number): BabaMap {
  if (!cacheCushion.has(year)) {
    cacheCushion.set(year, loadCushionYear(year));
  }
  return cacheCushion.get(year)!;
}

function getMoistureGMap(year: number): BabaMap {
  if (!cacheMoistureG.has(year)) {
    cacheMoistureG.set(year, loadMoistureYear(year, 'G'));
  }
  return cacheMoistureG.get(year)!;
}

function getMoisture4Map(year: number): BabaMap {
  if (!cacheMoisture4.has(year)) {
    cacheMoisture4.set(year, loadMoistureYear(year, '4'));
  }
  return cacheMoisture4.get(year)!;
}

/**
 * race_id と 開催回・日 から BABA の RX_ID を組み立てる
 * track を渡すとその競馬場の場コードで組み立てる（race_id の場コードが誤っている場合に使用）
 * race_id: YYYYMMDD + 場コード2桁 + レース番号2桁（例: 202601250601）
 * RX_ID: RX + 場コード2桁 + 年2桁 + 回1桁 + 日1桁 + レース2桁（例: RX06261101）
 */
export function buildRxId(
  raceId: string,
  kai: number,
  nichi: number,
  track?: string
): string | null {
  if (!raceId || raceId.length < 12) return null;
  const year = raceId.substring(0, 4);
  const year2 = year.substring(2, 4);
  const venue2 = track ? (TRACK_TO_VENUE2[track] ?? raceId.substring(8, 10)) : raceId.substring(8, 10);
  const race2 = raceId.substring(10, 12);
  return `RX${venue2}${year2}${kai}${nichi}${race2}`;
}

/**
 * 検索用の RX_ID 候補リスト（CSV が回・日を 2桁で持つ場合に備える）
 * track を渡すとその競馬場の場コードで組み立てる
 */
export function buildRxIdCandidates(
  raceId: string,
  kai: number,
  nichi: number,
  track?: string
): string[] {
  const primary = buildRxId(raceId, kai, nichi, track);
  if (!primary) return [];
  const venue2 = track ? (TRACK_TO_VENUE2[track] ?? raceId.substring(8, 10)) : raceId.substring(8, 10);
  const year2 = raceId.substring(2, 4);
  const race2 = raceId.substring(10, 12);
  const kai2 = String(kai).padStart(2, '0');
  const nichi2 = String(nichi).padStart(2, '0');
  const candidates = [primary];
  const altNichi2 = `RX${venue2}${year2}${kai}${nichi2}${race2}`;
  if (altNichi2 !== primary) candidates.push(altNichi2);
  const altBoth2 = `RX${venue2}${year2}${kai2}${nichi2}${race2}`;
  if (altBoth2 !== primary && altBoth2 !== altNichi2) candidates.push(altBoth2);
  return candidates;
}

/** マップから芝/ダ別の値を最初にヒットした候補で取得 */
function getFromMapByCandidates(
  map: BabaMap,
  candidateIds: string[],
  surface: Surface
): number | undefined {
  for (const id of candidateIds) {
    const entry = map.get(id);
    const val = surface === 'turf' ? entry?.turf : entry?.dirt;
    if (val != null) return val;
  }
  return undefined;
}

/** いずれかのマップに候補が1つでも存在するか */
function hasAnyCandidateInMaps(
  candidateIds: string[],
  cushionMap: BabaMap,
  moistureGMap: BabaMap,
  moisture4Map: BabaMap
): boolean {
  for (const id of candidateIds) {
    if (cushionMap.has(id) || moistureGMap.has(id) || moisture4Map.has(id)) {
      return true;
    }
  }
  return false;
}

/**
 * レースの馬場コンディション（クッション値・含水率）を取得
 * track を渡すとその競馬場の場コードで RX_ID を組み立てる（race_id の場コードが誤っている場合に使用）
 * @param raceId - 統合レースID（YYYYMMDD + 場コード2桁 + レース2桁）
 * @param surface - 芝なら 'turf'、ダートなら 'dirt'（race_info.track から変換）
 * @param kai - 回次
 * @param nichi - 日次
 * @param track - 競馬場名（省略時は race_id の場コードを使用）
 */
export function getBabaForRace(
  raceId: string,
  surface: Surface,
  kai: number,
  nichi: number,
  track?: string
): BabaValues | null {
  const candidateIds = buildRxIdCandidates(raceId, kai, nichi, track);
  if (candidateIds.length === 0) return null;

  const year = parseInt(raceId.substring(0, 4), 10);
  if (Number.isNaN(year)) return null;

  const cushionMap = getCushionMap(year);
  const moistureGMap = getMoistureGMap(year);
  const moisture4Map = getMoisture4Map(year);

  const cushion = getFromMapByCandidates(cushionMap, candidateIds, surface);
  const moistureG = getFromMapByCandidates(moistureGMap, candidateIds, surface);
  const moisture4 = getFromMapByCandidates(moisture4Map, candidateIds, surface);

  const foundInData = hasAnyCandidateInMaps(candidateIds, cushionMap, moistureGMap, moisture4Map);
  if (!foundInData) {
    return null;
  }

  return {
    cushion: cushion != null ? cushion : undefined,
    moistureG: moistureG != null ? moistureG : undefined,
    moisture4: moisture4 != null ? moisture4 : undefined,
  };
}

/**
 * レースの馬場コンディションを取得し、解釈ラベル（クッション性・含水率目安）を付与
 * @param venue - 競馬場名（含水率→馬場状態の目安は競馬場別のため。RX_ID の場コードにも使用）
 */
export function getBabaCondition(
  raceId: string,
  surface: Surface,
  kai: number,
  nichi: number,
  venue: string
): BabaCondition | null {
  const values = getBabaForRace(raceId, surface, kai, nichi, venue);
  if (!values) return null;

  const result: BabaCondition = { ...values, surface };
  if (values.cushion != null) {
    result.cushionLabel = getCushionLabel(values.cushion);
  }
  const moisturePct = values.moistureG ?? values.moisture4;
  if (moisturePct != null) {
    result.moistureConditionLabel = getMoistureConditionLabel(venue, surface, moisturePct);
  }
  return result;
}

/**
 * race_info.track（芝/ダ）から Surface を判定
 */
export function trackToSurface(track: string): Surface {
  if (!track) return 'turf';
  if (track === '芝' || track.startsWith('芝')) return 'turf';
  return 'dirt';
}

/** 競馬場ごとの馬場サマリー（芝・ダート両方） */
export interface VenueBabaSummary {
  turf: BabaCondition | null;
  dirt: BabaCondition | null;
  hasData: boolean;
}

/**
 * 競馬場ごとの馬場情報を芝・ダート両方取得
 * レース一覧ヘッダーに表示するために使用
 * @param date - 日付（YYYY-MM-DD形式）
 * @param venue - 競馬場名
 * @param kai - 回次
 * @param nichi - 日次
 */
export function getVenueBabaSummary(
  date: string,
  venue: string,
  kai: number,
  nichi: number
): VenueBabaSummary {
  // ダミーのレースID（年月日 + 場コード + 01）を作成
  const [year, month, day] = date.split('-');
  const venueCode = TRACK_TO_VENUE2[venue] ?? '05';
  const dummyRaceId = `${year}${month}${day}${venueCode}01`;

  const turf = getBabaCondition(dummyRaceId, 'turf', kai, nichi, venue);
  const dirt = getBabaCondition(dummyRaceId, 'dirt', kai, nichi, venue);

  return {
    turf,
    dirt,
    hasData: turf !== null || dirt !== null,
  };
}
