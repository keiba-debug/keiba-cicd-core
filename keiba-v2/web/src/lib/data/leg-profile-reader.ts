/**
 * 脚質・能力プロファイル reader (Regulus leg_profile.py が emit する leg_profiles.json を読む)
 * races/YYYY/MM/DD/leg_profiles.json = { race_id(16桁): { umaban: LegProfile } }
 * 出走表(races-v2)の展開予想タブ等で使用。表示専用・買い目には影響しない。
 */
import fs from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';
import type { LegProfile } from './predictions-reader';

export type { LegProfile };

/** 指定レース(16桁race_id)の馬番→脚質プロファイル を返す。無ければ null。 */
export function getLegProfilesForRace(
  date: string,
  raceId16: string,
): Record<number, LegProfile> | null {
  try {
    const [y, m, d] = date.split('-');
    if (!y || !m || !d) return null;
    const filePath = path.join(DATA3_ROOT, 'races', y, m, d, 'leg_profiles.json');
    if (!fs.existsSync(filePath)) return null;
    const byRace = JSON.parse(fs.readFileSync(filePath, 'utf-8')) as Record<string, Record<string, LegProfile>>;
    const per = byRace[raceId16];
    if (!per) return null;
    const out: Record<number, LegProfile> = {};
    for (const [uma, lp] of Object.entries(per)) {
      out[Number(uma)] = lp;
    }
    return out;
  } catch {
    return null;
  }
}
