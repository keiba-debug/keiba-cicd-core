/**
 * TARGET 買い目取り込みCSV (FF CSV) ライター
 *
 * TARGET frontier JV の買い目取り込み機能用CSVを出力する。
 * 公式仕様: https://targetfaq.jra-van.jp/faq/detail?site=SVKNEGBV&category=48&id=693
 *
 * FF CSV構造（1行 = 1買い目, 12フィールド）:
 *   [0]  レースID (16桁)
 *   [1]  返還フラグ (0=有効)
 *   [2]  券種 (0=単勝, 1=複勝, 2=枠連, 3=馬連, 4=ワイド, 5=馬単, 6=三連複, 7=三連単)
 *   [3]  目１ (馬番) ※必須
 *   [4]  目２ (0 = なし)
 *   [5]  目３ (0 = なし)
 *   [6]  購入金額 (円単位)
 *   [7]  オッズ (0 = 未確定)
 *   [8]  的中時配当 (0 = 未確定)
 *   [9]  エリア (省略可)
 *   [10] マーク (省略可)
 *   [11] 一括購入目用馬番 (省略可)
 *
 * ファイル名: FFyyyymmdd.CSV
 * 出力先: {JV_DATA_ROOT}/MY_DATA/
 * エンコーディング: Shift-JIS (cp932)
 * 改行: CRLF
 * 取り込み: TARGET側で「買い目取り込み」メニューから読み込む
 */

import * as fs from 'fs';
import * as path from 'path';
import * as iconv from 'iconv-lite';
import { JV_DATA_ROOT } from '@/lib/config';

const FF_CSV_DIR = path.join(JV_DATA_ROOT, 'TXT');

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
  written: number;   // 書込み買い目数
  skipped: number;   // 未使用（互換性のため残す）
  filePath: string;  // 書込み先ファイルパス
}

/**
 * FF CSV ファイルパスを取得
 * ファイル名: FFyyyymmdd_HHmmss.CSV（出力ごとにユニーク）
 */
function getFfFilePath(dateStr: string): string {
  const now = new Date();
  const hh = String(now.getHours()).padStart(2, '0');
  const mm = String(now.getMinutes()).padStart(2, '0');
  const ss = String(now.getSeconds()).padStart(2, '0');
  return path.join(FF_CSV_DIR, `FF${dateStr}_${hh}${mm}${ss}.CSV`);
}

/**
 * 1件の買い目を FF CSV 行に変換
 */
function buildFfRow(raceId: string, bet: PdBet): string {
  const fields = [
    raceId,                  // [0] レースID
    '0',                     // [1] 返還フラグ (0=有効)
    String(bet.betType),     // [2] 券種
    String(bet.umaban),      // [3] 目１ (馬番)
    '0',                     // [4] 目２
    '0',                     // [5] 目３
    String(bet.amount),      // [6] 購入金額（円単位）
    '0',                     // [7] オッズ（未確定）
    '0',                     // [8] 的中時配当（未確定）
    '',                      // [9] エリア（省略）
    '',                      // [10] マーク（省略）
    '',                      // [11] 一括購入目用（省略）
  ];
  return fields.join(',');
}

/**
 * 推奨買い目を FF CSV に書き込む
 *
 * - 日付別ファイル（FFyyyymmdd.CSV）に書込み
 * - 既存ファイルがある場合は上書き（取り込みは追加形式なので問題なし）
 * - TARGET側で「買い目取り込み」メニューから読み込む
 */
export function writePdBets(entries: PdRaceEntry[]): PdWriteResult {
  if (entries.length === 0) {
    return { written: 0, skipped: 0, filePath: '' };
  }

  // 日付でグループ化（race_idの先頭8桁 = YYYYMMDD）
  const byDate = new Map<string, { raceId: string; bet: PdBet }[]>();
  for (const entry of entries) {
    const dateStr = entry.raceId.slice(0, 8);
    if (!byDate.has(dateStr)) byDate.set(dateStr, []);
    for (const bet of entry.bets) {
      byDate.get(dateStr)!.push({ raceId: entry.raceId, bet });
    }
  }

  let totalWritten = 0;
  let lastFilePath = '';

  for (const [dateStr, bets] of byDate) {
    const filePath = getFfFilePath(dateStr);
    lastFilePath = filePath;

    // FF CSV行を生成
    const rows = bets.map(b => buildFfRow(b.raceId, b.bet));
    const content = rows.join('\r\n') + '\r\n';
    const buf = iconv.encode(content, 'cp932');

    // ディレクトリ確認
    if (!fs.existsSync(FF_CSV_DIR)) {
      fs.mkdirSync(FF_CSV_DIR, { recursive: true });
    }

    fs.writeFileSync(filePath, buf);
    totalWritten += rows.length;
  }

  return { written: totalWritten, skipped: 0, filePath: lastFilePath };
}

/**
 * 指定日付の FF CSV を削除する
 * @deprecated FF CSVは取り込み用なので通常削除不要
 */
export function clearPdBets(raceIds: string[]): number {
  if (raceIds.length === 0) return 0;

  // 日付でグループ化
  const dates = new Set(raceIds.map(id => id.slice(0, 8)));
  let cleared = 0;

  for (const dateStr of dates) {
    const filePath = getFfFilePath(dateStr);
    if (fs.existsSync(filePath)) {
      fs.unlinkSync(filePath);
      cleared++;
    }
  }

  return cleared;
}
