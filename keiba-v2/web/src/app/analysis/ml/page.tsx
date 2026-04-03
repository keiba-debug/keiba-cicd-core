'use client';

import { useState, useMemo } from 'react';
import dynamic from 'next/dynamic';
import { cn } from '@/lib/utils';
import { useMlResult } from '@/hooks/useMlResult';
import { TABS, type TabKey } from './utils';
import ModelSelector, { type ModelSelection } from './ModelSelector';
import VersionSelector from './VersionSelector';

const TabSkeleton = () => (
  <div className="flex h-64 items-center justify-center">
    <div className="text-gray-400">読み込み中...</div>
  </div>
);

const OverviewTab = dynamic(() => import('./tabs/OverviewTab'), { loading: TabSkeleton, ssr: false });
const ValueTab = dynamic(() => import('./tabs/ValueTab'), { loading: TabSkeleton, ssr: false });
const ValuePicksTab = dynamic(() => import('./tabs/ValuePicksTab'), { loading: TabSkeleton, ssr: false });
const ImportanceTab = dynamic(() => import('./tabs/ImportanceTab'), { loading: TabSkeleton, ssr: false });
const PredictionsTab = dynamic(() => import('./tabs/PredictionsTab'), { loading: TabSkeleton, ssr: false });
const ObstacleTab = dynamic(() => import('./tabs/ObstacleTab'), { loading: TabSkeleton, ssr: false });

export default function MlAnalysisPage() {
  const [modelSel, setModelSel] = useState<ModelSelection>({ modelId: 'polaris', version: null });
  // polaris: 既存のuseMlResult (experiment result + obstacle meta)
  // enif/eclipse: /api/ml/result?model=xxx&version=xxx
  const selectedVersion = modelSel.modelId === 'polaris' ? modelSel.version : null;
  const { data, isLoading, error } = useMlResult(selectedVersion);

  // 非polarisモデルのメタデータ（障害・eclipse等）
  const [otherMeta, setOtherMeta] = useState<Record<string, unknown> | null>(null);
  const [otherLoading, setOtherLoading] = useState(false);

  // モデル変更ハンドラ
  const handleModelChange = (sel: ModelSelection) => {
    setModelSel(sel);
    if (sel.modelId !== 'polaris') {
      setOtherLoading(true);
      const url = sel.version
        ? `/api/ml/result?model=${sel.modelId}&version=${sel.version}`
        : `/api/ml/result?model=${sel.modelId}`;
      fetch(url)
        .then(r => r.json())
        .then(d => { setOtherMeta(d); setOtherLoading(false); })
        .catch(() => { setOtherMeta(null); setOtherLoading(false); });
    } else {
      setOtherMeta(null);
    }
  };

  const [activeTab, setActiveTab] = useState<TabKey>('overview');

  // 表示するタブを選択中モデルに応じてフィルタ
  const visibleTabs = useMemo(() => {
    if (modelSel.modelId === 'polaris') return TABS;
    if (modelSel.modelId === 'enif') return TABS.filter(t => t.key === 'obstacle');
    return TABS.filter(t => t.key === 'overview');
  }, [modelSel.modelId]);

  // タブがフィルタで消えた場合、先頭タブに切替
  const effectiveTab = visibleTabs.find(t => t.key === activeTab) ? activeTab : visibleTabs[0]?.key ?? 'overview';

  const isPolaris = modelSel.modelId === 'polaris';
  const loading = isPolaris ? isLoading : otherLoading;

  if (loading) return <div className="flex h-64 items-center justify-center"><div className="text-gray-500">読み込み中...</div></div>;

  // polaris: data必須 / 他モデル: otherMeta必須
  if (isPolaris && (error || !data)) return (
    <div className="flex h-64 flex-col items-center justify-center gap-2">
      <div className="text-red-500">{error?.message ?? 'データがありません'}</div>
      <p className="text-sm text-gray-500">ML実験スクリプトを実行してください</p>
    </div>
  );

  // 障害モデル: enif選択時はotherMetaをobstacle_modelとして渡す
  const obstacleModel = isPolaris
    ? data?.obstacle_model
    : modelSel.modelId === 'enif' ? otherMeta : null;

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      {/* ヘッダー */}
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">
            ML Report
            {isPolaris && data?.version?.startsWith('polaris') && (
              <span className="ml-2 inline-flex items-center rounded-full px-2.5 py-0.5 text-sm font-medium bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
                {data.version}
              </span>
            )}
            {!isPolaris && otherMeta && (
              <span className="ml-2 inline-flex items-center rounded-full px-2.5 py-0.5 text-sm font-medium bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400">
                {(otherMeta as { version?: string }).version ?? modelSel.modelId}
              </span>
            )}
          </h1>
          {isPolaris && data && (
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              {data.version_alias ? `${data.version_alias} — ` : ''}{data.model ?? 'LightGBM'} ({data.split?.train ?? ''} → {data.split?.test ?? ''})
            </p>
          )}
          {!isPolaris && otherMeta && (
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              {(otherMeta as { train_period?: string }).train_period ?? ''}
              {(otherMeta as { test_period?: string }).test_period ? ` → ${(otherMeta as { test_period?: string }).test_period}` : ''}
            </p>
          )}
        </div>
      </div>

      {/* モデルセレクター */}
      <div className="mb-5">
        <ModelSelector selected={modelSel} onChange={handleModelChange} />
      </div>

      {/* 用語ガイド */}
      {isPolaris && (
        <details className="mb-5">
          <summary className="cursor-pointer text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400">用語ガイド</summary>
          <div className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-xs text-gray-600 dark:border-gray-700 dark:bg-gray-800/50 dark:text-gray-400">
            <div><strong>P</strong> — 3着内予測 / <strong>W</strong> — 1着予測 / <strong>AR</strong> — 着差回帰</div>
            <div><strong>Gap</strong> — 人気順位 - PR（大きい=過小評価）</div>
            <div><strong>EV</strong> — P(win)×オッズ（1.0超=期待値プラス）</div>
            <div><strong>AUC</strong> — 判別力 / <strong>ECE</strong> — キャリブレーション精度</div>
          </div>
        </details>
      )}

      {/* タブナビゲーション */}
      <div className="mb-4 flex gap-1 rounded-lg bg-gray-100 p-1 dark:bg-gray-800">
        {visibleTabs.map((tab) => (
          <button key={tab.key} onClick={() => setActiveTab(tab.key)}
            className={cn('flex-1 rounded-md px-3 py-2 text-sm font-medium transition-colors',
              effectiveTab === tab.key
                ? 'bg-white text-gray-900 shadow dark:bg-gray-700 dark:text-gray-100'
                : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
            )}>
            {tab.label}
          </button>
        ))}
      </div>

      {/* タブコンテンツ（polaris） */}
      {isPolaris && data && (
        <>
          {effectiveTab === 'overview' && <OverviewTab data={data} obstacleModel={data.obstacle_model} />}
          {effectiveTab === 'value' && <ValueTab data={data} />}
          {effectiveTab === 'picks' && (
            data.value_bet_picks && data.value_bet_picks.length > 0
              ? <ValuePicksTab picks={data.value_bet_picks} />
              : <div className="py-8 text-center text-gray-400">value_bet_picksがありません（v3ではバックテスト結果に含まれません）</div>
          )}
          {effectiveTab === 'importance' && <ImportanceTab data={data} />}
          {effectiveTab === 'obstacle' && <ObstacleTab obstacleModel={data.obstacle_model} />}
          {effectiveTab === 'predictions' && (
            data.race_predictions.length > 0
              ? <PredictionsTab predictions={data.race_predictions} />
              : <div className="py-8 text-center text-gray-400">レース別予測データはありません（v3ではバックテスト結果に含まれません）</div>
          )}
        </>
      )}

      {/* タブコンテンツ（enif = 障害） */}
      {modelSel.modelId === 'enif' && obstacleModel && (
        <ObstacleTab obstacleModel={obstacleModel} />
      )}

      {/* タブコンテンツ（その他モデル — 将来拡張用） */}
      {!isPolaris && modelSel.modelId !== 'enif' && otherMeta && (
        <div className="rounded-lg border p-6">
          <h2 className="text-lg font-semibold mb-4">{modelSel.modelId} Model Meta</h2>
          <pre className="text-xs bg-muted/50 rounded p-4 overflow-auto max-h-96">
            {JSON.stringify(otherMeta, null, 2)}
          </pre>
        </div>
      )}

      {/* データなしフォールバック */}
      {!isPolaris && !otherMeta && !loading && (
        <div className="py-8 text-center text-gray-400">
          このモデルのデータがありません
        </div>
      )}
    </div>
  );
}
