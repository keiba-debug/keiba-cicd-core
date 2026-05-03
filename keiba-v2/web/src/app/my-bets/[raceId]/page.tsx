/**
 * My印からの推奨買い目画面
 *
 * 出走表ヘッダーの「My印買い目」ボタンから新規タブで開く。
 * 戦略タブで複数戦略の結果を比較し、TARGET FFCSV出力できる。
 */

import { Suspense } from 'react';
import { notFound } from 'next/navigation';
import MyBetsView from '@/components/my-bets/MyBetsView';

export const dynamic = 'force-dynamic';

interface PageProps {
  params: Promise<{ raceId: string }>;
  searchParams: Promise<{ markSet?: string }>;
}

export default async function Page({ params, searchParams }: PageProps) {
  const { raceId } = await params;
  const { markSet: markSetParam } = await searchParams;
  const markSet = parseInt(markSetParam ?? '1', 10);

  if (!/^\d{16}$/.test(raceId)) {
    notFound();
  }

  return (
    <div className="container mx-auto p-4 max-w-7xl">
      <Suspense fallback={<div className="text-muted-foreground">読み込み中...</div>}>
        <MyBetsView raceId={raceId} markSet={markSet} />
      </Suspense>
    </div>
  );
}
