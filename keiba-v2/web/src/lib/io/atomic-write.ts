/**
 * クロスファイル共通: アトミック書き込み + mkdir-based advisory lock
 *
 * 経緯:
 *  - Session 125 で my_marks_v2 用に同等実装を入れた (lib/data/my-marks-v2-writer.ts)
 *  - Session 126 で bankroll route が同じ穴 (writeFile 直書き、ロック無し) を抱えていると
 *    シズネレビュー (af17447ae78bb3da5) で M1 指摘 → 共通化
 *
 * 設計:
 *  - writeAtomic: fs.openSync + fsync + rename。Windows EPERM/EBUSY は unlink → rename
 *  - withFileLock: `{filePath}.lock` ディレクトリの mkdir 原子性。proper-lockfile 依存無し。
 *    staleMs=5s で書込みプロセス死亡時の自動復旧 (writer は <100ms で完了する前提)
 */
import * as fs from 'fs';
import * as path from 'path';

function ensureDir(dir: string): void {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

/**
 * tmp に書いて fsync → rename。 OS クラッシュ時の 0 バイト残骸を防ぐ。
 */
export function writeAtomic(filePath: string, content: string): void {
  ensureDir(path.dirname(filePath));
  const tmp = `${filePath}.tmp.${process.pid}.${Date.now()}`;

  const fd = fs.openSync(tmp, 'w');
  try {
    fs.writeSync(fd, content, 0, 'utf-8');
    fs.fsyncSync(fd);
  } finally {
    fs.closeSync(fd);
  }

  try {
    fs.renameSync(tmp, filePath);
  } catch (e) {
    if (fs.existsSync(filePath)) {
      try {
        fs.unlinkSync(filePath);
        fs.renameSync(tmp, filePath);
      } catch (e2) {
        try { fs.unlinkSync(tmp); } catch { /* tmp cleanup best-effort */ }
        throw e2;
      }
    } else {
      try { fs.unlinkSync(tmp); } catch { /* tmp cleanup best-effort */ }
      throw e;
    }
  }
}

export interface FileLockOptions {
  timeoutMs?: number;
  retryIntervalMs?: number;
  staleMs?: number;
}

/**
 * mkdir-based advisory lock。 `fn()` 実行中は他プロセスから同じ filePath への lock 取得を防ぐ。
 *
 * Step 1 単独運用 (1 PC 1 ユーザー) では proper-lockfile を入れる必要無いという判断。
 * 死んだ lock は staleMs 経過で自動回収される。
 */
export async function withFileLock<T>(
  filePath: string,
  fn: () => T | Promise<T>,
  opts: FileLockOptions = {}
): Promise<T> {
  const lockDir = `${filePath}.lock`;
  const timeoutMs = opts.timeoutMs ?? 5000;
  const retryIntervalMs = opts.retryIntervalMs ?? 50;
  const staleMs = opts.staleMs ?? 5000;
  const startTime = Date.now();

  ensureDir(path.dirname(filePath));

  while (true) {
    try {
      fs.mkdirSync(lockDir);
      break;
    } catch (e) {
      const code = (e as NodeJS.ErrnoException).code;
      if (code !== 'EEXIST') throw e;

      try {
        const stat = fs.statSync(lockDir);
        const age = Date.now() - stat.mtimeMs;
        if (age > staleMs) {
          console.warn(`[atomic-write] removing stale lock: ${lockDir} (age=${age}ms)`);
          try { fs.rmdirSync(lockDir); } catch { /* race: someone else removed it */ }
          continue;
        }
      } catch { /* lock disappeared between mkdir and stat — retry */ }

      if (Date.now() - startTime > timeoutMs) {
        throw new Error(`[atomic-write] failed to acquire lock for ${filePath} within ${timeoutMs}ms`);
      }

      await new Promise((resolve) => setTimeout(resolve, retryIntervalMs));
    }
  }

  try {
    return await fn();
  } finally {
    try {
      fs.rmdirSync(lockDir);
    } catch (e) {
      console.error(`[atomic-write] failed to release lock ${lockDir}:`, e);
    }
  }
}
