/**
 * 管理画面用API: コマンド実行
 * POST /api/admin/execute
 */

import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';
import { ActionType, getCommandArgs, getCommandArgsRange, getAction, type CommandOptions } from '@/lib/admin/commands';
import { ADMIN_CONFIG } from '@/lib/admin/config';
import { DATA_ROOT } from '@/lib/config';

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

        // 特別なアクションのコマンドを生成
        let commandsList: string[][] = [];
        let customCwd: string | undefined;
        
        if (action === 'calc_race_type_standards') {
          // レース特性基準値算出 - JRA-VANデータから算出（TARGETディレクトリで実行）
          // --since 2020: 2020年以降〜現在年まですべて計算対象
          customCwd = ADMIN_CONFIG.targetPath;
          const raceTypeOutput = path.join(DATA_ROOT, 'target', 'race_type_standards.json');
          commandsList = [
            ['scripts/calculate_race_type_standards_jv.py', '--since', '2020', '--output', raceTypeOutput]
          ];
        } else if (action === 'calc_rating_standards') {
          // レイティング基準値算出 - 競馬ブックデータから算出（keibabookディレクトリで実行）
          // --since 2023: 2023年以降のデータを対象
          customCwd = ADMIN_CONFIG.keibabookPath;
          const ratingOutput = path.join(DATA_ROOT, 'keibabook', 'rating_standards.json');
          commandsList = [
            ['scripts/calculate_rating_standards.py', '--since', '2023', '--output', ratingOutput]
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
        } else if (action === 'build_trainer_index') {
          // 調教師インデックス作成 - 競馬ブック厩舎IDとJRA-VAN調教師コードの対応辞書を構築（TARGETディレクトリで実行）
          customCwd = ADMIN_CONFIG.targetPath;
          commandsList = [
            ['scripts/build_trainer_index.py', '--build-index']
          ];
        } else if (action === 'analyze_trainer_patterns') {
          // 調教師パターン分析 - 過去3年の調教×着順データから勝負パターンを統計分析（TARGETディレクトリで実行）
          customCwd = ADMIN_CONFIG.targetPath;
          const historyOutput = path.join(DATA_ROOT, 'target', 'trainer_training_history.json');
          const patternsOutput = path.join(DATA_ROOT, 'target', 'trainer_patterns.json');
          commandsList = [
            ['scripts/collect_trainer_training_history.py', '--since', '2023', '--output', historyOutput],
            ['scripts/analyze_trainer_patterns.py', '--input', historyOutput, '--output', patternsOutput],
          ];
        } else if (action === 'v4_build_race') {
          // v4 レース構築 - JRA-VAN SE/SR → data3/races/ (keiba-v2ディレクトリで実行)
          customCwd = ADMIN_CONFIG.v2Path;
          const dateArg = date || '';
          commandsList = dateArg
            ? [['-m', 'builders.build_race_master', '--date', dateArg]]
            : [['-m', 'builders.build_race_master']];
        } else if (action === 'v4_build_kbext') {
          // v4 KB拡張変換 - data2 integrated → data3/keibabook/ (keiba-v2ディレクトリで実行)
          customCwd = ADMIN_CONFIG.v2Path;
          const dateArg = date || '';
          commandsList = dateArg
            ? [['-m', 'keibabook.ext_builder', '--date', dateArg]]
            : [['-m', 'keibabook.ext_builder']];
        } else if (action === 'v4_predict') {
          // v4 ML予測 - ML v3モデルでValue Bet予測 (keiba-v2ディレクトリで実行)
          customCwd = ADMIN_CONFIG.v2Path;
          const dateArg = date || '';
          commandsList = dateArg
            ? [['-m', 'ml.predict', '--date', dateArg]]
            : [['-m', 'ml.predict']];
        } else if (action === 'v4_pipeline') {
          // v4 パイプライン - レース構築 → KB拡張変換 → ML予測 を一括実行 (keiba-v2ディレクトリで実行)
          customCwd = ADMIN_CONFIG.v2Path;
          const dateArg = date || '';
          if (dateArg) {
            commandsList = [
              ['-m', 'builders.build_race_master', '--date', dateArg],
              ['-m', 'keibabook.ext_builder', '--date', dateArg],
              ['-m', 'ml.predict', '--date', dateArg],
            ];
          } else {
            commandsList = [
              ['-m', 'builders.build_race_master'],
              ['-m', 'keibabook.ext_builder'],
              ['-m', 'ml.predict'],
            ];
          }
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
