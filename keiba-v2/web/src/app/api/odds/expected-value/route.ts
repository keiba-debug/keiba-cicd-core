/**
 * 期待値計算API
 *
 * GET /api/odds/expected-value?raceId=2026013105010101&bankroll=100000
 *
 * 全出走馬の期待値を計算して返す
 */

import { NextRequest, NextResponse } from 'next/server';
import { getRaceOddsFromRt, isRtDataAvailable } from '@/lib/data/rt-data-reader';
import { getHorseInfoByUmaban, lookupHorseInfo } from '@/lib/data/race-horse-names';
import type { HorseOdds } from '@/lib/data/rt-data-types';
import type { ExpectedValueHorse, ExpectedValueResponse } from '@/types/prediction';
import { getDbLatestOdds } from '@/lib/data/db-odds';

/**
 * 勝率を推定する
 * - レイティングまたはAI指数がある場合：それを正規化して勝率に変換
 * - ない場合：オッズの逆数から簡易的に推定
 */
function estimateWinRate(horse: HorseOdds & { aiIndex?: number; rating?: number }, allHorses: (HorseOdds & { aiIndex?: number; rating?: number })[]): number {
  // 1. レイティングを使った推定
  const ratings = allHorses.filter((h) => h.rating != null).map((h) => h.rating!);
  if (ratings.length > 0 && horse.rating != null) {
    // レイティングをソフトマックスで正規化
    const totalExp = ratings.reduce((sum, r) => sum + Math.exp(r / 10), 0);
    const winRate = Math.exp(horse.rating / 10) / totalExp;
    return winRate;
  }

  // 2. AI指数を使った推定
  const aiIndices = allHorses.filter((h) => h.aiIndex != null).map((h) => h.aiIndex!);
  if (aiIndices.length > 0 && horse.aiIndex != null) {
    // AI指数をソフトマックスで正規化
    const totalExp = aiIndices.reduce((sum, ai) => sum + Math.exp(ai / 10), 0);
    const winRate = Math.exp(horse.aiIndex / 10) / totalExp;
    return winRate;
  }

  // 3. オッズの逆数から簡易推定
  if (!horse.winOdds || horse.winOdds <= 0) return 0;

  const oddsHorses = allHorses.filter((h) => h.winOdds != null && h.winOdds > 0);
  if (oddsHorses.length === 0) return 0;

  const totalInverse = oddsHorses.reduce((sum, h) => sum + 1 / h.winOdds!, 0);
  const winRate = (1 / horse.winOdds) / totalInverse;

  return winRate;
}

/**
 * Kelly基準で賭け金の割合を計算（フラクショナルKelly: 0.25）
 * f = ((b * p - q) / b) * fraction
 *
 * - b: 純利益率（オッズ - 1.0）
 * - p: 勝率
 * - q: 1 - 勝率
 * - fraction: リスク調整係数（デフォルト0.25）
 */
function calculateKellyFraction(
  winRate: number,
  odds: number,
  fraction: number = 0.25
): number {
  if (winRate <= 0 || odds <= 1.0) return 0;

  const b = odds - 1.0;
  const p = winRate;
  const q = 1.0 - p;

  const fullKelly = (b * p - q) / b;

  // Kelly基準が負の場合は賭けない
  if (fullKelly <= 0) return 0;

  return Math.max(0, fullKelly * fraction);
}

/**
 * 推奨賭け金を計算
 * - 100円単位に丸める
 * - 最低100円未満は0円（賭けない）
 */
function calculateRecommendedBet(
  kellyFraction: number,
  bankroll: number
): number {
  const bet = Math.floor(bankroll * kellyFraction);
  const rounded = Math.floor(bet / 100) * 100;
  return rounded >= 100 ? rounded : 0;
}

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const raceId = searchParams.get('raceId');
  const bankroll = parseInt(searchParams.get('bankroll') || '100000', 10);

  if (!raceId || raceId.length !== 16) {
    return NextResponse.json(
      { error: 'raceId required (16 digits)', example: '/api/odds/expected-value?raceId=2026013105010101' },
      { status: 400 }
    );
  }

  // 1. 馬情報を取得（DB/RT共通）
  const horseInfo = getHorseInfoByUmaban(raceId);

  // 2. DB優先でオッズ取得
  let horsesWithInfo: (HorseOdds & { aiIndex?: number; rating?: number })[];

  const dbOdds = await getDbLatestOdds(raceId);
  if (dbOdds.source !== 'none' && dbOdds.horses.length > 0) {
    horsesWithInfo = dbOdds.horses.map((h) => {
      const ub = String(h.umaban);
      const info = lookupHorseInfo(horseInfo, ub);
      return {
        umaban: ub,
        winOdds: h.winOdds,
        placeOddsMin: h.placeOddsMin,
        placeOddsMax: h.placeOddsMax,
        ninki: h.ninki,
        aiIndex: info?.aiIndex,
        rating: info?.rating,
        horseName: info?.horseName,
      };
    });
  } else {
    // RT_DATAフォールバック
    if (!isRtDataAvailable()) {
      return NextResponse.json(
        { error: 'No odds data available', raceId, hint: 'DBにもRT_DATAにもデータがありません' },
        { status: 404 }
      );
    }
    const odds = getRaceOddsFromRt(raceId);
    if (!odds) {
      return NextResponse.json(
        { error: 'Odds not found', raceId, hint: '該当レースのオッズデータがありません' },
        { status: 404 }
      );
    }
    horsesWithInfo = odds.horses.map((h) => {
      const info = lookupHorseInfo(horseInfo, h.umaban);
      return {
        ...h,
        aiIndex: info?.aiIndex,
        rating: info?.rating,
        horseName: info?.horseName,
      };
    });
  }

  // 3. 各馬の期待値を計算
  const results: ExpectedValueHorse[] = horsesWithInfo.map((horse) => {
    const winOdds = horse.winOdds;

    if (!winOdds || winOdds <= 0) {
      // オッズが不明な馬は期待値計算不可
      return {
        umaban: horse.umaban,
        horseName: horse.horseName,
        winOdds: null,
        estimatedWinRate: null,
        expectedValue: null,
        expectedValueRate: null,
        kellyFraction: null,
        recommendedBet: null,
        recommendation: 'none',
      };
    }

    // 勝率推定
    const winRate = estimateWinRate(horse, horsesWithInfo);

    if (winRate <= 0) {
      return {
        umaban: horse.umaban,
        horseName: horse.horseName,
        winOdds,
        estimatedWinRate: 0,
        expectedValue: null,
        expectedValueRate: null,
        kellyFraction: null,
        recommendedBet: null,
        recommendation: 'none',
      };
    }

    // 期待値計算
    const expectedValue = winRate * winOdds - 1; // 1単位賭けた場合の期待利益
    const expectedValueRate = winRate * winOdds * 100; // 期待値率（%）

    // Kelly基準賭け金計算
    const kellyFraction = calculateKellyFraction(winRate, winOdds);
    const recommendedBet = calculateRecommendedBet(kellyFraction, bankroll);

    // 推奨度判定
    let recommendation: ExpectedValueHorse['recommendation'];
    if (expectedValueRate >= 120) {
      recommendation = 'strong_buy';
    } else if (expectedValueRate >= 110) {
      recommendation = 'buy';
    } else if (expectedValueRate >= 95) {
      recommendation = 'neutral';
    } else if (expectedValueRate >= 80) {
      recommendation = 'sell';
    } else {
      recommendation = 'none';
    }

    return {
      umaban: horse.umaban,
      horseName: horse.horseName,
      winOdds,
      estimatedWinRate: winRate * 100, // パーセント表記
      expectedValue,
      expectedValueRate,
      kellyFraction,
      recommendedBet,
      recommendation,
    };
  });

  // 4. 期待値率降順でソート
  const sorted = results.sort((a, b) => (b.expectedValueRate ?? 0) - (a.expectedValueRate ?? 0));

  // 5. レスポンス構築
  const response: ExpectedValueResponse = {
    raceId,
    totalHorses: sorted.length,
    profitableCount: sorted.filter((h) => (h.expectedValueRate ?? 0) >= 110).length,
    horses: sorted,
  };

  return NextResponse.json(response);
}
