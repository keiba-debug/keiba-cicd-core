'use client';

/**
 * 馬プロフィールヘッダーコンポーネント（v2）
 */

import React from 'react';
import { Badge } from '@/components/ui/badge';
import type { HorseBasicInfo } from '@/lib/data/integrated-horse-reader';

interface HorseHeaderProps {
  basic: HorseBasicInfo;
}

export function HorseHeader({ basic }: HorseHeaderProps) {
  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg border p-6">
      <div className="flex items-center gap-4 mb-4">
        <span className="text-4xl">🐴</span>
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-3">
            {basic.name || `馬ID: ${basic.id}`}
            {basic.age && (
              <Badge variant="secondary" className="text-sm font-normal">
                {basic.age}
              </Badge>
            )}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            馬ID: {basic.id}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
        {basic.trainer && (
          <div>
            <span className="text-muted-foreground">調教師</span>
            <p className="font-medium">{basic.trainer}</p>
          </div>
        )}
        {basic.jockey && (
          <div>
            <span className="text-muted-foreground">直近騎手</span>
            <p className="font-medium">{basic.jockey}</p>
          </div>
        )}
        <div>
          <span className="text-muted-foreground">通算出走</span>
          <p className="font-medium">{basic.totalRaces}戦</p>
        </div>
        {basic.updatedAt && (
          <div>
            <span className="text-muted-foreground">最終更新</span>
            <p className="font-medium text-xs">{basic.updatedAt}</p>
          </div>
        )}
      </div>
    </div>
  );
}
