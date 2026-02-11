'use client';

import React from 'react';
import { Play, Video, Binoculars } from 'lucide-react';

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
    // レーシングビュアーは別タブで開く
    multiViewWindow = window.open(targetUrl, '_blank');
  };

  return (
    <div className="flex gap-1 items-center flex-nowrap" onClick={(e) => e.stopPropagation()}>
      <button
        onClick={(e) => openMultiView(e, 'paddock')}
        className="w-5 h-5 rounded bg-orange-500 hover:bg-orange-600 hover:scale-110 hover:shadow-md text-white transition-all flex items-center justify-center"
        title="パドック映像をマルチビューに追加"
      >
        <Binoculars className="w-3 h-3" />
      </button>
      <button
        onClick={(e) => openMultiView(e, 'race')}
        className="w-5 h-5 rounded bg-green-600 hover:bg-green-700 hover:scale-110 hover:shadow-md text-white transition-all flex items-center justify-center"
        title="レース映像をマルチビューに追加"
      >
        <Play className="w-3 h-3" />
      </button>
      <button
        onClick={(e) => openMultiView(e, 'patrol')}
        className="w-5 h-5 rounded bg-red-500 hover:bg-red-600 hover:scale-110 hover:shadow-md text-white transition-all flex items-center justify-center"
        title="パトロール映像をマルチビューに追加"
      >
        <Video className="w-3 h-3" />
      </button>
    </div>
  );
}
