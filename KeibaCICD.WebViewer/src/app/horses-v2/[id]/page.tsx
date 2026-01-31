/**
 * 馬プロフィールページ（v2 新方式）
 * JSON → 直接レンダリング
 */

import { notFound } from 'next/navigation';
import { Metadata } from 'next';
import Link from 'next/link';
import { getIntegratedHorseData } from '@/lib/data/integrated-horse-reader';
import { getHorseCommentByName } from '@/lib/data/target-comment-reader';
import { 
  HorseHeader, 
  HorsePastRacesTable, 
  HorseStatsSection,
  HorseUserMemo,
  HorseAnalysisSection,
} from '@/components/horse-v2';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { HorseRaceSelector } from '@/components/horse-race-selector';
import { analyzeHorse } from '@/lib/horse-analyzer';
import { MessageSquareText } from 'lucide-react';

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
  const horseName = basic.name || `馬ID: ${id}`;
  
  return {
    title: `${horseName} (馬情報)`,
    description: `${horseName} ${basic.age} - プロフィール・過去成績`,
  };
}

export default async function HorseProfileV2Page({ params }: PageParams) {
  const { id } = await params;
  const horseData = await getIntegratedHorseData(id);
  
  if (!horseData) {
    notFound();
  }

  const { basic, pastRaces, stats, userMemo } = horseData;

  // TARGETの馬コメントを取得（馬名からkettoNumを検索）
  const targetComment = getHorseCommentByName(basic.name);

  // 馬分析を実行
  const analysis = analyzeHorse(pastRaces, stats);

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

        {/* ヘッダー（トレンドインジケーター付き） */}
        <HorseHeader basic={basic} recentRaces={pastRaces.slice(0, 5)} />

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
              <span className="text-sm">📖</span>
              完全成績
            </a>
            <a
              href={`https://p.keibabook.co.jp/db/uma/${id}/crireki`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 px-2 py-1 text-sm bg-muted hover:bg-muted/80 rounded transition-colors"
            >
              <span className="text-sm">📊</span>
              調教履歴
            </a>
            {basic.trainerLink && (
              <a
                href={basic.trainerLink}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 px-2 py-1 text-sm bg-muted hover:bg-muted/80 rounded transition-colors"
              >
                <span className="text-sm">🏇</span>
                厩舎情報
              </a>
            )}
          </div>
        </div>

        <Separator className="my-6" />

        {/* 成績統計 */}
        <HorseStatsSection stats={stats} />

        <Separator className="my-6" />

        {/* 分析セクション */}
        <HorseAnalysisSection analysis={analysis} />

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

        {/* TARGETコメント（読み取り専用） */}
        {targetComment && (
          <>
            <Card className="border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-950/20">
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-base">
                  <MessageSquareText className="w-4 h-4 text-amber-600" />
                  TARGETメモ
                  <span className="text-xs font-normal text-muted-foreground">（読み取り専用）</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="whitespace-pre-wrap text-sm">{targetComment.comment}</p>
              </CardContent>
            </Card>
            <Separator className="my-6" />
          </>
        )}

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
