/**
 * 特別登録データリーダー
 * races/YYYY/MM/DD/registration.json を読み込む
 */

import fs from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';

// --- 型定義 ---

export interface RecentResult {
  race_code: string;
  date: string;
  venue: string;
  distance: number;
  track_type: string;
  finish: number | null;
  odds: number | null;
  grade: string;
  race_name: string;
}

export interface RegistrationEntry {
  renban: number;
  ketto_num: string;
  horse_name: string;
  sex: string;
  age: number | null;
  trainer_name: string;
  weight_carried: number;
  tozai: string;
  recent_results: RecentResult[];
}

export interface RegistrationRace {
  race_code: string;
  venue_name: string;
  venue_code: string;
  race_number: number;
  race_name: string;
  grade: string;
  distance: number;
  track_type: string;
  registered_count: number;
  entries: RegistrationEntry[];
}

export interface RegistrationData {
  date: string;
  created_at: string;
  source: string;
  total_races: number;
  total_entries: number;
  races: RegistrationRace[];
}

// --- リーダー関数 ---

const RACES_DIR = path.join(DATA3_ROOT, 'races');

export function getRegistrationByDate(date: string): RegistrationData | null {
  const [y, m, d] = date.split('-');
  const filePath = path.join(RACES_DIR, y, m, d, 'registration.json');

  if (!fs.existsSync(filePath)) {
    return null;
  }

  try {
    const raw = fs.readFileSync(filePath, 'utf-8');
    return JSON.parse(raw) as RegistrationData;
  } catch {
    return null;
  }
}

export function getAvailableRegistrationDates(): string[] {
  const dates: string[] = [];

  try {
    const years = fs.readdirSync(RACES_DIR).filter(f => /^\d{4}$/.test(f)).sort().reverse();

    for (const year of years) {
      const yearPath = path.join(RACES_DIR, year);
      const months = fs.readdirSync(yearPath).filter(f => /^\d{2}$/.test(f)).sort().reverse();

      for (const month of months) {
        const monthPath = path.join(yearPath, month);
        const days = fs.readdirSync(monthPath).filter(f => /^\d{2}$/.test(f)).sort().reverse();

        for (const day of days) {
          const regPath = path.join(monthPath, day, 'registration.json');
          if (fs.existsSync(regPath)) {
            dates.push(`${year}-${month}-${day}`);
          }
        }
      }

      if (dates.length >= 30) break;
    }
  } catch {
    // ignore
  }

  return dates;
}
