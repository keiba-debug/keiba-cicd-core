/**
 * mykeibadb (MySQL) レース情報取得モジュール
 *
 * JRA-VANの RACE_SHOSAI テーブルからレース基本情報を取得する。
 * keibabook スクレイピングの代替/補完として使用。
 */

import mysql from 'mysql2/promise';

// --- 接続プール（db-odds.ts と共有） ---

let pool: mysql.Pool | null = null;

function getPool(): mysql.Pool {
  if (!pool) {
    pool = mysql.createPool({
      host: process.env.MYKEIBADB_HOST || 'localhost',
      port: parseInt(process.env.MYKEIBADB_PORT || '3306', 10),
      user: process.env.MYKEIBADB_USER || 'root',
      password: process.env.MYKEIBADB_PASS || 'test123!',
      database: process.env.MYKEIBADB_DB || 'mykeibadb',
      charset: 'utf8mb4',
      waitForConnections: true,
      connectionLimit: 5,
      queueLimit: 0,
    });
  }
  return pool;
}

// --- 定数マッピング ---

/** TRACK_CODE先頭1桁 → track_type */
const TRACK_CODE_TYPE: Record<string, string> = {
  '1': 'turf',
  '2': 'dirt',
  '5': 'obstacle',
};

/** 馬場状態コード → 表示名 */
const BABA_CODE_MAP: Record<string, string> = {
  '1': '良',
  '2': '稍重',
  '3': '重',
  '4': '不良',
};

/** 天候コード → 表示名 */
const TENKO_CODE_MAP: Record<string, string> = {
  '1': '晴',
  '2': '曇',
  '3': '雨',
  '4': '小雨',
  '5': '雪',
  '6': '小雪',
};

// --- 型定義 ---

export interface DbRaceInfo {
  raceCode: string;
  trackCode: string;       // JRA-VAN TRACK_CODE (2桁: "17"=芝内, "18"=芝外, "24"=ダート等)
  trackType: string;       // 'turf' | 'dirt' | 'obstacle' | ''
  distance: number;
  courseKubun: string;      // A/B/C/D/E
  tenko: string;           // 天候表示名
  shibaBaba: string;       // 芝馬場状態表示名
  dirtBaba: string;        // ダート馬場状態表示名
  hassoJikoku: string;     // 発走時刻 (HHmm)
  raceName: string;        // レース名
  gradeCode: string;       // グレードコード
  shussoTosu: number;      // 出走頭数
}

interface RaceShosaiRow {
  RACE_CODE: string;
  TRACK_CODE: string;
  KYORI: string;
  COURSE_KUBUN: string;
  TENKO_CODE: string;
  SHIBA_BABAJOTAI_CODE: string;
  DIRT_BABAJOTAI_CODE: string;
  HASSO_JIKOKU: string;
  KYOSOMEI_HONDAI: string;
  GRADE_CODE: string;
  SHUSSO_TOSU: string;
}

/**
 * 指定日の全レース情報をRACE_SHOSAIから取得
 * @param dateYYYYMMDD "20260215" 形式
 * @returns raceCode → DbRaceInfo のマップ
 */
export async function getDbRaceInfoByDate(dateYYYYMMDD: string): Promise<Map<string, DbRaceInfo>> {
  const result = new Map<string, DbRaceInfo>();
  try {
    const db = getPool();
    const [rows] = await db.query<mysql.RowDataPacket[]>(
      `SELECT RACE_CODE, TRACK_CODE, KYORI, COURSE_KUBUN, TENKO_CODE,
              SHIBA_BABAJOTAI_CODE, DIRT_BABAJOTAI_CODE, HASSO_JIKOKU,
              KYOSOMEI_HONDAI, GRADE_CODE, SHUSSO_TOSU
       FROM RACE_SHOSAI
       WHERE RACE_CODE LIKE ?
       ORDER BY RACE_CODE`,
      [`${dateYYYYMMDD}%`]
    );

    for (const r of rows as RaceShosaiRow[]) {
      const trackCode = (r.TRACK_CODE || '').trim();
      const trackType = TRACK_CODE_TYPE[trackCode.substring(0, 1)] || '';
      const kyori = parseInt(r.KYORI || '0', 10);
      const tenkoCode = (r.TENKO_CODE || '').trim();
      const shibaCode = (r.SHIBA_BABAJOTAI_CODE || '').trim();
      const dirtCode = (r.DIRT_BABAJOTAI_CODE || '').trim();

      result.set(r.RACE_CODE, {
        raceCode: r.RACE_CODE,
        trackCode,
        trackType,
        distance: isNaN(kyori) ? 0 : kyori,
        courseKubun: (r.COURSE_KUBUN || '').trim(),
        tenko: TENKO_CODE_MAP[tenkoCode] || '',
        shibaBaba: BABA_CODE_MAP[shibaCode] || '',
        dirtBaba: BABA_CODE_MAP[dirtCode] || '',
        hassoJikoku: (r.HASSO_JIKOKU || '').trim(),
        raceName: (r.KYOSOMEI_HONDAI || '').trim(),
        gradeCode: (r.GRADE_CODE || '').trim(),
        shussoTosu: parseInt(r.SHUSSO_TOSU || '0', 10) || 0,
      });
    }
  } catch (error) {
    console.error('[db-race] Error fetching race info:', error);
  }
  return result;
}

/**
 * 複数日のレース情報を一括取得
 * @param dates "20260215" 形式の配列
 */
export async function getDbRaceInfoByDates(dates: string[]): Promise<Map<string, DbRaceInfo>> {
  if (dates.length === 0) return new Map();
  if (dates.length === 1) return getDbRaceInfoByDate(dates[0]);

  const result = new Map<string, DbRaceInfo>();
  try {
    const db = getPool();
    const conditions = dates.map(() => 'RACE_CODE LIKE ?').join(' OR ');
    const params = dates.map(d => `${d}%`);
    const [rows] = await db.query<mysql.RowDataPacket[]>(
      `SELECT RACE_CODE, TRACK_CODE, KYORI, COURSE_KUBUN, TENKO_CODE,
              SHIBA_BABAJOTAI_CODE, DIRT_BABAJOTAI_CODE, HASSO_JIKOKU,
              KYOSOMEI_HONDAI, GRADE_CODE, SHUSSO_TOSU
       FROM RACE_SHOSAI
       WHERE ${conditions}
       ORDER BY RACE_CODE`,
      params
    );

    for (const r of rows as RaceShosaiRow[]) {
      const trackCode = (r.TRACK_CODE || '').trim();
      const trackType = TRACK_CODE_TYPE[trackCode.substring(0, 1)] || '';
      const kyori = parseInt(r.KYORI || '0', 10);
      const tenkoCode = (r.TENKO_CODE || '').trim();
      const shibaCode = (r.SHIBA_BABAJOTAI_CODE || '').trim();
      const dirtCode = (r.DIRT_BABAJOTAI_CODE || '').trim();

      result.set(r.RACE_CODE, {
        raceCode: r.RACE_CODE,
        trackCode,
        trackType,
        distance: isNaN(kyori) ? 0 : kyori,
        courseKubun: (r.COURSE_KUBUN || '').trim(),
        tenko: TENKO_CODE_MAP[tenkoCode] || '',
        shibaBaba: BABA_CODE_MAP[shibaCode] || '',
        dirtBaba: BABA_CODE_MAP[dirtCode] || '',
        hassoJikoku: (r.HASSO_JIKOKU || '').trim(),
        raceName: (r.KYOSOMEI_HONDAI || '').trim(),
        gradeCode: (r.GRADE_CODE || '').trim(),
        shussoTosu: parseInt(r.SHUSSO_TOSU || '0', 10) || 0,
      });
    }
  } catch (error) {
    console.error('[db-race] Error fetching race info for multiple dates:', error);
  }
  return result;
}

/**
 * TRACK_CODE先頭1桁からtrack_type文字列に変換
 */
export function trackCodeToType(trackCode: string): string {
  return TRACK_CODE_TYPE[trackCode.substring(0, 1)] || '';
}

/**
 * track_typeを日本語表示に変換
 */
export function trackTypeToJapanese(trackType: string): string {
  switch (trackType) {
    case 'turf': return '芝';
    case 'dirt': return 'ダ';
    case 'obstacle': return '障';
    default: return trackType === '芝' ? '芝' : trackType === 'ダ' ? 'ダ' : '';
  }
}
