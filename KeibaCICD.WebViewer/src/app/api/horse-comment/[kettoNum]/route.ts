/**
 * 馬コメント API
 * 
 * GET: 馬コメントを取得
 * PUT: 馬コメントを保存（TARGET UMA_COMに書き込み）
 */

import { NextRequest, NextResponse } from 'next/server';
import { getHorseComment } from '@/lib/data/target-comment-reader';
import { writeHorseComment } from '@/lib/data/target-comment-writer';

interface RouteParams {
  params: Promise<{
    kettoNum: string;
  }>;
}

/**
 * GET /api/horse-comment/[kettoNum]
 * 馬コメントを取得
 */
export async function GET(
  request: NextRequest,
  { params }: RouteParams
) {
  try {
    const { kettoNum } = await params;
    
    if (!kettoNum || kettoNum.length !== 10) {
      return NextResponse.json(
        { error: '無効な馬ID（10桁のkettoNumが必要です）' },
        { status: 400 }
      );
    }
    
    const comment = getHorseComment(kettoNum);
    
    return NextResponse.json({
      kettoNum,
      comment: comment?.comment || '',
      source: comment?.source || null,
    });
  } catch (error) {
    console.error('[HorseComment API] GET error:', error);
    return NextResponse.json(
      { error: 'コメント取得に失敗しました' },
      { status: 500 }
    );
  }
}

/**
 * PUT /api/horse-comment/[kettoNum]
 * 馬コメントを保存
 */
export async function PUT(
  request: NextRequest,
  { params }: RouteParams
) {
  try {
    const { kettoNum } = await params;
    
    if (!kettoNum || kettoNum.length !== 10) {
      return NextResponse.json(
        { error: '無効な馬ID（10桁のkettoNumが必要です）' },
        { status: 400 }
      );
    }
    
    const body = await request.json();
    const { comment } = body;
    
    if (typeof comment !== 'string') {
      return NextResponse.json(
        { error: 'commentフィールドが必要です' },
        { status: 400 }
      );
    }
    
    // TARGET UMA_COMに書き込み
    const result = writeHorseComment(kettoNum, comment);
    
    if (!result.success) {
      return NextResponse.json(
        { error: result.message },
        { status: 500 }
      );
    }
    
    return NextResponse.json({
      success: true,
      message: result.message,
      kettoNum,
    });
  } catch (error) {
    console.error('[HorseComment API] PUT error:', error);
    return NextResponse.json(
      { error: 'コメント保存に失敗しました' },
      { status: 500 }
    );
  }
}
