'use client';

import React from 'react';
import { PrepSummaryCard, DataStatusTable } from '@/components/admin';

export default function DataStatusPage() {
  return (
    <div className="container mx-auto p-4 max-w-7xl space-y-4">
      <h1 className="text-xl font-bold">データ登録状況</h1>

      <PrepSummaryCard />

      <DataStatusTable weeks={12} />

      {/* 凡例 */}
      <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
        <div><span className="font-medium text-foreground">インデックス</span>: race_date_index のレース数</div>
        <div><span className="font-medium text-foreground">race JSON</span>: race_*.json ファイル数（黄=不足、赤=0）</div>
        <div><span className="font-medium text-foreground">KB登録率</span>: kb_ext ファイル数 / race JSON 数</div>
        <div><span className="font-medium text-foreground">JRDB</span>: jrdb_pre_idm 設定済みレース率</div>
        <div><span className="font-medium text-foreground">馬場</span>: 含水率/クッション値 ✓=全R有 △=一部 ✗=なし</div>
        <div><span className="font-medium text-foreground">成績</span>: finish_position データあり</div>
        <div><span className="font-medium text-foreground">予測</span>: predictions.json 存在</div>
      </div>
    </div>
  );
}
