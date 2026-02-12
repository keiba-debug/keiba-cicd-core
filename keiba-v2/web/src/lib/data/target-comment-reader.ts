/**
 * TARGETコメントデータリーダー
 * 
 * TARGETフロントエンドで管理している馬コメント・レース結果コメントを読み取る
 * - UMA_COM: 馬ごとの永続的なメモ
 * - KEK_COM: レース別・馬別の結果コメント
 * - YOS_COM: レース別・馬別の予想コメント
 */

import fs from 'fs';
import path from 'path';
import iconv from 'iconv-lite';
import { JV_DATA_ROOT } from '../config';

// MY_DATAディレクトリのパス
const MY_DATA_PATH = path.join(JV_DATA_ROOT, 'MY_DATA');

// 場コード対応表
const VENUE_CODE_MAP: Record<string, string> = {
  '札幌': '01',
  '函館': '02',
  '福島': '03',
  '新潟': '04',
  '東京': '05',
  '中山': '06',
  '中京': '07',
  '京都': '08',
  '阪神': '09',
  '小倉': '10',
};

const VENUE_NAME_MAP: Record<string, string> = {
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

/** 馬コメント */
export interface HorseComment {
  /** 馬ID（10桁 kettoNum） */
  horseId: string;
  /** コメント本文 */
  comment: string;
  /** ソースファイル */
  source?: string;
}

/** レース別馬別コメント */
export interface RaceHorseComment {
  /** レースキー（場コード+年2桁+回+日+レース番号2桁） */
  raceKey: string;
  /** 馬番（2桁） */
  horseNumber: number;
  /** コメント本文 */
  comment: string;
  /** コメントタイプ（予想 or 結果） */
  type: 'prediction' | 'result';
  /** ソースファイル */
  source?: string;
}

/**
 * Shift-JIS（CP932）でファイルを読み込み
 */
function readShiftJisFile(filePath: string): string | null {
  if (!fs.existsSync(filePath)) {
    return null;
  }
  try {
    const buffer = fs.readFileSync(filePath);
    return iconv.decode(buffer, 'cp932');
  } catch {
    return null;
  }
}

/**
 * CSVレコードをパース（カンマ区切り、ダブルクォート対応）
 */
function parseCSVLine(line: string): { key: string; value: string } | null {
  if (!line.trim()) return null;
  
  // シンプルなケース: ダブルクォートなし
  const firstComma = line.indexOf(',');
  if (firstComma === -1) return null;
  
  const key = line.substring(0, firstComma);
  let value = line.substring(firstComma + 1);
  
  // ダブルクォートで囲まれている場合
  if (value.startsWith('"') && value.endsWith('"')) {
    value = value.substring(1, value.length - 1).replace(/""/g, '"');
  }
  
  return { key, value };
}

/**
 * 馬コメント（UMA_COM）を取得
 * @param horseId - 馬ID（10桁 kettoNum）
 */
export function getHorseComment(horseId: string): HorseComment | null {
  if (!horseId || horseId.length !== 10) return null;
  
  // 馬IDから年を抽出（最初の4桁）
  const year = horseId.substring(0, 4);
  const yearDir = path.join(MY_DATA_PATH, 'UMA_COM', year);
  
  if (!fs.existsSync(yearDir)) {
    return null;
  }
  
  // 該当年のすべてのDATファイルを検索
  try {
    const files = fs.readdirSync(yearDir).filter(f => f.endsWith('.DAT'));
    
    for (const file of files) {
      const filePath = path.join(yearDir, file);
      const content = readShiftJisFile(filePath);
      if (!content) continue;
      
      const lines = content.split(/\r?\n/);
      for (const line of lines) {
        const parsed = parseCSVLine(line);
        if (parsed && parsed.key === horseId) {
          return {
            horseId,
            comment: parsed.value,
            source: `UMA_COM/${year}/${file}`,
          };
        }
      }
    }
  } catch {
    return null;
  }
  
  return null;
}

/**
 * 複数の馬コメントを一括取得
 * @param horseIds - 馬IDの配列
 */
export function getHorseCommentsBatch(horseIds: string[]): Map<string, HorseComment> {
  const result = new Map<string, HorseComment>();
  
  // 年ごとにグループ化して効率的に検索
  const idsByYear = new Map<string, string[]>();
  for (const id of horseIds) {
    if (!id || id.length !== 10) continue;
    const year = id.substring(0, 4);
    if (!idsByYear.has(year)) {
      idsByYear.set(year, []);
    }
    idsByYear.get(year)!.push(id);
  }
  
  for (const [year, ids] of idsByYear) {
    const yearDir = path.join(MY_DATA_PATH, 'UMA_COM', year);
    if (!fs.existsSync(yearDir)) continue;
    
    try {
      const files = fs.readdirSync(yearDir).filter(f => f.endsWith('.DAT'));
      const idSet = new Set(ids);
      
      for (const file of files) {
        if (idSet.size === 0) break;
        
        const filePath = path.join(yearDir, file);
        const content = readShiftJisFile(filePath);
        if (!content) continue;
        
        const lines = content.split(/\r?\n/);
        for (const line of lines) {
          const parsed = parseCSVLine(line);
          if (parsed && idSet.has(parsed.key)) {
            result.set(parsed.key, {
              horseId: parsed.key,
              comment: parsed.value,
              source: `UMA_COM/${year}/${file}`,
            });
            idSet.delete(parsed.key);
          }
        }
      }
    } catch {
      continue;
    }
  }
  
  return result;
}

/**
 * レースコメントファイルのパスを構築
 * @param type - 'KEK' (結果) or 'YOS' (予想)
 * @param venue - 競馬場名
 * @param year - 年（4桁）
 * @param kai - 回
 * @param nichi - 日
 */
function buildRaceCommentFilePath(
  type: 'KEK' | 'YOS',
  venue: string,
  year: string,
  kai: number,
  nichi: number
): string | null {
  const venueCode = VENUE_CODE_MAP[venue];
  if (!venueCode) return null;
  
  const year2 = year.substring(2, 4);
  const prefix = type === 'KEK' ? 'KC' : 'YC';
  const fileName = `${prefix}${venueCode}${year2}${kai}${nichi}.DAT`;
  
  return path.join(MY_DATA_PATH, `${type}_COM`, year, fileName);
}

/**
 * レースキーを構築（コメントファイル内のキー形式）
 * @param venue - 競馬場名
 * @param year - 年（4桁）
 * @param kai - 回
 * @param nichi - 日
 * @param raceNumber - レース番号
 * @param horseNumber - 馬番
 */
function buildRaceCommentKey(
  venue: string,
  year: string,
  kai: number,
  nichi: number,
  raceNumber: number,
  horseNumber: number
): string | null {
  const venueCode = VENUE_CODE_MAP[venue];
  if (!venueCode) return null;
  
  const year2 = year.substring(2, 4);
  const race2 = String(raceNumber).padStart(2, '0');
  const horse2 = String(horseNumber).padStart(2, '0');
  
  return `${venueCode}${year2}${kai}${nichi}${race2}${horse2}`;
}

/**
 * レース別馬別コメントを取得
 * @param type - 'prediction' (予想) or 'result' (結果)
 * @param venue - 競馬場名
 * @param year - 年（4桁）
 * @param kai - 回
 * @param nichi - 日
 * @param raceNumber - レース番号
 * @param horseNumber - 馬番
 */
export function getRaceHorseComment(
  type: 'prediction' | 'result',
  venue: string,
  year: string,
  kai: number,
  nichi: number,
  raceNumber: number,
  horseNumber: number
): RaceHorseComment | null {
  const fileType = type === 'prediction' ? 'YOS' : 'KEK';
  const filePath = buildRaceCommentFilePath(fileType, venue, year, kai, nichi);
  if (!filePath) return null;
  
  const content = readShiftJisFile(filePath);
  if (!content) return null;
  
  const targetKey = buildRaceCommentKey(venue, year, kai, nichi, raceNumber, horseNumber);
  if (!targetKey) return null;
  
  const lines = content.split(/\r?\n/);
  for (const line of lines) {
    const parsed = parseCSVLine(line);
    if (parsed && parsed.key === targetKey) {
      return {
        raceKey: targetKey,
        horseNumber,
        comment: parsed.value,
        type,
        source: filePath,
      };
    }
  }
  
  return null;
}

/**
 * レース全体のコメントを一括取得
 * @param type - 'prediction' (予想) or 'result' (結果)
 * @param venue - 競馬場名
 * @param year - 年（4桁）
 * @param kai - 回
 * @param nichi - 日
 * @param raceNumber - レース番号
 */
export function getRaceComments(
  type: 'prediction' | 'result',
  venue: string,
  year: string,
  kai: number,
  nichi: number,
  raceNumber: number
): Map<number, RaceHorseComment> {
  const result = new Map<number, RaceHorseComment>();
  
  const fileType = type === 'prediction' ? 'YOS' : 'KEK';
  const filePath = buildRaceCommentFilePath(fileType, venue, year, kai, nichi);
  if (!filePath) return result;
  
  const content = readShiftJisFile(filePath);
  if (!content) return result;
  
  const venueCode = VENUE_CODE_MAP[venue];
  if (!venueCode) return result;
  
  const year2 = year.substring(2, 4);
  const race2 = String(raceNumber).padStart(2, '0');
  const keyPrefix = `${venueCode}${year2}${kai}${nichi}${race2}`;
  
  const lines = content.split(/\r?\n/);
  for (const line of lines) {
    const parsed = parseCSVLine(line);
    if (!parsed) continue;
    
    if (parsed.key.startsWith(keyPrefix)) {
      const horseNumStr = parsed.key.substring(keyPrefix.length);
      const horseNumber = parseInt(horseNumStr, 10);
      if (!isNaN(horseNumber)) {
        result.set(horseNumber, {
          raceKey: parsed.key,
          horseNumber,
          comment: parsed.value,
          type,
          source: filePath,
        });
      }
    }
  }
  
  return result;
}

/**
 * レース全体の予想コメントと結果コメントを両方取得
 */
export function getRaceAllComments(
  venue: string,
  year: string,
  kai: number,
  nichi: number,
  raceNumber: number
): {
  predictions: Map<number, RaceHorseComment>;
  results: Map<number, RaceHorseComment>;
} {
  return {
    predictions: getRaceComments('prediction', venue, year, kai, nichi, raceNumber),
    results: getRaceComments('result', venue, year, kai, nichi, raceNumber),
  };
}

/**
 * コメントデータの存在確認
 */
export function hasCommentData(): boolean {
  return fs.existsSync(MY_DATA_PATH);
}

/**
 * デバッグ用: MY_DATAパス取得
 */
export function getMyDataPath(): string {
  return MY_DATA_PATH;
}

// ============================================================
// 馬名インデックス関連
// ============================================================

import { DATA3_ROOT } from '../config';

// 馬名→kettoNumインデックスのキャッシュ
let horseNameIndexCache: Record<string, string> | null = null;

/**
 * 馬名インデックスを読み込み（キャッシュ付き）
 */
function loadHorseNameIndex(): Record<string, string> {
  if (horseNameIndexCache) return horseNameIndexCache;

  const indexPath = path.join(DATA3_ROOT, 'indexes', 'horse_name_index.json');
  if (!fs.existsSync(indexPath)) {
    console.warn('[TargetCommentReader] horse_name_index.json not found:', indexPath);
    return {};
  }
  
  try {
    const content = fs.readFileSync(indexPath, 'utf-8');
    const data = JSON.parse(content);
    horseNameIndexCache = data.index || {};
    return horseNameIndexCache ?? {};
  } catch (e) {
    console.error('[TargetCommentReader] Failed to load horse_name_index.json:', e);
    return {};
  }
}

/**
 * 馬名からkettoNumを取得
 * @param horseName 馬名
 * @param trainingSummaryMap オプション: training_summary.jsonのデータ（初出走馬のフォールバック用）
 */
export function getKettoNumByName(
  horseName: string,
  trainingSummaryMap?: Record<string, { kettoNum?: string }>
): string | null {
  const index = loadHorseNameIndex();

  // 直接一致
  if (index[horseName]) {
    return index[horseName];
  }

  // 正規化して検索（外国馬等のプレフィックス除去）
  const normalized = horseName.replace(/^[\(（][外地父市][）\)]/g, '');
  if (index[normalized]) {
    return index[normalized];
  }

  // フォールバック: training_summary.jsonからkettoNumを取得（初出走馬対応）
  if (trainingSummaryMap) {
    const summary = trainingSummaryMap[horseName] || trainingSummaryMap[normalized];
    if (summary?.kettoNum) {
      return summary.kettoNum;
    }
  }

  return null;
}

/**
 * 馬名からコメントを取得
 * @param horseName 馬名
 */
export function getHorseCommentByName(horseName: string): HorseComment | null {
  const kettoNum = getKettoNumByName(horseName);
  if (!kettoNum) return null;
  
  return getHorseComment(kettoNum);
}
