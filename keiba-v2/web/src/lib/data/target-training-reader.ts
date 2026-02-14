/**
 * TARGET CK_DATA (調教データ) 読み込みユーティリティ
 * 
 * WC*.DAT: 坂路調教データ（92バイト固定長）
 * HC*.DAT: コース調教データ（47バイト固定長）
 * 
 * ファイル名規則:
 * - WC{場所}{YYYYMMDD}.DAT: 坂路調教（0=美浦、1=栗東）
 * - HC{場所}{YYYYMMDD}.DAT: コース調教（0=美浦、1=栗東）
 */

import fs from 'fs';
import path from 'path';
import iconv from 'iconv-lite';
import { DATA3_ROOT } from '@/lib/config';
import { getHorseRaceResultsFromTarget, preloadTargetRaceIndex } from './target-race-result-reader';

const JV_DATA_ROOT = process.env.JV_DATA_ROOT || 'Y:/';
const CK_DATA_PATH = path.join(JV_DATA_ROOT, 'CK_DATA');
const UM_DATA_PATH = path.join(JV_DATA_ROOT, 'UM_DATA');

// レコード長
const WC_RECORD_LEN = 94;  // 92バイト + CRLF(2バイト)
const HC_RECORD_LEN = 49;  // 47バイト + CRLF(2バイト)
const UM_RECORD_LEN = 1609;  // UM_DATAのレコード長

// インメモリキャッシュ
const fileBufferCache = new Map<string, Buffer>();
const horseNameCache = new Map<string, string>();
const umDataCache = new Map<string, Buffer>();  // UM_DATAファイルキャッシュ

/**
 * 坂路調教レコード
 *
 * レコード構造（92バイト + CRLF）:
 * 位置0: 場所コード (1) — '0'=美浦, '1'=栗東
 * 位置1-8: 日付 YYYYMMDD (8)
 * 位置9-12: 時刻 HHMM (4)
 * 位置13-22: 血統登録番号 (10)
 * 位置23-67: 各種フラグ/予備 (45)
 * 位置68-71: 4Fタイム合計 (4) — 0.1秒単位 (例: 0527 = 52.7s)
 * 位置72-74: Lap4 (3) — 0.1秒単位
 * 位置75-78: 3Fタイム合計 (4)
 * 位置79-81: Lap3 (3)
 * 位置82-85: 2Fタイム合計 (4)
 * 位置86-88: Lap2 (3)
 * 位置89-91: Lap1 (3)
 */
export interface TrainingRecord {
  recordType: 'sakamichi' | 'course';
  date: string;           // YYYY/MM/DD
  time: string;           // HH:MM
  kettoNum: string;       // 血統登録番号（10桁）
  location: string;       // 美浦 or 栗東
  
  // 坂路専用フィールド
  time4f?: string;        // 4Fタイム（例: "52.3"）
  time3f?: string;        // 3Fタイム
  time2f?: string;        // 2Fタイム
  lap4?: string;          // ラップ4
  lap3?: string;          // ラップ3
  lap2?: string;          // ラップ2
  lap1?: string;          // ラップ1
  
  // コース専用フィールド
  time5f?: string;        // 5Fタイム
  
  // 付加情報（後でマージ）
  horseName?: string;     // 馬名
  trainerName?: string;   // 調教師名
}

/**
 * 調教データ集計結果
 */
export interface TrainingSummary {
  horseName: string;
  kettoNum: string;
  trainerName: string;
  lapRank: string;        // SS, S+, A-, B= など
  timeRank: string;       // 坂, コ, 両, -
  detail: string;         // 調教詳細
}

/**
 * Shift-JISデコード
 */
function decodeShiftJis(buffer: Buffer, start: number, length: number): string {
  try {
    const slice = buffer.subarray(start, start + length);
    return iconv.decode(slice, 'Shift_JIS').trim();
  } catch {
    return '';
  }
}

/**
 * タイム整形（4桁→秒.1秒）
 */
function formatTime(raw: string): string {
  if (!raw || raw.length < 3) return '';
  const val = parseInt(raw, 10);
  if (isNaN(val) || val === 0) return '';
  const sec = Math.floor(val / 10);
  const tenth = val % 10;
  return `${sec}.${tenth}`;
}

/**
 * ラップ整形（3桁→秒.1秒）
 */
function formatLap(raw: string): string {
  if (!raw || raw.length < 3) return '';
  const val = parseInt(raw, 10);
  if (isNaN(val) || val === 0) return '';
  const sec = Math.floor(val / 10);
  const tenth = val % 10;
  return `${sec}.${tenth}`;
}

/**
 * 場所コードから名称に変換
 * ファイル名から取得: WC0 = 美浦, WC1 = 栗東
 */
function locationCodeToName(code: string): string {
  if (code === '0') return 'Miho';
  if (code === '1') return 'Ritto';
  return code;
}

/**
 * 坂路調教レコードをパース
 */
function parseWcRecord(buffer: Buffer, offset: number, location: string): TrainingRecord | null {
  if (offset + 92 > buffer.length) {
    return null;
  }

  try {
    // レコードタイプ: '0'=美浦, '1'=栗東（両方とも有効な調教レコード）
    const recordType = decodeShiftJis(buffer, offset, 1);
    if (recordType !== '0' && recordType !== '1') {
      return null;
    }
    
    const dateRaw = decodeShiftJis(buffer, offset + 1, 8);
    const timeRaw = decodeShiftJis(buffer, offset + 9, 4);
    const kettoNum = decodeShiftJis(buffer, offset + 13, 10);
    
    // タイム・ラップ（位置68-91）
    const time4fRaw = decodeShiftJis(buffer, offset + 68, 4);
    const lap4Raw = decodeShiftJis(buffer, offset + 72, 3);
    const time3fRaw = decodeShiftJis(buffer, offset + 75, 4);
    const lap3Raw = decodeShiftJis(buffer, offset + 79, 3);
    const time2fRaw = decodeShiftJis(buffer, offset + 82, 4);
    const lap2Raw = decodeShiftJis(buffer, offset + 86, 3);
    const lap1Raw = decodeShiftJis(buffer, offset + 89, 3);
    
    // 日付整形
    const date = dateRaw.length === 8 
      ? `${dateRaw.substring(0, 4)}/${dateRaw.substring(4, 6)}/${dateRaw.substring(6, 8)}`
      : '';
    
    // 時刻整形
    const time = timeRaw.length === 4 
      ? `${timeRaw.substring(0, 2)}:${timeRaw.substring(2, 4)}`
      : '';
    
    return {
      recordType: 'sakamichi',
      date,
      time,
      kettoNum,
      location: locationCodeToName(location),
      time4f: formatTime(time4fRaw),
      time3f: formatTime(time3fRaw),
      time2f: formatTime(time2fRaw),
      lap4: formatLap(lap4Raw),
      lap3: formatLap(lap3Raw),
      lap2: formatLap(lap2Raw),
      lap1: formatLap(lap1Raw),
    };
  } catch (e) {
    console.error('[TargetTrainingReader] Parse WC error:', e);
    return null;
  }
}

/**
 * コース調教レコードをパース
 */
function parseHcRecord(buffer: Buffer, offset: number, location: string): TrainingRecord | null {
  if (offset + 47 > buffer.length) {
    return null;
  }

  try {
    // レコードタイプ: '0'=美浦, '1'=栗東（両方とも有効な調教レコード）
    const recordType = decodeShiftJis(buffer, offset, 1);
    if (recordType !== '0' && recordType !== '1') {
      return null;
    }
    
    const dateRaw = decodeShiftJis(buffer, offset + 1, 8);
    const timeRaw = decodeShiftJis(buffer, offset + 9, 4);
    const kettoNum = decodeShiftJis(buffer, offset + 13, 10);
    
    // コース調教タイム（HC 47バイトレコード）
    // 位置23: 5Fタイム(4B), 位置27: 5F-3F差(3B), 位置30: 3Fタイム(4B)
    // 位置34: Lap3(3B), 位置37: 2Fタイム(4B), 位置41: Lap2(3B), 位置44: Lap1(3B)
    const time5fRaw = decodeShiftJis(buffer, offset + 23, 4);
    const time3fRaw = decodeShiftJis(buffer, offset + 30, 4);
    const time2fRaw = decodeShiftJis(buffer, offset + 37, 4);
    const lap2Raw = decodeShiftJis(buffer, offset + 41, 3);
    const lap1Raw = decodeShiftJis(buffer, offset + 44, 3);
    
    // 日付整形
    const date = dateRaw.length === 8 
      ? `${dateRaw.substring(0, 4)}/${dateRaw.substring(4, 6)}/${dateRaw.substring(6, 8)}`
      : '';
    
    // 時刻整形
    const time = timeRaw.length === 4 
      ? `${timeRaw.substring(0, 2)}:${timeRaw.substring(2, 4)}`
      : '';
    
    const t5f = formatTime(time5fRaw);
    const t3f = formatTime(time3fRaw);

    // time4f近似: (5F + 3F) / 2  — HC形式には4Fフィールドが無いため
    let t4f: string | undefined;
    const n5f = parseFloat(t5f);
    const n3f = parseFloat(t3f);
    if (!isNaN(n5f) && !isNaN(n3f) && n5f > n3f) {
      t4f = ((n5f + n3f) / 2).toFixed(1);
    }

    return {
      recordType: 'course',
      date,
      time,
      kettoNum,
      location: locationCodeToName(location),
      time5f: t5f,
      time4f: t4f,
      time3f: t3f,
      time2f: formatTime(time2fRaw),
      lap2: formatLap(lap2Raw),
      lap1: formatLap(lap1Raw),
    };
  } catch (e) {
    console.error('[TargetTrainingReader] Parse HC error:', e);
    return null;
  }
}

/**
 * バッファをキャッシュ付きで取得
 */
function getBufferCached(filePath: string): Buffer | null {
  if (fileBufferCache.has(filePath)) {
    return fileBufferCache.get(filePath)!;
  }
  
  try {
    if (!fs.existsSync(filePath)) {
      return null;
    }
    const buffer = fs.readFileSync(filePath);
    // 最大50ファイルまでキャッシュ
    if (fileBufferCache.size >= 50) {
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
 * 指定日の調教データファイルパスを取得
 */
function getTrainingFilePaths(dateStr: string): { wc: string[]; hc: string[] } {
  // dateStr: YYYYMMDD
  if (dateStr.length !== 8) {
    return { wc: [], hc: [] };
  }
  
  const year = dateStr.substring(0, 4);
  const yearMonth = dateStr.substring(0, 6);
  
  const basePath = path.join(CK_DATA_PATH, year, yearMonth);
  
  const wc: string[] = [];
  const hc: string[] = [];
  
  // 美浦・栗東の両方をチェック
  for (const loc of ['0', '1']) {
    const wcFile = path.join(basePath, `WC${loc}${dateStr}.DAT`);
    const hcFile = path.join(basePath, `HC${loc}${dateStr}.DAT`);
    
    if (fs.existsSync(wcFile)) {
      wc.push(wcFile);
    }
    if (fs.existsSync(hcFile)) {
      hc.push(hcFile);
    }
  }
  
  return { wc, hc };
}

/**
 * 指定日の全調教データを取得
 */
export async function getTrainingDataForDate(dateStr: string): Promise<TrainingRecord[]> {
  const { wc, hc } = getTrainingFilePaths(dateStr);
  const records: TrainingRecord[] = [];
  
  // 坂路調教
  for (const filePath of wc) {
    const buffer = getBufferCached(filePath);
    if (!buffer) continue;
    
    const location = path.basename(filePath).charAt(2); // WC{0|1}...
    const content = iconv.decode(buffer, 'Shift_JIS');
    const lines = content.split('\r\n');
    
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      if (line.length < 70) continue;
      
      // テキストとして処理（固定長）
      const record = parseWcRecordFromText(line, location);
      if (record) {
        records.push(record);
      }
    }
  }
  
  // コース調教
  for (const filePath of hc) {
    const buffer = getBufferCached(filePath);
    if (!buffer) continue;
    
    const location = path.basename(filePath).charAt(2); // HC{0|1}...
    const content = iconv.decode(buffer, 'Shift_JIS');
    const lines = content.split('\r\n');
    
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      if (line.length < 40) continue;
      
      const record = parseHcRecordFromText(line, location);
      if (record) {
        records.push(record);
      }
    }
  }
  
  return records;
}

/**
 * テキスト行から坂路調教レコードをパース
 * 
 * レコード構造（92バイト）:
 * [0]: レコードタイプ (1)
 * [1-8]: 日付 YYYYMMDD
 * [9-12]: 時刻 HHMM
 * [13-22]: 血統登録番号 (10桁)
 * [23-24]: 何か（不明）
 * ... 中間部分（フラグ/オプション）
 * 末尾から逆算:
 * [-6..-4]: Lap1 (0.1秒単位)
 * [-9..-7]: Lap2
 * [-12..-10]: 2Fタイム
 * [-15..-13]: Lap3
 * [-18..-16]: 3Fタイム
 * [-21..-19]: Lap4
 * [-24..-22]: 4Fタイム
 */
function parseWcRecordFromText(line: string, location: string): TrainingRecord | null {
  if (line.length < 70) return null;

  try {
    // レコードタイプ: '0'=美浦, '1'=栗東（両方とも有効な調教レコード）
    const recordType = line.charAt(0);
    if (recordType !== '0' && recordType !== '1') return null;
    
    const dateRaw = line.substring(1, 9);
    const timeRaw = line.substring(9, 13);
    const kettoNum = line.substring(13, 23);
    
    // 末尾から逆算してタイム・ラップを取得
    const len = line.length;
    
    // 末尾6バイト: Lap1(3) + 何か(3)? → 実際には末尾3バイトがLap1
    const lap1Raw = line.substring(len - 3);
    const lap2Raw = line.substring(len - 6, len - 3);
    const time2fRaw = line.substring(len - 10, len - 6);  // 4桁
    const lap3Raw = line.substring(len - 13, len - 10);
    const time3fRaw = line.substring(len - 17, len - 13);
    const lap4Raw = line.substring(len - 20, len - 17);
    const time4fRaw = line.substring(len - 24, len - 20);
    
    const date = `${dateRaw.substring(0, 4)}/${dateRaw.substring(4, 6)}/${dateRaw.substring(6, 8)}`;
    const time = `${timeRaw.substring(0, 2)}:${timeRaw.substring(2, 4)}`;
    
    return {
      recordType: 'sakamichi',
      date,
      time,
      kettoNum,
      location: locationCodeToName(location),
      time4f: formatTime(time4fRaw),
      time3f: formatTime(time3fRaw),
      time2f: formatTime(time2fRaw),
      lap4: formatLap(lap4Raw),
      lap3: formatLap(lap3Raw),
      lap2: formatLap(lap2Raw),
      lap1: formatLap(lap1Raw),
    };
  } catch {
    return null;
  }
}

/**
 * テキスト行からコース調教レコードをパース
 */
function parseHcRecordFromText(line: string, location: string): TrainingRecord | null {
  if (line.length < 40) return null;

  try {
    const recordType = line.charAt(0);
    if (recordType !== '0' && recordType !== '1') return null;

    const dateRaw = line.substring(1, 9);
    const timeRaw = line.substring(9, 13);
    const kettoNum = line.substring(13, 23);

    // コース調教タイム（HC 47バイトレコード）
    // 位置23: 5Fタイム(4B), 位置27: 5F-3F差(3B), 位置30: 3Fタイム(4B)
    // 位置34: Lap3(3B), 位置37: 2Fタイム(4B), 位置41: Lap2(3B), 位置44: Lap1(3B)
    const time5fRaw = line.substring(23, 27);
    const time3fRaw = line.substring(30, 34);
    const time2fRaw = line.substring(37, 41);
    const lap2Raw = line.substring(41, 44);
    const lap1Raw = line.substring(44, 47);

    const date = `${dateRaw.substring(0, 4)}/${dateRaw.substring(4, 6)}/${dateRaw.substring(6, 8)}`;
    const time = `${timeRaw.substring(0, 2)}:${timeRaw.substring(2, 4)}`;

    const t5f = formatTime(time5fRaw);
    const t3f = formatTime(time3fRaw);

    // time4f近似: (5F + 3F) / 2  — HC形式には4Fフィールドが無いため
    let t4f: string | undefined;
    const n5f = parseFloat(t5f);
    const n3f = parseFloat(t3f);
    if (!isNaN(n5f) && !isNaN(n3f) && n5f > n3f) {
      t4f = ((n5f + n3f) / 2).toFixed(1);
    }

    return {
      recordType: 'course',
      date,
      time,
      kettoNum,
      location: locationCodeToName(location),
      time5f: t5f,
      time4f: t4f,
      time3f: t3f,
      time2f: formatTime(time2fRaw),
      lap2: formatLap(lap2Raw),
      lap1: formatLap(lap1Raw),
    };
  } catch {
    return null;
  }
}

/**
 * 調教データが利用可能かチェック
 */
export function isTrainingDataAvailable(): boolean {
  return fs.existsSync(CK_DATA_PATH);
}

/**
 * 利用可能な日付一覧を取得
 */
export function getAvailableTrainingDates(year: number, month: number): string[] {
  const yearMonth = `${year}${String(month).padStart(2, '0')}`;
  const basePath = path.join(CK_DATA_PATH, String(year), yearMonth);
  
  if (!fs.existsSync(basePath)) {
    return [];
  }
  
  const dates = new Set<string>();
  
  try {
    const files = fs.readdirSync(basePath);
    for (const file of files) {
      // WC0YYYYMMDD.DAT or HC1YYYYMMDD.DAT
      const match = file.match(/^[WH]C[01](\d{8})\.DAT$/i);
      if (match) {
        dates.add(match[1]);
      }
    }
  } catch {
    // ignore
  }
  
  return Array.from(dates).sort();
}

/**
 * キャッシュクリア
 */
export function clearTrainingCache(): void {
  fileBufferCache.clear();
  horseNameCache.clear();
  umDataCache.clear();
}

// デバッグログフラグ
let umDebugLogged = false;

/**
 * UM_DATAファイルから馬名を検索（内部関数）
 */
function searchHorseNameInUmFile(filePath: string, kettoNum: string): string {
  try {
    if (!fs.existsSync(filePath)) {
      if (!umDebugLogged) {
        console.log(`[UM_DATA] File not found: ${filePath}`);
      }
      return '';
    }
    
    // キャッシュからデータ取得、なければ読み込み
    let data: Buffer;
    if (umDataCache.has(filePath)) {
      data = umDataCache.get(filePath)!;
    } else {
      data = fs.readFileSync(filePath);
      umDataCache.set(filePath, data);
      if (!umDebugLogged) {
        console.log(`[UM_DATA] Loaded: ${filePath}, size=${data.length}, records=${Math.floor(data.length / UM_RECORD_LEN)}`);
      }
    }
    
    // 血統登録番号で検索（線形探索）
    const numRecords = Math.floor(data.length / UM_RECORD_LEN);
    for (let i = 0; i < numRecords; i++) {
      const offset = i * UM_RECORD_LEN;
      // 血統登録番号: offset+11から10バイト
      const recordKettoNum = iconv.decode(data.subarray(offset + 11, offset + 21), 'Shift_JIS').trim();
      
      if (recordKettoNum === kettoNum) {
        // 馬名: offset+46から36バイト
        const horseName = iconv.decode(data.subarray(offset + 46, offset + 82), 'Shift_JIS')
          .replace(/\u3000/g, '')  // 全角スペース除去
          .trim();
        if (!umDebugLogged) {
          console.log(`[UM_DATA] Found: kettoNum=${kettoNum}, horseName=${horseName}`);
          umDebugLogged = true;
        }
        return horseName;
      }
    }
  } catch (error) {
    // ignore
  }
  return '';
}

/**
 * UM_DATA（馬基本データ）から馬名を取得
 * 血統登録番号から馬名を検索
 * 血統登録番号の先頭4桁は生年なので、その年のUM_DATAを優先検索
 */
function getHorseNameFromUmData(kettoNum: string): string {
  try {
    // 血統登録番号から生年を抽出（先頭4桁）
    const birthYear = parseInt(kettoNum.substring(0, 4), 10);
    
    if (!isNaN(birthYear) && birthYear >= 2000 && birthYear <= 2030) {
      // 生年のUM_DATAを優先検索（下半期→上半期）
      for (let half = 2; half >= 1; half--) {
        const fileName = `UM${birthYear}${half}.DAT`;
        const filePath = path.join(UM_DATA_PATH, String(birthYear), fileName);
        const name = searchHorseNameInUmFile(filePath, kettoNum);
        if (name) return name;
      }
    }
    
    // 見つからなければ、最近の年を検索
    const currentYear = new Date().getFullYear();
    for (let year = currentYear; year >= currentYear - 5; year--) {
      if (year === birthYear) continue;  // 既に検索済み
      for (let half = 2; half >= 1; half--) {
        const fileName = `UM${year}${half}.DAT`;
        const filePath = path.join(UM_DATA_PATH, String(year), fileName);
        const name = searchHorseNameInUmFile(filePath, kettoNum);
        if (name) return name;
      }
    }
  } catch (error) {
    console.error('[getHorseNameFromUmData] Error:', error);
  }
  
  return '';
}

/**
 * 血統登録番号から馬名を取得
 * 優先順位: 1. キャッシュ → 2. SE_DATA → 3. UM_DATA → 4. horse master JSON
 */
export async function getHorseNameByKettoNum(kettoNum: string): Promise<string> {
  // キャッシュチェック
  if (horseNameCache.has(kettoNum)) {
    return horseNameCache.get(kettoNum)!;
  }

  try {
    // 1. SE_DATAから馬名を取得（過去レース成績あり）
    const results = await getHorseRaceResultsFromTarget(kettoNum);
    if (results.length > 0 && results[0].horseName) {
      horseNameCache.set(kettoNum, results[0].horseName);
      return results[0].horseName;
    }
  } catch {
    // ignore
  }

  // 2. SE_DATAになければUM_DATAから取得（新馬・未出走馬対応）
  const umName = getHorseNameFromUmData(kettoNum);
  if (umName) {
    horseNameCache.set(kettoNum, umName);
    return umName;
  }

  // 3. horse master JSONから取得（data3/masters/horses/{ketto_num}.json）
  try {
    const masterPath = path.join(DATA3_ROOT, 'masters', 'horses', `${kettoNum}.json`);
    if (fs.existsSync(masterPath)) {
      const content = fs.readFileSync(masterPath, 'utf-8');
      const master = JSON.parse(content);
      if (master.name) {
        horseNameCache.set(kettoNum, master.name);
        return master.name;
      }
    }
  } catch {
    // ignore
  }

  return '';
}

/**
 * 調教データに馬名を付加
 */
export async function enrichTrainingRecordsWithHorseNames(
  records: TrainingRecord[]
): Promise<TrainingRecord[]> {
  // SE_DATAインデックスを事前構築
  preloadTargetRaceIndex();
  
  // ユニークな血統登録番号を抽出
  const kettoNums = [...new Set(records.map(r => r.kettoNum))];
  
  // 馬名を一括取得
  const nameMap = new Map<string, string>();
  for (const kettoNum of kettoNums) {
    const name = await getHorseNameByKettoNum(kettoNum);
    if (name) {
      nameMap.set(kettoNum, name);
    }
  }
  
  // 馬名を付加
  return records.map(r => ({
    ...r,
    horseName: nameMap.get(r.kettoNum) || '',
  }));
}

/**
 * 調教ラップ分類を計算
 * SS, S+, S=, S-, A+, A=, A-, B+, B=, B-, C+, C=, C-, D+, D=, D-
 *
 * 閾値定義（坂路・コース共通 — 元仕様準拠）:
 *   S: Lap2, Lap1 共に11秒台以下 (< 12.0)
 *   A: Lap1のみ11秒台以下 (< 12.0)
 *   B: Lap2, Lap1 共に12秒台 (12.0 ≤ x < 13.0)
 *   C: Lap1のみ12秒台 (12.0 ≤ Lap1 < 13.0)
 *   D: Lap1 13秒台以上 (≥ 13.0)
 *   SS: S分類 + 好タイム + 加速or同タイム
 *
 * 好タイム基準（4F）:
 *   坂路: 美浦 ≤ 52.9, 栗東 ≤ 53.9
 *   コース: ≤ 52.2
 */
export function calculateLapRank(
  lap2: string,
  lap1: string,
  time4f: string,
  location: string,
  recordType: 'sakamichi' | 'course' = 'sakamichi'
): string {
  const l2 = parseFloat(lap2);
  const l1 = parseFloat(lap1);
  const t4f = parseFloat(time4f);

  if (isNaN(l2) || isNaN(l1)) return '';

  // 加速/減速/同タイム判定
  let accel: '+' | '=' | '-';
  if (l2 > l1) {
    accel = '+';  // 加速
  } else if (l2 < l1) {
    accel = '-';  // 減速
  } else {
    accel = '=';  // 同タイム
  }

  // 好タイム判定（4Fタイム基準）
  let goodTime = false;
  if (!isNaN(t4f)) {
    if (recordType === 'course') {
      goodTime = t4f <= 52.2;
    } else {
      goodTime = (location === 'Miho' && t4f <= 52.9) ||
                 (location === 'Ritto' && t4f <= 53.9);
    }
  }

  // ラップ分類（坂路・コース共通閾値）
  let baseRank: string;

  if (l2 < 12.0 && l1 < 12.0) {
    // S分類: 2F連続11秒台以下
    if (goodTime && accel !== '-') {
      return 'SS';  // 好タイム + S分類 + 加速or同タイム
    }
    baseRank = 'S';
  } else if (l1 < 12.0 && l2 >= 12.0) {
    // A分類: 終い11秒台以下
    baseRank = 'A';
  } else if (l2 < 13.0 && l1 < 13.0) {
    // B分類: 12秒台キープ
    baseRank = 'B';
  } else if (l1 < 13.0) {
    // C分類: 終い12秒台
    baseRank = 'C';
  } else {
    // D分類: 13秒台以上
    baseRank = 'D';
  }

  return baseRank + accel;
}

/**
 * 調教タイム分類を計算
 * 坂, コ, 両, -
 */
export function calculateTimeRank(
  sakamichiRecords: TrainingRecord[],
  courseRecords: TrainingRecord[]
): string {
  // 好タイム基準（4F）— 元仕様準拠
  const hasSakamichiGoodTime = sakamichiRecords.some(r => {
    const t4f = parseFloat(r.time4f || '');
    if (isNaN(t4f)) return false;
    return (r.location === 'Miho' && t4f <= 52.9) ||
           (r.location === 'Ritto' && t4f <= 53.9);
  });

  const hasCourseGoodTime = courseRecords.some(r => {
    const t4f = parseFloat(r.time4f || '');
    if (isNaN(t4f)) return false;
    return t4f <= 52.2;
  });
  
  if (hasSakamichiGoodTime && hasCourseGoodTime) return 'Both';
  if (hasSakamichiGoodTime) return 'Sakamichi';
  if (hasCourseGoodTime) return 'Course';
  return '-';
}

/**
 * 曜日を取得（0=日, 1=月, ..., 6=土）
 */
function getDayOfWeek(dateStr: string): number {
  // dateStr: YYYY/MM/DD or YYYYMMDD
  const normalized = dateStr.replace(/\//g, '');
  const year = parseInt(normalized.substring(0, 4), 10);
  const month = parseInt(normalized.substring(4, 6), 10) - 1;
  const day = parseInt(normalized.substring(6, 8), 10);
  return new Date(year, month, day).getDay();
}

/**
 * 日付文字列を比較用に正規化
 */
function normalizeDate(dateStr: string): string {
  return dateStr.replace(/\//g, '');
}

/**
 * 基準日から最終追い切り・一週前追い切りの日付範囲を計算
 */
export function getTrainingDateRanges(baseDateStr: string): {
  finalStart: string;
  finalEnd: string;
  weekAgoStart: string;
  weekAgoEnd: string;
} {
  // baseDateStr: YYYYMMDD（レース開催日）
  const year = parseInt(baseDateStr.substring(0, 4), 10);
  const month = parseInt(baseDateStr.substring(4, 6), 10) - 1;
  const day = parseInt(baseDateStr.substring(6, 8), 10);
  const baseDate = new Date(year, month, day);
  
  // 基準日の曜日
  const baseDow = baseDate.getDay();
  
  // 最終追い切り: 基準日から遡って直近の水曜(3)・木曜(4)
  // 土曜開催(6)なら水(3)・木(4)、日曜開催(0)なら木(4)・金(5)的に調整が必要だが
  // 通常は水木を最終追い切りとする
  
  let daysToThursday = baseDow - 4;
  if (daysToThursday <= 0) daysToThursday += 7;
  
  const thursdayDate = new Date(baseDate);
  thursdayDate.setDate(baseDate.getDate() - daysToThursday);
  
  const wednesdayDate = new Date(thursdayDate);
  wednesdayDate.setDate(thursdayDate.getDate() - 1);
  
  // 一週前
  const weekAgoThursday = new Date(thursdayDate);
  weekAgoThursday.setDate(thursdayDate.getDate() - 7);
  
  const weekAgoWednesday = new Date(wednesdayDate);
  weekAgoWednesday.setDate(wednesdayDate.getDate() - 7);
  
  const formatDate = (d: Date): string => {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    return `${y}${m}${dd}`;
  };
  
  return {
    finalStart: formatDate(wednesdayDate),
    finalEnd: formatDate(thursdayDate),
    weekAgoStart: formatDate(weekAgoWednesday),
    weekAgoEnd: formatDate(weekAgoThursday),
  };
}

/**
 * 調教サマリーを生成
 */
export async function generateTrainingSummary(
  baseDateStr: string
): Promise<TrainingSummary[]> {
  const ranges = getTrainingDateRanges(baseDateStr);
  
  // 全期間の調教データを取得（最終2週間分）
  const allRecords: TrainingRecord[] = [];
  
  // 日付リストを生成（2週間分）
  const startDate = new Date(
    parseInt(ranges.weekAgoStart.substring(0, 4), 10),
    parseInt(ranges.weekAgoStart.substring(4, 6), 10) - 1,
    parseInt(ranges.weekAgoStart.substring(6, 8), 10)
  );
  const endDate = new Date(
    parseInt(ranges.finalEnd.substring(0, 4), 10),
    parseInt(ranges.finalEnd.substring(4, 6), 10) - 1,
    parseInt(ranges.finalEnd.substring(6, 8), 10)
  );
  
  // 日付を1日ずつ進めながらデータ取得
  const currentDate = new Date(startDate);
  while (currentDate <= endDate) {
    const dateStr = `${currentDate.getFullYear()}${String(currentDate.getMonth() + 1).padStart(2, '0')}${String(currentDate.getDate()).padStart(2, '0')}`;
    const records = await getTrainingDataForDate(dateStr);
    allRecords.push(...records);
    currentDate.setDate(currentDate.getDate() + 1);
  }
  
  // 馬名を付加
  const enrichedRecords = await enrichTrainingRecordsWithHorseNames(allRecords);
  
  // 馬ごとにグループ化
  const horseMap = new Map<string, TrainingRecord[]>();
  for (const record of enrichedRecords) {
    const key = record.kettoNum;
    if (!horseMap.has(key)) {
      horseMap.set(key, []);
    }
    horseMap.get(key)!.push(record);
  }
  
  // 各馬のサマリーを生成
  const summaries: TrainingSummary[] = [];
  
  for (const [kettoNum, records] of horseMap) {
    const horseName = records[0].horseName || '';
    if (!horseName) continue;  // 馬名がない場合はスキップ
    
    // 坂路とコースに分類
    const sakamichiRecords = records.filter(r => r.recordType === 'sakamichi');
    const courseRecords = records.filter(r => r.recordType === 'course');
    
    // 最終追い切りと一週前を分類
    const finalRecords = records.filter(r => {
      const d = normalizeDate(r.date);
      return d >= ranges.finalStart && d <= ranges.finalEnd;
    });
    const weekAgoRecords = records.filter(r => {
      const d = normalizeDate(r.date);
      return d >= ranges.weekAgoStart && d <= ranges.weekAgoEnd;
    });
    
    // 全レコードから最高ランクを計算
    let bestRank = '';
    let bestScore = 0;
    
    for (const r of records) {
      const rank = calculateLapRank(r.lap2 || '', r.lap1 || '', r.time4f || '', r.location, r.recordType);
      const score = getLapRankScore(rank);
      if (score > bestScore) {
        bestScore = score;
        bestRank = rank;
      }
    }
    
    // 調教タイム分類
    const timeRank = calculateTimeRank(sakamichiRecords, courseRecords);
    
    // 調教詳細を生成
    const detail = generateTrainingDetail(finalRecords, weekAgoRecords, records, ranges);
    
    summaries.push({
      horseName,
      kettoNum,
      trainerName: '',  // TODO: 調教師名取得
      lapRank: bestRank,
      timeRank: timeRank === 'Both' ? '両' : 
                timeRank === 'Sakamichi' ? '坂' : 
                timeRank === 'Course' ? 'コ' : '',
      detail,
    });
  }
  
  // 馬名でソート
  summaries.sort((a, b) => a.horseName.localeCompare(b.horseName, 'ja'));
  
  return summaries;
}

/**
 * ラップ分類のスコアを取得
 */
function getLapRankScore(rank: string): number {
  const scores: Record<string, number> = {
    'SS': 16,
    'S+': 15, 'S=': 14, 'S-': 13,
    'A+': 12, 'A=': 11, 'A-': 10,
    'B+': 9, 'B=': 8, 'B-': 7,
    'C+': 6, 'C=': 5, 'C-': 4,
    'D+': 3, 'D=': 2, 'D-': 1,
  };
  return scores[rank] || 0;
}

/**
 * 調教詳細文字列を生成
 * 出力形式: 「最終:坂路A+ 1週前:コースB-」のような日本語形式
 */
function generateTrainingDetail(
  finalRecords: TrainingRecord[],
  weekAgoRecords: TrainingRecord[],
  allRecords: TrainingRecord[],
  ranges: { finalStart: string; finalEnd: string; weekAgoStart: string; weekAgoEnd: string }
): string {
  const parts: string[] = [];
  
  // 最終追い切り
  if (finalRecords.length > 0) {
    // 坂路とコースで最高ランクを取得
    const finalSakamichi = finalRecords.filter(r => r.recordType === 'sakamichi');
    const finalCourse = finalRecords.filter(r => r.recordType === 'course');
    
    const finalParts: string[] = [];
    
    if (finalSakamichi.length > 0) {
      const best = getBestRecord(finalSakamichi);
      if (best) {
        const rank = calculateLapRank(best.lap2 || '', best.lap1 || '', best.time4f || '', best.location, best.recordType);
        const timeStr = isGoodTime(best) ? `(${best.time4f})` : '';
        finalParts.push(`坂路${rank}${timeStr}`);
      }
    }
    
    if (finalCourse.length > 0) {
      const best = getBestRecord(finalCourse);
      if (best) {
        const rank = calculateLapRank(best.lap2 || '', best.lap1 || '', best.time4f || '', best.location, best.recordType);
        const timeStr = isGoodTime(best) ? `(${best.time4f})` : '';
        finalParts.push(`コース${rank}${timeStr}`);
      }
    }
    
    if (finalParts.length > 0) {
      parts.push(`最終:${finalParts.join(',')}`);
    }
  } else {
    parts.push('最終:なし');
  }
  
  // 一週前追い切り
  if (weekAgoRecords.length > 0) {
    const weekAgoSakamichi = weekAgoRecords.filter(r => r.recordType === 'sakamichi');
    const weekAgoCourse = weekAgoRecords.filter(r => r.recordType === 'course');
    
    const weekAgoParts: string[] = [];
    
    if (weekAgoSakamichi.length > 0) {
      const best = getBestRecord(weekAgoSakamichi);
      if (best) {
        const rank = calculateLapRank(best.lap2 || '', best.lap1 || '', best.time4f || '', best.location, best.recordType);
        weekAgoParts.push(`坂路${rank}`);
      }
    }
    
    if (weekAgoCourse.length > 0) {
      const best = getBestRecord(weekAgoCourse);
      if (best) {
        const rank = calculateLapRank(best.lap2 || '', best.lap1 || '', best.time4f || '', best.location, best.recordType);
        weekAgoParts.push(`コース${rank}`);
      }
    }
    
    if (weekAgoParts.length > 0) {
      parts.push(`1週前:${weekAgoParts.join(',')}`);
    }
  }
  
  return parts.join(' ');
}

/**
 * 最高ランクのレコードを取得
 */
function getBestRecord(records: TrainingRecord[]): TrainingRecord | null {
  let best: TrainingRecord | null = null;
  let bestScore = 0;
  
  for (const r of records) {
    const rank = calculateLapRank(r.lap2 || '', r.lap1 || '', r.time4f || '', r.location, r.recordType);
    const score = getLapRankScore(rank);
    if (score > bestScore) {
      bestScore = score;
      best = r;
    }
  }
  
  return best;
}

/**
 * 好タイムかどうか判定
 */
function isGoodTime(record: TrainingRecord): boolean {
  const t4f = parseFloat(record.time4f || '');
  if (isNaN(t4f)) return false;
  
  if (record.recordType === 'sakamichi') {
    return (record.location === 'Miho' && t4f <= 52.9) ||
           (record.location === 'Ritto' && t4f <= 53.9);
  } else {
    return t4f <= 52.2;
  }
}

/**
 * サマリーをタブ区切りテキストに変換（TARGET取り込み用）
 */
export function summaryToTsv(summaries: TrainingSummary[]): string {
  const lines: string[] = [];
  
  // ヘッダー
  lines.push('HorseName\tTrainer\tLapRank\tTimeRank\tDetail');
  
  // データ行
  for (const s of summaries) {
    lines.push(`${s.horseName}\t${s.trainerName}\t${s.lapRank}\t${s.timeRank}\t${s.detail}`);
  }
  
  return lines.join('\r\n');
}
