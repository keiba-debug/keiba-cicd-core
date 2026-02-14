/**
 * TARGET PD CSV (買い目) ライター
 *
 * TARGET frontier JV の買い目データCSV（PDyyyymm.CSV）に書き込む。
 * フォーマットは target_reader.py の読み込み仕様と対称。
 *
 * CSV構造（1行 = 1レース）:
 *   Field 0:   race_id (16桁)
 *   Field 1-15: レース情報（空でOK）
 *   Field 16:  投資合計（100円単位）
 *   Field 17:  払戻金額（0 = 未確定）
 *   Field 18-117: 各種データ（空でOK）
 *   Field 118: 買い目件数
 *   Field 119+: 買い目詳細（10フィールド × 件数）
 *     [0] 的中フラグ (0)
 *     [1] 券種コード (0=単勝, 1=複勝)
 *     [2] 馬番1
 *     [3] 馬番2 (0)
 *     [4] 馬番3 (0)
 *     [5] 金額（100円単位）
 *     [6] オッズ (0.0 = 未確定)
 *     [7-8] 空
 *     [9] 0
 *
 * エンコーディング: Shift-JIS (cp932)
 * 改行: CRLF
 */

import * as fs from 'fs';
import * as path from 'path';
import * as iconv from 'iconv-lite';
import { JV_DATA_ROOT } from '@/lib/config';

const MY_DATA_DIR = path.join(JV_DATA_ROOT, 'MY_DATA');

/** 券種コード */
export const BET_TYPE_CODE = {
  tansho: 0,   // 単勝
  fukusho: 1,  // 複勝
} as const;

/** 1件の買い目 */
export interface PdBet {
  betType: number;  // 0=単勝, 1=複勝
  umaban: number;   // 馬番
  amount: number;   // 金額（円）
}

/** 1レース分の買い目 */
export interface PdRaceEntry {
  raceId: string;   // 16桁レースID
  bets: PdBet[];
}

/** 書込み結果 */
export interface PdWriteResult {
  written: number;   // 新規書込みレース数
  skipped: number;   // 既存のためスキップしたレース数
  filePath: string;  // 書込み先ファイルパス
}

/** PD CSV ファイルパスを取得 */
function getPdFilePath(year: number, month: number): string {
  return path.join(MY_DATA_DIR, `PD${year}${String(month).padStart(2, '0')}.CSV`);
}

/**
 * 既存の PD CSV を読み込み、raceId → 生CSV行 のマップを返す
 */
function readExistingPd(filePath: string): Map<string, string> {
  const result = new Map<string, string>();
  if (!fs.existsSync(filePath)) return result;

  const buf = fs.readFileSync(filePath);
  const content = iconv.decode(buf, 'cp932');
  const lines = content.split(/\r?\n/).filter(l => l.trim());

  for (const line of lines) {
    const raceId = line.split(',')[0];
    if (raceId && raceId.length === 16) {
      result.set(raceId, line);
    }
  }
  return result;
}

/**
 * 1レース分の PD CSV 行を生成
 */
function buildPdRow(entry: PdRaceEntry): string {
  const totalAmount100 = entry.bets.reduce(
    (sum, b) => sum + Math.round(b.amount / 100), 0
  );

  // Header fields (0-117): 118個
  const header: string[] = new Array(118).fill('');
  header[0] = entry.raceId;           // race_id
  header[16] = String(totalAmount100); // 投資合計（100円単位）
  header[17] = '0';                    // 払戻金額

  // Bet count (field 118)
  const betCount = entry.bets.length;

  // Bet records (10 fields each, starting at field 119)
  const betFields: string[] = [];
  for (const bet of entry.bets) {
    betFields.push('0');                              // [0] 的中フラグ
    betFields.push(String(bet.betType));              // [1] 券種コード
    betFields.push(String(bet.umaban));               // [2] 馬番1
    betFields.push('0');                              // [3] 馬番2
    betFields.push('0');                              // [4] 馬番3
    betFields.push(String(Math.round(bet.amount / 100))); // [5] 金額（100円単位）
    betFields.push('0.0');                            // [6] オッズ（未確定）
    betFields.push('');                               // [7] 空
    betFields.push('');                               // [8] 空
    betFields.push('0');                              // [9] 予備
  }

  return [...header, String(betCount), ...betFields].join(',');
}

/**
 * 推奨買い目を PD CSV に書き込む
 *
 * - 月別ファイル（PDyyyymm.CSV）に書込み
 * - 同一race_idが既存の場合はスキップ（手動購入の上書き防止）
 * - ファイルが存在しない場合は新規作成
 */
export function writePdBets(entries: PdRaceEntry[]): PdWriteResult {
  if (entries.length === 0) {
    return { written: 0, skipped: 0, filePath: '' };
  }

  // 年月でグループ化
  const byMonth = new Map<string, PdRaceEntry[]>();
  for (const entry of entries) {
    const year = entry.raceId.slice(0, 4);
    const month = entry.raceId.slice(4, 6);
    const key = `${year}-${month}`;
    if (!byMonth.has(key)) byMonth.set(key, []);
    byMonth.get(key)!.push(entry);
  }

  let totalWritten = 0;
  let totalSkipped = 0;
  let lastFilePath = '';

  for (const [ym, monthEntries] of byMonth) {
    const [yearStr, monthStr] = ym.split('-');
    const filePath = getPdFilePath(parseInt(yearStr), parseInt(monthStr));
    lastFilePath = filePath;

    // 既存データ読み込み
    const existing = readExistingPd(filePath);

    // 新規エントリ追加（既存はスキップ）
    for (const entry of monthEntries) {
      if (existing.has(entry.raceId)) {
        totalSkipped++;
        continue;
      }
      existing.set(entry.raceId, buildPdRow(entry));
      totalWritten++;
    }

    // race_id昇順でソートして書き出し
    const sortedKeys = [...existing.keys()].sort();
    const lines = sortedKeys.map(k => existing.get(k)!);
    const content = lines.join('\r\n') + '\r\n';
    const buf = iconv.encode(content, 'cp932');

    // ディレクトリ確認
    if (!fs.existsSync(MY_DATA_DIR)) {
      fs.mkdirSync(MY_DATA_DIR, { recursive: true });
    }

    fs.writeFileSync(filePath, buf);
  }

  return { written: totalWritten, skipped: totalSkipped, filePath: lastFilePath };
}

/**
 * 指定レースの買い目を PD CSV から削除する（再書込み用）
 */
export function clearPdBets(raceIds: string[]): number {
  if (raceIds.length === 0) return 0;

  // 年月でグループ化
  const byMonth = new Map<string, string[]>();
  for (const raceId of raceIds) {
    const year = raceId.slice(0, 4);
    const month = raceId.slice(4, 6);
    const key = `${year}-${month}`;
    if (!byMonth.has(key)) byMonth.set(key, []);
    byMonth.get(key)!.push(raceId);
  }

  let cleared = 0;

  for (const [ym, ids] of byMonth) {
    const [yearStr, monthStr] = ym.split('-');
    const filePath = getPdFilePath(parseInt(yearStr), parseInt(monthStr));
    const existing = readExistingPd(filePath);
    if (existing.size === 0) continue;

    for (const raceId of ids) {
      if (existing.delete(raceId)) cleared++;
    }

    // 書き戻し
    const sortedKeys = [...existing.keys()].sort();
    const lines = sortedKeys.map(k => existing.get(k)!);
    const content = lines.length > 0 ? lines.join('\r\n') + '\r\n' : '';
    const buf = iconv.encode(content, 'cp932');
    fs.writeFileSync(filePath, buf);
  }

  return cleared;
}
