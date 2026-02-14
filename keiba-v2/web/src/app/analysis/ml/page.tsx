'use client';

import { useState } from 'react';
import dynamic from 'next/dynamic';
import { cn } from '@/lib/utils';
import { useMlResult } from '@/hooks/useMlResult';
import { TABS, type TabKey } from './utils';

const TabSkeleton = () => (
  <div className="flex h-64 items-center justify-center">
    <div className="text-gray-400">読み込み中...</div>
  </div>
);

const OverviewTab = dynamic(() => import('./tabs/OverviewTab'), { loading: TabSkeleton, ssr: false });
const ValueTab = dynamic(() => import('./tabs/ValueTab'), { loading: TabSkeleton, ssr: false });
const ValuePicksTab = dynamic(() => import('./tabs/ValuePicksTab'), { loading: TabSkeleton, ssr: false });
const RoiTab = dynamic(() => import('./tabs/RoiTab'), { loading: TabSkeleton, ssr: false });
const ImportanceTab = dynamic(() => import('./tabs/ImportanceTab'), { loading: TabSkeleton, ssr: false });
const PredictionsTab = dynamic(() => import('./tabs/PredictionsTab'), { loading: TabSkeleton, ssr: false });

export default function MlAnalysisPage() {
  const { data, isLoading, error } = useMlResult();
  const [activeTab, setActiveTab] = useState<TabKey>('overview');

  if (isLoading) return <div className="flex h-64 items-center justify-center"><div className="text-gray-500">読み込み中...</div></div>;
  if (error || !data) return (
    <div className="flex h-64 flex-col items-center justify-center gap-2">
      <div className="text-red-500">{error?.message ?? 'データがありません'}</div>
      <p className="text-sm text-gray-500">ML実験スクリプトを実行してください</p>
    </div>
  );

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">ML分析</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          {data.description ?? data.experiment} — {data.model ?? 'LightGBM'} ({data.experiment})
        </p>
      </div>

      <div className="mb-5 grid grid-cols-2 gap-x-6 gap-y-1.5 rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-xs text-gray-600 dark:border-gray-700 dark:bg-gray-800/50 dark:text-gray-400">
        <div><span className="font-semibold text-gray-800 dark:text-gray-200">Model A（精度）</span> — 全{data.models.accuracy.features.length}特徴量（オッズ含む）で3着内を予測。的中率重視</div>
        <div><span className="font-semibold text-gray-800 dark:text-gray-200">Model B（Value）</span> — 市場系特徴量を除外した{data.models.value.features.length}特徴量。市場に依存しない能力評価</div>
        <div><span className="font-semibold text-gray-800 dark:text-gray-200">VR（Value Rank）</span> — Model Bによるレース内の順位（1=最も能力が高い）</div>
        <div><span className="font-semibold text-gray-800 dark:text-gray-200">Gap</span> — 人気順位 - VR。大きいほど市場が過小評価している馬</div>
        <div><span className="font-semibold text-gray-800 dark:text-gray-200">Value Bet</span> — VR≤3 かつ Gap≥3 の馬。モデルは上位評価だが人気薄</div>
        <div><span className="font-semibold text-gray-800 dark:text-gray-200">AUC</span> — モデルの判別力（0.5=ランダム、1.0=完全予測）</div>
        <div><span className="font-semibold text-gray-800 dark:text-gray-200">ROI</span> — 回収率。100%超えで利益が出る戦略</div>
        <div><span className="font-semibold text-gray-800 dark:text-gray-200">複勝ROI</span> — 3着以内的中時の払戻（オッズ÷3.5で概算）</div>
      </div>

      <div className="mb-4 flex gap-1 rounded-lg bg-gray-100 p-1 dark:bg-gray-800">
        {TABS.map((tab) => (
          <button key={tab.key} onClick={() => setActiveTab(tab.key)}
            className={cn('flex-1 rounded-md px-3 py-2 text-sm font-medium transition-colors',
              activeTab === tab.key
                ? 'bg-white text-gray-900 shadow dark:bg-gray-700 dark:text-gray-100'
                : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
            )}>
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'overview' && <OverviewTab data={data} />}
      {activeTab === 'value' && <ValueTab data={data} />}
      {activeTab === 'picks' && (
        data.value_bet_picks && data.value_bet_picks.length > 0
          ? <ValuePicksTab picks={data.value_bet_picks} />
          : <div className="py-8 text-center text-gray-400">value_bet_picksがありません（v3ではバックテスト結果に含まれません）</div>
      )}
      {activeTab === 'roi' && <RoiTab roiA={data.roi_analysis.accuracy_model} roiV={data.roi_analysis.value_model} />}
      {activeTab === 'importance' && <ImportanceTab data={data} />}
      {activeTab === 'predictions' && (
        data.race_predictions.length > 0
          ? <PredictionsTab predictions={data.race_predictions} />
          : <div className="py-8 text-center text-gray-400">レース別予測データはありません（v3ではバックテスト結果に含まれません）</div>
      )}
    </div>
  );
}
