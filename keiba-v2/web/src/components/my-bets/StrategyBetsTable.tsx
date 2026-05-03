'use client';

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { BetCandidate, BET_TYPE_LABEL } from './types';

interface Props {
  bets: BetCandidate[];
  horseNames: Record<number, string>;
}

const MARK_COLOR: Record<string, string> = {
  '◎': 'bg-red-500 text-white',
  '○': 'bg-blue-500 text-white',
  '▲': 'bg-green-600 text-white',
  '△': 'bg-yellow-500 text-black',
  '★': 'bg-purple-500 text-white',
  '穴': 'bg-pink-600 text-white',
};

function MarkBadge({ mark }: { mark: string }) {
  if (!mark) return <span className="text-muted-foreground">-</span>;
  const cls = MARK_COLOR[mark] ?? 'bg-gray-500 text-white';
  return (
    <span
      className={`inline-flex items-center justify-center w-5 h-5 text-xs rounded ${cls}`}
    >
      {mark}
    </span>
  );
}

function HorseCell({
  horses,
  marks,
  names,
}: {
  horses: number[];
  marks: string[];
  names: Record<number, string>;
}) {
  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      {horses.map((u, idx) => (
        <span key={idx} className="inline-flex items-center gap-0.5">
          <MarkBadge mark={marks[idx] ?? ''} />
          <span className="font-mono text-sm">{u}</span>
          <span className="text-xs text-muted-foreground">
            {names[u] ?? ''}
          </span>
          {idx < horses.length - 1 && (
            <span className="text-muted-foreground">→</span>
          )}
        </span>
      ))}
    </div>
  );
}

function evClass(ev: number): string {
  if (ev >= 3.0) return 'text-red-600 font-bold';
  if (ev >= 2.0) return 'text-orange-600 font-semibold';
  if (ev >= 1.5) return 'text-amber-700 font-semibold';
  if (ev >= 1.0) return 'text-emerald-700';
  return 'text-muted-foreground';
}

export default function StrategyBetsTable({ bets, horseNames }: Props) {
  if (bets.length === 0) {
    return (
      <div className="text-sm text-muted-foreground py-4">
        条件を満たす買い目がありません
      </div>
    );
  }
  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-20">券種</TableHead>
            <TableHead>馬番</TableHead>
            <TableHead className="text-right w-20">確率</TableHead>
            <TableHead className="text-right w-20">オッズ</TableHead>
            <TableHead className="text-right w-20">EV</TableHead>
            <TableHead className="text-right w-20">金額</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {bets.map((b, idx) => (
            <TableRow key={idx}>
              <TableCell>
                <Badge variant="outline">{BET_TYPE_LABEL[b.betType]}</Badge>
              </TableCell>
              <TableCell>
                <HorseCell
                  horses={b.horses}
                  marks={b.marks}
                  names={horseNames}
                />
              </TableCell>
              <TableCell className="text-right font-mono text-sm">
                {(b.probability * 100).toFixed(2)}%
              </TableCell>
              <TableCell className="text-right font-mono text-sm">
                {b.odds.toFixed(1)}
              </TableCell>
              <TableCell className={`text-right font-mono ${evClass(b.ev)}`}>
                {b.ev.toFixed(2)}
              </TableCell>
              <TableCell className="text-right font-mono text-sm font-semibold">
                ¥{(b.stake ?? 0).toLocaleString()}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
