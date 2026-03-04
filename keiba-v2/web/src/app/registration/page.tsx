import { getRegistrationByDate, getAvailableRegistrationDates } from '@/lib/data/registration-reader';
import { RegistrationContent } from './registration-content';

interface PageProps {
  searchParams: Promise<{ date?: string }>;
}

export default async function RegistrationPage({ searchParams }: PageProps) {
  const params = await searchParams;
  const availableDates = getAvailableRegistrationDates();

  if (availableDates.length === 0) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-12 text-center">
        <h1 className="text-2xl font-bold mb-4">特別登録</h1>
        <p className="text-muted-foreground">
          特別登録データがありません。管理画面から「特別登録データ生成」を実行してください。
        </p>
      </div>
    );
  }

  const targetDate = params.date && availableDates.includes(params.date)
    ? params.date
    : availableDates[0];

  const data = getRegistrationByDate(targetDate);

  if (!data) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-12 text-center">
        <h1 className="text-2xl font-bold mb-4">特別登録</h1>
        <p className="text-muted-foreground">
          {targetDate} のデータが見つかりません。
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
      <RegistrationContent
        data={data}
        availableDates={availableDates}
        currentDate={targetDate}
      />
    </div>
  );
}
