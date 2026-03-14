import { promises as fs } from 'fs';
import path from 'path';
import { KEIBA_DATA_ROOT } from '@/lib/config';

const FILENAME = 'formation_backtest.json';

export async function getFormationBacktest(): Promise<unknown | null> {
  const filePath = path.join(KEIBA_DATA_ROOT, 'ml', FILENAME);
  try {
    const raw = await fs.readFile(filePath, 'utf-8');
    return JSON.parse(raw);
  } catch {
    return null;
  }
}
