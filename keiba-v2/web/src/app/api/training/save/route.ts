/**
 * 調教サマリー保存API
 * 
 * POST /api/training/save?date=YYYYMMDD
 * 
 * TARGETのCK_DATAから調教サマリーを生成し、
 * data3/races/{year}/{month}/{day}/temp/training_summary.json
 * として保存
 */

import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import {
  generateTrainingSummary,
  isTrainingDataAvailable,
  getTrainingDateRanges,
  TrainingSummary,
} from '@/lib/data/target-training-reader';
import { DATA3_ROOT } from '@/lib/config';

export async function POST(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const dateStr = searchParams.get('date');

  // 利用可能かチェック
  if (!isTrainingDataAvailable()) {
    return NextResponse.json({
      error: 'Training data not available',
      path: process.env.JV_DATA_ROOT || 'C:/TFJV',
    }, { status: 500 });
  }

  // 日付パラメータ検証
  if (!dateStr || dateStr.length !== 8) {
    return NextResponse.json({
      error: 'Invalid date format. Use YYYYMMDD.',
      example: '/api/training/save?date=20260125',
    }, { status: 400 });
  }

  try {
    console.log(`[TrainingSaveAPI] Generating and saving summary for date: ${dateStr}`);
    
    // 日付範囲を計算
    const ranges = getTrainingDateRanges(dateStr);
    
    // サマリー生成
    const summaries = await generateTrainingSummary(dateStr);
    console.log(`[TrainingSaveAPI] Generated ${summaries.length} summaries`);

    // 保存先パスを構築
    const year = dateStr.substring(0, 4);
    const month = dateStr.substring(4, 6);
    const day = dateStr.substring(6, 8);
    const targetDir = path.join(DATA3_ROOT, 'races', year, month, day, 'temp');
    const targetFile = path.join(targetDir, 'training_summary.json');

    // ディレクトリがなければ作成
    if (!fs.existsSync(targetDir)) {
      fs.mkdirSync(targetDir, { recursive: true });
    }

    // 馬名をキーにしたマップ形式で保存（検索効率化）
    const summaryMap: Record<string, TrainingSummary> = {};
    for (const s of summaries) {
      summaryMap[s.horseName] = s;
    }

    const outputData = {
      meta: {
        date: dateStr,
        created_at: new Date().toISOString(),
        ranges,
        count: summaries.length,
      },
      summaries: summaryMap,
    };

    // JSON保存
    fs.writeFileSync(targetFile, JSON.stringify(outputData, null, 2), 'utf-8');
    console.log(`[TrainingSaveAPI] Saved to: ${targetFile}`);

    return NextResponse.json({
      success: true,
      date: dateStr,
      path: targetFile,
      count: summaries.length,
    });
  } catch (error) {
    console.error('[TrainingSaveAPI] Error:', error);
    return NextResponse.json({
      error: 'Failed to save training summary',
      message: error instanceof Error ? error.message : String(error),
    }, { status: 500 });
  }
}

export async function GET(request: NextRequest) {
  // GETでも同じ処理を実行（便宜上）
  return POST(request);
}
