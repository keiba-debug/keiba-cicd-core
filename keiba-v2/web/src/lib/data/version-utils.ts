/**
 * バージョン管理ユーティリティ（サーバーサイド専用）
 * versions.json マニフェストの読み込みとパス解決
 */

import { promises as fs } from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';

export interface VersionEntry {
  version: string;
  archived_at: string;
  created_at?: string;
  files?: string[];
  [key: string]: unknown;
}

const ML_VERSIONS_PATH = path.join(DATA3_ROOT, 'ml', 'versions', 'versions.json');

/**
 * ML versions.json からバージョン一覧を返す（新しい順）
 */
export async function getMlVersionManifest(): Promise<VersionEntry[]> {
  try {
    const content = await fs.readFile(ML_VERSIONS_PATH, 'utf-8');
    const entries: VersionEntry[] = JSON.parse(content);
    return entries.sort(
      (a, b) => (b.archived_at ?? '').localeCompare(a.archived_at ?? '')
    );
  } catch {
    return [];
  }
}

/**
 * バージョン指定付きMLファイルパスを返す
 * version が undefined/null なら既存のライブパスを返す
 */
export function getVersionedMlPath(filename: string, version?: string | null): string {
  if (!version) {
    return path.join(DATA3_ROOT, 'ml', filename);
  }
  return path.join(DATA3_ROOT, 'ml', 'versions', `v${version}`, filename);
}
