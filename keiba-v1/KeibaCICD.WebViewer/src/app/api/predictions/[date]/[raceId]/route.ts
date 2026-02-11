/**
 * 予想API
 * 
 * GET /api/predictions/{date}/{raceId} - 予想取得
 * POST /api/predictions/{date}/{raceId} - 予想保存
 * DELETE /api/predictions/{date}/{raceId} - 予想削除
 */

import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

interface Prediction {
  race_id: string;
  race_date: string;
  race_name: string;
  venue: string;
  race_number: number;
  created_at: string;
  updated_at: string;
  marks: { [horseNumber: string]: string };  // ◎○▲△×
  scores: { [horseNumber: string]: number }; // 0-100
  comment: string;
  confidence: '高' | '中' | '低';
  status: 'draft' | 'confirmed';
}

// データディレクトリのパス
const DATA_DIR = path.join(
  process.cwd(),
  '..',
  'KeibaCICD.AI',
  'data',
  'predictions'
);

/**
 * 日付ディレクトリのパスを取得
 */
function getDateDir(date: string): string {
  return path.join(DATA_DIR, date);
}

/**
 * ファイルパスを取得
 */
function getFilePath(date: string, raceId: string): string {
  return path.join(getDateDir(date), `${raceId}.json`);
}

/**
 * 予想を読み込む
 */
async function loadPrediction(date: string, raceId: string): Promise<Prediction | null> {
  const filePath = getFilePath(date, raceId);
  
  try {
    const content = await fs.readFile(filePath, 'utf-8');
    return JSON.parse(content);
  } catch (error) {
    return null;
  }
}

/**
 * 予想を保存
 */
async function savePrediction(data: Prediction): Promise<void> {
  const filePath = getFilePath(data.race_date, data.race_id);
  
  // ディレクトリが存在しない場合は作成
  await fs.mkdir(getDateDir(data.race_date), { recursive: true });
  
  data.updated_at = new Date().toISOString();
  
  await fs.writeFile(filePath, JSON.stringify(data, null, 2), 'utf-8');
}

/**
 * GET: 予想を取得
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ date: string; raceId: string }> }
) {
  try {
    const { date, raceId } = await params;
    
    const prediction = await loadPrediction(date, raceId);
    
    if (!prediction) {
      return NextResponse.json({
        exists: false,
        prediction: null,
      });
    }
    
    return NextResponse.json({
      exists: true,
      prediction,
    });
  } catch (error) {
    console.error('[PredictionsAPI] GET Error:', error);
    return NextResponse.json(
      { error: '予想の取得に失敗しました', message: String(error) },
      { status: 500 }
    );
  }
}

/**
 * POST: 予想を保存
 */
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ date: string; raceId: string }> }
) {
  try {
    const { date, raceId } = await params;
    const body = await request.json();
    
    const {
      race_name = '',
      venue = '',
      race_number = 0,
      marks = {},
      scores = {},
      comment = '',
      confidence = '中',
      status = 'draft',
    } = body;
    
    // 既存の予想を読み込む
    const existing = await loadPrediction(date, raceId);
    
    const prediction: Prediction = {
      race_id: raceId,
      race_date: date,
      race_name,
      venue,
      race_number,
      created_at: existing?.created_at || new Date().toISOString(),
      updated_at: new Date().toISOString(),
      marks,
      scores,
      comment,
      confidence,
      status,
    };
    
    await savePrediction(prediction);
    
    return NextResponse.json({
      success: true,
      prediction,
    });
  } catch (error) {
    console.error('[PredictionsAPI] POST Error:', error);
    return NextResponse.json(
      { error: '予想の保存に失敗しました', message: String(error) },
      { status: 500 }
    );
  }
}

/**
 * DELETE: 予想を削除
 */
export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ date: string; raceId: string }> }
) {
  try {
    const { date, raceId } = await params;
    const filePath = getFilePath(date, raceId);
    
    try {
      await fs.unlink(filePath);
    } catch (error) {
      // ファイルが存在しない場合は無視
    }
    
    return NextResponse.json({
      success: true,
    });
  } catch (error) {
    console.error('[PredictionsAPI] DELETE Error:', error);
    return NextResponse.json(
      { error: '予想の削除に失敗しました', message: String(error) },
      { status: 500 }
    );
  }
}
