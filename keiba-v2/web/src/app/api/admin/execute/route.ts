/**
 * 管理画面用API: コマンド実行
 * POST /api/admin/execute
 * 全コマンドがv2(keiba-v2/)ネイティブ — v1依存なし
 */

import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import { ActionType, getCommandArgs, getCommandArgsRange, getAction, type CommandOptions } from '@/lib/admin/commands';
import { ADMIN_CONFIG } from '@/lib/admin/config';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

interface ExecuteRequest {
  action: ActionType;
  date?: string; // YYYY-MM-DD形式（単一日付用）
  startDate?: string; // YYYY-MM-DD形式（日付範囲用）
  endDate?: string; // YYYY-MM-DD形式（日付範囲用）
  isRangeAction?: boolean; // 日付範囲アクションかどうか
  raceFrom?: number; // 開始レース番号
  raceTo?: number; // 終了レース番号
  track?: string; // 競馬場フィルタ
}

/**
 * SSE形式でログをストリーミング
 */
export async function POST(request: NextRequest) {
  try {
    const body: ExecuteRequest = await request.json();
    const { action, date, startDate, endDate, isRangeAction, raceFrom, raceTo, track } = body;

    // バリデーション
    if (!action) {
      return NextResponse.json(
        { error: 'action は必須です' },
        { status: 400 }
      );
    }

    const actionConfig = getAction(action);

    // 日付不要アクション以外は日付バリデーション
    if (!actionConfig?.noDateRequired) {
      // 日付範囲アクションの場合
      if (isRangeAction) {
        if (!startDate || !endDate) {
          return NextResponse.json(
            { error: 'startDate と endDate は必須です（日付範囲アクション）' },
            { status: 400 }
          );
        }
      } else {
        if (!date) {
          return NextResponse.json(
            { error: 'date は必須です' },
            { status: 400 }
          );
        }
      }
    }
    if (!actionConfig) {
      return NextResponse.json(
        { error: `不明なアクション: ${action}` },
        { status: 400 }
      );
    }

    // SSEストリームを作成
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      async start(controller) {
        let isClosed = false;

        const sendEvent = (type: string, data: object) => {
          // コントローラーが閉じられている場合は何もしない
          if (isClosed) return;
          try {
            const event = `data: ${JSON.stringify({ type, ...data })}\n\n`;
            controller.enqueue(encoder.encode(event));
          } catch {
            // コントローラーが閉じられている場合のエラーを無視
            isClosed = true;
          }
        };

        // 日付範囲アクションかどうかでコマンドリストを切り替え
        const options: CommandOptions = {
          raceFrom,
          raceTo,
          track,
        };

        // v4パイプラインのコマンド生成ヘルパー（スクレイピング後用）
        // batch_scraperがkb_extを直接構築するため、ext_builderは不要
        const buildV4AfterScrapeCommands = (dateArg: string, includeRaceBuild: boolean): string[][] => {
          const cmds: string[][] = [];
          if (includeRaceBuild) {
            cmds.push(dateArg ? ['-m', 'builders.build_race_master', '--date', dateArg] : ['-m', 'builders.build_race_master']);
          }
          cmds.push(dateArg ? ['-m', 'keibabook.cyokyo_enricher', '--date', dateArg] : ['-m', 'keibabook.cyokyo_enricher']);
          cmds.push(dateArg ? ['-m', 'ml.predict', '--date', dateArg] : ['-m', 'ml.predict']);
          return cmds;
        };

        // レガシーv4パイプライン（v4_pipelineアクション用 — ext_builder含む）
        const buildV4PipelineCommands = (dateArg: string, includeRaceBuild: boolean): string[][] => {
          const cmds: string[][] = [];
          if (includeRaceBuild) {
            cmds.push(dateArg ? ['-m', 'builders.build_race_master', '--date', dateArg] : ['-m', 'builders.build_race_master']);
          }
          cmds.push(dateArg ? ['-m', 'keibabook.ext_builder', '--date', dateArg] : ['-m', 'keibabook.ext_builder']);
          cmds.push(dateArg ? ['-m', 'keibabook.cyokyo_enricher', '--date', dateArg] : ['-m', 'keibabook.cyokyo_enricher']);
          cmds.push(dateArg ? ['-m', 'ml.predict', '--date', dateArg] : ['-m', 'ml.predict']);
          return cmds;
        };

        // コマンドリストを構築（全てv2Pathで実行）
        let commands: string[][] = [];

        if (action === 'batch_prepare') {
          // 前日準備: スクレイピング(basic) → v4パイプライン(race_build→cyokyo_enrich→predict)
          const dateArg = date || '';
          if (isRangeAction && startDate && endDate) {
            commands = [
              ['-m', 'keibabook.batch_scraper', '--start', startDate, '--end', endDate, '--types', 'basic'],
              ...buildV4AfterScrapeCommands(dateArg, true),
            ];
          } else {
            commands = [
              ['-m', 'keibabook.batch_scraper', '--date', dateArg, '--types', 'basic'],
              ...buildV4AfterScrapeCommands(dateArg, true),
            ];
          }
        } else if (action === 'batch_after_race') {
          // レース後更新: paddok → seiseki → cyokyo_enrich → predict
          const dateArg = date || '';
          if (isRangeAction && startDate && endDate) {
            commands = [
              ['-m', 'keibabook.batch_scraper', '--start', startDate, '--end', endDate, '--types', 'paddok'],
              ['-m', 'keibabook.batch_scraper', '--start', startDate, '--end', endDate, '--types', 'seiseki'],
              ...buildV4AfterScrapeCommands(dateArg, false),
            ];
          } else {
            commands = [
              ['-m', 'keibabook.batch_scraper', '--date', dateArg, '--types', 'paddok'],
              ['-m', 'keibabook.batch_scraper', '--date', dateArg, '--types', 'seiseki'],
              ...buildV4AfterScrapeCommands(dateArg, false),
            ];
          }
        } else if (action === 'sunpyo_update') {
          // 寸評更新: seiseki再取得 → cyokyo_enrich
          if (isRangeAction && startDate && endDate) {
            commands = [
              ['-m', 'keibabook.batch_scraper', '--start', startDate, '--end', endDate, '--types', 'seiseki'],
            ];
          }
        } else if (action === 'calc_race_type_standards') {
          commands = [['-m', 'analysis.race_type_standards', '--since', '2020']];
        } else if (action === 'calc_rating_standards') {
          commands = [['-m', 'analysis.rating_standards', '--since', '2023']];
        } else if (action === 'training_summary') {
          const dateArg = date || '';
          commands = [dateArg
            ? ['-m', 'keibabook.cyokyo_enricher', '--date', dateArg]
            : ['-m', 'keibabook.cyokyo_enricher']];
        } else if (action === 'build_horse_name_index') {
          commands = [['-m', 'builders.build_horse_name_index']];
        } else if (action === 'build_trainer_index') {
          commands = [['-m', 'builders.build_trainer_kb_index']];
        } else if (action === 'analyze_trainer_patterns') {
          commands = [['-m', 'analysis.trainer_patterns', '--since', '2023']];
        } else if (action === 'v4_build_race') {
          const dateArg = date || '';
          commands = [dateArg ? ['-m', 'builders.build_race_master', '--date', dateArg] : ['-m', 'builders.build_race_master']];
        } else if (action === 'v4_build_kbext') {
          const dateArg = date || '';
          commands = [dateArg ? ['-m', 'keibabook.ext_builder', '--date', dateArg] : ['-m', 'keibabook.ext_builder']];
        } else if (action === 'v4_cyokyo_enrich') {
          const dateArg = date || '';
          commands = [dateArg ? ['-m', 'keibabook.cyokyo_enricher', '--date', dateArg] : ['-m', 'keibabook.cyokyo_enricher']];
        } else if (action === 'v4_predict') {
          const dateArg = date || '';
          commands = [dateArg ? ['-m', 'ml.predict', '--date', dateArg] : ['-m', 'ml.predict']];
        } else if (action === 'v4_pipeline') {
          const dateArg = date || '';
          commands = buildV4PipelineCommands(dateArg, true);
        } else {
          commands = isRangeAction && startDate && endDate
            ? getCommandArgsRange(action, startDate, endDate, options)
            : getCommandArgs(action, date || '', options);
        }

        const totalCommands = commands.length;
        const startTime = Date.now();

        sendEvent('start', {
          action,
          label: actionConfig.label,
          icon: actionConfig.icon,
          totalCommands,
          timestamp: new Date().toISOString(),
        });

        try {
          for (let i = 0; i < commands.length; i++) {
            const args = commands[i];

            sendEvent('progress', {
              current: i + 1,
              total: totalCommands,
              command: `python ${args.join(' ')}`,
            });

            await executeCommand(
              args,
              (message, level) => {
                sendEvent('log', {
                  message,
                  level,
                  timestamp: new Date().toISOString(),
                });
              }
            );
          }

          const duration = Date.now() - startTime;
          sendEvent('complete', {
            success: true,
            duration,
            message: `${actionConfig.icon} ${actionConfig.label} 完了 (${(duration / 1000).toFixed(1)}秒)`,
          });
        } catch (error) {
          const duration = Date.now() - startTime;
          const errorMessage = error instanceof Error ? error.message : String(error);

          sendEvent('error', {
            success: false,
            duration,
            message: `${actionConfig.label} エラー: ${errorMessage}`,
          });
        }

        isClosed = true;
        controller.close();
      },
    });

    return new Response(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
      },
    });
  } catch (error) {
    console.error('API Error:', error);
    return NextResponse.json(
      { error: 'Internal Server Error' },
      { status: 500 }
    );
  }
}

/**
 * 単一のコマンドを実行（全てv2Pathで実行）
 */
function executeCommand(
  args: string[],
  onLog: (message: string, level: 'info' | 'warning' | 'error') => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const cwd = ADMIN_CONFIG.v2Path;
    const pythonPath = ADMIN_CONFIG.pythonPath;

    onLog(`実行: python ${args.join(' ')}`, 'info');

    const child = spawn(pythonPath, args, {
      cwd,
      shell: true,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    });

    child.stdout?.on('data', (data: Buffer) => {
      const lines = data.toString('utf-8').split('\n').filter(Boolean);
      for (const line of lines) {
        onLog(line.trim(), 'info');
      }
    });

    child.stderr?.on('data', (data: Buffer) => {
      const lines = data.toString('utf-8').split('\n').filter(Boolean);
      for (const line of lines) {
        // 進捗表示などはwarningとして扱う
        onLog(line.trim(), 'warning');
      }
    });

    child.on('close', (code: number | null) => {
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`プロセス終了コード: ${code}`));
      }
    });

    child.on('error', (error: Error) => {
      reject(error);
    });
  });
}
