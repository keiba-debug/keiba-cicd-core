// データソースの設定

import path from 'path';

/** 競馬データ全般のルート（環境変数 DATA_ROOT） */
export const DATA_ROOT = process.env.DATA_ROOT || 'C:/KEIBA-CICD/data2';

/** 後方互換性のため KEIBA_DATA_ROOT_DIR も提供（DATA_ROOT のエイリアス） */
export const KEIBA_DATA_ROOT_DIR = DATA_ROOT;

/** JRA-VAN（JV）データのルート（環境変数 JV_DATA_ROOT_DIR） */
export const JV_DATA_ROOT_DIR = process.env.JV_DATA_ROOT_DIR || 'C:/TFJV';

/** v4データルート (data3)（環境変数 DATA3_ROOT） */
export const DATA3_ROOT = process.env.DATA3_ROOT || 'C:/KEIBA-CICD/data3';

/** AIデータ（bankroll/purchases/predictions）（data3/userdata/） */
export const AI_DATA_PATH = path.join(DATA3_ROOT, 'userdata');

/** BABAデータ（クッション値・含水率） */
export const BABA_DATA_PATH = path.join(DATA_ROOT, 'baba');

export const PATHS = {
  races: `${KEIBA_DATA_ROOT_DIR}/races`,
  horses: `${KEIBA_DATA_ROOT_DIR}/horses/profiles`,
  logs: `${KEIBA_DATA_ROOT_DIR}/logs`,
  target: `${KEIBA_DATA_ROOT_DIR}/target`,
  userdata: `${KEIBA_DATA_ROOT_DIR}/userdata`,
} as const;

/** ユーザーデータディレクトリ（スタートメモなど） */
export const USER_DATA_DIR = PATHS.userdata;

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
