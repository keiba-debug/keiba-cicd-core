/**
 * target_reader.py 実行ラッパー (日別 TARGET CSV)
 */

import { spawn } from 'child_process';
import path from 'path';
import { ADMIN_CONFIG } from '@/lib/admin/config';

const TIMEOUT_MS = 60_000;

export interface TargetDailyBet {
  bet_type: string;
  selection: string;
  amount: number;
  odds: number;
  is_hit: boolean;
  payout: number;
}

export interface TargetDailyRace {
  race_id: string;
  venue: string;
  race_number: number;
  total_bet: number;
  total_payout: number;
  profit: number;
  recovery_rate: number;
  hits: string[];
  bets: TargetDailyBet[];
  confirmed: boolean;
}

export interface TargetDailyResult {
  date: string;
  races: TargetDailyRace[];
  has_data?: boolean;
  file_exists?: boolean;
}

/** YYYYMMDD。 失敗時は null (TARGET 未使用環境でも page は落とさない) */
export async function readTargetDaily(dateYmd: string): Promise<TargetDailyResult | null> {
  if (!/^\d{8}$/.test(dateYmd)) return null;

  const scriptPath = path.join(ADMIN_CONFIG.aiToolsPath, 'target_reader.py');

  return new Promise((resolve) => {
    const child = spawn(ADMIN_CONFIG.pythonPath, [scriptPath, '--date', dateYmd], {
      cwd: ADMIN_CONFIG.v2Path,
      shell: true,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    });

    let stdout = '';
    let stderr = '';
    const timer = setTimeout(() => {
      child.kill();
      console.warn('[TargetReader] timeout', dateYmd);
      resolve(null);
    }, TIMEOUT_MS);

    child.stdout?.on('data', (chunk: Buffer) => {
      stdout += chunk.toString('utf-8');
    });
    child.stderr?.on('data', (chunk: Buffer) => {
      stderr += chunk.toString('utf-8');
    });

    child.on('error', (err) => {
      clearTimeout(timer);
      console.warn('[TargetReader] spawn error:', err.message);
      resolve(null);
    });

    child.on('close', (code) => {
      clearTimeout(timer);
      if (code !== 0) {
        console.warn('[TargetReader] exit', code, stderr.slice(0, 200));
        resolve(null);
        return;
      }
      try {
        const jsonMatch = stdout.match(/\{[\s\S]*\}/);
        if (!jsonMatch) {
          resolve(null);
          return;
        }
        resolve(JSON.parse(jsonMatch[0]) as TargetDailyResult);
      } catch (e) {
        console.warn('[TargetReader] parse error:', e);
        resolve(null);
      }
    });
  });
}
