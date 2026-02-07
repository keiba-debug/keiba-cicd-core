/**
 * TARGETコメント書き込みライブラリ
 * 
 * TARGETフロントエンドで管理しているコメントデータへの書き込み
 * - UMA_COM: 馬ごとの永続的なメモ
 * - KEK_COM: レース別・馬別の結果コメント
 * - YOS_COM: レース別・馬別の予想コメント
 * 
 * 注意: Shift-JIS（CP932）形式、CSV形式で保存
 */

import fs from 'fs';
import path from 'path';
import iconv from 'iconv-lite';
import { JV_DATA_ROOT_DIR } from '../config';

// MY_DATAディレクトリのパス
const MY_DATA_PATH = path.join(JV_DATA_ROOT_DIR, 'MY_DATA');

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

/** 書き込み結果 */
export interface WriteResult {
  success: boolean;
  message: string;
  filePath?: string;
}

/**
 * コメント値をCSV形式にエスケープ
 */
function escapeCSVValue(value: string): string {
  // カンマ、ダブルクォート、改行が含まれる場合はダブルクォートで囲む
  if (value.includes(',') || value.includes('"') || value.includes('\n') || value.includes('\r')) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

/**
 * Shift-JIS（CP932）でファイルを書き込み
 */
function writeShiftJisFile(filePath: string, content: string): void {
  const buffer = iconv.encode(content, 'cp932');
  fs.writeFileSync(filePath, buffer);
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
 * ディレクトリを再帰的に作成
 */
function ensureDir(dirPath: string): void {
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
  }
}

/**
 * レースコメントファイルのパスを構築
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
 * レース予想/結果コメントを書き込み
 * @param type - 'prediction' (予想) or 'result' (結果)
 * @param venue - 競馬場名
 * @param year - 年（4桁）
 * @param kai - 回
 * @param nichi - 日
 * @param raceNumber - レース番号
 * @param horseNumber - 馬番
 * @param comment - コメント本文
 */
export function writeRaceComment(
  type: 'prediction' | 'result',
  venue: string,
  year: string,
  kai: number,
  nichi: number,
  raceNumber: number,
  horseNumber: number,
  comment: string
): WriteResult {
  try {
    const fileType = type === 'prediction' ? 'YOS' : 'KEK';
    const filePath = buildRaceCommentFilePath(fileType, venue, year, kai, nichi);
    if (!filePath) {
      return { success: false, message: `無効な競馬場名: ${venue}` };
    }
    
    const key = buildRaceCommentKey(venue, year, kai, nichi, raceNumber, horseNumber);
    if (!key) {
      return { success: false, message: 'レースキーの生成に失敗しました' };
    }
    
    // ディレクトリを作成
    ensureDir(path.dirname(filePath));
    
    // 既存ファイルを読み込み
    const existingContent = readShiftJisFile(filePath);
    const lines: string[] = existingContent ? existingContent.split(/\r?\n/).filter(l => l.trim()) : [];
    
    // 既存のキーを検索して更新/追加
    let found = false;
    const newLines = lines.map(line => {
      const commaIndex = line.indexOf(',');
      if (commaIndex > 0) {
        const lineKey = line.substring(0, commaIndex);
        if (lineKey === key) {
          found = true;
          // コメントが空の場合は削除（空行として）
          if (!comment.trim()) {
            return null; // 削除マーク
          }
          return `${key},${escapeCSVValue(comment)}`;
        }
      }
      return line;
    }).filter((line): line is string => line !== null);
    
    // 新規追加（コメントが空でない場合のみ）
    if (!found && comment.trim()) {
      newLines.push(`${key},${escapeCSVValue(comment)}`);
    }
    
    // ソートしてから保存（キー順）
    newLines.sort((a, b) => {
      const keyA = a.split(',')[0] || '';
      const keyB = b.split(',')[0] || '';
      return keyA.localeCompare(keyB);
    });
    
    // ファイルに書き込み（CRLF）
    writeShiftJisFile(filePath, newLines.join('\r\n') + (newLines.length > 0 ? '\r\n' : ''));
    
    return {
      success: true,
      message: found ? 'コメントを更新しました' : 'コメントを追加しました',
      filePath,
    };
  } catch (error) {
    return {
      success: false,
      message: `書き込みエラー: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

/**
 * 馬コメント（UMA_COM）を書き込み
 * @param kettoNum - 馬ID（10桁）
 * @param comment - コメント本文
 */
export function writeHorseComment(kettoNum: string, comment: string): WriteResult {
  try {
    if (!kettoNum || kettoNum.length !== 10) {
      return { success: false, message: `無効な馬ID: ${kettoNum}` };
    }
    
    // 馬IDから年を抽出（最初の4桁）
    const year = kettoNum.substring(0, 4);
    const yearDir = path.join(MY_DATA_PATH, 'UMA_COM', year);
    
    // ディレクトリを作成
    ensureDir(yearDir);
    
    // ファイル番号を決定（既存ファイルを検索）
    let targetFile: string | null = null;
    let foundInFile: string | null = null;
    
    // 既存ファイルを検索
    if (fs.existsSync(yearDir)) {
      const files = fs.readdirSync(yearDir).filter(f => f.endsWith('.DAT')).sort();
      
      for (const file of files) {
        const filePath = path.join(yearDir, file);
        const content = readShiftJisFile(filePath);
        if (!content) continue;
        
        const lines = content.split(/\r?\n/);
        for (const line of lines) {
          const commaIndex = line.indexOf(',');
          if (commaIndex > 0 && line.substring(0, commaIndex) === kettoNum) {
            foundInFile = file;
            break;
          }
        }
        if (foundInFile) break;
      }
      
      // 見つかった場合はそのファイル、なければ最新ファイルまたは新規作成
      if (foundInFile) {
        targetFile = foundInFile;
      } else if (files.length > 0) {
        // 最新のファイルに追加
        targetFile = files[files.length - 1];
      }
    }
    
    // 新規ファイルの場合
    if (!targetFile) {
      // UC{年4桁}{通番}.DAT 形式
      targetFile = `UC${year}1.DAT`;
    }
    
    const filePath = path.join(yearDir, targetFile);
    
    // 既存ファイルを読み込み
    const existingContent = readShiftJisFile(filePath);
    const lines: string[] = existingContent ? existingContent.split(/\r?\n/).filter(l => l.trim()) : [];
    
    // 既存のキーを検索して更新/追加
    let found = false;
    const newLines = lines.map(line => {
      const commaIndex = line.indexOf(',');
      if (commaIndex > 0) {
        const lineKey = line.substring(0, commaIndex);
        if (lineKey === kettoNum) {
          found = true;
          // コメントが空の場合は削除
          if (!comment.trim()) {
            return null;
          }
          return `${kettoNum},${escapeCSVValue(comment)}`;
        }
      }
      return line;
    }).filter((line): line is string => line !== null);
    
    // 新規追加（コメントが空でない場合のみ）
    if (!found && comment.trim()) {
      newLines.push(`${kettoNum},${escapeCSVValue(comment)}`);
    }
    
    // ソートしてから保存（キー順）
    newLines.sort((a, b) => {
      const keyA = a.split(',')[0] || '';
      const keyB = b.split(',')[0] || '';
      return keyA.localeCompare(keyB);
    });
    
    // ファイルに書き込み（CRLF）
    writeShiftJisFile(filePath, newLines.join('\r\n') + (newLines.length > 0 ? '\r\n' : ''));
    
    return {
      success: true,
      message: found ? 'コメントを更新しました' : 'コメントを追加しました',
      filePath,
    };
  } catch (error) {
    return {
      success: false,
      message: `書き込みエラー: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

/**
 * 複数のレースコメントを一括書き込み
 */
export function writeRaceCommentsBatch(
  type: 'prediction' | 'result',
  venue: string,
  year: string,
  kai: number,
  nichi: number,
  raceNumber: number,
  comments: Array<{ horseNumber: number; comment: string }>
): WriteResult {
  try {
    const fileType = type === 'prediction' ? 'YOS' : 'KEK';
    const filePath = buildRaceCommentFilePath(fileType, venue, year, kai, nichi);
    if (!filePath) {
      return { success: false, message: `無効な競馬場名: ${venue}` };
    }
    
    // ディレクトリを作成
    ensureDir(path.dirname(filePath));
    
    // 既存ファイルを読み込み
    const existingContent = readShiftJisFile(filePath);
    const lines: string[] = existingContent ? existingContent.split(/\r?\n/).filter(l => l.trim()) : [];
    
    // 更新対象のキーを生成
    const updateMap = new Map<string, string>();
    for (const { horseNumber, comment } of comments) {
      const key = buildRaceCommentKey(venue, year, kai, nichi, raceNumber, horseNumber);
      if (key) {
        updateMap.set(key, comment);
      }
    }
    
    // 既存行を更新
    const usedKeys = new Set<string>();
    const newLines = lines.map(line => {
      const commaIndex = line.indexOf(',');
      if (commaIndex > 0) {
        const lineKey = line.substring(0, commaIndex);
        if (updateMap.has(lineKey)) {
          usedKeys.add(lineKey);
          const newComment = updateMap.get(lineKey)!;
          if (!newComment.trim()) {
            return null; // 削除
          }
          return `${lineKey},${escapeCSVValue(newComment)}`;
        }
      }
      return line;
    }).filter((line): line is string => line !== null);
    
    // 新規追加
    for (const [key, comment] of updateMap) {
      if (!usedKeys.has(key) && comment.trim()) {
        newLines.push(`${key},${escapeCSVValue(comment)}`);
      }
    }
    
    // ソートしてから保存
    newLines.sort((a, b) => {
      const keyA = a.split(',')[0] || '';
      const keyB = b.split(',')[0] || '';
      return keyA.localeCompare(keyB);
    });
    
    // ファイルに書き込み
    writeShiftJisFile(filePath, newLines.join('\r\n') + (newLines.length > 0 ? '\r\n' : ''));
    
    return {
      success: true,
      message: `${comments.length}件のコメントを保存しました`,
      filePath,
    };
  } catch (error) {
    return {
      success: false,
      message: `書き込みエラー: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}
