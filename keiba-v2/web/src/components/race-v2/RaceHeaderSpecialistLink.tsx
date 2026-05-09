/**
 * 出走表ヘッダー直下に置く Specialist 画面への小さいリンク行 (Server Component)
 *
 * スペシャリストモデルが適用されたレースのみ、タイトル近くに目立つように表示。
 * 詳細(推奨Top3)は NiigataChokuBanner で別途表示。ここはあくまで「導線」。
 *
 * 将来的に複数モデル該当時はカンマ区切りで列挙する想定。
 */

import Link from 'next/link';
import { getNiigataChokuOverlay } from '@/lib/data/niigata1000-overlay-reader';

interface Props {
  raceId16: string;
  date: string;  // YYYY-MM-DD
}

export function RaceHeaderSpecialistLink({ raceId16, date }: Props) {
  const niigataSummary = getNiigataChokuOverlay(raceId16, date);

  // 適用 specialist が無ければ非表示
  const tags: { id: string; label: string }[] = [];
  if (niigataSummary?.applied) {
    tags.push({ id: 'niigata1000', label: '🌪 千直' });
  }
  if (tags.length === 0) return null;

  return (
    <div className="mx-4 -mt-2 mb-2 flex items-center gap-2 flex-wrap">
      <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-700">
        Specialist Model:
      </span>
      {tags.map((t) => (
        <span
          key={t.id}
          className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700 border border-indigo-200"
        >
          {t.label}
        </span>
      ))}
      <Link
        href={`/specialist/${raceId16}`}
        target="_blank"
        rel="noopener noreferrer"
        className="text-xs font-bold px-3 py-1 rounded-full bg-indigo-600 text-white hover:bg-indigo-700 transition-colors shadow-sm"
      >
        ⭐ 専用予想画面 →
      </Link>
    </div>
  );
}
