/**
 * 管理画面用API: コマンド実行
 * POST /api/admin/execute
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
        const sendEvent = (type: string, data: object) => {
          const event = `data: ${JSON.stringify({ type, ...data })}\n\n`;
          controller.enqueue(encoder.encode(event));
        };

        // 日付範囲アクションかどうかでコマンドリストを切り替え
        const options: CommandOptions = {
          raceFrom,
          raceTo,
          track,
        };

        // 特別なアクションのコマンドを生成
        let commandsList: string[][] = [];
        let customCwd: string | undefined;
        
        if (action === 'calc_race_type_standards') {
          // レース特性基準値算出 - JRA-VANデータから算出（TARGETディレクトリで実行）
          // --since 2020: 2020年以降〜現在年まですべて計算対象
          customCwd = ADMIN_CONFIG.targetPath;
          commandsList = [
            ['scripts/calculate_race_type_standards_jv.py', '--since', '2020', '--output', 'data/race_type_standards.json']
          ];
        } else if (action === 'calc_rating_standards') {
          // レイティング基準値算出 - 競馬ブックデータから算出（keibabookディレクトリで実行）
          // --since 2023: 2023年以降のデータを対象
          customCwd = ADMIN_CONFIG.keibabookPath;
          commandsList = [
            ['scripts/calculate_rating_standards.py', '--since', '2023', '--output', 'data/rating_standards.json']
          ];
        } else if (action === 'training_summary') {
          // 調教サマリ生成 - CK_DATAから調教サマリJSONを生成（TARGETディレクトリで実行）
          customCwd = ADMIN_CONFIG.targetPath;
          if (isRangeAction && startDate && endDate) {
            commandsList = [
              ['scripts/generate_training_summary.py', '--start', startDate, '--end', endDate]
            ];
          } else if (date) {
            commandsList = [
              ['scripts/generate_training_summary.py', '--date', date]
            ];
          }
        } else if (action === 'build_horse_name_index') {
          // 馬名インデックス作成 - UM_DATAから馬名→血統番号の辞書を再構築（TARGETディレクトリで実行）
          customCwd = ADMIN_CONFIG.targetPath;
          commandsList = [
            ['scripts/horse_id_mapper.py', '--build-index']
          ];
        } else {
          commandsList = isRangeAction && startDate && endDate
            ? getCommandArgsRange(action, startDate, endDate, options)
            : getCommandArgs(action, date || '', options);
        }
        
        const startTime = Date.now();

        sendEvent('start', {
          action,
          label: actionConfig.label,
          icon: actionConfig.icon,
          totalCommands: commandsList.length,
          timestamp: new Date().toISOString(),
        });

        try {
          for (let i = 0; i < commandsList.length; i++) {
            const args = commandsList[i];

            sendEvent('progress', {
              current: i + 1,
              total: commandsList.length,
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
              },
              customCwd
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
            message: `❌ ${actionConfig.label} エラー: ${errorMessage}`,
          });
        }

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
 * 単一のコマンドを実行
 */
function executeCommand(
  args: string[],
  onLog: (message: string, level: 'info' | 'warning' | 'error') => void,
  customCwd?: string
): Promise<void> {
  return new Promise((resolve, reject) => {
    const cwd = customCwd || ADMIN_CONFIG.keibabookPath;
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
