import { getPredictionsLive, getPredictionsByDate, getAvailablePredictionDates, getResultsByDate, enrichPredictionsFromDb } from '@/lib/data/predictions-reader';
import { PredictionsContent } from './predictions-content';
import Link from 'next/link';

export const metadata = { title: 'Value Bet | KeibaCICD' };
export const dynamic = 'force-dynamic';

export default async function PredictionsPage({
  searchParams,
}: {
  searchParams: Promise<{ date?: string }>;
}) {
  const params = await searchParams;
  const dates = getAvailablePredictionDates();
  const targetDate = params.date || null;
  let data = targetDate ? getPredictionsByDate(targetDate) : getPredictionsLive();

  if (!data) {
    return (
      <div className="py-12 text-center text-muted-foreground">
        <h1 className="text-2xl font-bold mb-4">予測データなし</h1>
        <p>
          {targetDate
            ? `${targetDate} の予測アーカイブが見つかりません。`
            : 'predictions_live.json が見つかりません。管理画面から予測を実行してください。'}
        </p>
        {dates.length > 0 && (
          <div className="mt-6">
            <p className="text-sm mb-3">利用可能な予測アーカイブ:</p>
            <div className="flex flex-wrap gap-2 justify-center">
              {dates.slice(0, 10).map(d => (
                <Link
                  key={d}
                  href={`/predictions?date=${d}`}
                  className="px-3 py-1.5 rounded border bg-background hover:bg-muted text-sm"
                >
                  {d}
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  // Enrich missing track_type/distance from DB (RACE_SHOSAI)
  data = await enrichPredictionsFromDb(data);

  const results = getResultsByDate(data.date);

  return (
    <PredictionsContent
      data={data}
      availableDates={dates}
      currentDate={data.date}
      isArchive={!!targetDate}
      results={results}
    />
  );
}
