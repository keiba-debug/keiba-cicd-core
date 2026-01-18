'use client';

import React from 'react';

interface JraViewerMiniLinksProps {
  paddockUrl: string | null;
  raceUrl: string | null;
  patrolUrl: string | null;
}

/**
 * JRAレーシングビュアーへのミニリンクボタン（一覧用）
 */
export function JraViewerMiniLinks({ paddockUrl, raceUrl, patrolUrl }: JraViewerMiniLinksProps) {
  if (!paddockUrl && !raceUrl && !patrolUrl) {
    return null;
  }

  const openUrl = (e: React.MouseEvent, url: string | null) => {
    e.preventDefault();
    e.stopPropagation();
    if (url) {
      window.open(url, '_blank', 'noopener,noreferrer');
    }
  };

  return (
    <div className="flex gap-1 items-center" onClick={(e) => e.stopPropagation()}>
      {paddockUrl && (
        <button
          onClick={(e) => openUrl(e, paddockUrl)}
          className="px-2 py-0.5 text-xs rounded bg-blue-600 hover:bg-blue-500 text-white transition-colors"
          title="パドック映像"
        >
          ▶ パドック
        </button>
      )}
      {raceUrl && (
        <button
          onClick={(e) => openUrl(e, raceUrl)}
          className="px-2 py-0.5 text-xs rounded bg-red-600 hover:bg-red-500 text-white transition-colors"
          title="レース映像"
        >
          ▶ レース
        </button>
      )}
      {patrolUrl && (
        <button
          onClick={(e) => openUrl(e, patrolUrl)}
          className="px-2 py-0.5 text-xs rounded bg-amber-600 hover:bg-amber-500 text-white transition-colors"
          title="パトロール映像"
        >
          ▶ パトロール
        </button>
      )}
    </div>
  );
}
