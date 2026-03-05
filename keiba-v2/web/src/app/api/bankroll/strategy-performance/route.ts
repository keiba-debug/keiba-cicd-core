/**
 * Strategy-Performance API
 *
 * GET /api/bankroll/strategy-performance?preset=intersection&year=2026
 *
 * predictions.json の推奨 × race結果をクロス集計し、
 * プリセット別の月別・年間パフォーマンスを返す。
 *
 * intersection プリセットがない古いファイルでは races から自前フィルタ。
 */

import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

// Intersection Filter 条件
const INTERSECTION = {
  maxRankW: 1,
  minWinGap: 4,
  minWinEv: 1.3,
  maxMargin: 60,
};

interface BetRecord {
  date: string;
  race_id: string;
  umaban: number;
  horse_name: string;
  odds: number;
  win_amount: number;
  place_amount: number;
  strength: string;
  win_vb_gap: number;
  win_ev: number;
  // 結果
  finish_position: number | null;
  result_odds: number | null;
  is_win: boolean;
  is_place: boolean;
  win_return: number;
}

interface MonthStats {
  month: string;
  bets: number;
  hits: number;
  hitRate: number;
  invested: number;
  returned: number;
  profit: number;
  roi: number;
}

export async function GET(request: NextRequest) {
  const preset = request.nextUrl.searchParams.get('preset') || 'intersection';
  const yearParam = request.nextUrl.searchParams.get('year');
  const year = yearParam ? parseInt(yearParam) : new Date().getFullYear();

  const racesRoot = path.join(DATA3_ROOT, 'races');

  // 指定年のディレクトリを走査
  const yearDir = path.join(racesRoot, String(year));
  if (!fs.existsSync(yearDir)) {
    return NextResponse.json({ error: `No data for year ${year}` }, { status: 404 });
  }

  const allBets: BetRecord[] = [];

  // 月→日→predictions.json を走査
  const months = fs.readdirSync(yearDir).filter(d => /^\d{2}$/.test(d)).sort();
  for (const mm of months) {
    const monthDir = path.join(yearDir, mm);
    const days = fs.readdirSync(monthDir).filter(d => /^\d{2}$/.test(d)).sort();

    for (const dd of days) {
      const predFile = path.join(monthDir, dd, 'predictions.json');
      if (!fs.existsSync(predFile)) continue;

      const dateStr = `${year}-${mm}-${dd}`;
      try {
        const predData = JSON.parse(fs.readFileSync(predFile, 'utf-8'));

        // プリセットからベットを抽出
        let bets: Array<{
          race_id: string;
          umaban: number;
          horse_name: string;
          odds: number;
          win_amount: number;
          place_amount: number;
          strength: string;
          win_vb_gap: number;
          win_ev: number;
        }> = [];

        const presetRecs = predData.recommendations?.[preset];
        if (presetRecs && presetRecs.bets && presetRecs.bets.length > 0) {
          // プリセットの推奨をそのまま使用
          bets = presetRecs.bets.map((b: Record<string, unknown>) => ({
            race_id: b.race_id as string,
            umaban: b.umaban as number,
            horse_name: b.horse_name as string,
            odds: (b.odds as number) || 0,
            win_amount: (b.win_amount as number) || 0,
            place_amount: (b.place_amount as number) || 0,
            strength: (b.strength as string) || 'normal',
            win_vb_gap: (b.win_gap ?? b.gap ?? 0) as number,
            win_ev: (b.win_ev ?? 0) as number,
          }));
        } else if (preset === 'intersection' && predData.races) {
          // Fallback: races から intersection 条件を自前フィルタ
          for (const race of predData.races) {
            for (const e of race.entries) {
              if (
                e.rank_w === 1 &&
                (e.win_vb_gap ?? 0) >= INTERSECTION.minWinGap &&
                (e.win_ev ?? 0) >= INTERSECTION.minWinEv &&
                (e.predicted_margin ?? 999) <= INTERSECTION.maxMargin
              ) {
                bets.push({
                  race_id: race.race_id,
                  umaban: e.umaban,
                  horse_name: e.horse_name,
                  odds: e.odds || 0,
                  win_amount: 100, // フォールバック時は100円
                  place_amount: 0,
                  strength: (e.win_vb_gap ?? 0) >= 6 ? 'strong' : 'normal',
                  win_vb_gap: e.win_vb_gap ?? 0,
                  win_ev: e.win_ev ?? 0,
                });
              }
            }
          }
        }

        // レース結果とクロス集計
        for (const bet of bets) {
          let finishPos: number | null = null;
          let resultOdds: number | null = null;

          // race_{race_id}.json を探す
          const raceFile = path.join(monthDir, dd, `race_${bet.race_id}.json`);
          if (fs.existsSync(raceFile)) {
            try {
              const raceData = JSON.parse(fs.readFileSync(raceFile, 'utf-8'));
              const entry = raceData.entries?.find(
                (e: { umaban: number }) => e.umaban === bet.umaban
              );
              if (entry) {
                finishPos = entry.finish_position ?? null;
                resultOdds = entry.odds ?? null;
              }
            } catch {
              // race file parse error - skip
            }
          }

          const isWin = finishPos === 1;
          const numRunners = (() => {
            try {
              const raceData = JSON.parse(fs.readFileSync(raceFile, 'utf-8'));
              return raceData.num_runners ?? raceData.entries?.length ?? 18;
            } catch {
              return 18;
            }
          })();
          const placeLimit = numRunners >= 8 ? 3 : numRunners >= 5 ? 2 : 1;
          const isPlace = finishPos !== null && finishPos > 0 && finishPos <= placeLimit;

          allBets.push({
            date: dateStr,
            race_id: bet.race_id,
            umaban: bet.umaban,
            horse_name: bet.horse_name,
            odds: bet.odds,
            win_amount: bet.win_amount,
            place_amount: bet.place_amount,
            strength: bet.strength,
            win_vb_gap: bet.win_vb_gap,
            win_ev: bet.win_ev,
            finish_position: finishPos,
            result_odds: resultOdds,
            is_win: isWin,
            is_place: isPlace,
            win_return: isWin ? bet.win_amount * (resultOdds || bet.odds) : 0,
          });
        }
      } catch {
        // predictions.json parse error - skip
      }
    }
  }

  // 月別集計
  const monthMap = new Map<string, BetRecord[]>();
  for (const bet of allBets) {
    const month = bet.date.slice(0, 7); // YYYY-MM
    if (!monthMap.has(month)) monthMap.set(month, []);
    monthMap.get(month)!.push(bet);
  }

  const monthly: MonthStats[] = [];
  for (const [month, bets] of [...monthMap.entries()].sort()) {
    const invested = bets.reduce((s, b) => s + b.win_amount + b.place_amount, 0);
    const returned = bets.reduce((s, b) => s + b.win_return, 0);
    const hits = bets.filter(b => b.is_win).length;
    monthly.push({
      month,
      bets: bets.length,
      hits,
      hitRate: bets.length > 0 ? hits / bets.length : 0,
      invested,
      returned,
      profit: returned - invested,
      roi: invested > 0 ? (returned / invested) * 100 : 0,
    });
  }

  // 全体集計
  const totalInvested = allBets.reduce((s, b) => s + b.win_amount + b.place_amount, 0);
  const totalReturned = allBets.reduce((s, b) => s + b.win_return, 0);
  const totalHits = allBets.filter(b => b.is_win).length;

  return NextResponse.json({
    preset,
    year,
    overall: {
      bets: allBets.length,
      hits: totalHits,
      hitRate: allBets.length > 0 ? totalHits / allBets.length : 0,
      invested: totalInvested,
      returned: totalReturned,
      profit: totalReturned - totalInvested,
      roi: totalInvested > 0 ? (totalReturned / totalInvested) * 100 : 0,
      avgOdds: allBets.length > 0
        ? allBets.reduce((s, b) => s + b.odds, 0) / allBets.length
        : 0,
    },
    monthly,
    bets: allBets.map(b => ({
      date: b.date,
      race_id: b.race_id,
      umaban: b.umaban,
      horse_name: b.horse_name,
      odds: b.odds,
      win_amount: b.win_amount,
      strength: b.strength,
      win_vb_gap: b.win_vb_gap,
      win_ev: b.win_ev,
      finish_position: b.finish_position,
      is_win: b.is_win,
      win_return: b.win_return,
    })),
    backtest: preset === 'intersection' ? {
      expectedRoi: 310.7,
      expectedHitRate: 19.6,
      annualBets: 46,
      monthlyBets: 3.8,
    } : null,
  });
}
