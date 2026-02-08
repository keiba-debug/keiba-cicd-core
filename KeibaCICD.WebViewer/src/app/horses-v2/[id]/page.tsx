/**
 * 馬プロフィールページ（v2 新方式）
 * JSON → 直接レンダリング
 */

import { notFound } from 'next/navigation';
import { Metadata } from 'next';
import Link from 'next/link';
import { getIntegratedHorseData } from '@/lib/data/integrated-horse-reader';
import { getHorseCommentByName, getKettoNumByName, getHorseComment } from '@/lib/data/target-comment-reader';
import { findKettoNumFromRecentTraining } from '@/lib/data/training-summary-reader';
import {
  HorseHeader,
  HorsePastRacesTable,
  HorseStatsSection,
  HorseCommentEditor,
  HorseAnalysisSection,
} from '@/components/horse-v2';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { RefreshButton } from '@/components/ui/refresh-button';
import { HorseRaceSelector } from '@/components/horse-race-selector';
import { analyzeHorse } from '@/lib/horse-analyzer';

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

  const { basic, pastRaces, stats } = horseData;

  // 馬名からkettoNumを取得（初出走馬はtraining_summaryからフォールバック）
  const kettoNum = getKettoNumByName(basic.name) || findKettoNumFromRecentTraining(basic.name) || '';
  
  // TARGETの馬コメントを取得
  const targetComment = kettoNum ? getHorseComment(kettoNum) : null;

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
    waku: race.frameNumber ? String(race.frameNumber) : undefined,
  }));

  return (
    <div className="min-h-screen bg-background">
      <div className="container py-6 max-w-7xl">
        {/* パンくずリスト + データ更新 */}
        <div className="flex items-center justify-between mb-4">
          <nav className="flex items-center space-x-2 text-sm text-muted-foreground">
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
          <RefreshButton size="sm" />
        </div>

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
            {kettoNum && (
              <a
                href={`https://db.netkeiba.com/horse/result/${kettoNum}/`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 px-2 py-1 text-sm bg-green-100 dark:bg-green-900/30 hover:bg-green-200 dark:hover:bg-green-900/50 text-green-800 dark:text-green-300 rounded transition-colors"
              >
                <span className="text-sm">🐴</span>
                netkeiba
              </a>
            )}
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

        {/* 馬コメント（編集可能、TARGETに保存） */}
        <div className="mt-4">
          <HorseCommentEditor 
            kettoNum={kettoNum}
            horseName={basic.name}
            initialComment={targetComment?.comment || ''}
          />
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

        {/* 分析セクション - 一番下に配置 */}
        <HorseAnalysisSection analysis={analysis} />

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
