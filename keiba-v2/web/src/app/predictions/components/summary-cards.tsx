import { Card, CardContent } from '@/components/ui/card';

interface SummaryCardsProps {
  totalRaces: number;
  totalEntries: number;
  totalVB: number;
  betCount: number;
  betTotalAmount: number;
  hasBets: boolean;
  venueNames: string[];
}

export function SummaryCards({ totalRaces, totalEntries, totalVB, betCount, betTotalAmount, hasBets, venueNames }: SummaryCardsProps) {
  return (
    <div id="section-summary" className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
      <Card>
        <CardContent className="pt-4 pb-3 text-center">
          <div className="text-3xl font-bold">{totalRaces}</div>
          <div className="text-xs text-muted-foreground">レース</div>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="pt-4 pb-3 text-center">
          <div className="text-3xl font-bold">{totalEntries}</div>
          <div className="text-xs text-muted-foreground">出走頭数</div>
        </CardContent>
      </Card>
      <Card className="border-amber-200 dark:border-amber-800">
        <CardContent className="pt-4 pb-3 text-center">
          <div className="text-3xl font-bold text-amber-600">{totalVB}</div>
          <div className="text-xs text-muted-foreground">VB候補 (gap&ge;3)</div>
        </CardContent>
      </Card>
      <Card className="border-indigo-200 dark:border-indigo-800">
        <CardContent className="pt-4 pb-3 text-center">
          <div className={`text-3xl font-bold ${hasBets ? 'text-indigo-600' : 'text-muted-foreground'}`}>
            {hasBets ? betCount : '-'}
          </div>
          <div className="text-xs text-muted-foreground">bet推奨</div>
          {hasBets && betTotalAmount > 0 && (
            <div className="text-[10px] text-muted-foreground mt-0.5">
              &yen;{betTotalAmount.toLocaleString()}
            </div>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardContent className="pt-4 pb-3 text-center">
          <div className="text-3xl font-bold">{venueNames.join(' / ')}</div>
          <div className="text-xs text-muted-foreground">開催場</div>
        </CardContent>
      </Card>
    </div>
  );
}
