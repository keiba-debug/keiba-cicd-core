/**
 * 調教分析データ取得・更新API
 * GET: training_analysis.json 読み込み（フォールバック: trainer_patterns.json）
 * POST: trainer_comments.json のコメント更新
 */

import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';
import { DATA3_ROOT, AI_DATA_PATH } from '@/lib/config';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

// 新形式 (training_analysis.py)
const TRAINING_ANALYSIS_PATH = path.join(
  DATA3_ROOT,
  'analysis',
  'training_analysis.json'
);

// 旧形式 (trainer_patterns.py) - フォールバック用
const TRAINER_PATTERNS_PATH = path.join(
  DATA3_ROOT,
  'analysis',
  'trainer_patterns.json'
);

const TRAINER_COMMENTS_PATH = path.join(
  AI_DATA_PATH,
  'trainer_comments.json'
);

interface TrainerEntry {
  name: string;
  jvn_code: string;
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
    conditions: Record<string, unknown>;
    stats: {
      win_rate: number;
      top3_rate: number;
      top5_rate: number;
      avg_finish: number;
      sample_size: number;
      confidence: string;
      lift: number;
    };
  }>;
  all_patterns: Record<string, Record<string, unknown>>;
  comment: string;
}

export async function GET(_request: NextRequest) {
  try {
    // training_analysis.json を優先、なければ trainer_patterns.json
    let filePath = TRAINING_ANALYSIS_PATH;
    try {
      await fs.access(TRAINING_ANALYSIS_PATH);
    } catch {
      try {
        await fs.access(TRAINER_PATTERNS_PATH);
        filePath = TRAINER_PATTERNS_PATH;
      } catch {
        return NextResponse.json(
          {
            error: 'not_found',
            message: '調教分析データがありません。管理画面から「調教分析」を実行してください。',
          },
          { status: 404 }
        );
      }
    }

    const content = await fs.readFile(filePath, 'utf-8');
    const data = JSON.parse(content);

    // コメントをマージ
    let comments: Record<string, string> = {};
    try {
      const commentsContent = await fs.readFile(TRAINER_COMMENTS_PATH, 'utf-8');
      comments = JSON.parse(commentsContent);
    } catch {
      // コメントファイルなし
    }

    // trainersにコメントをマージ
    const trainers = data.trainers || {};
    for (const [code, trainer] of Object.entries(trainers)) {
      const t = trainer as TrainerEntry;
      if (comments[code] && !t.comment) {
        t.comment = comments[code];
      }
    }

    // サマリー計算
    const entries = Object.values(trainers) as TrainerEntry[];
    const withPatterns = entries.filter(
      (t) => t.best_patterns && t.best_patterns.length > 0
    );

    const totalTop3 = entries.reduce(
      (sum, t) => sum + (t.overall_stats?.top3_rate || 0),
      0
    );

    const topTrainers = [...entries]
      .filter((t) => (t.overall_stats?.sample_size || t.total_runners) >= 20)
      .sort((a, b) => (b.overall_stats?.top3_rate || 0) - (a.overall_stats?.top3_rate || 0))
      .slice(0, 10)
      .map((t) => ({
        name: t.name,
        tozai: t.tozai || '',
        top3_rate: t.overall_stats.top3_rate,
        win_rate: t.overall_stats.win_rate,
        sample_size: t.overall_stats.sample_size || t.total_runners,
        patternCount: t.best_patterns?.length || 0,
      }));

    return NextResponse.json({
      ...data,
      summary: {
        totalRecords: data.metadata?.total_records || 0,
        totalTrainers: entries.length,
        trainersWithPatterns: withPatterns.length,
        avgTop3Rate:
          entries.length > 0 ? totalTop3 / entries.length : 0,
        topTrainers,
      },
    });
  } catch (error) {
    console.error('Training analysis API error:', error);
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

    let comments: Record<string, string> = {};
    try {
      const content = await fs.readFile(TRAINER_COMMENTS_PATH, 'utf-8');
      comments = JSON.parse(content);
    } catch {
      // ファイルが存在しない場合は空で開始
    }

    if (comment) {
      comments[jvnCode] = comment;
    } else {
      delete comments[jvnCode];
    }

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
