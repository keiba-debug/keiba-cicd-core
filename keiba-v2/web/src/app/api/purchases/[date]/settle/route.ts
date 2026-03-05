/**
 * 購入結果自動反映API
 *
 * POST /api/purchases/{date}/settle
 *
 * race_*.json の finish_position を参照し、
 * 購入レコードの status / payout を自動更新する。
 */

import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';
import { AI_DATA_PATH, DATA3_ROOT } from '@/lib/config';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

interface PurchaseItem {
  id: string;
  race_id: string;
  race_name: string;
  venue: string;
  race_number: number;
  bet_type: string;
  selection: string;
  amount: number;
  odds: number | null;
  expected_value: number | null;
  status: 'planned' | 'purchased' | 'result_win' | 'result_lose';
  payout: number;
  confidence: '高' | '中' | '低';
  reason: string;
  created_at: string;
  updated_at: string;
}

interface DailyPurchases {
  date: string;
  budget: number;
  total_planned: number;
  total_purchased: number;
  total_payout: number;
  items: PurchaseItem[];
  updated_at: string;
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ date: string }> }
) {
  try {
    const { date } = await params;

    // 購入データを読み込む
    const purchasePath = path.join(AI_DATA_PATH, 'purchases', `${date}.json`);
    let purchases: DailyPurchases;
    try {
      const content = await fs.readFile(purchasePath, 'utf-8');
      purchases = JSON.parse(content);
    } catch {
      return NextResponse.json(
        { error: '購入データがありません' },
        { status: 404 }
      );
    }

    if (purchases.items.length === 0) {
      return NextResponse.json({ message: '購入レコードが空です', settled: 0 });
    }

    // 日付パース (YYYY-MM-DD)
    const [y, m, d] = date.split('-');
    const racesDir = path.join(DATA3_ROOT, 'races', y, m, d);

    // レース結果をキャッシュ（race_id → { umaban → entry }）
    const raceResults = new Map<string, Map<number, { finish_position: number; odds: number; num_runners: number }>>();

    const loadRaceResult = async (raceId: string) => {
      if (raceResults.has(raceId)) return raceResults.get(raceId)!;

      const raceFile = path.join(racesDir, `race_${raceId}.json`);
      try {
        const content = await fs.readFile(raceFile, 'utf-8');
        const raceData = JSON.parse(content);
        const entryMap = new Map<number, { finish_position: number; odds: number; num_runners: number }>();
        const numRunners = raceData.num_runners ?? raceData.entries?.length ?? 18;

        for (const entry of raceData.entries || []) {
          if (entry.umaban != null) {
            entryMap.set(entry.umaban, {
              finish_position: entry.finish_position ?? 0,
              odds: entry.odds ?? 0,
              num_runners: numRunners,
            });
          }
        }
        raceResults.set(raceId, entryMap);
        return entryMap;
      } catch {
        // レースファイルなし
        raceResults.set(raceId, new Map());
        return new Map<number, { finish_position: number; odds: number; num_runners: number }>();
      }
    };

    let settledCount = 0;
    let winCount = 0;
    let totalPayout = 0;

    for (const item of purchases.items) {
      // すでに結果確定済みならスキップ
      if (item.status === 'result_win' || item.status === 'result_lose') continue;
      // planned はまだ購入してないのでスキップ
      if (item.status === 'planned') continue;

      // 馬番を selection から取得
      const umaban = parseInt(item.selection.split('-')[0]);
      if (isNaN(umaban)) continue;

      const entryMap = await loadRaceResult(item.race_id);
      if (entryMap.size === 0) continue; // レース結果なし

      const result = entryMap.get(umaban);
      if (!result || result.finish_position === 0) continue; // 出走取消等

      const fp = result.finish_position;

      if (item.bet_type === '単勝') {
        if (fp === 1) {
          // 的中
          const payoutOdds = result.odds || item.odds || 1;
          const payout = Math.floor(item.amount * payoutOdds / 100) * 100; // 10円単位に丸め
          item.status = 'result_win';
          item.payout = payout;
          winCount++;
          totalPayout += payout;
        } else {
          item.status = 'result_lose';
          item.payout = 0;
        }
        item.updated_at = new Date().toISOString();
        settledCount++;
      } else if (item.bet_type === '複勝') {
        const placeLimit = result.num_runners >= 8 ? 3 : result.num_runners >= 5 ? 2 : 1;
        if (fp <= placeLimit) {
          // 複勝的中 — 正確な配当はrace_*.jsonにないので概算（オッズの1/3程度）
          const placeOdds = (item.odds || 1) * 0.35;
          const payout = Math.floor(item.amount * placeOdds / 100) * 100;
          item.status = 'result_win';
          item.payout = Math.max(payout, item.amount); // 最低でも元返し
          winCount++;
          totalPayout += item.payout;
        } else {
          item.status = 'result_lose';
          item.payout = 0;
        }
        item.updated_at = new Date().toISOString();
        settledCount++;
      }
    }

    // 合計を再計算
    purchases.total_purchased = purchases.items
      .filter(i => ['purchased', 'result_win', 'result_lose'].includes(i.status))
      .reduce((sum, i) => sum + i.amount, 0);
    purchases.total_payout = purchases.items
      .filter(i => i.status === 'result_win')
      .reduce((sum, i) => sum + i.payout, 0);
    purchases.total_planned = purchases.items
      .filter(i => i.status === 'planned')
      .reduce((sum, i) => sum + i.amount, 0);
    purchases.updated_at = new Date().toISOString();

    // 保存
    await fs.writeFile(purchasePath, JSON.stringify(purchases, null, 2), 'utf-8');

    return NextResponse.json({
      success: true,
      settled: settledCount,
      wins: winCount,
      totalPayout,
      totalInvested: purchases.total_purchased,
      profit: purchases.total_payout - purchases.total_purchased,
    });
  } catch (error) {
    console.error('[SettleAPI] Error:', error);
    return NextResponse.json(
      { error: '結果反映に失敗しました', details: String(error) },
      { status: 500 }
    );
  }
}
