/**
 * 馬メモAPI
 * GET /api/horse-memo?horseId=XXXXXXX
 * POST /api/horse-memo { horseId, memo }
 */

import { NextRequest, NextResponse } from 'next/server';
import { getHorseMemo, updateHorseMemo } from '@/lib/data/horse-memo';

export const runtime = 'nodejs';

/**
 * メモ取得
 */
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const horseId = searchParams.get('horseId');

    if (!horseId) {
      return NextResponse.json(
        { error: 'horseId は必須です' },
        { status: 400 }
      );
    }

    const memo = await getHorseMemo(horseId);
    return NextResponse.json({ memo });
  } catch (error) {
    console.error('GET /api/horse-memo error:', error);
    return NextResponse.json(
      { error: 'Internal Server Error' },
      { status: 500 }
    );
  }
}

/**
 * メモ保存
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { horseId, memo } = body;

    if (!horseId) {
      return NextResponse.json(
        { error: 'horseId は必須です' },
        { status: 400 }
      );
    }

    const success = await updateHorseMemo(horseId, memo || '');
    
    if (!success) {
      return NextResponse.json(
        { error: '馬プロファイルが見つかりません' },
        { status: 404 }
      );
    }

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('POST /api/horse-memo error:', error);
    return NextResponse.json(
      { error: 'Internal Server Error' },
      { status: 500 }
    );
  }
}
