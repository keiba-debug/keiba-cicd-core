/**
 * レイティング基準値取得API
 */

import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

// レイティング基準値ファイルのパス
const RATING_STANDARDS_PATH = path.join(
  process.cwd(),
  '..',
  'KeibaCICD.keibabook',
  'data',
  'rating_standards.json'
);

export async function GET(request: NextRequest) {
  try {
    // ファイル存在チェック
    try {
      await fs.access(RATING_STANDARDS_PATH);
    } catch {
      return NextResponse.json(
        { 
          error: 'not_found',
          message: 'レイティング基準値データがありません。管理画面から「レイティング基準値算出」を実行してください。'
        },
        { status: 404 }
      );
    }

    // ファイル読み込み
    const content = await fs.readFile(RATING_STANDARDS_PATH, 'utf-8');
    const data = JSON.parse(content);

    // サマリー情報を追加
    const byGrade = data.by_grade || {};
    const summary = {
      totalGrades: Object.keys(byGrade).length,
      totalRaces: data.metadata?.total_races || 0,
      years: data.metadata?.years || 'unknown',
    };

    return NextResponse.json({
      ...data,
      summary,
    });

  } catch (error) {
    console.error('Rating standards API error:', error);
    return NextResponse.json(
      { 
        error: 'server_error',
        message: error instanceof Error ? error.message : 'サーバーエラーが発生しました'
      },
      { status: 500 }
    );
  }
}
