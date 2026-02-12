/**
 * 調教データデバッグ用API
 * GET /api/debug/training?date=YYYYMMDD
 */

import { NextRequest, NextResponse } from 'next/server';
import { 
  getTrainingDataForDate, 
  isTrainingDataAvailable,
  getAvailableTrainingDates 
} from '@/lib/data/target-training-reader';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const dateStr = searchParams.get('date');
  const action = searchParams.get('action');
  
  // 利用可能かチェック
  if (!isTrainingDataAvailable()) {
    return NextResponse.json({ 
      error: 'Training data not available',
      path: process.env.JV_DATA_ROOT || 'Y:/'
    }, { status: 500 });
  }
  
  // 利用可能な日付一覧
  if (action === 'dates') {
    const year = parseInt(searchParams.get('year') || '2026', 10);
    const month = parseInt(searchParams.get('month') || '1', 10);
    const dates = getAvailableTrainingDates(year, month);
    return NextResponse.json({ year, month, dates });
  }
  
  // 指定日のデータを取得
  if (!dateStr || dateStr.length !== 8) {
    return NextResponse.json({ 
      error: 'Invalid date format. Use YYYYMMDD.',
      example: '/api/debug/training?date=20260123'
    }, { status: 400 });
  }
  
  try {
    const records = await getTrainingDataForDate(dateStr);
    
    // 統計情報
    const stats = {
      total: records.length,
      sakamichi: records.filter(r => r.recordType === 'sakamichi').length,
      course: records.filter(r => r.recordType === 'course').length,
      miho: records.filter(r => r.location === '美浦').length,
      ritto: records.filter(r => r.location === '栗東').length,
    };
    
    // サンプルデータ（最初の20件）
    const samples = records.slice(0, 20);
    
    return NextResponse.json({
      date: dateStr,
      stats,
      samples,
    });
  } catch (error) {
    return NextResponse.json({ 
      error: 'Failed to read training data',
      message: error instanceof Error ? error.message : String(error)
    }, { status: 500 });
  }
}
