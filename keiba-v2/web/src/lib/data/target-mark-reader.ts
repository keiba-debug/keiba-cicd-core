/**
 * TARGET馬印ファイル読み込みライブラリ
 * 
 * ファイル形式:
 * - ファイル名: UMyykpp.DAT (yy=西暦下2桁, k=回次, pp=場所名漢字)
 * - 1レコード = 44バイト（レース印6バイト + 馬印36バイト + 改行2バイト）
 * - 全体 = 96レコード（8日 × 12レース）
 * - エンコーディング: Shift-JIS
 */

import * as fs from 'fs';
import * as path from 'path';
import * as iconv from 'iconv-lite';

// 印のバイトパターン（Shift-JIS）
const MARK_BYTES_TO_SYMBOL: Record<string, string> = {
  '819d': '◎',  // 本命
  '819b': '○',  // 対抗
  '81a3': '▲',  // 単穴
  '81a2': '△',  // 連下
  '8756': '★',  // 注意
  '8c8a': '穴',  // 穴馬
  '2020': '',    // 無印
};

// 逆引き（印記号 → Shift-JIS バイト列）
const SYMBOL_TO_MARK_BYTES: Record<string, Buffer> = {
  '◎': Buffer.from([0x81, 0x9d]),
  '○': Buffer.from([0x81, 0x9b]),
  '▲': Buffer.from([0x81, 0xa3]),
  '△': Buffer.from([0x81, 0xa2]),
  '★': Buffer.from([0x87, 0x56]),
  '穴': Buffer.from([0x8c, 0x8a]),
  '': Buffer.from([0x20, 0x20]),
};

// 場所コード → 漢字マッピング
const VENUE_CODE_TO_KANJI: Record<string, string> = {
  '01': '札',
  '02': '函',
  '03': '福',
  '04': '新',
  '05': '東',
  '06': '中',
  '07': '名',
  '08': '京',
  '09': '阪',
  '10': '小',
};

// 競馬場名 → 漢字マッピング
const VENUE_NAME_TO_KANJI: Record<string, string> = {
  '札幌': '札',
  '函館': '函',
  '福島': '福',
  '新潟': '新',
  '東京': '東',
  '中山': '中',
  '中京': '名',
  '京都': '京',
  '阪神': '阪',
  '小倉': '小',
};

export interface RaceMarks {
  raceMark: string;
  colorCode: string;
  horseMarks: Record<number, string>;  // 馬番 → 印
}

/**
 * 印セットフォルダ名
 */
const MARK_SET_FOLDERS: Record<number, string> = {
  1: '',           // MY_DATA直下
  2: 'UmaMark2',
  3: 'UmaMark3',
  4: 'UmaMark4',
  5: 'UmaMark5',
  6: 'UmaMark6',
  7: 'UmaMark7',
  8: 'UmaMark8',
};

/**
 * MY_DATAディレクトリパスを取得
 */
function getMyDataDir(markSet: number = 1): string {
  const jvRoot = process.env.JV_DATA_ROOT || 'C:\\TFJV';
  const baseDir = path.join(jvRoot, 'MY_DATA');
  const subFolder = MARK_SET_FOLDERS[markSet] || '';
  return subFolder ? path.join(baseDir, subFolder) : baseDir;
}

/**
 * 馬印ファイルパスを生成
 */
export function getMarkFilePath(
  year: number,
  kai: number,
  venue: string,  // 競馬場名（例: '東京'）または漢字1文字
  markSet: number = 1  // 印セット番号（1-8）
): string {
  const myDataDir = getMyDataDir(markSet);
  const yy = String(year).slice(-2);
  
  // 競馬場名から漢字1文字を取得
  const venueKanji = VENUE_NAME_TO_KANJI[venue] || venue;
  
  const filename = `UM${yy}${kai}${venueKanji}.DAT`;
  return path.join(myDataDir, filename);
}

/**
 * レコードインデックスを計算
 * @param day 日次（1-8）
 * @param raceNumber レース番号（1-12）
 */
function getRecordIndex(day: number, raceNumber: number): number {
  return (day - 1) * 12 + (raceNumber - 1);
}

/**
 * 指定レースの馬印を取得
 */
export function getRaceMarks(
  year: number,
  kai: number,
  day: number,
  raceNumber: number,
  venue: string,
  markSet: number = 1  // 印セット番号（1-8）
): RaceMarks | null {
  const filePath = getMarkFilePath(year, kai, venue, markSet);
  
  if (!fs.existsSync(filePath)) {
    return null;
  }
  
  const content = fs.readFileSync(filePath);
  const recordIndex = getRecordIndex(day, raceNumber);
  const recordStart = recordIndex * 44;
  
  if (recordStart + 44 > content.length) {
    return null;
  }
  
  // レース印（バイト0-5）
  const colorCode = content[recordStart + 1] !== 0x20 
    ? String.fromCharCode(content[recordStart + 1]) 
    : '';
  
  // レース印（バイト2-5）をShift-JISデコード
  const raceMarkBytes = content.slice(recordStart + 2, recordStart + 6);
  let raceMark = '';
  try {
    raceMark = iconv.decode(Buffer.from(raceMarkBytes), 'shift-jis').trim();
  } catch {
    raceMark = '';
  }
  
  // 馬印（バイト6-41、18頭分）
  const horseMarks: Record<number, string> = {};
  for (let uma = 1; uma <= 18; uma++) {
    const offset = recordStart + 6 + (uma - 1) * 2;
    const b1 = content[offset];
    const b2 = content[offset + 1];
    const hexKey = b1.toString(16).padStart(2, '0') + b2.toString(16).padStart(2, '0');
    const mark = MARK_BYTES_TO_SYMBOL[hexKey] || '';
    if (mark) {
      horseMarks[uma] = mark;
    }
  }
  
  return {
    raceMark,
    colorCode,
    horseMarks,
  };
}

/**
 * 馬印を書き込み
 */
export function writeHorseMark(
  year: number,
  kai: number,
  day: number,
  raceNumber: number,
  venue: string,
  horseNumber: number,
  mark: string,  // '◎', '○', '▲', '△', '★', '穴', '' (無印)
  markSet: number = 1  // 印セット番号（1-8）
): boolean {
  const markBytes = SYMBOL_TO_MARK_BYTES[mark];
  if (!markBytes) {
    console.error(`Unknown mark: ${mark}`);
    return false;
  }
  
  const filePath = getMarkFilePath(year, kai, venue, markSet);
  const recordIndex = getRecordIndex(day, raceNumber);
  const recordStart = recordIndex * 44;
  const offset = recordStart + 6 + (horseNumber - 1) * 2;
  
  let content: Buffer;
  
  // ファイルが存在しない場合は新規作成
  if (!fs.existsSync(filePath)) {
    // 96レコード × 44バイト
    content = Buffer.alloc(96 * 44, 0x20);  // スペースで初期化
    for (let i = 0; i < 96; i++) {
      const base = i * 44;
      content[base + 42] = 0x0d;  // CR
      content[base + 43] = 0x0a;  // LF
    }
    
    // ディレクトリ作成
    const dir = path.dirname(filePath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
  } else {
    content = fs.readFileSync(filePath);
  }
  
  // 書き込み
  markBytes.copy(content, offset);
  
  fs.writeFileSync(filePath, content);
  return true;
}

/**
 * 全印をクリア
 */
export function clearHorseMark(
  year: number,
  kai: number,
  day: number,
  raceNumber: number,
  venue: string,
  horseNumber: number,
  markSet: number = 1  // 印セット番号（1-8）
): boolean {
  return writeHorseMark(year, kai, day, raceNumber, venue, horseNumber, '', markSet);
}

// 有効な印一覧
export const VALID_MARKS = ['◎', '○', '▲', '△', '★', '穴', ''] as const;
export type MarkSymbol = typeof VALID_MARKS[number];
