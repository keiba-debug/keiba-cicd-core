// データソースの設定

import path from 'path';

/** JRA-VANデータルート（環境変数 JV_DATA_ROOT） */
export const JV_DATA_ROOT = process.env.JV_DATA_ROOT || 'C:/TFJV';

/** データルート（環境変数 KEIBA_DATA_ROOT） */
export const KEIBA_DATA_ROOT = process.env.KEIBA_DATA_ROOT || 'C:/KEIBA-CICD/data3';
/** @deprecated DATA3_ROOT を使う箇所は KEIBA_DATA_ROOT に置き換え可 */
export const DATA3_ROOT = KEIBA_DATA_ROOT;

/** AIデータ（bankroll/purchases/predictions）（data3/userdata/） */
export const AI_DATA_PATH = path.join(DATA3_ROOT, 'userdata');

/** BABAデータ（クッション値・含水率） */
export const BABA_DATA_PATH = path.join(DATA3_ROOT, 'analysis', 'baba');

// 競馬場コード
export const TRACKS = [
  '中山',
  '東京',
  '京都',
  '阪神',
  '中京',
  '新潟',
  '小倉',
  '福島',
  '札幌',
  '函館',
] as const;

export type TrackName = (typeof TRACKS)[number];
