/**
 * WIN5推奨馬 API
 * GET /api/win5?date=YYYY-MM-DD
 *
 * races/YYYY/MM/DD/win5_picks.json を読み込んで返す
 * レース結果がある場合は着順・的中判定も付与
 * mykeibadbから払戻金も取得
 */

import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import mysql from 'mysql2/promise';
import { DATA3_ROOT } from '@/lib/config';

interface RaceEntry {
  umaban: number;
  horse_name: string;
  finish_position?: number;
  odds?: number;
  popularity?: number;
}

interface RaceJson {
  race_id: string;
  entries: RaceEntry[];
}

interface LegResult {
  leg: number;
  winner_umaban: number;
  winner_name: string;
  winner_odds: number;
  winner_popularity: number;
  has_result: boolean;
}

// --- DB接続 ---

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
    });
  }
  return pool;
}

interface Win5Payout {
  kumiban: number[];
  payout: number;
  tickets: number;
}

async function loadWin5Payout(yyyy: string, mmdd: string): Promise<Win5Payout | null> {
  try {
    const db = getPool();
    const [rows] = await db.query<mysql.RowDataPacket[]>(
      `SELECT WIN5_KUMIBAN1, WIN5_KUMIBAN2, WIN5_KUMIBAN3, WIN5_KUMIBAN4, WIN5_KUMIBAN5,
              WIN5_HARAIMODOSHIKIN, TEKICHU_HYOSU
       FROM win5_haraimodoshi
       WHERE KAISAI_NEN = ? AND KAISAI_GAPPI = ?
       LIMIT 1`,
      [yyyy, mmdd]
    );
    if (!rows.length) return null;
    const row = rows[0];
    return {
      kumiban: [
        parseInt(row.WIN5_KUMIBAN1, 10),
        parseInt(row.WIN5_KUMIBAN2, 10),
        parseInt(row.WIN5_KUMIBAN3, 10),
        parseInt(row.WIN5_KUMIBAN4, 10),
        parseInt(row.WIN5_KUMIBAN5, 10),
      ],
      payout: parseInt((row.WIN5_HARAIMODOSHIKIN || '0').trim(), 10),
      tickets: parseInt((row.TEKICHU_HYOSU || '0').trim(), 10),
    };
  } catch {
    return null;
  }
}

function loadRaceResult(racesDir: string, raceId: string): LegResult | null {
  const raceFile = path.join(racesDir, `race_${raceId}.json`);
  if (!fs.existsSync(raceFile)) return null;

  try {
    const raw = fs.readFileSync(raceFile, 'utf-8');
    const race: RaceJson = JSON.parse(raw);
    const winner = race.entries.find(e => e.finish_position === 1);
    if (!winner) return null;
    return {
      leg: 0, // caller sets this
      winner_umaban: winner.umaban,
      winner_name: winner.horse_name,
      winner_odds: winner.odds ?? 0,
      winner_popularity: winner.popularity ?? 0,
      has_result: true,
    };
  } catch {
    return null;
  }
}

export async function GET(req: NextRequest) {
  const date = req.nextUrl.searchParams.get('date');
  if (!date || !/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    return NextResponse.json({ error: 'date parameter required (YYYY-MM-DD)' }, { status: 400 });
  }

  const [yyyy, mm, dd] = date.split('-');
  const racesDir = path.join(DATA3_ROOT, 'races', yyyy, mm, dd);
  const picksPath = path.join(racesDir, 'win5_picks.json');

  if (!fs.existsSync(picksPath)) {
    return NextResponse.json({ error: 'not_found', message: `win5_picks.json not found for ${date}` }, { status: 404 });
  }

  try {
    const raw = fs.readFileSync(picksPath, 'utf-8');
    const data = JSON.parse(raw);

    // レース結果を読み取り
    const results: LegResult[] = [];
    if (data.races && Array.isArray(data.races)) {
      for (const race of data.races) {
        const result = loadRaceResult(racesDir, race.race_id);
        if (result) {
          result.leg = race.leg;
          results.push(result);
        }
      }
    }

    // 全5レースの結果が揃っているか
    const allResultsAvailable = results.length === 5;
    const winnerUmabans = new Map<number, number>();
    for (const r of results) {
      winnerUmabans.set(r.leg, r.winner_umaban);
    }

    // 戦略ごとの的中判定
    const strategyResults: Record<string, { hit: boolean; hitLegs: number[] }> = {};
    if (allResultsAvailable && data.strategies) {
      for (const [name, strategy] of Object.entries(data.strategies) as [string, { legs: { leg: number; picks: { umaban: number }[] }[] }][]) {
        const hitLegs: number[] = [];
        let allHit = true;
        for (const leg of strategy.legs) {
          const winnerUma = winnerUmabans.get(leg.leg);
          const legHit = leg.picks.some(p => p.umaban === winnerUma);
          if (legHit) {
            hitLegs.push(leg.leg);
          } else {
            allHit = false;
          }
        }
        strategyResults[name] = { hit: allHit, hitLegs };
      }
    }

    data.results = results;
    data.strategy_results = strategyResults;

    // WIN5払戻金
    const payout = await loadWin5Payout(yyyy, mm + dd);
    if (payout) {
      data.payout = payout;
    }

    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ error: 'parse_error' }, { status: 500 });
  }
}
