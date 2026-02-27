import { promises as fs } from 'fs';
import path from 'path';
import { KEIBA_DATA_ROOT } from '@/lib/config';
import type { SimulationData } from '@/app/analysis/simulation/types';

export async function getSimulationResult(): Promise<SimulationData | null> {
  const filePath = path.join(KEIBA_DATA_ROOT, 'ml', 'bankroll_simulation.json');
  try {
    const raw = await fs.readFile(filePath, 'utf-8');
    return JSON.parse(raw) as SimulationData;
  } catch {
    return null;
  }
}
