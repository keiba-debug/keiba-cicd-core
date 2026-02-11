/**
 * TARGET JV-Data 馬データ直接読み込みモジュール
 * 
 * JRA-VAN JV-DataのUM（競走馬マスタ）から馬情報を高速読み込み
 * 
 * 最適化:
 * - ファイルバッファのキャッシュ
 * - 馬IDインデックスのキャッシュ
 */

import fs from 'fs';
import path from 'path';
import iconv from 'iconv-lite';

// JV-Data パス (TARGET frontier JV のデータディレクトリ)
const JV_DATA_ROOT = process.env.JV_DATA_ROOT_DIR || 'Y:/';
const UM_DATA_PATH = path.join(JV_DATA_ROOT, 'UM_DATA');

// レコード長
const UM_RECORD_LEN = 1609;

// キャッシュ
const fileBufferCache = new Map<string, Buffer>();
const horseIndexCache = new Map<string, { file: string; offset: number }>();
let indexBuilt = false;

// 性別コード
const SEX_CODES: Record<string, string> = {
  '1': '牡',
  '2': '牝',
  '3': 'セン',
};

/**
 * TARGET馬データ
 */
export interface TargetHorseData {
  horseId: string;        // 血統登録番号
  name: string;           // 馬名
  nameKana: string;       // 馬名カナ
  nameEng: string;        // 馬名英字
  birthDate: string;      // 生年月日 (YYYYMMDD)
  sex: string;            // 性別名
  trainerCode: string;    // 調教師コード
  trainerName: string;    // 調教師名略称
  ownerName: string;      // 馬主名
  isActive: boolean;      // 現役フラグ
}

/**
 * Shift-JIS バイト列をデコード
 */
function decodeShiftJis(buffer: Buffer, start: number, length: number): string {
  try {
    const slice = buffer.slice(start, start + length);
    const decoded = iconv.decode(slice, 'Shift_JIS');
    // 全角スペースと @ を除去してトリム
    return decoded.replace(/[\u3000@]/g, '').trim();
  } catch (e) {
    return '';
  }
}

/**
 * UMファイル一覧を取得（新しい順）
 * @param yearLimit 取得する年数（デフォルト10年）
 */
function getUmFiles(yearLimit: number = 10): string[] {
  const files: string[] = [];

  if (!fs.existsSync(UM_DATA_PATH)) {
    return files;
  }

  try {
    const years = fs.readdirSync(UM_DATA_PATH)
      .filter(d => /^\d{4}$/.test(d))
      .sort((a, b) => parseInt(b) - parseInt(a))
      .slice(0, yearLimit);

    for (const year of years) {
      const yearPath = path.join(UM_DATA_PATH, year);
      if (!fs.existsSync(yearPath)) continue;

      const umFiles = fs.readdirSync(yearPath)
        .filter(f => /^UM\d+\.DAT$/i.test(f))
        .sort((a, b) => b.localeCompare(a));

      for (const umFile of umFiles) {
        files.push(path.join(yearPath, umFile));
      }
    }
  } catch (e) {
    console.error('[TargetHorseReader] ファイル一覧取得エラー:', e);
  }

  return files;
}

/**
 * UMレコードをパース
 */
function parseUmRecord(buffer: Buffer, offset: number): TargetHorseData | null {
  try {
    if (offset + UM_RECORD_LEN > buffer.length) {
      return null;
    }

    // レコードタイプチェック (先頭2バイトが "UM")
    const recordType = decodeShiftJis(buffer, offset, 2);
    if (recordType !== 'UM') {
      return null;
    }

    // フィールド抽出 (1-based offset を 0-based に変換)
    const horseId = decodeShiftJis(buffer, offset + 11, 10);
    const delKubun = decodeShiftJis(buffer, offset + 21, 1);
    const birthDate = decodeShiftJis(buffer, offset + 38, 8);
    const name = decodeShiftJis(buffer, offset + 46, 36);
    const nameKana = decodeShiftJis(buffer, offset + 82, 36);
    const nameEng = decodeShiftJis(buffer, offset + 118, 60);
    const sexCd = decodeShiftJis(buffer, offset + 200, 1);
    const trainerCode = decodeShiftJis(buffer, offset + 849, 5);
    const trainerName = decodeShiftJis(buffer, offset + 854, 8);
    
    // 馬主名 (推定オフセット)
    let ownerName = '';
    try {
      ownerName = decodeShiftJis(buffer, offset + 970, 44);
    } catch (e) {
      // ignore
    }

    return {
      horseId,
      name,
      nameKana,
      nameEng,
      birthDate,
      sex: SEX_CODES[sexCd] || `不明(${sexCd})`,
      trainerCode,
      trainerName,
      ownerName,
      isActive: delKubun === '0',
    };
  } catch (e) {
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
    const buffer = fs.readFileSync(filePath);
    // 最大5ファイルまでキャッシュ（メモリ制限）
    if (fileBufferCache.size >= 5) {
      const firstKey = fileBufferCache.keys().next().value;
      if (firstKey) fileBufferCache.delete(firstKey);
    }
    fileBufferCache.set(filePath, buffer);
    return buffer;
  } catch (e) {
    return null;
  }
}

/**
 * 馬IDインデックスを構築（初回のみ、バックグラウンドで）
 */
function buildHorseIndexIfNeeded(): void {
  if (indexBuilt) return;
  indexBuilt = true;  // 二重実行防止
  
  const startTime = Date.now();
  const umFiles = getUmFiles();
  
  for (const umFile of umFiles) {
    try {
      const buffer = getBufferCached(umFile);
      if (!buffer) continue;
      
      const numRecords = Math.floor(buffer.length / UM_RECORD_LEN);
      
      for (let i = 0; i < numRecords; i++) {
        const offset = i * UM_RECORD_LEN;
        const horseId = decodeShiftJis(buffer, offset + 11, 10);
        
        if (horseId && !horseIndexCache.has(horseId)) {
          horseIndexCache.set(horseId, { file: umFile, offset });
        }
      }
    } catch (e) {
      // ignore
    }
  }
  
  const elapsed = Date.now() - startTime;
  console.log(`[TargetHorseReader] Index built: ${horseIndexCache.size} horses in ${elapsed}ms`);
}

/**
 * 馬IDでTARGETデータを検索（インデックス使用）
 * 
 * @param horseId 血統登録番号（10桁）またはkeibabook ID（7桁）
 * @param horseName オプション: 馬名（ID検索失敗時に名前検索）
 * @returns TargetHorseData or null
 */
export async function findHorseFromTarget(horseId: string, horseName?: string): Promise<TargetHorseData | null> {
  // 10桁に正規化
  const normalizedId = horseId.padStart(10, '0');
  
  // インデックスから検索（高速）
  if (horseIndexCache.has(normalizedId)) {
    const { file, offset } = horseIndexCache.get(normalizedId)!;
    const buffer = getBufferCached(file);
    if (buffer) {
      return parseUmRecord(buffer, offset);
    }
  }
  
  // インデックスにない場合は線形検索（初回または新規馬）
  const umFiles = getUmFiles();

  for (const umFile of umFiles) {
    try {
      const buffer = getBufferCached(umFile);
      if (!buffer) continue;
      
      const numRecords = Math.floor(buffer.length / UM_RECORD_LEN);

      for (let i = 0; i < numRecords; i++) {
        const offset = i * UM_RECORD_LEN;
        
        // クイックチェック: 馬IDの位置を直接確認
        const idAtOffset = decodeShiftJis(buffer, offset + 11, 10);
        
        // インデックスに追加
        if (idAtOffset && !horseIndexCache.has(idAtOffset)) {
          horseIndexCache.set(idAtOffset, { file: umFile, offset });
        }
        
        if (idAtOffset === normalizedId) {
          return parseUmRecord(buffer, offset);
        }
      }
    } catch (e) {
      console.error(`[TargetHorseReader] ファイル読み込みエラー ${umFile}:`, e);
    }
  }

  // IDで見つからない場合、馬名で検索（完全一致）
  if (horseName) {
    const normalizedName = horseName.replace(/\s+/g, '');
    
    for (const umFile of umFiles) {
      try {
        const buffer = getBufferCached(umFile);
        if (!buffer) continue;
        
        const numRecords = Math.floor(buffer.length / UM_RECORD_LEN);
        
        for (let i = 0; i < numRecords; i++) {
          const offset = i * UM_RECORD_LEN;
          const nameAtOffset = decodeShiftJis(buffer, offset + 46, 36);
          
          if (nameAtOffset === normalizedName) {
            console.log(`[TargetHorseReader] Found by name: ${normalizedName}`);
            return parseUmRecord(buffer, offset);
          }
        }
      } catch (e) {
        // ignore
      }
    }
  }

  return null;
}

/**
 * インデックスを事前構築（アプリ起動時に呼び出し推奨）
 */
export function preloadHorseIndex(): void {
  if (!indexBuilt) {
    buildHorseIndexIfNeeded();
  }
}

/**
 * 馬名でTARGETデータを検索
 * 
 * @param query 検索文字列
 * @param limit 最大件数
 * @returns TargetHorseDataの配列
 */
export async function searchHorsesFromTarget(query: string, limit: number = 20): Promise<TargetHorseData[]> {
  const results: TargetHorseData[] = [];
  const queryLower = query.toLowerCase();

  const umFiles = getUmFiles();

  for (const umFile of umFiles) {
    try {
      const buffer = fs.readFileSync(umFile);
      const numRecords = Math.floor(buffer.length / UM_RECORD_LEN);

      for (let i = 0; i < numRecords; i++) {
        const offset = i * UM_RECORD_LEN;
        
        // 馬名部分を直接確認
        const name = decodeShiftJis(buffer, offset + 46, 36);
        
        if (name.toLowerCase().includes(queryLower)) {
          const record = parseUmRecord(buffer, offset);
          if (record) {
            results.push(record);
            if (results.length >= limit) {
              return results;
            }
          }
        }
      }
    } catch (e) {
      console.error(`[TargetHorseReader] ファイル読み込みエラー ${umFile}:`, e);
    }
  }

  return results;
}

/**
 * TARGETデータが利用可能かチェック
 */
export function isTargetDataAvailable(): boolean {
  try {
    if (!fs.existsSync(UM_DATA_PATH)) {
      return false;
    }
    
    const umFiles = getUmFiles();
    return umFiles.length > 0;
  } catch (e) {
    return false;
  }
}

/**
 * 馬の年齢を計算
 */
export function calculateHorseAge(birthDate: string, refDate: Date = new Date()): number {
  if (!birthDate || birthDate.length !== 8) {
    return 0;
  }

  try {
    const birthYear = parseInt(birthDate.substring(0, 4), 10);
    // 競馬では1月1日で加齢
    return refDate.getFullYear() - birthYear;
  } catch (e) {
    return 0;
  }
}
