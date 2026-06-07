/**
 * purchase_ledger の未精算 ticket を DB 配当で settle する (ml/settle_ledger.py ラッパ)
 *
 * /bankroll/auto 表示前に冪等実行。 既に settled_at がある ticket はスキップされる。
 */

import { spawn } from 'child_process';
import { ADMIN_CONFIG } from '@/lib/admin/config';

const SETTLE_TIMEOUT_MS = 90_000;

/** YYYY-MM-DD。 ledger 無し・精算対象無しも ok: true (表示は空/未確定のまま) */
export async function settleLedgerForDate(dateIso: string): Promise<{ ok: boolean; error?: string }> {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(dateIso)) {
    return { ok: false, error: 'invalid date' };
  }

  return new Promise((resolve) => {
    const cwd = ADMIN_CONFIG.v2Path;
    const args = ['-m', 'ml.settle_ledger', '--date', dateIso, '--allow-pre-reconcile'];

    const child = spawn(ADMIN_CONFIG.pythonPath, args, {
      cwd,
      shell: true,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    });

    let stderr = '';
    const timer = setTimeout(() => {
      child.kill();
      resolve({ ok: false, error: 'settle timeout' });
    }, SETTLE_TIMEOUT_MS);

    child.stderr?.on('data', (chunk: Buffer) => {
      stderr += chunk.toString('utf-8');
    });

    child.on('error', (err) => {
      clearTimeout(timer);
      resolve({ ok: false, error: err.message });
    });

    child.on('close', (code) => {
      clearTimeout(timer);
      if (code === 0) {
        resolve({ ok: true });
        return;
      }
      resolve({ ok: false, error: stderr.trim() || `exit ${code}` });
    });
  });
}
