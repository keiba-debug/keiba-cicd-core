/**
 * 調教サマリーAPI
 * 
 * GET /api/training/summary?date=YYYYMMDD
 * - date: レース開催日（基準日）
 * - format: json | tsv (デフォルト: json)
 * 
 * TARGETのCK_DATAから直接調教データを読み込み、
 * 馬ごとの調教サマリー（ラップ分類、タイム分類、詳細）を生成
 */

import { NextRequest, NextResponse } from 'next/server';
import {
  generateTrainingSummary,
  summaryToTsv,
  isTrainingDataAvailable,
  getTrainingDateRanges,
} from '@/lib/data/target-training-reader';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const dateStr = searchParams.get('date');
  const format = searchParams.get('format') || 'json';

  // 利用可能かチェック
  if (!isTrainingDataAvailable()) {
    return NextResponse.json({
      error: 'Training data not available',
      path: process.env.JV_DATA_ROOT_DIR || 'Y:/',
    }, { status: 500 });
  }

  // 日付パラメータ検証
  if (!dateStr || dateStr.length !== 8) {
    return NextResponse.json({
      error: 'Invalid date format. Use YYYYMMDD.',
      example: '/api/training/summary?date=20260125',
    }, { status: 400 });
  }

  try {
    console.log(`[TrainingSummaryAPI] Generating summary for date: ${dateStr}`);
    
    // 日付範囲を計算
    const ranges = getTrainingDateRanges(dateStr);
    console.log(`[TrainingSummaryAPI] Date ranges:`, ranges);

    // サマリー生成
    const summaries = await generateTrainingSummary(dateStr);
    console.log(`[TrainingSummaryAPI] Generated ${summaries.length} summaries`);

    // TSV形式の場合
    if (format === 'tsv') {
      const tsv = summaryToTsv(summaries);
      return new NextResponse(tsv, {
        headers: {
          'Content-Type': 'text/tab-separated-values; charset=shift_jis',
          'Content-Disposition': `attachment; filename="training_${dateStr}.txt"`,
        },
      });
    }

    // JSON形式
    return NextResponse.json({
      date: dateStr,
      ranges,
      count: summaries.length,
      summaries,
    });
  } catch (error) {
    console.error('[TrainingSummaryAPI] Error:', error);
    return NextResponse.json({
      error: 'Failed to generate training summary',
      message: error instanceof Error ? error.message : String(error),
    }, { status: 500 });
  }
}
