'use client';

import { useState, useMemo } from 'react';
import dynamic from 'next/dynamic';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { LayoutGrid, List, TrendingUp, TrendingDown, Minus, Zap, Loader2 } from 'lucide-react';
import {
  HorseEntryTable,
  RaceResultSection,
  TenkaiSection,
  PredictionSection,
  PurchasePlanSection,
  TargetCommentsModal,
} from '@/components/race-v2';

// 調教・厩舎情報セクションを遅延読み込み
// ssr: false でクライアントサイドのみでレンダリング（Radix UIのハイドレーションエラー回避）
const TrainingInfoSection = dynamic(
  () => import('./TrainingInfoSection').then(mod => ({ default: mod.default })),
  {
    loading: () => (
      <div className="border rounded-lg p-4 flex items-center justify-center gap-2 text-muted-foreground">
        <Loader2 className="w-4 h-4 animate-spin" />
        <span className="text-sm">調教・厩舎情報を読み込み中...</span>
      </div>
    ),
    ssr: false,
  }
);
import { RaceMemoSection } from '@/components/race-v2/RaceMemoSection';
import StakeholderCommentsSection from './StakeholderCommentsSection';

// 調教分析セクションを遅延読み込み（初期表示高速化）
// ssr: false でクライアントサイドのみでレンダリング（Radix UIのハイドレーションエラー回避）
const TrainingAnalysisSection = dynamic(
  () => import('./TrainingAnalysisSection'),
  {
    loading: () => (
      <div className="border rounded-lg p-4 flex items-center justify-center gap-2 text-muted-foreground">
        <Loader2 className="w-4 h-4 animate-spin" />
        <span className="text-sm">調教分析を読み込み中...</span>
      </div>
    ),
    ssr: false,
  }
);
import type { IntegratedRaceData } from '@/lib/data/integrated-race-reader';
import type { CourseRpciInfo } from '@/lib/data/rpci-utils';
import type { RatingStandards } from '@/lib/data/rating-utils';
import type { BabaCondition } from '@/lib/data/baba-reader';
import type { TrainingSummaryData } from '@/lib/data/training-summary-reader';
import type { RaceHorseComment, HorseComment } from '@/lib/data/target-comment-reader';
import { analyzeRaceRatings } from '@/lib/data/rating-utils';
import { POSITIVE_BG } from '@/lib/positive-colors';

interface PreviousTrainingEntry {
  date: string;
  training: TrainingSummaryData;
}

/** TARGETコメント（馬番→コメント） */
export interface TargetCommentsMap {
  predictions: Record<number, RaceHorseComment>;
  results: Record<number, RaceHorseComment>;
  /** 馬コメント（UMA_COM）馬番→コメント */
  horseComments?: Record<number, HorseComment>;
}

/** レース開催情報（コメント編集用） */
interface KaisaiInfo {
  kai: number;
  nichi: number;
}

interface RaceDetailContentProps {
  raceData: IntegratedRaceData;
  showResults: boolean;
  /** URLから取得した正確な日付（YYYY-MM-DD形式） */
  urlDate?: string;
  /** URLから取得した正確な競馬場名 */
  urlTrack?: string;
  trainingSummaryMap?: Record<string, TrainingSummaryData>;
  previousTrainingMap?: Record<string, PreviousTrainingEntry>;
  rpciInfo?: CourseRpciInfo | null;
  ratingStandards?: RatingStandards | null;
  babaInfo?: BabaCondition | null;
  /** TARGETコメント */
  targetComments?: TargetCommentsMap;
  /** 開催情報（回・日） */
  kaisaiInfo?: KaisaiInfo;
}

type DisplayMode = 'tabs' | 'all';

export function RaceDetailContent({ raceData, showResults, urlDate, urlTrack, trainingSummaryMap = {}, previousTrainingMap = {}, rpciInfo, ratingStandards, babaInfo, targetComments, kaisaiInfo }: RaceDetailContentProps) {
  const [displayMode, setDisplayMode] = useState<DisplayMode>('all');

  // TARGETコメント編集用のレース情報
  const raceInfoForComments = useMemo(() => {
    if (!kaisaiInfo || !urlTrack || !urlDate) return undefined;
    const raceNumber = parseInt(raceData.meta?.race_id?.slice(-2) || '0', 10);
    if (!raceNumber) return undefined;
    
    return {
      venue: urlTrack,
      year: urlDate.split('-')[0],
      kai: kaisaiInfo.kai,
      nichi: kaisaiInfo.nichi,
      raceNumber,
    };
  }, [kaisaiInfo, urlTrack, urlDate, raceData.meta?.race_id]);

  // レイティング分析を実行
  const ratingAnalysis = useMemo(() => {
    return analyzeRaceRatings(
      raceData.entries,
      raceData.race_info.grade,
      ratingStandards,
      raceData.race_info.race_condition
    );
  }, [raceData.entries, raceData.race_info.grade, ratingStandards, raceData.race_info.race_condition]);

  return (
    <>
      {/* 表示モード切替 */}
      <div className="flex items-center justify-end gap-2 mb-4">
        <span className="text-sm text-muted-foreground mr-2">表示モード:</span>
        <div className="flex rounded-lg border bg-muted p-1">
          <Button
            variant={displayMode === 'tabs' ? 'default' : 'ghost'}
            size="sm"
            className="h-7 px-3 gap-1.5"
            onClick={() => setDisplayMode('tabs')}
          >
            <LayoutGrid className="h-3.5 w-3.5" />
            <span className="text-xs">タブ</span>
          </Button>
          <Button
            variant={displayMode === 'all' ? 'default' : 'ghost'}
            size="sm"
            className="h-7 px-3 gap-1.5"
            onClick={() => setDisplayMode('all')}
          >
            <List className="h-3.5 w-3.5" />
            <span className="text-xs">全表示</span>
          </Button>
        </div>
      </div>

      {/* タブモード */}
      {displayMode === 'tabs' && (
        <Tabs defaultValue={showResults ? 'results' : 'entries'} className="w-full">
          <TabsList className="grid w-full grid-cols-5">
            <TabsTrigger value="entries">出走表</TabsTrigger>
            <TabsTrigger value="prediction">予想・購入</TabsTrigger>
            <TabsTrigger value="training">調教・談話</TabsTrigger>
            <TabsTrigger value="tenkai">展開予想</TabsTrigger>
            {showResults && <TabsTrigger value="results">結果</TabsTrigger>}
          </TabsList>

          {/* 出走表タブ */}
          <TabsContent value="entries" className="mt-4 space-y-4">
            {/* レイティング分析カード */}
            {ratingAnalysis && (
              <RatingAnalysisCard analysis={ratingAnalysis} grade={raceData.race_info.grade} />
            )}
            
            <div className="bg-white dark:bg-gray-900 rounded-lg border p-4">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold">🐎 出走表</h2>
                <TargetCommentsModal entries={raceData.entries} targetComments={targetComments} raceInfo={raceInfoForComments} trainingSummaryMap={trainingSummaryMap} />
              </div>
              <HorseEntryTable 
                entries={raceData.entries}
                showResult={showResults}
                trainingSummaryMap={trainingSummaryMap}
                targetComments={targetComments}
              />
            </div>
          </TabsContent>

          {/* 予想・購入タブ */}
          <TabsContent value="prediction" className="mt-4 space-y-4">
            <RaceMemoSection
              raceId={raceData.meta?.race_id || ''}
              raceDate={urlDate || raceData.race_info.date?.replace(/\//g, '-') || ''}
              raceName={`${urlTrack || raceData.race_info.venue || ''}${raceData.race_info.race_number || 0}R ${raceData.race_info.race_name || ''}`}
              showResults={showResults}
            />
            {/* TODO: 予想入力・購入計画は将来実装予定
            <PredictionSection
              raceId={raceData.meta?.race_id || ''}
              raceDate={raceData.race_info.date?.replace(/-/g, '') || ''}
              raceName={raceData.race_info.race_name || ''}
              venue={raceData.race_info.venue || ''}
              raceNumber={raceData.race_info.race_number || 0}
              entries={raceData.entries.map(e => ({
                horse_number: e.horse_number,
                horse_name: e.horse_name,
                jockey_name: e.jockey_name,
                odds: e.odds,
              }))}
            />
            <PurchasePlanSection
              raceId={raceData.meta?.race_id || ''}
              raceDate={raceData.race_info.date?.replace(/-/g, '') || ''}
              raceName={raceData.race_info.race_name || ''}
              venue={raceData.race_info.venue || ''}
              raceNumber={raceData.race_info.race_number || 0}
              entries={raceData.entries.map(e => ({
                horse_number: e.horse_number,
                horse_name: e.horse_name,
                jockey_name: e.jockey_name,
                odds: e.odds,
              }))}
            />
            */}
          </TabsContent>

          {/* 調教・談話タブ */}
          <TabsContent value="training" className="mt-4 space-y-6">
            <TrainingAnalysisSection 
              entries={raceData.entries} 
              trainingSummaryMap={trainingSummaryMap}
              previousTrainingMap={previousTrainingMap}
            />
            <StakeholderCommentsSection 
              entries={raceData.entries} 
            />
          </TabsContent>

          {/* 展開予想タブ */}
          <TabsContent value="tenkai" className="mt-4">
            <TenkaiSection 
              tenkaiData={raceData.tenkai_data}
              entries={raceData.entries}
            />
          </TabsContent>

          {/* 結果タブ */}
          {showResults && (
            <TabsContent value="results" className="mt-4">
              <RaceResultSection 
                entries={raceData.entries}
                payouts={raceData.payouts}
                tenkaiData={raceData.tenkai_data}
                distance={raceData.race_info.distance}
                rpciInfo={rpciInfo}
                raceId={raceData.meta?.race_id}
                raceDate={raceData.race_info.date}
                raceName={raceData.race_info.race_name}
              />
            </TabsContent>
          )}
        </Tabs>
      )}

      {/* 全表示モード */}
      {displayMode === 'all' && (
        <div className="space-y-6">
          {/* レイティング分析カード */}
          {ratingAnalysis && (
            <RatingAnalysisCard analysis={ratingAnalysis} grade={raceData.race_info.grade} />
          )}
          
          {/* 出走表 */}
          <div className="bg-white dark:bg-gray-900 rounded-lg border p-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">🐎 出走表</h2>
              <TargetCommentsModal entries={raceData.entries} targetComments={targetComments} raceInfo={raceInfoForComments} trainingSummaryMap={trainingSummaryMap} />
            </div>
            <HorseEntryTable 
              entries={raceData.entries}
              showResult={showResults}
              trainingSummaryMap={trainingSummaryMap}
              targetComments={targetComments}
            />
          </div>

          {/* 予想メモ */}
          <RaceMemoSection
            raceId={raceData.meta?.race_id || ''}
            raceDate={urlDate || raceData.race_info.date?.replace(/\//g, '-') || ''}
            raceName={`${urlTrack || raceData.race_info.venue || ''}${raceData.race_info.race_number || 0}R ${raceData.race_info.race_name || ''}`}
            showResults={showResults}
          />

          {/* TODO: 予想入力・購入計画は将来実装予定
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <PredictionSection
              raceId={raceData.meta?.race_id || ''}
              raceDate={raceData.race_info.date?.replace(/-/g, '') || ''}
              raceName={raceData.race_info.race_name || ''}
              venue={raceData.race_info.venue || ''}
              raceNumber={raceData.race_info.race_number || 0}
              entries={raceData.entries.map(e => ({
                horse_number: e.horse_number,
                horse_name: e.horse_name,
                jockey_name: e.jockey_name,
                odds: e.odds,
              }))}
            />
            <PurchasePlanSection
              raceId={raceData.meta?.race_id || ''}
              raceDate={raceData.race_info.date?.replace(/-/g, '') || ''}
              raceName={raceData.race_info.race_name || ''}
              venue={raceData.race_info.venue || ''}
              raceNumber={raceData.race_info.race_number || 0}
              entries={raceData.entries.map(e => ({
                horse_number: e.horse_number,
                horse_name: e.horse_name,
                jockey_name: e.jockey_name,
                odds: e.odds,
              }))}
            />
          </div>
          */}

          {/* 展開予想 */}
          {raceData.tenkai_data && (
            <TenkaiSection 
              tenkaiData={raceData.tenkai_data}
              entries={raceData.entries}
            />
          )}

          {/* 調教分析 */}
          <TrainingAnalysisSection 
            entries={raceData.entries} 
            trainingSummaryMap={trainingSummaryMap}
            previousTrainingMap={previousTrainingMap}
          />

          {/* 関係者コメント分析 */}
          <StakeholderCommentsSection 
            entries={raceData.entries} 
          />

          {/* レース結果 */}
          {showResults && (
            <RaceResultSection 
              entries={raceData.entries}
              payouts={raceData.payouts}
              tenkaiData={raceData.tenkai_data}
              distance={raceData.race_info.distance}
              rpciInfo={rpciInfo}
              babaInfo={babaInfo}
              raceId={raceData.meta?.race_id}
              raceDate={raceData.race_info.date}
              raceName={raceData.race_info.race_name}
            />
          )}
        </div>
      )}
    </>
  );
}

/**
 * レイティング分析カードコンポーネント
 */
interface RatingAnalysisCardProps {
  analysis: ReturnType<typeof analyzeRaceRatings>;
  grade?: string;
}

function RatingAnalysisCard({ analysis, grade }: RatingAnalysisCardProps) {
  if (!analysis) return null;
  
  // レベルアイコン
  const getLevelIcon = () => {
    if (analysis.levelLabel === '高レベル') {
      return <TrendingUp className="h-4 w-4 text-green-600 dark:text-green-400" />;
    } else if (analysis.levelLabel === '低レベル') {
      return <TrendingDown className="h-4 w-4 text-red-600 dark:text-red-400" />;
    }
    return <Minus className="h-4 w-4 text-gray-500" />;
  };
  
  // 混戦度カラー
  const getCompetitivenessColor = () => {
    if (analysis.competitivenessLabel.includes('混戦')) {
      return 'bg-red-100 text-red-700 border-red-200';
    } else if (analysis.competitivenessLabel === '力差明確') {
      return 'bg-green-100 text-green-700 border-green-200';
    }
    return 'bg-gray-100 text-gray-700 border-gray-200';
  };

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg border p-4">
      <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
        📊 レース分析
        {grade && <span className="text-xs font-normal text-muted-foreground">({grade})</span>}
      </h3>
      
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {/* レースレベル */}
        <div className="text-center p-3 bg-slate-50 rounded-lg">
          <div className="flex items-center justify-center gap-1 mb-1">
            {getLevelIcon()}
            <span className="font-semibold text-sm">{analysis.levelLabel}</span>
          </div>
          <div className="text-xs text-muted-foreground">{analysis.levelDescription}</div>
        </div>
        
        {/* 混戦度 */}
        <div className="text-center p-3 bg-slate-50 rounded-lg">
          <div className={`inline-flex items-center gap-1 px-2 py-1 rounded border text-xs font-medium mb-1 ${getCompetitivenessColor()}`}>
            <Zap className="h-3 w-3" />
            {analysis.competitivenessLabel}
          </div>
          <div className="text-xs text-muted-foreground">{analysis.competitivenessDescription}</div>
        </div>
        
        {/* 平均レイティング */}
        <div className="text-center p-3 bg-slate-50 rounded-lg">
          <div className="text-xl font-bold">{analysis.mean}</div>
          <div className="text-xs text-muted-foreground">平均レイティング</div>
        </div>
        
        {/* 上位差 */}
        <div className="text-center p-3 bg-slate-50 rounded-lg">
          <div className="text-xl font-bold">{analysis.top3Diff}<span className="text-sm font-normal">pt</span></div>
          <div className="text-xs text-muted-foreground">上位3頭と4位の差</div>
        </div>
      </div>
      
      {/* 補足情報 */}
      <div className="mt-3 pt-3 border-t flex flex-wrap gap-4 text-xs text-muted-foreground">
        <span>レンジ: {analysis.min} - {analysis.max}</span>
        <span>標準偏差: {analysis.stdev}</span>
        <span>中央値: {analysis.median}</span>
        <span>対象: {analysis.count}頭</span>
      </div>
    </div>
  );
}
