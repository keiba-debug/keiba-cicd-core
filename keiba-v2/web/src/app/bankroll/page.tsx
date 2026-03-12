'use client';

import React from 'react';
import dynamic from 'next/dynamic';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Settings } from 'lucide-react';
import { AlertBar } from '@/components/bankroll/AlertBar';
import { BudgetForm } from '@/components/bankroll/BudgetForm';

const TabSkeleton = () => (
  <div className="flex h-64 items-center justify-center">
    <div className="text-muted-foreground">読み込み中...</div>
  </div>
);

const ExecuteTab = dynamic(
  () => import('@/components/bankroll/ExecuteTab').then(m => ({ default: m.ExecuteTab })),
  { loading: TabSkeleton, ssr: false }
);

export default function BankrollPage() {
  return (
    <div className="container py-6 max-w-6xl">
      {/* ヘッダー */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold flex items-center gap-2">
          ⚡ 推奨馬券
        </h1>
        <div className="flex items-center gap-2">
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

      {/* 推奨馬券リスト */}
      <ExecuteTab />
    </div>
  );
}
