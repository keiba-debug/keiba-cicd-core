/**
 * TARGETコメント保存API
 * 
 * POST: コメントを保存
 * - レースコメント（予想/結果）
 * - 馬コメント
 */

import { NextRequest, NextResponse } from 'next/server';
import { writeRaceComment, writeHorseComment, writeRaceCommentsBatch } from '@/lib/data/target-comment-writer';

/** レースコメント保存リクエスト */
interface RaceCommentRequest {
  type: 'race';
  commentType: 'prediction' | 'result';
  venue: string;
  year: string;
  kai: number;
  nichi: number;
  raceNumber: number;
  horseNumber: number;
  comment: string;
}

/** 馬コメント保存リクエスト */
interface HorseCommentRequest {
  type: 'horse';
  kettoNum: string;
  comment: string;
}

/** レースコメント一括保存リクエスト */
interface RaceCommentsBatchRequest {
  type: 'race_batch';
  commentType: 'prediction' | 'result';
  venue: string;
  year: string;
  kai: number;
  nichi: number;
  raceNumber: number;
  comments: Array<{ horseNumber: number; comment: string }>;
}

type CommentRequest = RaceCommentRequest | HorseCommentRequest | RaceCommentsBatchRequest;

export async function POST(request: NextRequest) {
  try {
    const body: CommentRequest = await request.json();
    
    if (body.type === 'race') {
      const { commentType, venue, year, kai, nichi, raceNumber, horseNumber, comment } = body;
      
      // バリデーション
      if (!venue || !year || !kai || !nichi || !raceNumber || !horseNumber) {
        return NextResponse.json(
          { success: false, message: '必須パラメータが不足しています' },
          { status: 400 }
        );
      }
      
      const result = writeRaceComment(
        commentType,
        venue,
        year,
        kai,
        nichi,
        raceNumber,
        horseNumber,
        comment
      );
      
      return NextResponse.json(result, { status: result.success ? 200 : 500 });
    }
    
    if (body.type === 'horse') {
      const { kettoNum, comment } = body;
      
      if (!kettoNum) {
        return NextResponse.json(
          { success: false, message: '馬ID（kettoNum）が必要です' },
          { status: 400 }
        );
      }
      
      const result = writeHorseComment(kettoNum, comment);
      return NextResponse.json(result, { status: result.success ? 200 : 500 });
    }
    
    if (body.type === 'race_batch') {
      const { commentType, venue, year, kai, nichi, raceNumber, comments } = body;
      
      if (!venue || !year || !kai || !nichi || !raceNumber || !comments) {
        return NextResponse.json(
          { success: false, message: '必須パラメータが不足しています' },
          { status: 400 }
        );
      }
      
      const result = writeRaceCommentsBatch(
        commentType,
        venue,
        year,
        kai,
        nichi,
        raceNumber,
        comments
      );
      
      return NextResponse.json(result, { status: result.success ? 200 : 500 });
    }
    
    return NextResponse.json(
      { success: false, message: '不明なリクエストタイプです' },
      { status: 400 }
    );
  } catch (error) {
    console.error('[API] target-comments error:', error);
    return NextResponse.json(
      { success: false, message: `サーバーエラー: ${error instanceof Error ? error.message : String(error)}` },
      { status: 500 }
    );
  }
}
