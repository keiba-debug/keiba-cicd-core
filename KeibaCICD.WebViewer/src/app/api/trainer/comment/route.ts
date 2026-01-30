import { NextRequest, NextResponse } from 'next/server';
import { readFile } from 'fs/promises';
import { join } from 'path';
import { KEIBA_DATA_ROOT_DIR } from '@/lib/config';

/**
 * 調教師コメント取得API
 * 
 * GET: /api/trainer/comment?trainer_id=ﾅ032
 * 
 * Returns: { comment: string | null, name: string | null, tozai: string | null }
 */

const TARGET_DATA_DIR = join(KEIBA_DATA_ROOT_DIR, 'target');

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const trainerId = searchParams.get('trainer_id');
    
    if (!trainerId) {
      return NextResponse.json({ error: 'trainer_idが必要です' }, { status: 400 });
    }
    
    // trainer_id_index.jsonを読み込む
    const indexPath = join(TARGET_DATA_DIR, 'trainer_id_index.json');
    
    try {
      const indexData = await readFile(indexPath, 'utf-8');
      const index = JSON.parse(indexData);
      
      const trainerInfo = index[trainerId];
      
      if (!trainerInfo) {
        // 調教師情報が見つからない場合は空のレスポンスを返す（エラーではない）
        return NextResponse.json({ 
          comment: null, 
          name: null, 
          tozai: null 
        });
      }
      
      // コメントから文字化け文字を除去
      let comment = trainerInfo.comment || null;
      if (comment && typeof comment === 'string') {
        comment = comment.replace(/\ufffd/g, '').replace(/�/g, '');
        comment = comment.replace(/�[A-Za-z0-9@]/g, '');
        comment = comment.trim();
        
        // 数字のみ、または短すぎるコメント（3文字以下）は無効とみなす
        if (comment === '' || /^\d+$/.test(comment) || comment.length <= 3) {
          comment = null;
        }
      } else if (typeof comment === 'number') {
        // 数値型の場合はnullにする（誤って数値が入っている場合）
        comment = null;
      }
      
      return NextResponse.json({
        comment: comment,
        name: trainerInfo.name || null,
        tozai: trainerInfo.tozai || null,
      });
    } catch (fileError: any) {
      if (fileError.code === 'ENOENT') {
        // ファイルが見つからない場合は空のレスポンスを返す（エラーではない）
        return NextResponse.json({ 
          comment: null, 
          name: null, 
          tozai: null
        });
      }
      console.error('ファイル読み込みエラー:', fileError);
      throw fileError;
    }
  } catch (error: any) {
    console.error('調教師コメント取得エラー:', error);
    return NextResponse.json(
      { 
        error: '調教師コメントの取得に失敗しました', 
        details: error.message
      },
      { status: 500 }
    );
  }
}
