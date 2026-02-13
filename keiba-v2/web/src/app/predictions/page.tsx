import { getPredictionsLive } from '@/lib/data/predictions-reader';
import { PredictionsContent } from './predictions-content';

export const metadata = { title: '当日ML予測一覧 | KeibaCICD' };
export const dynamic = 'force-dynamic';

export default function PredictionsPage() {
  const data = getPredictionsLive();

  if (!data) {
    return (
      <div className="py-12 text-center text-muted-foreground">
        <h1 className="text-2xl font-bold mb-4">ML予測データなし</h1>
        <p>predictions_live.json が見つかりません。管理画面からML予測を実行してください。</p>
      </div>
    );
  }

  return <PredictionsContent data={data} />;
}
