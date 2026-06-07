/**
 * 馬別 印履歴セクション (My印 / AI総合 / AI直前 / B本紙 / Bパドック)
 *
 * その馬の過去レースで付いていた各種印を着順と並べて時系列表示する。
 * 表示専用。 いずれかの印があるレースが無ければ何も描画しない。
 */

import type { HorseMarksHistory, HorseMarkHistoryEntry, HorseMarksReliability } from '@/lib/data/horse-marks-history-reader';

// 印 → 表示スタイル
const MARK_STYLE: Record<string, string> = {
  '◎': 'bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300 border-rose-300 dark:border-rose-800',
  '○': 'bg-orange-100 text-orange-700 dark:bg-orange-950/40 dark:text-orange-300 border-orange-300 dark:border-orange-800',
  '▲': 'bg-blue-100 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300 border-blue-300 dark:border-blue-800',
  '△': 'bg-teal-100 text-teal-700 dark:bg-teal-950/40 dark:text-teal-300 border-teal-300 dark:border-teal-800',
  'Ⅲ': 'bg-violet-100 text-violet-700 dark:bg-violet-950/40 dark:text-violet-300 border-violet-300 dark:border-violet-800',
  '穴': 'bg-amber-100 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300 border-amber-300 dark:border-amber-800',
  '消': 'bg-gray-100 text-gray-400 line-through dark:bg-gray-800 dark:text-gray-500 border-gray-300 dark:border-gray-700',
  '◆': 'bg-purple-100 text-purple-800 dark:bg-purple-950/40 dark:text-purple-300 border-purple-300 dark:border-purple-800',
  '◇': 'bg-fuchsia-100 text-fuchsia-700 dark:bg-fuchsia-950/40 dark:text-fuchsia-300 border-fuchsia-300 dark:border-fuchsia-800',
  'S': 'bg-amber-200 text-amber-900 dark:bg-amber-500/40 dark:text-amber-200 border-amber-400 dark:border-amber-600',
  'A': 'bg-emerald-200 text-emerald-900 dark:bg-emerald-500/40 dark:text-emerald-200 border-emerald-500 dark:border-emerald-600',
  'B': 'bg-sky-200 text-sky-900 dark:bg-sky-500/40 dark:text-sky-200 border-sky-500 dark:border-sky-600',
};

function MarkChip({ mark }: { mark: string }) {
  if (!mark) return <span className="text-gray-300 dark:text-gray-600">–</span>;
  const style = MARK_STYLE[mark] || 'bg-gray-100 text-gray-600 border-gray-300 dark:bg-gray-800 dark:text-gray-300';
  return (
    <span className={`inline-flex h-6 min-w-6 px-0.5 items-center justify-center rounded border text-sm font-bold ${style}`}>
      {mark}
    </span>
  );
}

function finishStyle(n: number): string {
  if (n === 1) return 'text-amber-600 font-bold';
  if (n === 2) return 'text-gray-500 font-semibold';
  if (n === 3) return 'text-orange-700 font-semibold';
  return 'text-muted-foreground';
}

function ReliabilityChip({ label, rel, accent }: { label: string; rel: HorseMarksReliability; accent: string }) {
  if (rel.races === 0) return null;
  const top3Rate = Math.round((rel.top3 / rel.races) * 100);
  return (
    <div className={`rounded-lg border px-3 py-1.5 text-xs ${accent}`}>
      <span className="font-semibold">{label}</span>
      <span className="ml-2">印付 {rel.races}走 → 3着内 {rel.top3} ({top3Rate}%) / 勝 {rel.win}</span>
    </div>
  );
}

function Row({ e }: { e: HorseMarkHistoryEntry }) {
  return (
    <tr className="border-b last:border-0 hover:bg-muted/40 transition-colors">
      <td className="px-2 py-2 whitespace-nowrap text-muted-foreground tabular-nums">{e.date}</td>
      <td className="px-2 py-2 whitespace-nowrap">{e.track}{e.raceNumber}R</td>
      <td className="px-2 py-2 max-w-[12rem] truncate" title={e.raceName}>
        <span className="text-muted-foreground">{e.distance && `${e.distance} `}</span>
        {e.raceName || '—'}
      </td>
      <td className="px-2 py-2 text-center tabular-nums">{e.umaban}</td>
      <td className="px-2 py-2 text-center">
        <span className={`tabular-nums ${finishStyle(e.finishNum)}`}>
          {e.finishNum > 0 ? `${e.finishNum}着` : (e.finishPosition || '—')}
        </span>
      </td>
      <td className="px-2 py-2 text-center"><MarkChip mark={e.myMark} /></td>
      <td className="px-2 py-2 text-center"><MarkChip mark={e.aiMark} /></td>
      <td className="px-2 py-2 text-center"><MarkChip mark={e.aiBuyMark} /></td>
      <td className="px-2 py-2 text-center"><MarkChip mark={e.honshiMark} /></td>
      <td className="px-2 py-2 text-center"><MarkChip mark={e.paddockMark} /></td>
      <td className="px-2 py-2 max-w-[10rem] text-xs text-muted-foreground" title={e.shortComment || undefined}>
        <span className="line-clamp-2">{e.shortComment || '–'}</span>
      </td>
    </tr>
  );
}

export function HorseMarksHistory({ history }: { history: HorseMarksHistory }) {
  // 印のあるレースが無ければセクションごと非表示 (ページを汚さない)
  if (history.entries.length === 0) return null;

  return (
    <div className="max-w-7xl">
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <h2 className="text-lg font-bold flex items-center gap-2">
          🎯 印履歴
          <span className="text-sm font-normal text-muted-foreground">各印と着順</span>
        </h2>
        <ReliabilityChip
          label="My印"
          rel={history.my}
          accent="border-rose-200 bg-rose-50 text-rose-800 dark:border-rose-900 dark:bg-rose-950/20 dark:text-rose-300"
        />
        <ReliabilityChip
          label="AI総合"
          rel={history.ai}
          accent="border-blue-200 bg-blue-50 text-blue-800 dark:border-blue-900 dark:bg-blue-950/20 dark:text-blue-300"
        />
        <ReliabilityChip
          label="AI直前"
          rel={history.aiBuy}
          accent="border-purple-200 bg-purple-50 text-purple-800 dark:border-purple-900 dark:bg-purple-950/20 dark:text-purple-300"
        />
        <ReliabilityChip
          label="B本紙"
          rel={history.honshi}
          accent="border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/20 dark:text-emerald-300"
        />
        <ReliabilityChip
          label="Bパドック"
          rel={history.paddock}
          accent="border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950/20 dark:text-amber-300"
        />
      </div>

      <div className="overflow-x-auto rounded-xl border bg-card shadow-sm">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50 text-xs text-muted-foreground">
              <th className="px-2 py-2 text-left font-medium">日付</th>
              <th className="px-2 py-2 text-left font-medium">開催</th>
              <th className="px-2 py-2 text-left font-medium">レース</th>
              <th className="px-2 py-2 text-center font-medium">馬番</th>
              <th className="px-2 py-2 text-center font-medium">着順</th>
              <th className="px-2 py-2 text-center font-medium">My印</th>
              <th className="px-2 py-2 text-center font-medium" title="AI総合評価印 (markSet2)">AI総合</th>
              <th className="px-2 py-2 text-center font-medium" title="AI直前評価印 (markSet3: ◆買い軸 / ◇相手)">AI直前</th>
              <th className="px-2 py-2 text-center font-medium" title="競馬ブック本紙印">B本紙</th>
              <th className="px-2 py-2 text-center font-medium" title="競馬ブック パドック評価 (S/A/B 等)">Bパドック</th>
              <th className="px-2 py-2 text-left font-medium min-w-24" title="競馬ブック短評 (kb_ext)">短評</th>
            </tr>
          </thead>
          <tbody>
            {history.entries.map((e) => (
              <Row key={`${e.raceId}-${e.umaban}`} e={e} />
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-2 text-[11px] text-muted-foreground">
        ※ My印・AI総合・AI直前は TARGET 馬印 (markSet1/2/3)。B本紙・Bパドック・短評は競馬ブック (kb_ext)。
        いずれかの印が付いたレースのみ表示。信頼性は各印種の対象印付き走の 3着内率 (参考値)。
      </p>
    </div>
  );
}
