'use client';

import React from 'react';
import { Button } from '@/components/ui/button';

interface JraViewerLinksProps {
  paddockUrl: string | null;
  raceUrl?: string | null;
  patrolUrl?: string | null;
}

/**
 * JRAレーシングビュアーへのリンクボタン
 */
export function JraViewerLinks({ paddockUrl, raceUrl, patrolUrl }: JraViewerLinksProps) {
  if (!paddockUrl && !raceUrl && !patrolUrl) {
    return null;
  }

  const openUrl = (url: string | null | undefined) => {
    if (url) {
      window.open(url, '_blank', 'noopener,noreferrer');
    }
  };

  return (
    <div className="flex gap-2 items-center flex-wrap">
      <span className="text-sm text-muted-foreground">🎬 JRAビュアー:</span>
      {paddockUrl && (
        <Button
          variant="outline"
          size="sm"
          onClick={() => openUrl(paddockUrl)}
          className="bg-blue-600 hover:bg-blue-500 text-white border-blue-700"
        >
          🐴 パドック
        </Button>
      )}
      {raceUrl && (
        <Button
          variant="outline"
          size="sm"
          onClick={() => openUrl(raceUrl)}
          className="bg-red-600 hover:bg-red-500 text-white border-red-700"
        >
          🏇 レース
        </Button>
      )}
      {patrolUrl && (
        <Button
          variant="outline"
          size="sm"
          onClick={() => openUrl(patrolUrl)}
          className="bg-amber-600 hover:bg-amber-500 text-white border-amber-700"
        >
          👁️ パトロール
        </Button>
      )}
    </div>
  );
}
