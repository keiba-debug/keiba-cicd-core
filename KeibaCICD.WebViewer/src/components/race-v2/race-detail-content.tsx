'use client';

import { useState } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { LayoutGrid, List } from 'lucide-react';
import {
  HorseEntryTable,
  TrainingInfoSection,
  RaceResultSection,
  TenkaiSection,
} from '@/components/race-v2';
import type { IntegratedRaceData } from '@/lib/data/integrated-race-reader';

// 調教サマリー型
interface TrainingSummaryData {
  lapRank?: string;
  timeRank?: string;
  detail?: string;
}

interface RaceDetailContentProps {
  raceData: IntegratedRaceData;
  showResults: boolean;
  trainingSummaryMap?: Record<string, TrainingSummaryData>;
}

type DisplayMode = 'tabs' | 'all';

export function RaceDetailContent({ raceData, showResults, trainingSummaryMap = {} }: RaceDetailContentProps) {
  const [displayMode, setDisplayMode] = useState<DisplayMode>('tabs');

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
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="entries">出走表</TabsTrigger>
            <TabsTrigger value="training">調教・談話</TabsTrigger>
            <TabsTrigger value="tenkai">展開予想</TabsTrigger>
            {showResults && <TabsTrigger value="results">結果</TabsTrigger>}
          </TabsList>

          {/* 出走表タブ */}
          <TabsContent value="entries" className="mt-4">
            <div className="bg-white dark:bg-gray-900 rounded-lg border p-4">
              <h2 className="text-lg font-semibold mb-4">🐎 出走表</h2>
              <HorseEntryTable 
                entries={raceData.entries}
                showResult={showResults}
                trainingSummaryMap={trainingSummaryMap}
              />
            </div>
          </TabsContent>

          {/* 調教・談話タブ */}
          <TabsContent value="training" className="mt-4">
            <TrainingInfoSection 
              entries={raceData.entries} 
              trainingSummaryMap={trainingSummaryMap}
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
              />
            </TabsContent>
          )}
        </Tabs>
      )}

      {/* 全表示モード */}
      {displayMode === 'all' && (
        <div className="space-y-6">
          {/* 出走表 */}
          <div className="bg-white dark:bg-gray-900 rounded-lg border p-4">
            <h2 className="text-lg font-semibold mb-4">🐎 出走表</h2>
            <HorseEntryTable 
              entries={raceData.entries}
              showResult={showResults}
              trainingSummaryMap={trainingSummaryMap}
            />
          </div>

          {/* 展開予想 */}
          {raceData.tenkai_data && (
            <TenkaiSection 
              tenkaiData={raceData.tenkai_data}
              entries={raceData.entries}
            />
          )}

          {/* 調教・厩舎情報 */}
          <TrainingInfoSection 
            entries={raceData.entries} 
            trainingSummaryMap={trainingSummaryMap}
          />

          {/* レース結果 */}
          {showResults && (
            <RaceResultSection 
              entries={raceData.entries}
              payouts={raceData.payouts}
            />
          )}
        </div>
      )}
    </>
  );
}
