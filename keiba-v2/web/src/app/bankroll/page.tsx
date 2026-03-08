'use client';

import React, { useState } from 'react';
import dynamic from 'next/dynamic';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Settings, Zap, BarChart3, Wallet } from 'lucide-react';
import { AlertBar } from '@/components/bankroll/AlertBar';
import { RefreshButton } from '@/components/bankroll/RefreshButton';
import { BudgetForm } from '@/components/bankroll/BudgetForm';

// =====================================================================
// タブ定義
// =====================================================================

const TABS = [
  { key: 'execute', label: '実行', icon: Zap },
  { key: 'performance', label: '成績', icon: BarChart3 },
  { key: 'fund', label: '資金管理', icon: Wallet },
] as const;

type TabKey = (typeof TABS)[number]['key'];

// =====================================================================
// 遅延読み込み
// =====================================================================

const TabSkeleton = () => (
  <div className="flex h-64 items-center justify-center">
    <div className="text-muted-foreground">読み込み中...</div>
  </div>
);

const ExecuteTab = dynamic(
  () => import('@/components/bankroll/ExecuteTab').then(m => ({ default: m.ExecuteTab })),
  { loading: TabSkeleton, ssr: false }
);
const PerformanceTab = dynamic(
  () => import('@/components/bankroll/PerformanceTab').then(m => ({ default: m.PerformanceTab })),
  { loading: TabSkeleton, ssr: false }
);
const FundTab = dynamic(
  () => import('@/components/bankroll/FundTab').then(m => ({ default: m.FundTab })),
  { loading: TabSkeleton, ssr: false }
);

// =====================================================================
// メインページ
// =====================================================================

export default function BankrollPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('execute');
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <div className="container py-6 max-w-6xl">
      {/* ヘッダー */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold flex items-center gap-2">
          💰 馬券
        </h1>
        <div className="flex items-center gap-2">
          <RefreshButton onRefresh={() => setRefreshKey(k => k + 1)} />
          <Dialog>
            <DialogTrigger asChild>
              <Button variant="outline" size="sm">
                <Settings className="h-4 w-4 mr-2" />
                予算設定
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[425px]">
              <DialogHeader>
                <DialogTitle>予算設定</DialogTitle>
              </DialogHeader>
              <BudgetForm isModal />
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* アラートバー */}
      <AlertBar />

      {/* タブ切り替え */}
      <div className="mb-5 flex gap-1 rounded-lg bg-gray-100 p-1 dark:bg-gray-800">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                'flex-1 flex items-center justify-center gap-2 rounded-md px-3 py-2.5 text-sm font-medium transition-colors',
                activeTab === tab.key
                  ? 'bg-white text-gray-900 shadow dark:bg-gray-700 dark:text-gray-100'
                  : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
              )}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* タブコンテンツ */}
      {activeTab === 'execute' && <ExecuteTab />}
      {activeTab === 'performance' && <PerformanceTab />}
      {activeTab === 'fund' && <FundTab refreshKey={refreshKey} />}
    </div>
  );
}
