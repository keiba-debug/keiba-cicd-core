/**
 * コマンド実行ロジック
 */

import { spawn, ChildProcess } from 'child_process';
import { ActionType, getCommandArgs, getAction } from './commands';

export interface ExecutionResult {
  success: boolean;
  action: ActionType;
  duration: number;
  error?: string;
}

export interface LogEntry {
  id: string;
  timestamp: string;
  level: 'info' | 'success' | 'warning' | 'error';
  message: string;
}

/**
 * コマンドを実行し、ログをコールバックで返す
 */
export async function executeAction(
  action: ActionType,
  date: string,
  onLog: (log: LogEntry) => void,
  onProgress?: (current: number, total: number) => void
): Promise<ExecutionResult> {
  const startTime = Date.now();
  const commandsList = getCommandArgs(action, date);
  const actionConfig = getAction(action);
  const actionLabel = actionConfig?.label || action;

  onLog({
    id: crypto.randomUUID(),
    timestamp: new Date().toISOString(),
    level: 'info',
    message: `${actionConfig?.icon || '🔄'} ${actionLabel} 開始...`,
  });

  try {
    for (let i = 0; i < commandsList.length; i++) {
      const args = commandsList[i];
      
      if (onProgress) {
        onProgress(i + 1, commandsList.length);
      }

      onLog({
        id: crypto.randomUUID(),
        timestamp: new Date().toISOString(),
        level: 'info',
        message: `実行中: python ${args.join(' ')}`,
      });

      await executeCommand(args, onLog);
    }

    const duration = Date.now() - startTime;

    onLog({
      id: crypto.randomUUID(),
      timestamp: new Date().toISOString(),
      level: 'success',
      message: `✅ ${actionLabel} 完了 (${(duration / 1000).toFixed(1)}秒)`,
    });

    return {
      success: true,
      action,
      duration,
    };
  } catch (error) {
    const duration = Date.now() - startTime;
    const errorMessage = error instanceof Error ? error.message : String(error);

    onLog({
      id: crypto.randomUUID(),
      timestamp: new Date().toISOString(),
      level: 'error',
      message: `❌ ${actionLabel} エラー: ${errorMessage}`,
    });

    return {
      success: false,
      action,
      duration,
      error: errorMessage,
    };
  }
}

/**
 * 単一のコマンドを実行
 */
function executeCommand(args: string[], onLog: (log: LogEntry) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    const pythonPath = process.env.PYTHON_PATH || 'python';
    const cwd = process.env.KEIBABOOK_PATH;

    if (!cwd) {
      reject(new Error('KEIBABOOK_PATH が設定されていません'));
      return;
    }

    const child: ChildProcess = spawn(pythonPath, args, {
      cwd,
      shell: true,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    });

    child.stdout?.on('data', (data: Buffer) => {
      const lines = data.toString('utf-8').split('\n').filter(Boolean);
      for (const line of lines) {
        onLog({
          id: crypto.randomUUID(),
          timestamp: new Date().toISOString(),
          level: 'info',
          message: line.trim(),
        });
      }
    });

    child.stderr?.on('data', (data: Buffer) => {
      const lines = data.toString('utf-8').split('\n').filter(Boolean);
      for (const line of lines) {
        // Pythonの進捗表示などはwarningとして扱う
        onLog({
          id: crypto.randomUUID(),
          timestamp: new Date().toISOString(),
          level: 'warning',
          message: line.trim(),
        });
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
