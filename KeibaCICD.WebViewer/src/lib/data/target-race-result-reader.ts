/**
 * TARGET SE_DATA (馬毎レース成績) 読み込みユーティリティ
 * 
 * SU*.DAT: 馬毎のレース成績データ（555バイト固定長）
 * SU*.IDX: 馬毎インデックス（馬ID→レコード位置）
 */

import fs from 'fs';
import path from 'path';
import iconv from 'iconv-lite';

const JV_DATA_ROOT = process.env.JV_DATA_ROOT_DIR || 'Y:/';
const SE_DATA_PATH = path.join(JV_DATA_ROOT, 'SE_DATA');
const SE_RECORD_LEN = 555;

// インメモリキャッシュ
const fileBufferCache = new Map<string, Buffer>();
const horseRaceIndexCache = new Map<string, Array<{ file: string; offset: number }>>();
let indexBuilt = false;

/**
 * TARGET馬レース成績
 */
export interface TargetRaceResult {
  // レース識別
  raceId: string;          // レースID（年+場所+回+日+レース番号）
  raceDate: string;        // 開催日 YYYYMMDD
  venue: string;           // 開催場所コード
  kai: number;             // 回
  nichi: number;           // 日
  raceNumber: number;      // レース番号
  
  // 馬情報
  kettoNum: string;        // 血統登録番号（10桁）
  horseName: string;       // 馬名
  wakuban: number;         // 枠番
  umaban: number;          // 馬番
  sex: string;             // 性別
  age: number;             // 馬齢
  
  // 騎手・調教師
  jockeyName: string;      // 騎手名
  trainerName: string;     // 調教師名
  
  // 斤量・馬体重
  weight: number;          // 負担重量（0.1kg単位）
  horseWeight: number;     // 馬体重
  weightDiff: string;      // 馬体重増減（符号付き）
  
  // 成績
  finishPosition: number;  // 確定着順
  time: string;            // 走破タイム
  last3f: string;          // 上がり3F
  odds: number;            // 単勝オッズ
  popularity: number;      // 単勝人気
  
  // コーナー通過順
  corner1: number;
  corner2: number;
  corner3: number;
  corner4: number;
}

/**
 * Shift-JISデコード
 */
function decodeShiftJis(buffer: Buffer, start: number, length: number): string {
  try {
    const slice = buffer.subarray(start, start + length);
    return iconv.decode(slice, 'Shift_JIS').trim().replace(/\u3000/g, '');
  } catch {
    return '';
  }
}

/**
 * 競馬場コードから名称に変換
 */
function venueCodeToName(code: string): string {
  const venues: Record<string, string> = {
    '01': '札幌', '02': '函館', '03': '福島', '04': '新潟', '05': '東京',
    '06': '中山', '07': '中京', '08': '京都', '09': '阪神', '10': '小倉',
  };
  return venues[code] || code;
}

/**
 * SE_DATAのSU*.DATファイル一覧を取得
 */
function getSuDatFiles(years?: number[]): string[] {
  const files: string[] = [];
  
  if (!fs.existsSync(SE_DATA_PATH)) {
    return files;
  }

  // 指定年または直近5年分
  const targetYears = years || [2026, 2025, 2024, 2023, 2022];
  
  for (const year of targetYears) {
    const yearPath = path.join(SE_DATA_PATH, year.toString());
    if (!fs.existsSync(yearPath)) continue;
    
    try {
      const yearFiles = fs.readdirSync(yearPath)
        .filter(f => f.startsWith('SU') && f.endsWith('.DAT'))
        .map(f => path.join(yearPath, f));
      files.push(...yearFiles);
    } catch {
      // ignore
    }
  }
  
  return files;
}

/**
 * バッファをキャッシュ付きで取得
 */
function getBufferCached(filePath: string): Buffer | null {
  if (fileBufferCache.has(filePath)) {
    return fileBufferCache.get(filePath)!;
  }
  
  try {
    const buffer = fs.readFileSync(filePath);
    // 最大20ファイルまでキャッシュ
    if (fileBufferCache.size >= 20) {
      const firstKey = fileBufferCache.keys().next().value;
      if (firstKey) fileBufferCache.delete(firstKey);
    }
    fileBufferCache.set(filePath, buffer);
    return buffer;
  } catch {
    return null;
  }
}

/**
 * SU*.DATレコードをパース
 */
function parseSeRecord(buffer: Buffer, offset: number): TargetRaceResult | null {
  if (offset + SE_RECORD_LEN > buffer.length) {
    return null;
  }
  
  const record = buffer.subarray(offset, offset + SE_RECORD_LEN);
  
  // レコードタイプ確認（SE）
  const recordType = decodeShiftJis(record, 0, 2);
  if (recordType !== 'SE') {
    return null;
  }
  
  try {
    // RACE_ID: offset 11-26 (16 bytes)
    // 年(4) + 月日(4) + 場所(2) + 回(2) + 日(2) + R番号(2)
    const raceYear = decodeShiftJis(record, 11, 4);      // Year: offset 11-14
    const monthDay = decodeShiftJis(record, 15, 4);      // MonthDay: offset 15-18 (MMDD)
    const venueCode = decodeShiftJis(record, 19, 2);     // JyoCD: offset 19-20
    const kai = parseInt(decodeShiftJis(record, 21, 2), 10) || 0;     // Kaiji: offset 21-22
    const nichi = parseInt(decodeShiftJis(record, 23, 2), 10) || 0;   // Nichiji: offset 23-24
    const raceNumber = parseInt(decodeShiftJis(record, 25, 2), 10) || 0;  // RaceNum: offset 25-26
    
    // 開催日: RACE_IDのYear + MonthDay
    const raceDate = raceYear + monthDay;  // YYYYMMDD形式
    
    // 馬情報 (1-based → 0-based offset conversion)
    // Wakuban = MidB2S(28,1) → offset 27
    // Umaban = MidB2S(29,2) → offset 28-29
    // KettoNum = MidB2S(31,10) → offset 30-39
    // Bamei = MidB2S(41,36) → offset 40-75
    // SexCD = MidB2S(79,1) → offset 78
    // Barei = MidB2S(83,2) → offset 82-83
    const wakuban = parseInt(decodeShiftJis(record, 27, 1), 10) || 0;
    const umaban = parseInt(decodeShiftJis(record, 28, 2), 10) || 0;
    const kettoNum = decodeShiftJis(record, 30, 10);
    const horseName = decodeShiftJis(record, 40, 36);
    const sex = decodeShiftJis(record, 78, 1);
    const age = parseInt(decodeShiftJis(record, 82, 2), 10) || 0;
    
    // 調教師・騎手
    // ChokyosiRyakusyo = MidB2S(91,8) → offset 90-97
    // KisyuRyakusyo = MidB2S(307,8) → offset 306-313
    const trainerName = decodeShiftJis(record, 90, 8);
    const jockeyName = decodeShiftJis(record, 306, 8);
    
    // 斤量（0.1kg単位）
    // Futan = MidB2S(289,3) → offset 288-290
    const weightStr = decodeShiftJis(record, 288, 3);
    const weight = parseInt(weightStr, 10) || 0;
    
    // 馬体重
    // BaTaijyu = MidB2S(325,3) → offset 324-326
    // ZogenFugo = MidB2S(328,1) → offset 327
    // ZogenSa = MidB2S(329,3) → offset 328-330
    const horseWeightStr = decodeShiftJis(record, 324, 3);
    const horseWeight = parseInt(horseWeightStr, 10) || 0;
    const zogenFugo = decodeShiftJis(record, 327, 1);
    const zogenSa = decodeShiftJis(record, 328, 3);
    const weightDiff = zogenFugo === '+' ? `+${parseInt(zogenSa, 10)}` :
                       zogenFugo === '-' ? `-${parseInt(zogenSa, 10)}` : '';
    
    // 成績
    // KakuteiJyuni = MidB2S(335,2) → offset 334-335
    // Time = MidB2S(339,4) → offset 338-341
    const finishPosition = parseInt(decodeShiftJis(record, 334, 2), 10) || 0;
    const time = decodeShiftJis(record, 338, 4);
    
    // コーナー通過順
    // Jyuni1c = MidB2S(352,2) → offset 351-352
    // Jyuni2c = MidB2S(354,2) → offset 353-354
    // Jyuni3c = MidB2S(356,2) → offset 355-356
    // Jyuni4c = MidB2S(358,2) → offset 357-358
    const corner1 = parseInt(decodeShiftJis(record, 351, 2), 10) || 0;
    const corner2 = parseInt(decodeShiftJis(record, 353, 2), 10) || 0;
    const corner3 = parseInt(decodeShiftJis(record, 355, 2), 10) || 0;
    const corner4 = parseInt(decodeShiftJis(record, 357, 2), 10) || 0;
    
    // オッズ・人気
    // Odds = MidB2S(360,4) → offset 359-362 (×10で格納)
    // Ninki = MidB2S(364,2) → offset 363-364
    const oddsStr = decodeShiftJis(record, 359, 4);
    const odds = parseFloat(oddsStr) / 10 || 0;
    const popularity = parseInt(decodeShiftJis(record, 363, 2), 10) || 0;
    
    // 上がり3F
    // HaronTimeL3 = MidB2S(391,3) → offset 390-392
    const last3f = decodeShiftJis(record, 390, 3);
    
    // レースID生成 (形式: YYYY + 回 + 場所コード + 日 + レース番号)
    // 例: 202601060901 = 2026年第1回中山9日目1R
    const raceId = `${raceYear}${String(kai).padStart(2, '0')}${venueCode}${String(nichi).padStart(2, '0')}${String(raceNumber).padStart(2, '0')}`;
    
    return {
      raceId,
      raceDate,
      venue: venueCodeToName(venueCode),
      kai,
      nichi,
      raceNumber,
      kettoNum,
      horseName,
      wakuban,
      umaban,
      sex,
      age,
      jockeyName,
      trainerName,
      weight: weight / 10,
      horseWeight,
      weightDiff,
      finishPosition,
      time: formatTime(time),
      last3f: formatLast3f(last3f),
      odds,
      popularity,
      corner1,
      corner2,
      corner3,
      corner4,
    };
  } catch (e) {
    console.error('[TargetRaceResultReader] Parse error:', e);
    return null;
  }
}

/**
 * タイム整形（MMSS.T → M:SS.T）
 */
function formatTime(raw: string): string {
  if (!raw || raw.length < 4) return '';
  const min = parseInt(raw.substring(0, 1), 10);
  const sec = raw.substring(1, 3);
  const tenth = raw.substring(3, 4);
  return `${min}:${sec}.${tenth}`;
}

/**
 * 上がり3F整形（SST → SS.T）
 */
function formatLast3f(raw: string): string {
  if (!raw || raw.length < 3) return '';
  const sec = raw.substring(0, 2);
  const tenth = raw.substring(2, 3);
  return `${sec}.${tenth}`;
}

/**
 * 馬毎レースインデックスを構築
 */
function buildHorseRaceIndexIfNeeded(): void {
  if (indexBuilt) return;
  
  const startTime = Date.now();
  const files = getSuDatFiles();
  let recordCount = 0;
  
  for (const file of files) {
    const buffer = getBufferCached(file);
    if (!buffer) continue;
    
    const numRecords = Math.floor(buffer.length / SE_RECORD_LEN);
    
    for (let i = 0; i < numRecords; i++) {
      const offset = i * SE_RECORD_LEN;
      const kettoNum = decodeShiftJis(buffer, offset + 30, 10);
      
      if (!kettoNum) continue;
      
      if (!horseRaceIndexCache.has(kettoNum)) {
        horseRaceIndexCache.set(kettoNum, []);
      }
      horseRaceIndexCache.get(kettoNum)!.push({ file, offset });
      recordCount++;
    }
  }
  
  indexBuilt = true;
  console.log(`[TargetRaceResultReader] Index built: ${horseRaceIndexCache.size} horses, ${recordCount} records in ${Date.now() - startTime}ms`);
}

/**
 * 馬IDから過去レース成績を取得（TARGET SE_DATA）
 */
export async function getHorseRaceResultsFromTarget(kettoNum: string): Promise<TargetRaceResult[]> {
  buildHorseRaceIndexIfNeeded();
  
  const normalizedId = kettoNum.padStart(10, '0');
  const entries = horseRaceIndexCache.get(normalizedId);
  
  if (!entries || entries.length === 0) {
    return [];
  }
  
  const results: TargetRaceResult[] = [];
  
  for (const { file, offset } of entries) {
    const buffer = getBufferCached(file);
    if (!buffer) continue;
    
    const result = parseSeRecord(buffer, offset);
    if (result) {
      results.push(result);
    }
  }
  
  // 日付降順でソート
  results.sort((a, b) => b.raceDate.localeCompare(a.raceDate));
  
  return results;
}

/**
 * インデックス事前構築
 */
export function preloadTargetRaceIndex(): void {
  buildHorseRaceIndexIfNeeded();
}

/**
 * TARGET SE_DATAが利用可能かチェック
 */
export function isTargetSeDataAvailable(): boolean {
  return fs.existsSync(SE_DATA_PATH);
}
