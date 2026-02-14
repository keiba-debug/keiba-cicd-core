/**
 * 推奨買い目 → TARGET PD CSV 書込みAPI
 *
 * POST: クライアントで算出した推奨買い目をTARGET PD CSV に一括書込み
 * Body: {
 *   bets: Array<{ raceId: string, umaban: number, betType: number, amount: number }>
 *   forceOverwrite?: boolean  — 既存レースの買い目を上書きする場合 true
 * }
 *
 * betType: 0=単勝, 1=複勝
 * amount: 金額（円）
 */

import { NextRequest, NextResponse } from 'next/server';
import { writePdBets, clearPdBets } from '@/lib/data/target-pd-writer';
import type { PdRaceEntry } from '@/lib/data/target-pd-writer';

interface BetInput {
  raceId: string;
  umaban: number;
  betType: number;  // 0=単勝, 1=複勝
  amount: number;   // 円
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const bets: BetInput[] = body.bets;
    const forceOverwrite: boolean = body.forceOverwrite ?? false;

    if (!Array.isArray(bets) || bets.length === 0) {
      return NextResponse.json(
        { error: '買い目データが空です' },
        { status: 400 }
      );
    }

    // バリデーション
    for (const bet of bets) {
      if (!bet.raceId || bet.raceId.length !== 16) {
        return NextResponse.json(
          { error: `無効なraceId: ${bet.raceId}` },
          { status: 400 }
        );
      }
      if (bet.umaban < 1 || bet.umaban > 18) {
        return NextResponse.json(
          { error: `無効な馬番: ${bet.umaban}` },
          { status: 400 }
        );
      }
      if (bet.betType !== 0 && bet.betType !== 1) {
        return NextResponse.json(
          { error: `無効な券種: ${bet.betType}（0=単勝, 1=複勝のみ対応）` },
          { status: 400 }
        );
      }
      if (bet.amount < 100 || bet.amount % 100 !== 0) {
        return NextResponse.json(
          { error: `無効な金額: ${bet.amount}（100円単位）` },
          { status: 400 }
        );
      }
    }

    // レース単位にグループ化
    const raceMap = new Map<string, PdRaceEntry>();
    let winBets = 0;
    let placeBets = 0;
    let totalAmount = 0;

    for (const bet of bets) {
      if (!raceMap.has(bet.raceId)) {
        raceMap.set(bet.raceId, { raceId: bet.raceId, bets: [] });
      }
      raceMap.get(bet.raceId)!.bets.push({
        betType: bet.betType,
        umaban: bet.umaban,
        amount: bet.amount,
      });
      if (bet.betType === 0) winBets++;
      else placeBets++;
      totalAmount += bet.amount;
    }

    const entries = [...raceMap.values()];

    // forceOverwrite の場合、既存エントリを先に削除
    let cleared = 0;
    if (forceOverwrite) {
      cleared = clearPdBets(entries.map(e => e.raceId));
    }

    // PD CSV 書込み
    const result = writePdBets(entries);

    return NextResponse.json({
      success: true,
      summary: {
        totalBets: bets.length,
        winBets,
        placeBets,
        totalAmount,
        racesWritten: result.written,
        racesSkipped: result.skipped,
        cleared,
        filePath: result.filePath,
      },
    });
  } catch (error) {
    console.error('[auto-bet API] Error:', error);
    return NextResponse.json(
      { error: '買い目書込みに失敗しました', details: String(error) },
      { status: 500 }
    );
  }
}
