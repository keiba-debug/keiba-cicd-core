'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

// 競馬場コード（JRAビュアー形式 - 1桁）
const TRACK_CODES: Record<string, number> = {
  '札幌': 1, '函館': 2, '福島': 3, '新潟': 4, '東京': 5,
  '中山': 6, '中京': 7, '京都': 8, '阪神': 9, '小倉': 10,
};

// レース番号を16進数に変換（1-9→数字, 10→a, 11→b, 12→c）
function raceNumberToHex(raceNumber: number): string {
  return raceNumber.toString(16);
}

type VideoType = 'paddock' | 'race' | 'patrol';

type SlotDate = {
  year: number;
  month: number;
  day: number;
};

interface ViewSlot {
  id: number;
  track: string;
  raceNumber: number;
  videoType: VideoType;
  url: string | null;
  date?: SlotDate;
  kai?: number;
  nichi?: number;
  label?: string; // 追加: レース名など
  umaban?: string; // 馬番（出走番号）
}

// クエリパラメータから渡されるレース情報
interface RaceParam {
  date: string;     // YYYY/MM/DD
  track: string;    // 競馬場名
  raceNumber: number;
  raceName?: string;
  videoType?: VideoType;
  kai?: number;
  nichi?: number;
  umaban?: string;  // 馬番（出走番号）
}

type MultiViewMessage = {
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
    umaban?: string;
  };
};

const STORAGE_KEY = 'keiba-multi-view-slots';
const MAX_SLOTS = Number.POSITIVE_INFINITY;

// URL生成
// JRA Racing Viewer URL format: 
// raceCode = YY + TrackCode(1桁) + Kai(1桁) + Nichi(1桁) + RaceNo(16進数1桁)
// 例: 中山1回7日目10R = 26 + 6 + 1 + 7 + a = 26617a
function generateUrl(
  year: number,
  month: number,
  day: number,
  track: string,
  kai: number,
  nichi: number,
  raceNumber: number,
  videoType: VideoType
): string {
  const trackCode = TRACK_CODES[track];
  if (trackCode === undefined) return '';
  const trackCodeHex = trackCode.toString(16);

  const yearShort = year % 100;
  const dateStr = `${year}${String(month).padStart(2, '0')}${String(day).padStart(2, '0')}`;
  
  // JRAビュアー形式: 年下2桁 + 場コード(1桁) + 回次(1桁) + 日次(16進数) + レース番号(16進数)
  // 例: 中山7日目1R→266171, 東京10日目3R→2554a3
  const raceCode = `${yearShort}${trackCodeHex}${kai}${nichi.toString(16)}${raceNumberToHex(raceNumber)}`;

  let suffix = '';
  if (videoType === 'paddock') suffix = '_p';
  else if (videoType === 'patrol') suffix = '_a';

  // URLはエンコードなし
  const target = `race/${year}/${dateStr}/${raceCode}${suffix}`;
  return `https://regist.prc.jp/api/windowopen.aspx?target=${target}&quality=4`;
}

function parseDateString(raw: string): SlotDate | null {
  const match = raw.match(/^(\d{4})[\/-](\d{1,2})[\/-](\d{1,2})$/);
  if (!match) return null;
  return {
    year: parseInt(match[1], 10),
    month: parseInt(match[2], 10),
    day: parseInt(match[3], 10),
  };
}

function buildSlotUrl(slot: ViewSlot): string | null {
  if (!slot.date || !slot.kai || !slot.nichi) return null;
  return generateUrl(
    slot.date.year,
    slot.date.month,
    slot.date.day,
    slot.track,
    slot.kai,
    slot.nichi,
    slot.raceNumber,
    slot.videoType
  );
}

function loadStoredSlots(): ViewSlot[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as ViewSlot[];
  } catch {
    return [];
  }
}

function MultiViewPage() {
  const searchParams = useSearchParams();
  
  // クエリパラメータから馬ID・馬名とレース情報を取得
  const horseId = searchParams.get('horseId');
  const horseName = searchParams.get('horse');
  const racesParam = searchParams.get('races');
  
  // ビュースロット
  const [slots, setSlots] = useState<ViewSlot[]>(() => loadStoredSlots());
  
  // 初期化フラグ
  const [initialized, setInitialized] = useState(false);
  const lastAddTokenRef = useRef<string | null>(null);

  // クエリパラメータからレース情報を初期化
  useEffect(() => {
    if (initialized || !racesParam) return;

    const initSlots = async () => {
      try {
        const races: RaceParam[] = JSON.parse(racesParam);
        if (!Array.isArray(races) || races.length === 0) return;

        const newSlots: ViewSlot[] = [];

        for (let i = 0; i < races.length; i++) {
          const race = races[i];
          const raceDate = parseDateString(race.date);
          if (!raceDate) continue;

          let raceKai = race.kai;
          let raceNichi = race.nichi;

          if (!raceKai || !raceNichi) {
            try {
              const res = await fetch(
                `/api/race-lookup?date=${race.date}&track=${encodeURIComponent(race.track)}&raceNumber=${race.raceNumber}`
              );
              if (res.ok) {
                const data = await res.json();
                if (data.race) {
                  raceKai = data.race.kai;
                  raceNichi = data.race.nichi;
                }
              }
            } catch {
              // エラーは無視
            }
          }

          const slot: ViewSlot = {
            id: i + 1,
            track: race.track,
            raceNumber: race.raceNumber,
            videoType: race.videoType || 'paddock',
            date: raceDate,
            kai: raceKai,
            nichi: raceNichi,
            url: null,
            label: race.raceName,
            umaban: race.umaban,
          };
          slot.url = buildSlotUrl(slot);
          newSlots.push(slot);
        }

        if (newSlots.length > 0) {
          setSlots(newSlots);
        }
        setInitialized(true);
      } catch {
        setInitialized(true);
      }
    };

    initSlots();
  }, [racesParam, initialized]);

  // 追加パラメータでスロットを追記
  useEffect(() => {
    const addToken = searchParams.get('add');
    const addDate = searchParams.get('date');
    const addTrack = searchParams.get('track');
    const addRaceNumber = searchParams.get('raceNumber');
    const addVideoType = searchParams.get('videoType') as VideoType | null;
    const addRaceName = searchParams.get('raceName');
    const addKai = searchParams.get('kai');
    const addNichi = searchParams.get('nichi');

    if (!addToken || lastAddTokenRef.current === addToken) return;
    if (!addDate || !addTrack || !addRaceNumber) return;

    lastAddTokenRef.current = addToken;

    const appendSlot = async () => {
      const raceDate = parseDateString(addDate);
      if (!raceDate) return;

      let raceKai = addKai ? Number(addKai) : undefined;
      let raceNichi = addNichi ? Number(addNichi) : undefined;

      if (!raceKai || !raceNichi) {
        try {
          const res = await fetch(
            `/api/race-lookup?date=${addDate}&track=${encodeURIComponent(addTrack)}&raceNumber=${addRaceNumber}`
          );
          if (res.ok) {
            const data = await res.json();
            if (data.race) {
              raceKai = data.race.kai;
              raceNichi = data.race.nichi;
            }
          }
        } catch {
          // エラーは無視
        }
      }

      setSlots((prev) => {
        const nextId = prev.length > 0 ? Math.max(...prev.map((s) => s.id)) + 1 : 1;
        const slot: ViewSlot = {
          id: nextId,
          track: addTrack,
          raceNumber: Number(addRaceNumber),
          videoType: addVideoType || 'paddock',
          date: raceDate,
          kai: raceKai,
          nichi: raceNichi,
          url: null,
          label: addRaceName || undefined,
        };
        slot.url = buildSlotUrl(slot);
        return [...prev, slot];
      });
    };

    appendSlot();

    const url = new URL(window.location.href);
    url.searchParams.delete('add');
    window.history.replaceState({}, '', url.toString());
  }, [searchParams]);

  // postMessage 経由の追加
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (event.origin !== window.location.origin) return;
      const data = event.data as MultiViewMessage | undefined;
      if (!data || data.type !== 'keiba:multi-view:add') return;

      const {
        add,
        date: addDate,
        track: addTrack,
        raceNumber: addRaceNumber,
        videoType: addVideoType,
        raceName: addRaceName,
        kai: addKai,
        nichi: addNichi,
        umaban: addUmaban,
      } = data.payload;

      if (!add || lastAddTokenRef.current === add) return;
      if (!addDate || !addTrack || !addRaceNumber) return;

      lastAddTokenRef.current = add;

      const appendSlot = async () => {
        const raceDate = parseDateString(addDate);
        if (!raceDate) return;

        let raceKai = addKai ? Number(addKai) : undefined;
        let raceNichi = addNichi ? Number(addNichi) : undefined;

        if (!raceKai || !raceNichi) {
          try {
            const res = await fetch(
              `/api/race-lookup?date=${addDate}&track=${encodeURIComponent(addTrack)}&raceNumber=${addRaceNumber}`
            );
            if (res.ok) {
              const result = await res.json();
              if (result.race) {
                raceKai = result.race.kai;
                raceNichi = result.race.nichi;
              }
            }
          } catch {
            // エラーは無視
          }
        }

        setSlots((prev) => {
          const nextId = prev.length > 0 ? Math.max(...prev.map((s) => s.id)) + 1 : 1;
          const slot: ViewSlot = {
            id: nextId,
            track: addTrack,
            raceNumber: Number(addRaceNumber),
            videoType: addVideoType || 'paddock',
            date: raceDate,
            kai: raceKai,
            nichi: raceNichi,
            url: null,
            label: addRaceName || undefined,
          umaban: addUmaban,
          };
          slot.url = buildSlotUrl(slot);
          return [...prev, slot];
        });
      };

      appendSlot();
    };

    window.addEventListener('message', handleMessage);
    return () => {
      window.removeEventListener('message', handleMessage);
    };
  }, []);

  // スロットを保存
  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(slots));
  }, [slots]);

  // 映像タイプのみ更新
  const updateVideoType = (id: number, videoType: VideoType) => {
    setSlots((prev) =>
      prev.map((slot) => {
        if (slot.id !== id) return slot;
        const updated = { ...slot, videoType };
        updated.url = buildSlotUrl(updated);
        return updated;
      })
    );
  };

  const closeAllSlots = () => {
    setSlots([]);
  };

  // スロット追加
  const addSlot = () => {
    const last = slots[slots.length - 1];
    const nextId = slots.length > 0 ? Math.max(...slots.map((s) => s.id)) + 1 : 1;
    const fallbackDate = new Date();
    const newSlot: ViewSlot = last
      ? {
          ...last,
          id: nextId,
          url: null,
        }
      : {
          id: nextId,
          track: '中山',
          raceNumber: 1,
          videoType: 'paddock',
          date: {
            year: fallbackDate.getFullYear(),
            month: fallbackDate.getMonth() + 1,
            day: fallbackDate.getDate(),
          },
          kai: 1,
          nichi: 1,
          url: null,
        };
    newSlot.url = buildSlotUrl(newSlot);
    setSlots((prev) => [...prev, newSlot]);
  };

  // スロット削除
  const removeSlot = (id: number) => {
    setSlots((prev) => prev.filter((s) => s.id !== id));
  };

  // レイアウトに応じたグリッドクラス
  const gridClass = 'grid-cols-1 md:grid-cols-2 auto-rows-fr';

  return (
    <div className="container py-6">
      {/* ヘッダー */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2 flex-wrap">
            📺 マルチビュー
            {horseName && (
              <Badge className="bg-emerald-600 text-white text-sm">
                🐴 {horseName}の過去レース
              </Badge>
            )}
            {horseId && (
              <Badge variant="outline" className="text-xs">
                馬番号: {horseId}
              </Badge>
            )}
            <Badge variant="outline" className="text-xs">実験的機能</Badge>
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {horseName 
              ? `${horseName}の過去レース映像を比較表示`
              : '複数の映像を同時に表示（iframeが許可されている場合のみ動作）'
            }
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="default"
            onClick={addSlot}
            disabled={false}
            className="bg-emerald-600 text-white hover:bg-emerald-500"
          >
            + 追加
          </Button>
          <Button
            variant="outline"
            onClick={closeAllSlots}
            disabled={slots.length === 0}
          >
            すべて閉じる
          </Button>
          {horseId && (
            <Button variant="outline" asChild>
              <Link href={`/horses/${horseId}`}>🐴 馬ページへ</Link>
            </Button>
          )}
          <Button variant="outline" asChild>
            <Link href="/">← 戻る</Link>
          </Button>
        </div>
      </div>

      {/* マルチビューエリア */}
      <div
        className={`grid ${gridClass} gap-4 h-[calc(100vh-220px)] min-h-[400px]`}
      >
        {slots.map((slot) => (
          <div
            key={slot.id}
            className="relative border rounded-lg overflow-hidden bg-black"
          >
            {/* ラベル & 切り替えボタン */}
            <div className="absolute top-2 left-2 z-10 flex flex-col gap-2">
              <div className="flex flex-wrap gap-2">
                <Badge className="bg-black/70 text-white">
                  {slot.track} {slot.raceNumber}R
                </Badge>
                <Badge
                  className={
                    slot.videoType === 'paddock'
                      ? 'bg-blue-600 text-white'
                      : slot.videoType === 'race'
                      ? 'bg-red-600 text-white'
                      : 'bg-amber-600 text-white'
                  }
                >
                  {slot.videoType === 'paddock'
                    ? 'パドック'
                    : slot.videoType === 'race'
                    ? 'レース'
                    : 'パトロール'}
                </Badge>
                {slot.label && (
                  <Badge className="bg-emerald-600/90 text-white">
                    {slot.label}
                  </Badge>
                )}
                {slot.umaban && (
                  <Badge className="bg-amber-500 text-white font-bold">
                    🔍 {slot.umaban}番
                  </Badge>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                {(['paddock', 'race', 'patrol'] as const).map((type) => (
                  <Button
                    key={type}
                    size="sm"
                    variant={slot.videoType === type ? 'default' : 'secondary'}
                    onClick={() => updateVideoType(slot.id, type)}
                    disabled={!slot.date || !slot.kai || !slot.nichi}
                    className="h-6 px-2 text-xs"
                  >
                    {type === 'paddock' ? 'パドック' : type === 'race' ? 'レース' : 'パトロール'}
                  </Button>
                ))}
              </div>
            </div>

            {/* 新しいウィンドウで開くボタン */}
            <div className="absolute top-2 right-2 z-10 flex gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => slot.url && window.open(slot.url, '_blank')}
                disabled={!slot.url}
              >
                🔗 別窓
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => removeSlot(slot.id)}
                className="text-white/80 hover:text-white"
              >
                ✕
              </Button>
            </div>

            {/* iframe */}
            {slot.url ? (
              <iframe
                src={slot.url}
                title={`${slot.track}${slot.raceNumber}R ${slot.videoType}`}
                className="w-full h-full border-0"
                allow="autoplay; fullscreen"
                sandbox="allow-same-origin allow-scripts allow-popups allow-forms"
              />
            ) : (
              <div className="flex items-center justify-center h-full text-white/50">
                レース一覧から追加してください
              </div>
            )}

            {/* iframe読み込み失敗時のフォールバック */}
            <div className="absolute inset-0 flex items-center justify-center bg-black/80 text-white text-center p-4 hidden" id={`fallback-${slot.id}`}>
              <div>
                <p className="mb-2">⚠️ iframeでの表示がブロックされています</p>
                <Button
                  variant="secondary"
                  onClick={() => slot.url && window.open(slot.url, '_blank')}
                >
                  別ウィンドウで開く
                </Button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* 注意事項 */}
      <div className="mt-6 p-4 bg-amber-500/10 border border-amber-500/30 rounded-lg">
        <h3 className="font-bold text-amber-600 mb-2">⚠️ 注意事項</h3>
        <ul className="text-sm text-muted-foreground space-y-1">
          <li>• JRAビュアーのセキュリティ設定により、iframe内での表示がブロックされる可能性があります</li>
          <li>• 表示されない場合は「別窓」ボタンで個別に開いてください</li>
          <li>• Windowsの「ウィンドウを左右に並べる」機能（Win + ← / →）で並べて配置できます</li>
        </ul>
      </div>
    </div>
  );
}

export default dynamic(() => Promise.resolve(MultiViewPage), { ssr: false });
