'use client';

import React from 'react';

type VideoType = 'paddock' | 'race' | 'patrol';
type MultiViewPayload = {
  type: 'keiba:multi-view:add';
  payload: {
    add: string;
    date: string;
    track: string;
    raceNumber: string;
    videoType: VideoType;
    raceName?: string;
    kai?: string;
    nichi?: string;
  };
};

let multiViewWindow: Window | null = null;

interface JraViewerMiniLinksProps {
  date: string;
  track: string;
  raceNumber: number;
  raceName?: string;
  kai?: number;
  nichi?: number;
}

/**
 * JRAレーシングビュアーへのミニリンクボタン（一覧用）
 */
export function JraViewerMiniLinks({
  date,
  track,
  raceNumber,
  raceName,
  kai,
  nichi,
}: JraViewerMiniLinksProps) {
  const openMultiView = (e: React.MouseEvent, videoType: VideoType) => {
    e.preventDefault();
    e.stopPropagation();
    const add = String(Date.now());
    const payload: MultiViewPayload = {
      type: 'keiba:multi-view:add',
      payload: {
        add,
        date,
        track,
        raceNumber: String(raceNumber),
        videoType,
        raceName,
        kai: kai ? String(kai) : undefined,
        nichi: nichi ? String(nichi) : undefined,
      },
    };

    if (multiViewWindow && !multiViewWindow.closed) {
      multiViewWindow.postMessage(payload, window.location.origin);
      multiViewWindow.focus();
      return;
    }

    const params = new URLSearchParams(payload.payload);
    const targetUrl = `/multi-view?${params.toString()}`;
    multiViewWindow = window.open(targetUrl, 'keiba-multi-view');
  };

  return (
    <div className="flex gap-0.5 items-center flex-nowrap" onClick={(e) => e.stopPropagation()}>
      <button
        onClick={(e) => openMultiView(e, 'paddock')}
        className="w-5 h-5 text-[10px] font-bold rounded bg-blue-600 hover:bg-blue-500 text-white transition-colors flex items-center justify-center"
        title="パドック映像をマルチビューに追加"
      >
        パ
      </button>
      <button
        onClick={(e) => openMultiView(e, 'race')}
        className="w-5 h-5 text-[10px] font-bold rounded bg-red-600 hover:bg-red-500 text-white transition-colors flex items-center justify-center"
        title="レース映像をマルチビューに追加"
      >
        ギ
      </button>
      <button
        onClick={(e) => openMultiView(e, 'patrol')}
        className="w-5 h-5 text-[10px] font-bold rounded bg-amber-600 hover:bg-amber-500 text-white transition-colors flex items-center justify-center"
        title="パトロール映像をマルチビューに追加"
      >
        T
      </button>
    </div>
  );
}
