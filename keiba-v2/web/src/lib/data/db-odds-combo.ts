/**
 * mykeibadb 複合馬券オッズ取得モジュール
 *
 * 馬連・馬単・ワイド・三連複・三連単のオッズを MySQL から一括取得する。
 * KUMIBAN 形式:
 *   - 4桁 (馬連/馬単/ワイド): "0102" → 馬1-馬2
 *   - 6桁 (三連複/三連単): "010203" → 馬1-馬2-馬3
 *
 * キー正規化:
 *   - 無順序ペア/トリオ (馬連/ワイド/三連複): 昇順ソートして "1-2-3" 形式
 *   - 順序付きペア/トリオ (馬単/三連単): そのまま "1-2-3" 形式
 */

import mysql from 'mysql2/promise';

// --- 接続プール（db-odds.ts と同じパターン） ---

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

function parseOddsValue(raw: string | null | undefined): number | null {
  if (!raw || raw.trim() === '' || /^[\*\-0]+$/.test(raw.trim())) {
    return null;
  }
  const val = parseInt(raw, 10);
  if (isNaN(val) || val <= 0) return null;
  return val / 10;
}

function parseNinki(raw: string | null | undefined): number | null {
  if (!raw || raw.trim() === '') return null;
  const v = parseInt(raw, 10);
  return isNaN(v) || v <= 0 ? null : v;
}

// --- キー生成 ---

/** 無順序ペア: 昇順ソート "min-max" */
export function pairKey(a: number, b: number): string {
  return a <= b ? `${a}-${b}` : `${b}-${a}`;
}

/** 順序付きペア: そのまま */
export function orderedPairKey(a: number, b: number): string {
  return `${a}-${b}`;
}

/** 無順序トリオ: 昇順ソート "a-b-c" */
export function trioKey(a: number, b: number, c: number): string {
  return [a, b, c].sort((x, y) => x - y).join('-');
}

/** 順序付きトリオ: そのまま */
export function orderedTrioKey(a: number, b: number, c: number): string {
  return `${a}-${b}-${c}`;
}

/** KUMIBAN 4桁 → [u1, u2] */
function parseKumi4(raw: string): [number, number] | null {
  if (!raw || raw.length !== 4) return null;
  const u1 = parseInt(raw.slice(0, 2), 10);
  const u2 = parseInt(raw.slice(2, 4), 10);
  if (isNaN(u1) || isNaN(u2)) return null;
  return [u1, u2];
}

/** KUMIBAN 6桁 → [u1, u2, u3] */
function parseKumi6(raw: string): [number, number, number] | null {
  if (!raw || raw.length !== 6) return null;
  const u1 = parseInt(raw.slice(0, 2), 10);
  const u2 = parseInt(raw.slice(2, 4), 10);
  const u3 = parseInt(raw.slice(4, 6), 10);
  if (isNaN(u1) || isNaN(u2) || isNaN(u3)) return null;
  return [u1, u2, u3];
}

// --- 型定義 ---

export interface OddsEntry {
  odds: number;
  ninki: number | null;
}

export interface WideOddsEntry {
  oddsMin: number;
  oddsMax: number;
  ninki: number | null;
}

export interface ComboOdds {
  raceId: string;
  /** 馬連 key=pairKey(a,b) (無順序) */
  umaren: Map<string, OddsEntry>;
  /** 馬単 key=orderedPairKey(a,b) (順序付き) */
  umatan: Map<string, OddsEntry>;
  /** ワイド key=pairKey(a,b) (無順序) */
  wide: Map<string, WideOddsEntry>;
  /** 三連複 key=trioKey(a,b,c) (無順序) */
  sanrenpuku: Map<string, OddsEntry>;
  /** 三連単 key=orderedTrioKey(a,b,c) (順序付き) */
  sanrentan: Map<string, OddsEntry>;
  /** 取得件数（デバッグ・空判定用） */
  counts: {
    umaren: number;
    umatan: number;
    wide: number;
    sanrenpuku: number;
    sanrentan: number;
  };
}

interface ComboRow {
  KUMIBAN: string;
  ODDS: string;
  NINKI: string;
}

interface WideRow {
  KUMIBAN: string;
  ODDS_SAITEI: string;
  ODDS_SAIKOU: string;
  NINKI: string;
}

// --- クエリ関数 ---

async function fetchPairOdds(
  raceCode: string,
  table: string,
  ordered: boolean
): Promise<Map<string, OddsEntry>> {
  const db = getPool();
  const [rows] = await db.query<mysql.RowDataPacket[]>(
    `SELECT KUMIBAN, ODDS, NINKI FROM ${table} WHERE RACE_CODE = ?`,
    [raceCode]
  );
  const map = new Map<string, OddsEntry>();
  for (const r of rows as ComboRow[]) {
    const pair = parseKumi4(r.KUMIBAN);
    if (!pair) continue;
    const odds = parseOddsValue(r.ODDS);
    if (odds === null) continue;
    const key = ordered ? orderedPairKey(pair[0], pair[1]) : pairKey(pair[0], pair[1]);
    map.set(key, { odds, ninki: parseNinki(r.NINKI) });
  }
  return map;
}

async function fetchTrioOdds(
  raceCode: string,
  table: string,
  ordered: boolean
): Promise<Map<string, OddsEntry>> {
  const db = getPool();
  const [rows] = await db.query<mysql.RowDataPacket[]>(
    `SELECT KUMIBAN, ODDS, NINKI FROM ${table} WHERE RACE_CODE = ?`,
    [raceCode]
  );
  const map = new Map<string, OddsEntry>();
  for (const r of rows as ComboRow[]) {
    const trio = parseKumi6(r.KUMIBAN);
    if (!trio) continue;
    const odds = parseOddsValue(r.ODDS);
    if (odds === null) continue;
    const key = ordered
      ? orderedTrioKey(trio[0], trio[1], trio[2])
      : trioKey(trio[0], trio[1], trio[2]);
    map.set(key, { odds, ninki: parseNinki(r.NINKI) });
  }
  return map;
}

async function fetchWideOdds(raceCode: string): Promise<Map<string, WideOddsEntry>> {
  const db = getPool();
  const [rows] = await db.query<mysql.RowDataPacket[]>(
    `SELECT KUMIBAN, ODDS_SAITEI, ODDS_SAIKOU, NINKI FROM odds3_wide WHERE RACE_CODE = ?`,
    [raceCode]
  );
  const map = new Map<string, WideOddsEntry>();
  for (const r of rows as WideRow[]) {
    const pair = parseKumi4(r.KUMIBAN);
    if (!pair) continue;
    const oddsMin = parseOddsValue(r.ODDS_SAITEI);
    const oddsMax = parseOddsValue(r.ODDS_SAIKOU);
    if (oddsMin === null) continue;
    map.set(pairKey(pair[0], pair[1]), {
      oddsMin,
      oddsMax: oddsMax ?? oddsMin,
      ninki: parseNinki(r.NINKI),
    });
  }
  return map;
}

// --- メイン関数 ---

/**
 * 指定レースの全複合馬券オッズを並列取得
 * @param raceCode 16桁 RACE_CODE
 */
export async function getDbAllCombinationOdds(raceCode: string): Promise<ComboOdds> {
  const empty: ComboOdds = {
    raceId: raceCode,
    umaren: new Map(),
    umatan: new Map(),
    wide: new Map(),
    sanrenpuku: new Map(),
    sanrentan: new Map(),
    counts: { umaren: 0, umatan: 0, wide: 0, sanrenpuku: 0, sanrentan: 0 },
  };

  try {
    const [umaren, umatan, wide, sanrenpuku, sanrentan] = await Promise.all([
      fetchPairOdds(raceCode, 'odds2_umaren', false),
      fetchPairOdds(raceCode, 'odds4_umatan', true),
      fetchWideOdds(raceCode),
      fetchTrioOdds(raceCode, 'odds5_sanrenpuku', false),
      fetchTrioOdds(raceCode, 'odds6_sanrentan', true),
    ]);

    return {
      raceId: raceCode,
      umaren,
      umatan,
      wide,
      sanrenpuku,
      sanrentan,
      counts: {
        umaren: umaren.size,
        umatan: umatan.size,
        wide: wide.size,
        sanrenpuku: sanrenpuku.size,
        sanrentan: sanrentan.size,
      },
    };
  } catch (error) {
    console.error('[db-odds-combo] Error fetching combination odds:', error);
    return empty;
  }
}
