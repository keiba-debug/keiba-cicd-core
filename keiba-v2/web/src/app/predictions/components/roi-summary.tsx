import { Card, CardContent } from '@/components/ui/card';

interface TrackROIStats {
  vbCount: number;
  winHits: number;
  placeHits: number;
  placeBetCount: number;
  winROI: number;
  placeROI: number;
  winProfit: number;
  placeProfit: number;
  hasAnyPlaceOdds: boolean;
}

interface RoiSummaryProps {
  composite: TrackROIStats;
  pick: TrackROIStats;
  vbCandidates: TrackROIStats;
}

function ROIRow({ label, s, badgeClass }: { label: string; s: TrackROIStats; badgeClass?: string }) {
  if (s.vbCount <= 0) return null;
  return (
    <div className="grid grid-cols-6 gap-2 text-center text-sm items-center py-1.5">
      <div className="text-left">
        {badgeClass ? (
          <span className={`px-2 py-0.5 rounded text-xs font-bold ${badgeClass}`}>{label}</span>
        ) : (
          <span className="text-xs font-bold">{label}</span>
        )}
      </div>
      <div>
        <div className="text-lg font-bold">{s.vbCount}</div>
      </div>
      <div>
        <div className="font-bold">{s.winHits}/{s.vbCount}</div>
      </div>
      <div>
        <div className={`font-bold ${s.winROI >= 100 ? 'text-green-600' : 'text-red-500'}`}>
          {s.winROI.toFixed(1)}%
        </div>
        <div className={`text-[10px] ${s.winProfit >= 0 ? 'text-green-600' : 'text-red-500'}`}>
          {s.winProfit >= 0 ? '+' : ''}&yen;{Math.round(s.winProfit).toLocaleString()}
        </div>
      </div>
      <div>
        <div className="font-bold">
          {s.hasAnyPlaceOdds ? `${s.placeHits}/${s.placeBetCount}` : '-'}
        </div>
      </div>
      <div>
        {s.hasAnyPlaceOdds ? (
          <>
            <div className={`font-bold ${s.placeROI >= 100 ? 'text-green-600' : 'text-red-500'}`}>
              {s.placeROI.toFixed(1)}%
            </div>
            <div className={`text-[10px] ${s.placeProfit >= 0 ? 'text-green-600' : 'text-red-500'}`}>
              {s.placeProfit >= 0 ? '+' : ''}&yen;{Math.round(s.placeProfit).toLocaleString()}
            </div>
          </>
        ) : <div className="text-muted-foreground">-</div>}
      </div>
    </div>
  );
}

export function RoiSummary({ composite, pick, vbCandidates }: RoiSummaryProps) {
  return (
    <Card id="section-roi" className="mb-6 border-blue-200 dark:border-blue-800">
      <CardContent className="py-4">
        <div className="flex items-center gap-2 mb-3">
          <span className="font-bold text-sm">注目馬 成績サマリー</span>
          <span className="text-xs text-muted-foreground">結果反映済</span>
        </div>
        <div className="grid grid-cols-6 gap-2 text-center text-[10px] text-muted-foreground border-b pb-1 mb-1">
          <div className="text-left">区分</div>
          <div>頭数</div>
          <div>単的中</div>
          <div>単勝ROI</div>
          <div>複的中</div>
          <div>複勝ROI</div>
        </div>
        <ROIRow label="総合1位" s={composite} badgeClass="bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300" />
        <ROIRow label="P1位" s={pick} badgeClass="bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300" />
        <ROIRow label="VB候補" s={vbCandidates} badgeClass="bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300" />
      </CardContent>
    </Card>
  );
}
