/**
 * 管理画面用API: JRDBデータダウンロード
 * POST /api/admin/jrdb-download
 *
 * SED/KYI/KAAの最新データをJRDBからダウンロード。
 * SSE形式で進捗をストリーミング。
 */

import { spawn } from 'child_process';
import { ADMIN_CONFIG } from '@/lib/admin/config';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const JRDB_TYPES = ['SED', 'KYI', 'KAA'] as const;

export async function POST() {
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

      send({
        type: 'start',
        message: `JRDB データダウンロード開始 (${JRDB_TYPES.join(', ')})`,
      });

      try {
        for (let i = 0; i < JRDB_TYPES.length; i++) {
          const jrdbType = JRDB_TYPES[i];
          const args = ['-m', 'jrdb.downloader', '--type', jrdbType, '--latest', '--latest-count', '20'];

          send({
            type: 'progress',
            current: i + 1,
            total: JRDB_TYPES.length,
            message: `[${i + 1}/${JRDB_TYPES.length}] ${jrdbType} ダウンロード中...`,
          });

          await new Promise<void>((resolve, reject) => {
            const child = spawn(ADMIN_CONFIG.pythonPath, args, {
              cwd: ADMIN_CONFIG.v2Path,
              shell: true,
              env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
            });

            child.stdout?.on('data', (data: Buffer) => {
              const lines = data.toString('utf-8').split('\n').filter(Boolean);
              for (const line of lines) {
                send({
                  type: 'log',
                  level: 'info',
                  message: line.trim(),
                });
              }
            });

            child.stderr?.on('data', (data: Buffer) => {
              const lines = data.toString('utf-8').split('\n').filter(Boolean);
              for (const line of lines) {
                send({
                  type: 'log',
                  level: 'warning',
                  message: line.trim(),
                });
              }
            });

            child.on('close', (code: number | null) => {
              if (code === 0) {
                send({
                  type: 'log',
                  level: 'info',
                  message: `${jrdbType} ダウンロード完了`,
                });
                resolve();
              } else {
                reject(new Error(`${jrdbType} ダウンロード失敗 (exit code: ${code})`));
              }
            });

            child.on('error', (error: Error) => {
              reject(error);
            });
          });
        }

        const duration = Date.now() - startTime;
        send({
          type: 'complete',
          success: true,
          message: `JRDB データダウンロード完了 (${(duration / 1000).toFixed(1)}秒)`,
        });
      } catch (err) {
        send({
          type: 'error',
          success: false,
          message: `JRDB ダウンロードエラー: ${err instanceof Error ? err.message : String(err)}`,
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
