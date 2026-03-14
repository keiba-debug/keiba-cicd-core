import { NextRequest, NextResponse } from 'next/server';
import { promises as fsp } from 'fs';
import path from 'path';

const DATA_ROOT = process.env.KEIBA_DATA_ROOT || 'C:/KEIBA-CICD/data3';

function getFilePath(date: string): string {
  return path.join(DATA_ROOT, 'confirmed_bets', `${date}.json`);
}

export interface ConfirmedBet {
  id: string;               // race_id + umaban + bet_type + confirmed_at
  confirmed_at: string;     // ISO8601
  date: string;             // YYYY-MM-DD
  race_id: string;
  venue: string;
  race_number: number;
  umaban: number;
  horse_name: string;
  bet_type: string;
  wide_pair?: number[] | null;
  wide_source?: string | null;
  odds_at_confirm: number;
  ev_at_confirm: number;
  gap_at_confirm: number;
  ar_deviation: number | null;
  pred_proba_w: number | null;
  amount: number;
  preset: string;
  adaptive_rule?: string | null;
}

// GET ?date=YYYY-MM-DD
export async function GET(request: NextRequest) {
  const date = request.nextUrl.searchParams.get('date');
  if (!date) {
    return NextResponse.json({ error: 'date required' }, { status: 400 });
  }
  const filePath = getFilePath(date);
  try {
    const raw = await fsp.readFile(filePath, 'utf-8');
    const bets: ConfirmedBet[] = JSON.parse(raw);
    return NextResponse.json({ bets });
  } catch {
    return NextResponse.json({ bets: [] });
  }
}

// POST: 1件追加（同じidは上書き）
export async function POST(request: NextRequest) {
  try {
    const bet: ConfirmedBet = await request.json();
    if (!bet.date || !bet.race_id) {
      return NextResponse.json({ error: 'date and race_id required' }, { status: 400 });
    }

    const dir = path.join(DATA_ROOT, 'confirmed_bets');
    await fsp.mkdir(dir, { recursive: true });

    const filePath = getFilePath(bet.date);
    let bets: ConfirmedBet[] = [];
    try {
      const raw = await fsp.readFile(filePath, 'utf-8');
      bets = JSON.parse(raw);
    } catch { /* 新規 */ }

    // 同じidがあれば削除（トグル用）
    const existingIdx = bets.findIndex(b => b.id === bet.id);
    if (existingIdx >= 0) {
      bets.splice(existingIdx, 1);
      await fsp.writeFile(filePath, JSON.stringify(bets, null, 2), 'utf-8');
      return NextResponse.json({ action: 'removed', bets });
    }

    bets.push(bet);
    await fsp.writeFile(filePath, JSON.stringify(bets, null, 2), 'utf-8');
    return NextResponse.json({ action: 'added', bets });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
