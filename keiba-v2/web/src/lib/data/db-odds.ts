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
  firstSnapshotTime: string | null;
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
): Promise<{ odds: Map<number, number>; time: string | null }> {
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
  if (!firstTime) return { odds: new Map(), time: null };

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

  return { odds, time: firstTime };
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

// --- 全スナップショット取得（時系列タブ用） ---

export interface DbOddsSnapshot {
  /** HAPPYO_TSUKIHI_JIFUN 生値 */
  time: string;
  /** HH:mm 表示用 */
  timeLabel: string;
  /** 各馬のオッズ (馬番文字列 → 単勝オッズ) */
  odds: Record<string, number>;
}

export interface DbTimeSeriesResult {
  raceId: string;
  source: 'db-timeseries' | 'none';
  snapshotCount: number;
  firstTime: string;
  lastTime: string;
  snapshots: DbOddsSnapshot[];
}

interface TimeSeriesRow {
  HAPPYO_TSUKIHI_JIFUN: string;
  UMABAN: string;
  ODDS: string;
  NINKI: string;
}

/**
 * HAPPYO_TSUKIHI_JIFUN (MMDDHHmm等) から HH:mm を抽出
 */
export function extractTimeLabel(raw: string): string {
  const s = raw.trim();
  // 8桁 MMDDHHmm → HH:mm
  if (s.length === 8 && /^\d{8}$/.test(s)) {
    return `${s.substring(4, 6)}:${s.substring(6, 8)}`;
  }
  // 4桁 HHmm → HH:mm
  if (s.length === 4 && /^\d{4}$/.test(s)) {
    return `${s.substring(0, 2)}:${s.substring(2, 4)}`;
  }
  // datetime形式 "YYYY-MM-DD HH:MM:SS" など
  const m = s.match(/(\d{2}):(\d{2})/);
  if (m) return `${m[1]}:${m[2]}`;
  return s;
}

/**
 * 全時系列スナップショットをDBから取得
 * Python側の get_timeseries_win_odds() と同等
 */
export async function getDbOddsAllTimeSeries(raceCode: string): Promise<DbTimeSeriesResult> {
  try {
    const db = getPool();
    const [rows] = await db.query<mysql.RowDataPacket[]>(
      `SELECT HAPPYO_TSUKIHI_JIFUN, UMABAN, ODDS, NINKI
       FROM odds1_tansho_jikeiretsu
       WHERE RACE_CODE = ?
       ORDER BY HAPPYO_TSUKIHI_JIFUN, UMABAN`,
      [raceCode]
    );

    if (rows.length === 0) {
      return { raceId: raceCode, source: 'none', snapshotCount: 0, firstTime: '', lastTime: '', snapshots: [] };
    }

    // スナップショット単位にグループ化
    const snapshotMap = new Map<string, Record<string, number>>();
    for (const r of rows as TimeSeriesRow[]) {
      const time = r.HAPPYO_TSUKIHI_JIFUN?.trim();
      if (!time) continue;
      const val = parseOddsValue(r.ODDS);
      if (val === null) continue;
      const umaban = String(parseInt(r.UMABAN, 10));

      if (!snapshotMap.has(time)) {
        snapshotMap.set(time, {});
      }
      snapshotMap.get(time)![umaban] = val;
    }

    const snapshots: DbOddsSnapshot[] = [];
    for (const [time, odds] of snapshotMap) {
      // 有効オッズが3頭未満のスナップショットは初期データ（****等）→スキップ
      const validCount = Object.values(odds).filter(v => v >= 1.0).length;
      if (validCount < 3) continue;

      snapshots.push({
        time,
        timeLabel: extractTimeLabel(time),
        odds,
      });
    }

    if (snapshots.length === 0) {
      return { raceId: raceCode, source: 'none', snapshotCount: 0, firstTime: '', lastTime: '', snapshots: [] };
    }

    return {
      raceId: raceCode,
      source: 'db-timeseries',
      snapshotCount: snapshots.length,
      firstTime: snapshots[0].timeLabel,
      lastTime: snapshots[snapshots.length - 1].timeLabel,
      snapshots,
    };
  } catch (error) {
    console.error('[db-odds] Error fetching all timeseries:', error);
    return { raceId: raceCode, source: 'none', snapshotCount: 0, firstTime: '', lastTime: '', snapshots: [] };
  }
}

// --- メイン関数 ---

/**
 * レースの最新オッズを取得
 *
 * 優先順位:
 *   1. odds1_tansho (OB15速報/確定) ← リアルタイム更新されるため最新
 *   2. odds1_tansho_jikeiretsu (時系列最新) ← 夜間バッチ配信で遅延あり
 *
 * トレンド計算: odds1_tansho_jikeiretsu の朝一スナップショットと比較
 */
export async function getDbLatestOdds(raceCode: string): Promise<DbOddsResult> {
  try {
    // 全データソースを並列取得
    const [finalWin, finalPlace, firstResult, tsInfo] = await Promise.all([
      getFinalWinOdds(raceCode),            // odds1_tansho (OB15速報/確定)
      getFinalPlaceOdds(raceCode),          // odds1_fukusho
      getFirstTimeseriesWinOdds(raceCode),  // 朝一オッズ (トレンド計算用)
      getLatestTimeseriesWinOdds(raceCode), // 時系列情報 (スナップショット数等)
    ]);

    // オッズソース決定: OB15速報(odds1_tansho) → 時系列最新(jikeiretsu)
    let winOdds: Map<number, { odds: number; ninki: number | null }>;
    let source: 'timeseries' | 'final';
    let placeOdds: Map<number, { low: number; high: number; ninki: number | null }>;

    if (finalWin.size > 0) {
      winOdds = finalWin;
      source = 'final';
      placeOdds = finalPlace;
    } else if (tsInfo.odds.size > 0) {
      winOdds = tsInfo.odds;
      source = 'timeseries';
      placeOdds = await getLatestTimeseriesPlaceOdds(raceCode);
    } else {
      return {
        raceId: raceCode,
        source: 'none',
        snapshotTime: null,
        firstSnapshotTime: null,
        snapshotCount: 0,
        horses: [],
      };
    }

    // 馬データ構築 (トレンドは朝一オッズとの比較)
    const firstOdds = firstResult.odds;
    const horses: DbHorseOdds[] = [];
    for (const [umaban, data] of winOdds) {
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
      source,
      snapshotTime: tsInfo.time,
      firstSnapshotTime: firstResult.time,
      snapshotCount: tsInfo.count,
      horses,
    };
  } catch (error) {
    console.error('[db-odds] Error fetching odds:', error);
    return {
      raceId: raceCode,
      source: 'none',
      snapshotTime: null,
      firstSnapshotTime: null,
      snapshotCount: 0,
      horses: [],
    };
  }
}

// --- 確定成績取得 ---

export interface DbRaceResultEntry {
  umaban: number;
  finishPosition: number;
  time: string;
  last3f: number;
  confirmedWinOdds: number;
  confirmedPlaceOddsMin: number | null;
  confirmedPlaceOddsMax: number | null;
  ninki: number;
}

export interface DbRaceResultsResponse {
  date: string;
  results: Record<string, DbRaceResultEntry[]>; // raceId → entries
  totalRaces: number;
}

interface ResultRow {
  RACE_CODE: string;
  UMABAN: string;
  KAKUTEI_CHAKUJUN: string;
  SOHA_TIME: string;
  KOHAN_3F: string;
  TANSHO_ODDS: string;
  TANSHO_NINKIJUN: string;
}

interface FukushoRow {
  RACE_CODE: string;
  UMABAN: string;
  ODDS_SAITEI: string;
  ODDS_SAIKOU: string;
}

/**
 * 指定日の全レース確定成績をmykeibadbから取得
 * umagoto_race_joho + odds1_fukusho を結合
 */
export async function getDbRaceResultsByDate(date: string): Promise<DbRaceResultsResponse> {
  try {
    const datePrefix = date.replace(/-/g, '');
    const db = getPool();

    // 成績データ取得
    const [resultRows] = await db.query<mysql.RowDataPacket[]>(
      `SELECT RACE_CODE, UMABAN, KAKUTEI_CHAKUJUN, SOHA_TIME, KOHAN_3F, TANSHO_ODDS, TANSHO_NINKIJUN
       FROM umagoto_race_joho
       WHERE RACE_CODE LIKE ? AND KAKUTEI_CHAKUJUN IS NOT NULL AND KAKUTEI_CHAKUJUN != '' AND KAKUTEI_CHAKUJUN != '00'
       ORDER BY RACE_CODE, CAST(UMABAN AS UNSIGNED)`,
      [`${datePrefix}%`]
    );

    if (resultRows.length === 0) {
      return { date, results: {}, totalRaces: 0 };
    }

    // 確定複勝オッズ取得
    const [fukushoRows] = await db.query<mysql.RowDataPacket[]>(
      `SELECT RACE_CODE, UMABAN, ODDS_SAITEI, ODDS_SAIKOU
       FROM odds1_fukusho
       WHERE RACE_CODE LIKE ?`,
      [`${datePrefix}%`]
    );

    // 複勝オッズをマップ化
    const fukushoMap = new Map<string, { min: number | null; max: number | null }>();
    for (const r of fukushoRows as FukushoRow[]) {
      const key = `${r.RACE_CODE}-${parseInt(r.UMABAN, 10)}`;
      fukushoMap.set(key, {
        min: parseOddsValue(r.ODDS_SAITEI),
        max: parseOddsValue(r.ODDS_SAIKOU),
      });
    }

    // レース別にグループ化
    const results: Record<string, DbRaceResultEntry[]> = {};
    for (const r of resultRows as ResultRow[]) {
      const raceCode = r.RACE_CODE;
      const umaban = parseInt(r.UMABAN, 10);
      const pos = parseInt(r.KAKUTEI_CHAKUJUN, 10);
      if (isNaN(pos) || pos <= 0) continue;

      const fukushoKey = `${raceCode}-${umaban}`;
      const fukusho = fukushoMap.get(fukushoKey);

      // SOHA_TIME: "1258" → "1:25.8"
      const rawTime = r.SOHA_TIME?.trim() || '';
      let timeStr = '';
      if (rawTime.length === 4) {
        const m = parseInt(rawTime[0], 10);
        const s = parseInt(rawTime.substring(1, 3), 10);
        const t = rawTime[3];
        timeStr = `${m}:${s.toString().padStart(2, '0')}.${t}`;
      }

      const entry: DbRaceResultEntry = {
        umaban,
        finishPosition: pos,
        time: timeStr,
        last3f: parseInt(r.KOHAN_3F || '0', 10) / 10,
        confirmedWinOdds: parseOddsValue(r.TANSHO_ODDS) ?? 0,
        confirmedPlaceOddsMin: fukusho?.min ?? null,
        confirmedPlaceOddsMax: fukusho?.max ?? null,
        ninki: parseInt(r.TANSHO_NINKIJUN || '0', 10),
      };

      if (!results[raceCode]) results[raceCode] = [];
      results[raceCode].push(entry);
    }

    return {
      date,
      results,
      totalRaces: Object.keys(results).length,
    };
  } catch (error) {
    console.error('[db-odds] Error fetching race results:', error);
    return { date, results: {}, totalRaces: 0 };
  }
}
