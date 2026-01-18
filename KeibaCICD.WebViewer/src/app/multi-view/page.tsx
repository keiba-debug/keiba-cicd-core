'use client';

import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

// 競馬場コード（JRAビュアー形式 - 1桁）
const TRACK_CODES: Record<string, number> = {
  '札幌': 1, '函館': 2, '福島': 3, '新潟': 4, '東京': 5,
  '中山': 6, '中京': 7, '京都': 8, '阪神': 9, '小倉': 0,
};

// レース番号を16進数に変換（1-9→数字, 10→a, 11→b, 12→c）
function raceNumberToHex(raceNumber: number): string {
  return raceNumber.toString(16);
}

type VideoType = 'paddock' | 'race' | 'patrol';

interface ViewSlot {
  id: number;
  track: string;
  raceNumber: number;
  videoType: VideoType;
  url: string | null;
  label?: string; // 追加: レース名など
  umaban?: string; // 馬番（出走番号）
}

// クエリパラメータから渡されるレース情報
interface RaceParam {
  date: string;     // YYYY/MM/DD
  track: string;    // 競馬場名
  raceNumber: number;
  raceName?: string;
  kai?: number;
  nichi?: number;
  umaban?: string;  // 馬番（出走番号）
}

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

  const yearShort = year % 100;
  const dateStr = `${year}${String(month).padStart(2, '0')}${String(day).padStart(2, '0')}`;
  
  // JRAビュアー形式: 年下2桁 + 場コード(1桁) + 回次(1桁) + 日次(16進数) + レース番号(16進数)
  // 例: 中山7日目1R→266171, 東京10日目3R→2554a3
  const raceCode = `${yearShort}${trackCode}${kai}${nichi.toString(16)}${raceNumberToHex(raceNumber)}`;

  let suffix = '';
  if (videoType === 'paddock') suffix = '_p';
  else if (videoType === 'patrol') suffix = '_a';

  // URLはエンコードなし
  const target = `race/${year}/${dateStr}/${raceCode}${suffix}`;
  return `https://regist.prc.jp/api/windowopen.aspx?target=${target}&quality=4`;
}

export default function MultiViewPage() {
  const searchParams = useSearchParams();
  
  // クエリパラメータから馬ID・馬名とレース情報を取得
  const horseId = searchParams.get('horseId');
  const horseName = searchParams.get('horse');
  const racesParam = searchParams.get('races');
  
  // 今日の日付（仮: 2026-01-18）- クエリパラメータがない場合のデフォルト
  const [date, setDate] = useState({ year: 2026, month: 1, day: 18 });
  const [kai, setKai] = useState(1); // 1回
  const [nichi, setNichi] = useState(7); // 7日目

  // 開催競馬場
  const [availableTracks] = useState(['中山', '京都', '東京', '阪神', '中京', '小倉', '福島', '新潟', '札幌', '函館']);

  // ビュースロット（最大4つ）
  const [slots, setSlots] = useState<ViewSlot[]>([
    { id: 1, track: '中山', raceNumber: 1, videoType: 'paddock', url: null },
    { id: 2, track: '京都', raceNumber: 1, videoType: 'paddock', url: null },
    { id: 3, track: '中山', raceNumber: 2, videoType: 'paddock', url: null },
    { id: 4, track: '京都', raceNumber: 2, videoType: 'paddock', url: null },
  ]);
  
  // 初期化フラグ
  const [initialized, setInitialized] = useState(false);

  // レイアウト - デフォルトで2x2
  const [layout, setLayout] = useState<'2x1' | '2x2' | '1x2'>('2x2');
  
  // クエリパラメータからレース情報を初期化
  useEffect(() => {
    if (initialized || !racesParam) return;
    
    try {
      const races: RaceParam[] = JSON.parse(racesParam);
      if (!Array.isArray(races) || races.length === 0) return;
      
      // 最初のレースから日付とkai/nichiを取得するためにAPIを呼ぶ
      const initSlots = async () => {
        const newSlots: ViewSlot[] = [];
        
        for (let i = 0; i < Math.min(races.length, 4); i++) {
          const race = races[i];
          
          // 日付をパース (YYYY/MM/DD)
          const dateParts = race.date.match(/(\d{4})\/(\d{1,2})\/(\d{1,2})/);
          if (!dateParts) continue;
          
          const raceDate = {
            year: parseInt(dateParts[1]),
            month: parseInt(dateParts[2]),
            day: parseInt(dateParts[3]),
          };
          
          // kai/nichiを取得するためにAPIを呼ぶ
          let raceKai = race.kai || 1;
          let raceNichi = race.nichi || 1;
          
          if (!race.kai || !race.nichi) {
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
          
          // 最初のスロットの日付を全体の日付として設定
          if (i === 0) {
            setDate(raceDate);
            setKai(raceKai);
            setNichi(raceNichi);
          }
          
          const url = generateUrl(
            raceDate.year,
            raceDate.month,
            raceDate.day,
            race.track,
            raceKai,
            raceNichi,
            race.raceNumber,
            'paddock'
          );
          
          newSlots.push({
            id: i + 1,
            track: race.track,
            raceNumber: race.raceNumber,
            videoType: 'paddock',
            url,
            label: race.raceName,
            umaban: race.umaban,
          });
        }
        
        if (newSlots.length > 0) {
          setSlots(newSlots);
          // スロット数に応じてレイアウトを自動調整
          if (newSlots.length <= 2) {
            setLayout('2x1');
          } else {
            setLayout('2x2');
          }
        }
        setInitialized(true);
      };
      
      initSlots();
    } catch {
      setInitialized(true);
    }
  }, [racesParam, initialized]);

  // URL更新
  useEffect(() => {
    setSlots((prev) =>
      prev.map((slot) => ({
        ...slot,
        url: generateUrl(
          date.year,
          date.month,
          date.day,
          slot.track,
          kai,
          nichi,
          slot.raceNumber,
          slot.videoType
        ),
      }))
    );
  }, [date, kai, nichi]);

  // スロット更新
  const updateSlot = (id: number, updates: Partial<ViewSlot>) => {
    setSlots((prev) =>
      prev.map((slot) => {
        if (slot.id !== id) return slot;
        const updated = { ...slot, ...updates };
        updated.url = generateUrl(
          date.year,
          date.month,
          date.day,
          updated.track,
          kai,
          nichi,
          updated.raceNumber,
          updated.videoType
        );
        return updated;
      })
    );
  };

  // スロット追加
  const addSlot = () => {
    if (slots.length >= 4) return;
    const newId = Math.max(...slots.map((s) => s.id)) + 1;
    const newTrack = slots.length % 2 === 0 ? '中山' : '京都'; // 交互に競馬場を設定
    const newRaceNumber = Math.floor(slots.length / 2) + 1; // レース番号も変える
    const newUrl = generateUrl(
      date.year,
      date.month,
      date.day,
      newTrack,
      kai,
      nichi,
      newRaceNumber,
      'paddock' as VideoType
    );
    setSlots((prev) => [
      ...prev,
      { id: newId, track: newTrack, raceNumber: newRaceNumber, videoType: 'paddock', url: newUrl },
    ]);
  };

  // スロット削除
  const removeSlot = (id: number) => {
    if (slots.length <= 1) return;
    setSlots((prev) => prev.filter((s) => s.id !== id));
  };

  // レイアウトに応じたグリッドクラス
  const gridClass =
    layout === '2x2'
      ? 'grid-cols-2 grid-rows-2'
      : layout === '1x2'
      ? 'grid-cols-1 grid-rows-2'
      : 'grid-cols-2 grid-rows-1';

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

      {/* コントロールパネル */}
      <Card className="mb-6">
        <CardHeader className="py-3">
          <CardTitle className="text-base">🎛️ 表示設定</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* レイアウト選択 */}
          <div className="flex items-center gap-4">
            <span className="text-sm font-medium">レイアウト:</span>
            <div className="flex gap-2">
              {(['2x1', '1x2', '2x2'] as const).map((l) => (
                <Button
                  key={l}
                  variant={layout === l ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setLayout(l)}
                >
                  {l === '2x1' ? '横2列' : l === '1x2' ? '縦2列' : '2x2'}
                </Button>
              ))}
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={addSlot}
              disabled={slots.length >= 4}
            >
              + 追加
            </Button>
          </div>

          {/* スロット設定 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {slots.map((slot, index) => (
              <div
                key={slot.id}
                className="flex items-center gap-2 p-3 bg-muted/30 rounded-lg border"
              >
                <span className="font-bold text-sm w-8">#{index + 1}</span>

                {/* 競馬場 */}
                <select
                  value={slot.track}
                  onChange={(e) => updateSlot(slot.id, { track: e.target.value })}
                  className="px-2 py-1 text-sm rounded border bg-background"
                >
                  {availableTracks.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>

                {/* レース番号 */}
                <select
                  value={slot.raceNumber}
                  onChange={(e) =>
                    updateSlot(slot.id, { raceNumber: parseInt(e.target.value) })
                  }
                  className="px-2 py-1 text-sm rounded border bg-background"
                >
                  {Array.from({ length: 12 }, (_, i) => i + 1).map((n) => (
                    <option key={n} value={n}>
                      {n}R
                    </option>
                  ))}
                </select>

                {/* 映像タイプ */}
                <select
                  value={slot.videoType}
                  onChange={(e) =>
                    updateSlot(slot.id, { videoType: e.target.value as VideoType })
                  }
                  className="px-2 py-1 text-sm rounded border bg-background"
                >
                  <option value="paddock">パドック</option>
                  <option value="race">レース</option>
                  <option value="patrol">パトロール</option>
                </select>

                {/* 削除 */}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => removeSlot(slot.id)}
                  disabled={slots.length <= 1}
                  className="ml-auto text-red-500 hover:text-red-700"
                >
                  ✕
                </Button>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* マルチビューエリア */}
      <div
        className={`grid ${gridClass} gap-4`}
        style={{ height: 'calc(100vh - 400px)', minHeight: '400px' }}
      >
        {slots.map((slot) => (
          <div
            key={slot.id}
            className="relative border rounded-lg overflow-hidden bg-black"
          >
            {/* ラベル */}
            <div className="absolute top-2 left-2 z-10 flex flex-wrap gap-2">
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

            {/* 新しいウィンドウで開くボタン */}
            <Button
              variant="secondary"
              size="sm"
              className="absolute top-2 right-2 z-10"
              onClick={() => slot.url && window.open(slot.url, '_blank')}
            >
              🔗 別窓
            </Button>

            {/* iframe */}
            {slot.url ? (
              <iframe
                src={slot.url}
                className="w-full h-full border-0"
                allow="autoplay; fullscreen"
                sandbox="allow-same-origin allow-scripts allow-popups allow-forms"
              />
            ) : (
              <div className="flex items-center justify-center h-full text-white/50">
                映像を選択してください
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
