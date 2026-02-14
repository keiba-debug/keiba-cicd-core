/**
 * mykeibadb (MySQL) オッズ取得モジュール
 *
 * JRA-VANの時系列オッズ / 確定オッズをMySQLから取得する。
 * Python側の core/odds_db.py と同等の機能をTypeScriptで提供。
 */

import mysql from 'mysql2/promise';

// --- 接続プール ---

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
      connectionLimit: 20,
      queueLimit: 0,
    });
  }
  return pool;
}

// --- オッズ値パーサー ---

function parseOddsValue(raw: string | null | undefined): number | null {
  if (!raw || raw.trim() === '' || raw === '----' || raw === '****' || raw === '0000') {
    return null;
  }
  const val = parseInt(raw, 10);
  if (isNaN(val)) return null;
  return val / 10;
}

// --- 型定義 ---

export interface DbHorseOdds {
  umaban: number;
  winOdds: number | null;
  placeOddsMin: number | null;
  placeOddsMax: number | null;
  ninki: number | null;
  firstWinOdds: number | null;
  oddsTrend: 'up' | 'down' | 'stable' | null;
}

export interface DbOddsResult {
  raceId: string;
  source: 'timeseries' | 'final' | 'none';
  snapshotTime: string | null;
  snapshotCount: number;
  horses: DbHorseOdds[];
}

// --- クエリ関数 ---

interface OddsRow {
  UMABAN: string;
  ODDS: string;
  NINKI: string;
}

interface PlaceOddsRow {
  UMABAN: string;
  ODDS_SAITEI: string;
  ODDS_SAIKOU: string;
  NINKI: string;
}

interface MaxTimeRow {
  latest_time: string | null;
}

interface MinTimeRow {
  first_time: string | null;
}

interface SnapCountRow {
  cnt: number;
}

/**
 * 時系列単勝オッズ: 最新スナップショットを取得
 */
async function getLatestTimeseriesWinOdds(
  raceCode: string
): Promise<{ odds: Map<number, { odds: number; ninki: number | null }>; time: string | null; count: number }> {
  const db = getPool();

  // スナップショット数を取得
  const [countRows] = await db.query<mysql.RowDataPacket[]>(
    'SELECT COUNT(DISTINCT HAPPYO_TSUKIHI_JIFUN) as cnt FROM odds1_tansho_jikeiretsu WHERE RACE_CODE = ?',
    [raceCode]
  );
  const count = (countRows[0] as SnapCountRow)?.cnt || 0;

  // 最新時刻を取得
  const [timeRows] = await db.query<mysql.RowDataPacket[]>(
    'SELECT MAX(HAPPYO_TSUKIHI_JIFUN) as latest_time FROM odds1_tansho_jikeiretsu WHERE RACE_CODE = ?',
    [raceCode]
  );
  const latestTime = (timeRows[0] as MaxTimeRow)?.latest_time;
  if (!latestTime) return { odds: new Map(), time: null, count: 0 };

  // 最新スナップショットのオッズ
  const [rows] = await db.query<mysql.RowDataPacket[]>(
    'SELECT UMABAN, ODDS, NINKI FROM odds1_tansho_jikeiretsu WHERE RACE_CODE = ? AND HAPPYO_TSUKIHI_JIFUN = ?',
    [raceCode, latestTime]
  );

  const odds = new Map<number, { odds: number; ninki: number | null }>();
  for (const r of rows as OddsRow[]) {
    const val = parseOddsValue(r.ODDS);
    if (val !== null) {
      const ninki = r.NINKI && r.NINKI.trim() ? parseInt(r.NINKI, 10) : null;
      odds.set(parseInt(r.UMABAN, 10), { odds: val, ninki: isNaN(ninki!) ? null : ninki });
    }
  }

  return { odds, time: latestTime, count };
}

/**
 * 時系列単勝オッズ: 最初の有効なスナップショット（朝一オッズ）を取得
 *
 * 初期スナップショットは ****（未設定）や 0000 が多いため、
 * 有効なオッズが5頭以上あるスナップショットを「朝一」とする。
 */
async function getFirstTimeseriesWinOdds(
  raceCode: string
): Promise<Map<number, number>> {
  const db = getPool();

  // 有効オッズが5頭以上ある最初のスナップショットを探す
  const [timeRows] = await db.query<mysql.RowDataPacket[]>(
    `SELECT HAPPYO_TSUKIHI_JIFUN as first_time
     FROM odds1_tansho_jikeiretsu
     WHERE RACE_CODE = ?
       AND ODDS REGEXP '^[0-9]+$' AND CAST(ODDS AS UNSIGNED) > 0
     GROUP BY HAPPYO_TSUKIHI_JIFUN
     HAVING COUNT(*) >= 5
     ORDER BY HAPPYO_TSUKIHI_JIFUN
     LIMIT 1`,
    [raceCode]
  );
  const firstTime = (timeRows[0] as MinTimeRow)?.first_time;
  if (!firstTime) return new Map();

  const [rows] = await db.query<mysql.RowDataPacket[]>(
    'SELECT UMABAN, ODDS FROM odds1_tansho_jikeiretsu WHERE RACE_CODE = ? AND HAPPYO_TSUKIHI_JIFUN = ?',
    [raceCode, firstTime]
  );

  const odds = new Map<number, number>();
  for (const r of rows as OddsRow[]) {
    const val = parseOddsValue(r.ODDS);
    if (val !== null) {
      odds.set(parseInt(r.UMABAN, 10), val);
    }
  }

  return odds;
}

/**
 * 時系列複勝オッズ: 最新スナップショットを取得
 */
async function getLatestTimeseriesPlaceOdds(
  raceCode: string
): Promise<Map<number, { low: number; high: number; ninki: number | null }>> {
  const db = getPool();

  const [timeRows] = await db.query<mysql.RowDataPacket[]>(
    'SELECT MAX(HAPPYO_TSUKIHI_JIFUN) as latest_time FROM odds1_fukusho_jikeiretsu WHERE RACE_CODE = ?',
    [raceCode]
  );
  const latestTime = (timeRows[0] as MaxTimeRow)?.latest_time;
  if (!latestTime) return new Map();

  const [rows] = await db.query<mysql.RowDataPacket[]>(
    'SELECT UMABAN, ODDS_SAITEI, ODDS_SAIKOU, NINKI FROM odds1_fukusho_jikeiretsu WHERE RACE_CODE = ? AND HAPPYO_TSUKIHI_JIFUN = ?',
    [raceCode, latestTime]
  );

  const odds = new Map<number, { low: number; high: number; ninki: number | null }>();
  for (const r of rows as PlaceOddsRow[]) {
    const low = parseOddsValue(r.ODDS_SAITEI);
    const high = parseOddsValue(r.ODDS_SAIKOU);
    if (low !== null) {
      const ninki = r.NINKI && r.NINKI.trim() ? parseInt(r.NINKI, 10) : null;
      odds.set(parseInt(r.UMABAN, 10), {
        low,
        high: high ?? low,
        ninki: isNaN(ninki!) ? null : ninki,
      });
    }
  }

  return odds;
}

/**
 * 確定単勝オッズ（フォールバック用）
 */
async function getFinalWinOdds(
  raceCode: string
): Promise<Map<number, { odds: number; ninki: number | null }>> {
  const db = getPool();
  const [rows] = await db.query<mysql.RowDataPacket[]>(
    'SELECT UMABAN, ODDS, NINKI FROM odds1_tansho WHERE RACE_CODE = ?',
    [raceCode]
  );

  const odds = new Map<number, { odds: number; ninki: number | null }>();
  for (const r of rows as OddsRow[]) {
    const val = parseOddsValue(r.ODDS);
    if (val !== null) {
      const ninki = r.NINKI && r.NINKI.trim() ? parseInt(r.NINKI, 10) : null;
      odds.set(parseInt(r.UMABAN, 10), { odds: val, ninki: isNaN(ninki!) ? null : ninki });
    }
  }

  return odds;
}

/**
 * 確定複勝オッズ（フォールバック用）
 */
async function getFinalPlaceOdds(
  raceCode: string
): Promise<Map<number, { low: number; high: number; ninki: number | null }>> {
  const db = getPool();
  const [rows] = await db.query<mysql.RowDataPacket[]>(
    'SELECT UMABAN, ODDS_SAITEI, ODDS_SAIKOU, NINKI FROM odds1_fukusho WHERE RACE_CODE = ?',
    [raceCode]
  );

  const odds = new Map<number, { low: number; high: number; ninki: number | null }>();
  for (const r of rows as PlaceOddsRow[]) {
    const low = parseOddsValue(r.ODDS_SAITEI);
    const high = parseOddsValue(r.ODDS_SAIKOU);
    if (low !== null) {
      const ninki = r.NINKI && r.NINKI.trim() ? parseInt(r.NINKI, 10) : null;
      odds.set(parseInt(r.UMABAN, 10), {
        low,
        high: high ?? low,
        ninki: isNaN(ninki!) ? null : ninki,
      });
    }
  }

  return odds;
}

// --- メイン関数 ---

/**
 * レースの最新オッズを取得（時系列 → 確定のフォールバック付き）
 */
export async function getDbLatestOdds(raceCode: string): Promise<DbOddsResult> {
  try {
    // 1) 時系列オッズを試行
    const ts = await getLatestTimeseriesWinOdds(raceCode);

    if (ts.odds.size > 0) {
      // 朝一オッズ + 複勝も取得
      const [firstOdds, placeOdds] = await Promise.all([
        getFirstTimeseriesWinOdds(raceCode),
        getLatestTimeseriesPlaceOdds(raceCode),
      ]);

      const horses: DbHorseOdds[] = [];
      for (const [umaban, data] of ts.odds) {
        const first = firstOdds.get(umaban) ?? null;
        const place = placeOdds.get(umaban);
        let trend: 'up' | 'down' | 'stable' | null = null;
        if (first !== null && data.odds !== first) {
          trend = data.odds > first ? 'up' : 'down';
        } else if (first !== null) {
          trend = 'stable';
        }

        horses.push({
          umaban,
          winOdds: data.odds,
          placeOddsMin: place?.low ?? null,
          placeOddsMax: place?.high ?? null,
          ninki: data.ninki,
          firstWinOdds: first,
          oddsTrend: trend,
        });
      }

      horses.sort((a, b) => a.umaban - b.umaban);

      return {
        raceId: raceCode,
        source: 'timeseries',
        snapshotTime: ts.time,
        snapshotCount: ts.count,
        horses,
      };
    }

    // 2) 確定オッズにフォールバック
    const [finalWin, finalPlace] = await Promise.all([
      getFinalWinOdds(raceCode),
      getFinalPlaceOdds(raceCode),
    ]);

    if (finalWin.size > 0) {
      const horses: DbHorseOdds[] = [];
      for (const [umaban, data] of finalWin) {
        const place = finalPlace.get(umaban);
        horses.push({
          umaban,
          winOdds: data.odds,
          placeOddsMin: place?.low ?? null,
          placeOddsMax: place?.high ?? null,
          ninki: data.ninki,
          firstWinOdds: null,
          oddsTrend: null,
        });
      }
      horses.sort((a, b) => a.umaban - b.umaban);

      return {
        raceId: raceCode,
        source: 'final',
        snapshotTime: null,
        snapshotCount: 0,
        horses,
      };
    }

    // 3) データなし
    return {
      raceId: raceCode,
      source: 'none',
      snapshotTime: null,
      snapshotCount: 0,
      horses: [],
    };
  } catch (error) {
    console.error('[db-odds] Error fetching odds:', error);
    return {
      raceId: raceCode,
      source: 'none',
      snapshotTime: null,
      snapshotCount: 0,
      horses: [],
    };
  }
}
