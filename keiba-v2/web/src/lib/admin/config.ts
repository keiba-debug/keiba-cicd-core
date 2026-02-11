/**
 * 管理画面用設定
 */

import path from 'path';
import fs from 'fs';

const keibabookPath =
  process.env.KEIBABOOK_PATH ||
  path.join(process.cwd(), '..', '..', 'keiba-v1', 'KeibaCICD.keibabook');

const targetPath =
  process.env.TARGET_PATH ||
  path.join(process.cwd(), '..', '..', 'keiba-v1', 'KeibaCICD.TARGET');

const v2Path =
  process.env.KEIBA_V2_PATH ||
  path.join(process.cwd(), '..');

const aiToolsPath =
  process.env.AI_TOOLS_PATH ||
  path.join(process.cwd(), '..', '..', 'keiba-v1', 'KeibaCICD.AI', 'tools');

/**
 * 管理画面から実行する Python を決定する。
 * 1. PYTHON_PATH が設定されていればそれを使用
 * 2. KeibaCICD.keibabook/.venv が存在すればその python を使用（依存をここに入れればレース後更新が動く）
 * 3. それ以外は PATH の python
 */
function resolvePythonPath(): string {
  if (process.env.PYTHON_PATH) return process.env.PYTHON_PATH;
  const winVenv = path.join(keibabookPath, '.venv', 'Scripts', 'python.exe');
  const unixVenv = path.join(keibabookPath, '.venv', 'bin', 'python');
  if (process.platform === 'win32' && fs.existsSync(winVenv)) return winVenv;
  if (fs.existsSync(unixVenv)) return unixVenv;
  return 'python';
}

export const ADMIN_CONFIG = {
  keibabookPath,
  targetPath,
  v2Path,
  aiToolsPath,
  pythonPath: resolvePythonPath(),
  commandTimeout: 5 * 60 * 1000, // 5分
};

export function getKeibabookPath(): string {
  return ADMIN_CONFIG.keibabookPath;
}

export function getPythonPath(): string {
  return ADMIN_CONFIG.pythonPath;
}
