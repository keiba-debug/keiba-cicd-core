/**
 * 発信者(調教師)信頼度 reader
 * comment_llm/commenters/_quant_trainer.json (gap降順の素の配列・キーは調教師フルネーム) を
 * masters/trainers.json (JRA-VAN code→フルネーム) で突合し、調教師コード→指標 のマップに変換する。
 *
 * ★結合キーは trainer_code(JRA-VAN 5桁)★。出馬表の entry_data.trainer は "栗藤野" 形式(東西略号+苗字)で
 * _quant のフルネーム "藤野健太" と一致しないため、code 経由でなければ結合できない。
 *
 * 出馬表(races-v2)の AIコメント印(markSet=4) の併記バッジで使用。表示専用・買い目には影響しない。
 * gap_pt = 強気コメント時の複勝圏率が「人気で期待される水準」をどれだけ上回るか(pt)。
 *   大 = 強気が結果に連動＝信頼できる発信者 / 0付近・負 = 結果と無関係な"オオカミ少年"。
 *   in-sample 約6ヶ月の参考値（個別順位は過信しない）。
 */
import fs from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';

export interface TrainerTrustEntry {
  name: string;
  gap_pt: number;
  z: number;
  n_strong: number;
  strong_place: number;
  strong_rate_of_all: number;
}

interface QuantRow extends TrainerTrustEntry {
  name: string;
}

/** 調教師コード(JRA-VAN 5桁) → 信頼度指標 のマップを返す。ファイルが無ければ null。 */
export function getTrainerTrustMap(): Record<string, TrainerTrustEntry> | null {
  try {
    const quantPath = path.join(DATA3_ROOT, 'comment_llm', 'commenters', '_quant_trainer.json');
    const masterPath = path.join(DATA3_ROOT, 'masters', 'trainers.json');
    if (!fs.existsSync(quantPath) || !fs.existsSync(masterPath)) return null;

    const rows = JSON.parse(fs.readFileSync(quantPath, 'utf-8')) as QuantRow[];
    const master = JSON.parse(fs.readFileSync(masterPath, 'utf-8')) as { code: string; name: string }[];
    if (!Array.isArray(rows) || !Array.isArray(master)) return null;

    // フルネーム → JRA-VAN code (master)
    const nameToCode: Record<string, string> = {};
    for (const m of master) {
      if (m && typeof m.name === 'string' && typeof m.code === 'string') nameToCode[m.name] = m.code;
    }

    // code → 信頼度指標
    const map: Record<string, TrainerTrustEntry> = {};
    for (const r of rows) {
      if (!r || typeof r.name !== 'string') continue;
      const code = nameToCode[r.name];
      if (!code) continue; // master に無いフルネームは結合できない（退厩・表記揺れ等）→ バッジ無し
      map[code] = {
        name: r.name,
        gap_pt: r.gap_pt,
        z: r.z,
        n_strong: r.n_strong,
        strong_place: r.strong_place,
        strong_rate_of_all: r.strong_rate_of_all,
      };
    }
    return map;
  } catch {
    return null;
  }
}
