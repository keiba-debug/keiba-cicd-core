/**
 * 調教師パターン分析データ取得・更新API
 * GET: trainer_patterns.json 読み込み
 * POST: trainer_id_index.json のコメント更新
 */

import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';
import { DATA3_ROOT, AI_DATA_PATH } from '@/lib/config';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const TRAINER_PATTERNS_PATH = path.join(
  DATA3_ROOT,
  'analysis',
  'trainer_patterns.json'
);

// 調教師コメントはユーザーデータとして保存
const TRAINER_COMMENTS_PATH = path.join(
  AI_DATA_PATH,
  'trainer_comments.json'
);

interface TrainerEntry {
  name: string;
  tozai: string;
  total_runners: number;
  overall_stats: {
    win_rate: number;
    top3_rate: number;
    top5_rate: number;
    avg_finish: number;
    sample_size: number;
  };
  best_patterns: Array<{
    description: string;
    human_label?: string | null;
    stats: { top3_rate: number; sample_size: number };
  }>;
}

export async function GET(_request: NextRequest) {
  try {
    try {
      await fs.access(TRAINER_PATTERNS_PATH);
    } catch {
      return NextResponse.json(
        {
          error: 'not_found',
          message: '調教師パターンデータがありません。管理画面から「調教師パターン分析」を実行してください。',
        },
        { status: 404 }
      );
    }

    const content = await fs.readFile(TRAINER_PATTERNS_PATH, 'utf-8');
    const data = JSON.parse(content);

    // サマリー計算
    const trainers = data.trainers || {};
    const entries = Object.values(trainers) as TrainerEntry[];
    const withPatterns = entries.filter(
      (t) => t.best_patterns && t.best_patterns.length > 0
    );

    const totalTop3 = entries.reduce(
      (sum, t) => sum + (t.overall_stats?.top3_rate || 0),
      0
    );

    // 好走率上位10名
    const topTrainers = [...entries]
      .filter((t) => t.overall_stats?.sample_size >= 20)
      .sort((a, b) => (b.overall_stats?.top3_rate || 0) - (a.overall_stats?.top3_rate || 0))
      .slice(0, 10)
      .map((t) => ({
        name: t.name,
        tozai: t.tozai,
        top3_rate: t.overall_stats.top3_rate,
        win_rate: t.overall_stats.win_rate,
        sample_size: t.overall_stats.sample_size,
        patternCount: t.best_patterns?.length || 0,
      }));

    return NextResponse.json({
      ...data,
      summary: {
        totalTrainers: entries.length,
        trainersWithPatterns: withPatterns.length,
        avgTop3Rate:
          entries.length > 0 ? totalTop3 / entries.length : 0,
        topTrainers,
      },
    });
  } catch (error) {
    console.error('Trainer patterns API error:', error);
    return NextResponse.json(
      {
        error: 'server_error',
        message:
          error instanceof Error
            ? error.message
            : 'サーバーエラーが発生しました',
      },
      { status: 500 }
    );
  }
}

/**
 * 調教師コメント更新（data3/userdata/trainer_comments.json に保存）
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { jvnCode, comment } = body as { jvnCode: string; comment: string };

    if (!jvnCode) {
      return NextResponse.json(
        { error: 'jvnCode は必須です' },
        { status: 400 }
      );
    }

    // trainer_comments.json 読み込み（なければ空オブジェクト）
    let comments: Record<string, string> = {};
    try {
      const content = await fs.readFile(TRAINER_COMMENTS_PATH, 'utf-8');
      comments = JSON.parse(content);
    } catch {
      // ファイルが存在しない場合は空で開始
    }

    // コメント更新
    if (comment) {
      comments[jvnCode] = comment;
    } else {
      delete comments[jvnCode];
    }

    // userdata ディレクトリ確保 & 保存
    await fs.mkdir(path.dirname(TRAINER_COMMENTS_PATH), { recursive: true });
    await fs.writeFile(TRAINER_COMMENTS_PATH, JSON.stringify(comments, null, 2), 'utf-8');

    return NextResponse.json({ success: true, jvnCode });
  } catch (error) {
    console.error('Trainer comment update error:', error);
    return NextResponse.json(
      {
        error: 'server_error',
        message: error instanceof Error ? error.message : 'サーバーエラーが発生しました',
      },
      { status: 500 }
    );
  }
}
