/**
 * 管理画面用API: レース日付インデックス再構築
 * POST /api/admin/rebuild-index
 */

import { NextResponse } from 'next/server';
import { clearRaceDateIndex, buildRaceDateIndex, getAvailableDatesFromIndex } from '@/lib/data/race-date-index';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function POST() {
  try {
    console.log('[RebuildIndex API] Clearing and rebuilding race date index...');
    
    // キャッシュをクリア
    clearRaceDateIndex();
    
    // インデックスを再構築
    await buildRaceDateIndex();
    
    // 結果を確認
    const dates = getAvailableDatesFromIndex();
    
    return NextResponse.json({
      success: true,
      message: `インデックス再構築完了: ${dates.length}件の日付`,
      dates: dates.slice(0, 10), // 最新10件を返す
    });
  } catch (error) {
    console.error('[RebuildIndex API] Error:', error);
    return NextResponse.json(
      { error: 'インデックス再構築エラー', details: String(error) },
      { status: 500 }
    );
  }
}

export async function GET() {
  try {
    const dates = getAvailableDatesFromIndex();
    return NextResponse.json({
      count: dates.length,
      dates: dates.slice(0, 20), // 最新20件
    });
  } catch (error) {
    return NextResponse.json(
      { error: String(error) },
      { status: 500 }
    );
  }
}
