/**
 * 管理画面用API: training_summary.json 一括生成
 * POST /api/admin/batch-training-summary
 *
 * data3/races/ 配下の全レース日付をスキャンし、
 * training_summary.json が未生成の日付に対して CK_DATA から一括生成する。
 * SSE形式で進捗をストリーミング。
 */

import { NextRequest } from 'next/server';
import fs from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';
import { getTrainingSummaryMap, hasTrainingSummary } from '@/lib/data/training-summary-reader';
import { isTrainingDataAvailable } from '@/lib/data/target-training-reader';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

interface BatchRequest {
  startDate?: string; // YYYY-MM-DD（省略時は全日付）
  endDate?: string;   // YYYY-MM-DD（省略時は全日付）
  forceRegenerate?: boolean; // true: 既存ファイルも再生成
}

/**
 * レースディレクトリから全日付を取得（YYYY-MM-DD形式、降順）
 */
function getAllRaceDates(): string[] {
  const racesDir = path.join(DATA3_ROOT, 'races');
  const dates: string[] = [];

  try {
    const years = fs.readdirSync(racesDir).filter(d => /^\d{4}$/.test(d)).sort();
    for (const year of years) {
      const yearDir = path.join(racesDir, year);
      const months = fs.readdirSync(yearDir).filter(d => /^\d{2}$/.test(d)).sort();
      for (const month of months) {
        const monthDir = path.join(yearDir, month);
        const days = fs.readdirSync(monthDir).filter(d => /^\d{2}$/.test(d)).sort();
        for (const day of days) {
          dates.push(`${year}-${month}-${day}`);
        }
      }
    }
  } catch {
    // ディレクトリが存在しない場合は空
  }

  return dates.sort().reverse(); // 降順（新しい日付から）
}

export async function POST(request: NextRequest) {
  const body: BatchRequest = await request.json().catch(() => ({}));
  const { startDate, endDate, forceRegenerate = false } = body;

  // CK_DATA の有無をチェック
  if (!isTrainingDataAvailable()) {
    return new Response(
      JSON.stringify({ error: 'CK_DATA が利用できません（JRA-VAN調教データディレクトリが見つかりません）' }),
      { status: 400, headers: { 'Content-Type': 'application/json' } }
    );
  }

  // SSEストリーム
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      const send = (data: Record<string, unknown>) => {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(data)}\n\n`));
      };

      try {
        // 全日付を取得
        let dates = getAllRaceDates();

        // 日付範囲でフィルタ
        if (startDate) {
          dates = dates.filter(d => d >= startDate);
        }
        if (endDate) {
          dates = dates.filter(d => d <= endDate);
        }

        // 未生成の日付をフィルタ
        const targetDates = forceRegenerate
          ? dates
          : dates.filter(d => !hasTrainingSummary(d));

        send({
          type: 'start',
          totalDates: dates.length,
          targetDates: targetDates.length,
          skippedDates: dates.length - targetDates.length,
          message: `全${dates.length}日中、${targetDates.length}日を生成対象（${dates.length - targetDates.length}日はスキップ）`,
        });

        let generated = 0;
        let failed = 0;

        for (let i = 0; i < targetDates.length; i++) {
          const date = targetDates[i];
          send({
            type: 'progress',
            current: i + 1,
            total: targetDates.length,
            date,
            message: `[${i + 1}/${targetDates.length}] ${date} を生成中...`,
          });

          try {
            const summaryMap = await getTrainingSummaryMap(date);
            const count = Object.keys(summaryMap).length;

            if (count > 0) {
              generated++;
              send({
                type: 'log',
                level: 'info',
                date,
                message: `${date}: ${count}頭の調教サマリーを生成・保存`,
              });
            } else {
              send({
                type: 'log',
                level: 'warning',
                date,
                message: `${date}: 調教データなし（CK_DATAに該当期間のデータがない可能性）`,
              });
            }
          } catch (err) {
            failed++;
            send({
              type: 'log',
              level: 'error',
              date,
              message: `${date}: エラー — ${err instanceof Error ? err.message : String(err)}`,
            });
          }
        }

        send({
          type: 'complete',
          success: true,
          generated,
          failed,
          total: targetDates.length,
          message: `完了: ${generated}日生成、${failed}日エラー（${dates.length - targetDates.length}日はスキップ）`,
        });
      } catch (err) {
        send({
          type: 'error',
          success: false,
          message: `一括生成エラー: ${err instanceof Error ? err.message : String(err)}`,
        });
      } finally {
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      Connection: 'keep-alive',
    },
  });
}

/**
 * GET: 現在のtraining_summary生成状況を確認
 */
export async function GET() {
  try {
    const dates = getAllRaceDates();
    const generated = dates.filter(d => hasTrainingSummary(d));
    const missing = dates.filter(d => !hasTrainingSummary(d));

    return new Response(
      JSON.stringify({
        totalDates: dates.length,
        generatedCount: generated.length,
        missingCount: missing.length,
        missingDates: missing.slice(0, 20), // 最新20件
        ckDataAvailable: isTrainingDataAvailable(),
      }),
      { headers: { 'Content-Type': 'application/json' } }
    );
  } catch (err) {
    return new Response(
      JSON.stringify({ error: String(err) }),
      { status: 500, headers: { 'Content-Type': 'application/json' } }
    );
  }
}
