import { promises as fs } from 'fs';
import path from 'path';
import { KEIBA_DATA_ROOT } from '@/lib/config';

const FILENAME = 'edge_validation.json';

/**
 * gap5単勝エッジの検証結果を読み込む (SoT = data3/ml/edge_validation.json)。
 * 生成元: python -m ml.export_edge_validation
 * 正本ドキュメント: docs/market_calibration_edge_map.md
 */
export async function getEdgeValidation(): Promise<unknown | null> {
  const filePath = path.join(KEIBA_DATA_ROOT, 'ml', FILENAME);
  try {
    const raw = await fs.readFile(filePath, 'utf-8');
    return JSON.parse(raw);
  } catch {
    return null;
  }
}
