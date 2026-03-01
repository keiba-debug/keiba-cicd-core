import { promises as fs } from 'fs';
import path from 'path';
import { KEIBA_DATA_ROOT } from '@/lib/config';
import type { SimulationData } from '@/app/analysis/simulation/types';

const FILENAME = 'bankroll_simulation.json';

/**
 * バンクロールシミュレーション結果を読み込む
 * version指定時はアーカイブ (versions/v{version}/) から読み込み
 */
export async function getSimulationResult(version?: string | null): Promise<SimulationData | null> {
  const filePath = version
    ? path.join(KEIBA_DATA_ROOT, 'ml', 'versions', `v${version}`, FILENAME)
    : path.join(KEIBA_DATA_ROOT, 'ml', FILENAME);
  try {
    const raw = await fs.readFile(filePath, 'utf-8');
    return JSON.parse(raw) as SimulationData;
  } catch {
    return null;
  }
}

/**
 * bankroll_simulation.json が存在するバージョン一覧を返す（新しい順）
 */
export async function getSimulationVersions(): Promise<string[]> {
  const versionsDir = path.join(KEIBA_DATA_ROOT, 'ml', 'versions');
  try {
    const entries = await fs.readdir(versionsDir, { withFileTypes: true });
    const versions: string[] = [];
    for (const entry of entries) {
      if (entry.isDirectory() && entry.name.startsWith('v')) {
        const simPath = path.join(versionsDir, entry.name, FILENAME);
        try {
          await fs.access(simPath);
          versions.push(entry.name.slice(1)); // remove 'v' prefix
        } catch {
          // no simulation file in this version
        }
      }
    }
    // Sort by version number descending
    return versions.sort((a, b) => {
      const na = a.split('.').map(Number);
      const nb = b.split('.').map(Number);
      for (let i = 0; i < Math.max(na.length, nb.length); i++) {
        const diff = (nb[i] || 0) - (na[i] || 0);
        if (diff !== 0) return diff;
      }
      return 0;
    });
  } catch {
    return [];
  }
}
