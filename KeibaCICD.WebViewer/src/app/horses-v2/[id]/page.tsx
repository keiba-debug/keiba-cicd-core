/**
 * 馬プロフィールページ（v2 新方式）
 * JSON → 直接レンダリング
 */

import { notFound } from 'next/navigation';
import { Metadata } from 'next';
import Link from 'next/link';
import { getIntegratedHorseData } from '@/lib/data/integrated-horse-reader';
import { 
  HorseHeader, 
  HorsePastRacesTable, 
  HorseStatsSection,
  HorseUserMemo,
} from '@/components/horse-v2';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { HorseRaceSelector } from '@/components/horse-race-selector';

interface PageParams {
  params: Promise<{
    id: string;
  }>;
}

export async function generateMetadata({ params }: PageParams): Promise<Metadata> {
  const { id } = await params;
  const horseData = await getIntegratedHorseData(id);
  
  if (!horseData) {
    return { title: '馬が見つかりません' };
  }
  
  const { basic } = horseData;
  const title = basic.name || `馬ID: ${id}`;
  
  return {
    title: `${title} | KeibaCICD`,
    description: `${title} ${basic.age} - プロフィール・過去成績`,
  };
}

export default async function HorseProfileV2Page({ params }: PageParams) {
  const { id } = await params;
  const horseData = await getIntegratedHorseData(id);
  
  if (!horseData) {
    notFound();
  }

  const { basic, pastRaces, stats, userMemo } = horseData;

  // 過去レースをHorseRaceSelector形式に変換
  const selectorRaces = pastRaces.slice(0, 20).map(race => ({
    date: race.date,
    track: race.track,
    raceName: race.raceName,
    raceNumber: race.raceNumber,
    result: race.finishPosition,
    distance: race.distance,
    umaban: String(race.horseNumber),
  }));

  return (
    <div className="min-h-screen bg-background">
      <div className="container py-6 max-w-7xl">
        {/* パンくずリスト */}
        <nav className="flex items-center space-x-2 text-sm text-muted-foreground mb-4">
          <Link href="/" className="hover:underline">
            トップ
          </Link>
          <span>/</span>
          <Link href="/horses" className="hover:underline">
            馬検索
          </Link>
          <span>/</span>
          <span className="text-foreground">{basic.name || `馬ID: ${id}`}</span>
        </nav>

        {/* ヘッダー */}
        <HorseHeader basic={basic} />

        {/* 外部リンク（上部） */}
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <span className="text-sm text-muted-foreground">外部リンク:</span>
          <div className="flex flex-wrap items-center gap-1">
            <a
              href={`https://p.keibabook.co.jp/db/uma/${id}/kanzen`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 px-2 py-1 text-sm bg-muted hover:bg-muted/80 rounded transition-colors"
            >
              <img src="/keibabook.ico" alt="" className="w-4 h-4" />
              完全成績
            </a>
            <a
              href={`https://p.keibabook.co.jp/db/uma/${id}/crireki`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 px-2 py-1 text-sm bg-muted hover:bg-muted/80 rounded transition-colors"
            >
              <img src="/keibabook.ico" alt="" className="w-4 h-4" />
              調教履歴
            </a>
          </div>
        </div>

        <Separator className="my-6" />

        {/* 成績統計 */}
        <HorseStatsSection stats={stats} />

        <Separator className="my-6" />

        {/* 過去レース映像比較 */}
        {selectorRaces.length > 0 && (
          <>
            <HorseRaceSelector 
              horseId={id}
              horseName={basic.name} 
              pastRaces={selectorRaces} 
            />
            <Separator className="my-6" />
          </>
        )}

        {/* 過去レース成績テーブル */}
        <HorsePastRacesTable races={pastRaces} />

        <Separator className="my-6" />

        {/* ユーザーメモ */}
        <HorseUserMemo horseId={id} horseName={basic.name} initialMemo={userMemo} />

        {/* フッター情報 */}
        <div className="mt-8 pt-4 border-t text-sm text-gray-500 dark:text-gray-400">
          <div className="flex flex-wrap gap-4">
            <span>馬ID: {basic.id}</span>
            {basic.updatedAt && <span>最終更新: {basic.updatedAt}</span>}
            <span>収集レース数: {pastRaces.length}</span>
          </div>
        </div>

        {/* 戻るボタン */}
        <div className="mt-8 flex gap-4">
          <Button variant="outline" asChild>
            <Link href="/">← レース一覧に戻る</Link>
          </Button>
          <Button variant="outline" asChild>
            <Link href="/horses">🔍 馬検索に戻る</Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
