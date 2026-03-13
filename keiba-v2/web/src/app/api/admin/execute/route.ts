/**
 * 管理画面用API: コマンド実行
 * POST /api/admin/execute
 * 全コマンドがv2(keiba-v2/)ネイティブ — v1依存なし
 */

import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import fs from 'fs';
import path from 'path';
import { ActionType, getCommandArgs, getCommandArgsRange, getAction, type CommandOptions } from '@/lib/admin/commands';
import { ADMIN_CONFIG } from '@/lib/admin/config';
import { DATA3_ROOT } from '@/lib/config';
import { clearRaceDateIndex, buildRaceDateIndex } from '@/lib/data/race-date-index';

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

    // 日付範囲 → 日付リスト展開（--dateのみ対応のスクリプト用）
    const expandDateRange = (start: string, end: string): string[] => {
      const dates: string[] = [];
      const cur = new Date(start + 'T00:00:00');
      const last = new Date(end + 'T00:00:00');
      while (cur <= last) {
        dates.push(cur.toISOString().slice(0, 10));
        cur.setDate(cur.getDate() + 1);
      }
      return dates;
    };

    // 日付範囲 → 開催日のみ展開（race_date_indexでフィルタ）
    const expandRaceDateRange = (start: string, end: string): string[] => {
      try {
        const indexPath = path.join(DATA3_ROOT, 'indexes', 'race_date_index.json');
        const index = JSON.parse(fs.readFileSync(indexPath, 'utf-8'));
        return Object.keys(index).filter(d => d >= start && d <= end).sort();
      } catch {
        // インデックス読み込み失敗時はフォールバック
        return expandDateRange(start, end);
      }
    };

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
        // レース前はJRA-VAN SE_DATAが無いため build_race_master だけでは race_*.json ができない。
        // build_race_from_keibabook で race_info + 出馬表から race_*.json を先に生成し、
        // その後 build_race_master でJRA-VANデータがあれば上書きする。
        const buildV4AfterScrapeCommands = (dateArg: string, includeRaceBuild: boolean): string[][] => {
          const cmds: string[][] = [];
          if (includeRaceBuild && dateArg) {
            cmds.push(['-m', 'builders.build_race_from_keibabook', '--date', dateArg]);
            cmds.push(['-m', 'builders.build_race_master', '--date', dateArg]);
          } else if (includeRaceBuild) {
            cmds.push(['-m', 'builders.build_race_master']);
          }
          cmds.push(dateArg ? ['-m', 'keibabook.cyokyo_enricher', '--date', dateArg] : ['-m', 'keibabook.cyokyo_enricher']);
          // v5.41: predict は batch_morning に移動（馬場データ取得後に実行）
          return cmds;
        };

        // v4パイプライン（v4_pipelineアクション用）
        // buildV4AfterScrapeCommandsと同一だが、includeRaceBuild=trueで呼ぶ想定
        const buildV4PipelineCommands = buildV4AfterScrapeCommands;

        // コマンドリストを構築（全てv2Pathで実行）
        let commands: string[][] = [];

        if (action === 'batch_prepare') {
          // 前日準備: スクレイピング(basic) → v4パイプライン(race_build→cyokyo_enrich→predict)
          if (isRangeAction && startDate && endDate) {
            commands = [
              ['-m', 'keibabook.batch_scraper', '--start', startDate, '--end', endDate, '--types', 'basic'],
            ];
            for (const d of expandDateRange(startDate, endDate)) {
              commands.push(...buildV4AfterScrapeCommands(d, true));
            }
          } else {
            const dateArg = date || '';
            commands = [
              ['-m', 'keibabook.batch_scraper', '--date', dateArg, '--types', 'basic'],
              ...buildV4AfterScrapeCommands(dateArg, true),
            ];
          }
        } else if (action === 'batch_morning') {
          // 直前情報登録: パドック情報のみ取得
          if (isRangeAction && startDate && endDate) {
            commands = [
              ['-m', 'keibabook.batch_scraper', '--start', startDate, '--end', endDate, '--types', 'paddok'],
            ];
          } else {
            const dateArg = date || '';
            const cmd = ['-m', 'keibabook.batch_scraper', '--date', dateArg, '--types', 'paddok'];
            if (raceFrom) cmd.push('--from-race', String(raceFrom));
            if (raceTo) cmd.push('--to-race', String(raceTo));
            commands = [cmd];
          }
        } else if (action === 'batch_after_race') {
          // 成績情報登録: 成績情報取得 → JRA-VANデータでrace_*.json更新 → 検索インデックス再構築
          if (isRangeAction && startDate && endDate) {
            commands = [
              ['-m', 'keibabook.batch_scraper', '--start', startDate, '--end', endDate, '--types', 'seiseki'],
            ];
            for (const d of expandRaceDateRange(startDate, endDate)) {
              commands.push(['-m', 'builders.build_race_master', '--date', d]);
            }
            commands.push(['-m', 'builders.build_race_search_index']);
          } else {
            const dateArg = date || '';
            const cmd = ['-m', 'keibabook.batch_scraper', '--date', dateArg, '--types', 'seiseki'];
            if (raceFrom) cmd.push('--from-race', String(raceFrom));
            if (raceTo) cmd.push('--to-race', String(raceTo));
            commands = [cmd];
            if (dateArg) commands.push(['-m', 'builders.build_race_master', '--date', dateArg]);
            commands.push(['-m', 'builders.build_race_search_index']);
          }
        } else if (action === 'sunpyo_update') {
          // 寸評更新: seiseki再取得（寸評・インタビュー・次走メモ）→ kb_ext更新
          const dateArg = date || '';
          if (isRangeAction && startDate && endDate) {
            commands = [
              ['-m', 'keibabook.batch_scraper', '--start', startDate, '--end', endDate, '--types', 'seiseki'],
            ];
          } else {
            commands = [
              ['-m', 'keibabook.batch_scraper', '--date', dateArg, '--types', 'seiseki'],
            ];
          }
        } else if (action === 'calc_race_type_standards') {
          commands = [['-m', 'analysis.race_type_standards', '--since', '2020']];
        } else if (action === 'calc_rating_standards') {
          commands = [['-m', 'analysis.rating_standards', '--since', '2023']];
        } else if (action === 'build_horse_name_index') {
          commands = [['-m', 'builders.build_horse_name_index']];
        } else if (action === 'build_trainer_index') {
          commands = [['-m', 'builders.build_trainer_kb_index']];
        } else if (action === 'analyze_trainer_patterns') {
          commands = [['-m', 'analysis.trainer_patterns', '--since', '2023']];
        } else if (action === 'analyze_training') {
          commands = [['-m', 'analysis.training_analysis', '--since', '2023']];
        } else if (action === 'rebuild_sire_stats') {
          commands = [['-m', 'builders.build_sire_stats']];
        } else if (action === 'rebuild_slow_start') {
          commands = [['-m', 'builders.build_slow_start_analysis']];
        } else if (action === 'rebuild_race_search_index') {
          commands = [['-m', 'builders.build_race_search_index']];
        } else if (action === 'v4_build_race') {
          if (isRangeAction && startDate && endDate) {
            for (const d of expandDateRange(startDate, endDate)) {
              commands.push(['-m', 'builders.build_race_master', '--date', d]);
            }
          } else {
            const dateArg = date || '';
            commands = [dateArg ? ['-m', 'builders.build_race_master', '--date', dateArg] : ['-m', 'builders.build_race_master']];
          }
        } else if (action === 'v4_predict') {
          if (isRangeAction && startDate && endDate) {
            for (const d of expandRaceDateRange(startDate, endDate)) {
              commands.push(['-m', 'ml.predict', '--date', d]);
              commands.push(['-m', 'ml.predict_closing', '--date', d]);
            }
          } else {
            const dateArg = date || '';
            commands = [dateArg ? ['-m', 'ml.predict', '--date', dateArg] : ['-m', 'ml.predict']];
            commands.push(dateArg ? ['-m', 'ml.predict_closing', '--date', dateArg] : ['-m', 'ml.predict_closing']);
          }
        } else if (action === 'v4_pipeline') {
          if (isRangeAction && startDate && endDate) {
            for (const d of expandDateRange(startDate, endDate)) {
              commands.push(...buildV4PipelineCommands(d, true));
            }
          } else {
            const dateArg = date || '';
            commands = buildV4PipelineCommands(dateArg, true);
          }
        } else if (action === 'vb_refresh') {
          // VBリフレッシュ: 最新オッズでVB/買い目を再計算
          if (isRangeAction && startDate && endDate) {
            for (const d of expandRaceDateRange(startDate, endDate)) {
              commands.push(['-m', 'ml.vb_refresh', '--date', d]);
            }
          } else {
            const dateArg = date || '';
            commands = [['-m', 'ml.vb_refresh', '--date', dateArg]];
          }
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

          // レースJSON構築を含むアクションはインデックスを自動再構築
          const indexRebuildActions: ActionType[] = ['batch_prepare', 'v4_build_race', 'v4_pipeline'];
          if (indexRebuildActions.includes(action)) {
            sendEvent('log', {
              message: '📋 レース日付インデックスを再構築中...',
              level: 'info',
              timestamp: new Date().toISOString(),
            });
            try {
              clearRaceDateIndex();
              await buildRaceDateIndex();
              sendEvent('log', {
                message: '✅ インデックス再構築完了',
                level: 'info',
                timestamp: new Date().toISOString(),
              });
            } catch (e) {
              sendEvent('log', {
                message: `⚠️ インデックス再構築エラー: ${e}`,
                level: 'warning',
                timestamp: new Date().toISOString(),
              });
            }
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
