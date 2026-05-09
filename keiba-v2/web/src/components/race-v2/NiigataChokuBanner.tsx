/**
 * 出走表ページ (/races-v2/...) 用 千直バナー (Server Component)
 *
 * 千直開催時のみ表示するコンパクトな情報帯。
 * - 「千直」バッジ + コース事典/全データ/オッズ画面リンク
 * - 推奨上位3頭サマリー (除外馬を除く)
 */

import Link from 'next/link';
import { getNiigataChokuOverlay } from '@/lib/data/niigata1000-overlay-reader';

interface Props {
  raceId16: string;
  date: string;  // YYYY-MM-DD
}

export function NiigataChokuBanner({ raceId16, date }: Props) {
  const summary = getNiigataChokuOverlay(raceId16, date);
  if (!summary || !summary.applied) return null;

  const top3 = summary.ranked
    .filter((r) => !r.overlay.is_rejected)
    .slice(0, 3);

  return (
    <div className="rounded-xl border-2 border-blue-200 bg-gradient-to-br from-blue-50 via-indigo-50/40 to-white px-4 py-3 mb-4 mx-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-bold px-2 py-0.5 rounded bg-blue-600 text-white">千直</span>
          <span className="text-sm font-bold text-blue-900">vega-niigata1000 ルール補正</span>
          <span className="text-[11px] text-gray-500">
            (新潟芝1000m直線・polaris+rule v0.2)
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs flex-wrap">
          <Link
            href={`/specialist/${raceId16}`}
            target="_blank"
            rel="noopener noreferrer"
            className="px-2.5 py-1 rounded bg-indigo-600 text-white hover:bg-indigo-700 font-bold"
          >
            ⭐ 専用予想画面 →
          </Link>
          <Link
            href="/analysis/specialists/niigata-1000m"
            target="_blank"
            rel="noopener noreferrer"
            className="px-2 py-1 rounded bg-white border border-blue-200 text-blue-700 hover:bg-blue-50"
          >
            コース事典 →
          </Link>
          <Link
            href="/analysis/specialists/niigata-1000m?tab=data"
            target="_blank"
            rel="noopener noreferrer"
            className="px-2 py-1 rounded bg-white border border-blue-200 text-blue-700 hover:bg-blue-50"
          >
            全データ →
          </Link>
          <Link
            href={`/odds-race/${raceId16}`}
            target="_blank"
            rel="noopener noreferrer"
            className="px-2 py-1 rounded bg-blue-600 text-white hover:bg-blue-700 font-bold"
          >
            オッズ画面 千直タブ →
          </Link>
        </div>
      </div>

      {top3.length > 0 && (
        <div className="mt-2.5 flex flex-wrap items-center gap-2">
          <span className="text-[10px] font-bold uppercase tracking-wider text-blue-700">
            補正後 推奨
          </span>
          {top3.map((r, i) => {
            const delta = r.overlay.delta_p * 100;
            return (
              <div
                key={r.umaban}
                className="flex items-center gap-1.5 text-xs bg-white border border-blue-200 rounded-full px-2.5 py-1"
              >
                <span className="text-[10px] font-bold text-gray-400">#{i + 1}</span>
                <span className="text-[10px] text-gray-500">
                  {r.overlay.wakuban ?? '?'}枠{r.umaban}番
                </span>
                <span className="font-bold">{r.horseName}</span>
                <span className="font-mono text-blue-700 font-bold">
                  {(r.overlay.display_score * 100).toFixed(1)}%
                </span>
                <span
                  className={`font-mono text-[10px] ${
                    delta > 0 ? 'text-emerald-600' : delta < 0 ? 'text-orange-600' : 'text-gray-400'
                  }`}
                >
                  ({delta > 0 ? '+' : ''}
                  {delta.toFixed(1)})
                </span>
              </div>
            );
          })}
          <span className="text-[10px] text-gray-400 ml-auto">
            {summary.ranked.filter((r) => r.overlay.is_rejected).length} 頭除外推奨 / 全
            {summary.ranked.length}頭
          </span>
        </div>
      )}
    </div>
  );
}
