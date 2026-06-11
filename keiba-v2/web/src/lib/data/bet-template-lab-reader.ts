import { promises as fs } from 'fs';
import path from 'path';
import { KEIBA_DATA_ROOT } from '@/lib/config';

const FILENAME = 'bet_template_lab.json';

/**
 * 買い方ラボ backtest 結果を読み込む (SoT = data3/ml/bet_template_lab.json)。
 * 生成元: python -m ml.export_bet_template_lab
 * version指定時はアーカイブ (versions/v{version}/) から読み込み。
 */
export async function getBetTemplateLab(version?: string | null): Promise<unknown | null> {
  const filePath = version
    ? path.join(KEIBA_DATA_ROOT, 'ml', 'versions', `v${version}`, FILENAME)
    : path.join(KEIBA_DATA_ROOT, 'ml', FILENAME);
  try {
    const raw = await fs.readFile(filePath, 'utf-8');
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

/**
 * bet_template_lab.json が存在するバージョン一覧を返す（新しい順）
 */
export async function getBetTemplateLabVersions(): Promise<string[]> {
  const versionsDir = path.join(KEIBA_DATA_ROOT, 'ml', 'versions');
  try {
    const entries = await fs.readdir(versionsDir, { withFileTypes: true });
    const versions: string[] = [];
    for (const entry of entries) {
      if (entry.isDirectory() && entry.name.startsWith('v')) {
        const fp = path.join(versionsDir, entry.name, FILENAME);
        try {
          await fs.access(fp);
          versions.push(entry.name.slice(1));
        } catch {
          // no lab file in this version
        }
      }
    }
    return versions.sort((a, b) => {
      const na = a.split(/[.-]/).map(s => parseInt(s) || 0);
      const nb = b.split(/[.-]/).map(s => parseInt(s) || 0);
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
