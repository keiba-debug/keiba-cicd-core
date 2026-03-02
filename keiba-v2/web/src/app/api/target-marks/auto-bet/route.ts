/**
 * 推奨買い目 → TARGET FF CSV 書込みAPI
 *
 * POST: クライアントで算出した推奨買い目をTARGET買い目取り込みCSVに一括書込み
 * Body: {
 *   bets: Array<{ raceId: string, umaban: number, umaban2?: number, umaban3?: number, betType: number, amount: number }>
 * }
 *
 * betType: 0=単勝, 1=複勝, 3=馬連, 4=ワイド, 5=馬単, 6=三連複
 * amount: 金額（円）
 *
 * 出力先: C:\TFJV\TXT\FFyyyymmdd_HHmmss.CSV
 * TARGET側で「買い目取り込み」メニューから読み込む
 */

import { NextRequest, NextResponse } from 'next/server';
import { writePdBets } from '@/lib/data/target-pd-writer';
import type { PdRaceEntry } from '@/lib/data/target-pd-writer';

/** 有効な券種コード */
const VALID_BET_TYPES = new Set([0, 1, 3, 4, 5, 6]);
/** 2頭必要な券種 */
const TWO_HORSE_TYPES = new Set([3, 4, 5]); // 馬連, ワイド, 馬単
/** 3頭必要な券種 */
const THREE_HORSE_TYPES = new Set([6]); // 三連複

interface BetInput {
  raceId: string;
  umaban: number;
  umaban2?: number; // 馬連/ワイド/馬単/三連複
  umaban3?: number; // 三連複
  betType: number;  // 0=単勝, 1=複勝, 3=馬連, 4=ワイド, 5=馬単, 6=三連複
  amount: number;   // 円
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const bets: BetInput[] = body.bets;

    if (!Array.isArray(bets) || bets.length === 0) {
      return NextResponse.json(
        { error: '買い目データが空です' },
        { status: 400 }
      );
    }

    // バリデーション
    const validUmaban = (u: number | undefined) => u != null && u >= 1 && u <= 18;
    for (const bet of bets) {
      if (!bet.raceId || bet.raceId.length !== 16) {
        return NextResponse.json(
          { error: `無効なraceId: ${bet.raceId}` },
          { status: 400 }
        );
      }
      if (!validUmaban(bet.umaban)) {
        return NextResponse.json(
          { error: `無効な馬番: ${bet.umaban}` },
          { status: 400 }
        );
      }
      if (!VALID_BET_TYPES.has(bet.betType)) {
        return NextResponse.json(
          { error: `無効な券種: ${bet.betType}（0,1,3,4,5,6対応）` },
          { status: 400 }
        );
      }
      if (TWO_HORSE_TYPES.has(bet.betType) && !validUmaban(bet.umaban2)) {
        return NextResponse.json(
          { error: `券種${bet.betType}には2頭必要です` },
          { status: 400 }
        );
      }
      if (THREE_HORSE_TYPES.has(bet.betType) && (!validUmaban(bet.umaban2) || !validUmaban(bet.umaban3))) {
        return NextResponse.json(
          { error: `券種${bet.betType}には3頭必要です` },
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
    let totalAmount = 0;

    for (const bet of bets) {
      if (!raceMap.has(bet.raceId)) {
        raceMap.set(bet.raceId, { raceId: bet.raceId, bets: [] });
      }
      raceMap.get(bet.raceId)!.bets.push({
        betType: bet.betType,
        umaban: bet.umaban,
        umaban2: bet.umaban2,
        umaban3: bet.umaban3,
        amount: bet.amount,
      });
      totalAmount += bet.amount;
    }

    const entries = [...raceMap.values()];

    // FF CSV 書込み
    const result = writePdBets(entries);

    const winBets = bets.filter(b => b.betType === 0).length;
    const placeBets = bets.filter(b => b.betType === 1).length;

    return NextResponse.json({
      success: true,
      summary: {
        totalBets: bets.length,
        winBets,
        placeBets,
        totalAmount,
        racesWritten: result.written,
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
