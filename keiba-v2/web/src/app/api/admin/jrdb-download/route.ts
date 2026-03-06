/**
 * 管理画面用API: JRDBデータダウンロード＆統合
 * POST /api/admin/jrdb-download
 *
 * 3段階パイプライン:
 *   1. SED/KYI/KAAの最新データをJRDBからダウンロード
 *   2. JRDBインデックス再構築 (build_jrdb_index)
 *   3. 対象日のrace JSONにJRDB指標を付与 (build_race_from_keibabook --force)
 *
 * SSE形式で進捗をストリーミング。
 */

import { spawn } from 'child_process';
import { ADMIN_CONFIG } from '@/lib/admin/config';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const JRDB_TYPES = ['SED', 'KYI', 'KAA'] as const;

function runPython(args: string[], send: (data: Record<string, unknown>) => void): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    const child = spawn(ADMIN_CONFIG.pythonPath, args, {
      cwd: ADMIN_CONFIG.v2Path,
      shell: true,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    });

    child.stdout?.on('data', (data: Buffer) => {
      const lines = data.toString('utf-8').split('\n').filter(Boolean);
      for (const line of lines) {
        send({ type: 'log', level: 'info', message: line.trim() });
      }
    });

    child.stderr?.on('data', (data: Buffer) => {
      const lines = data.toString('utf-8').split('\n').filter(Boolean);
      for (const line of lines) {
        send({ type: 'log', level: 'warning', message: line.trim() });
      }
    });

    child.on('close', (code: number | null) => {
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`exit code: ${code}`));
      }
    });

    child.on('error', (error: Error) => {
      reject(error);
    });
  });
}

export async function POST(request: Request) {
  // リクエストボディからdatesを取得（オプション）
  let dates: string[] = [];
  try {
    const body = await request.json();
    if (body.dates && Array.isArray(body.dates)) {
      dates = body.dates;
    } else if (body.date) {
      dates = [body.date];
    }
  } catch {
    // bodyなしの場合はダウンロード+index再構築のみ
  }

  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      let isClosed = false;

      const send = (data: Record<string, unknown>) => {
        if (isClosed) return;
        try {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(data)}\n\n`));
        } catch {
          isClosed = true;
        }
      };

      const startTime = Date.now();
      const totalSteps = 2 + (dates.length > 0 ? 1 : 0);
      let currentStep = 0;

      send({
        type: 'start',
        message: `JRDB データ統合開始 (${JRDB_TYPES.join('+')} DL → Index再構築${dates.length > 0 ? ` → Race JSON更新 ${dates.join(',')}` : ''})`,
      });

      try {
        // ── Step 1: JRDBダウンロード ──
        currentStep++;
        send({
          type: 'progress',
          current: currentStep,
          total: totalSteps,
          message: `[Step ${currentStep}/${totalSteps}] JRDB データダウンロード...`,
        });

        for (let i = 0; i < JRDB_TYPES.length; i++) {
          const jrdbType = JRDB_TYPES[i];
          const args = ['-m', 'jrdb.downloader', '--type', jrdbType, '--latest', '--latest-count', '20'];

          send({
            type: 'log',
            level: 'info',
            message: `  [${i + 1}/${JRDB_TYPES.length}] ${jrdbType} ダウンロード中...`,
          });

          await runPython(args, send);

          send({
            type: 'log',
            level: 'info',
            message: `  ${jrdbType} ダウンロード完了`,
          });
        }

        // ── Step 2: JRDB Index 再構築 ──
        currentStep++;
        send({
          type: 'progress',
          current: currentStep,
          total: totalSteps,
          message: `[Step ${currentStep}/${totalSteps}] JRDBインデックス再構築...`,
        });

        await runPython(['-m', 'builders.build_jrdb_index'], send);

        send({
          type: 'log',
          level: 'info',
          message: 'JRDBインデックス再構築 完了',
        });

        // ── Step 3: Race JSON 再構築（日付指定時のみ）──
        if (dates.length > 0) {
          currentStep++;
          send({
            type: 'progress',
            current: currentStep,
            total: totalSteps,
            message: `[Step ${currentStep}/${totalSteps}] Race JSON JRDB enrichment (${dates.join(', ')})...`,
          });

          for (const date of dates) {
            send({
              type: 'log',
              level: 'info',
              message: `  ${date} のRace JSONを再構築中...`,
            });

            await runPython(
              ['-m', 'builders.build_race_from_keibabook', '--date', date, '--force'],
              send,
            );

            send({
              type: 'log',
              level: 'info',
              message: `  ${date} Race JSON 更新完了`,
            });
          }
        }

        const duration = Date.now() - startTime;
        send({
          type: 'complete',
          success: true,
          message: `JRDB データ統合完了 (${(duration / 1000).toFixed(1)}秒)`,
        });
      } catch (err) {
        send({
          type: 'error',
          success: false,
          message: `JRDB 統合エラー: ${err instanceof Error ? err.message : String(err)}`,
        });
      } finally {
        isClosed = true;
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
