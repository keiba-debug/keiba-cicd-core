import Link from 'next/link';
import { notFound } from 'next/navigation';
import { getRaceDetail, getRaceNavigation, getRaceInfo } from '@/lib/data';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { RaceMemoEditor } from '@/components/race-memo-editor';
import { RaceContentWithMermaid } from '@/components/race-content-with-mermaid';
import { JraViewerLinks } from '@/components/jra-viewer-links';
import { generatePaddockUrl, generateRaceUrl, generatePatrolUrl, getKaisaiInfoFromRaceInfo } from '@/lib/jra-viewer-url';

interface PageProps {
  params: Promise<{
    date: string;
    track: string;
    id: string;
  }>;
}

export default async function RaceDetailPage({ params }: PageProps) {
  const { date, track: encodedTrack, id } = await params;
  const track = decodeURIComponent(encodedTrack);
  
  // レースIDからレース番号を抽出
  const currentRaceNumber = parseInt(id.slice(-2), 10);

  const [race, navigation, raceInfo] = await Promise.all([
    getRaceDetail(date, track, id),
    getRaceNavigation(date, track, currentRaceNumber),
    getRaceInfo(date),
  ]);

  if (!race) {
    notFound();
  }

  // JRAビュアーURL生成
  let paddockUrl: string | null = null;
  let raceUrl: string | null = null;
  let patrolUrl: string | null = null;
  
  if (raceInfo) {
    const kaisaiInfo = getKaisaiInfoFromRaceInfo(raceInfo.kaisai_data, id);
    if (kaisaiInfo) {
      const [year, month, day] = date.split('-').map(Number);
      const params = {
        year,
        month,
        day,
        track: kaisaiInfo.track,
        kai: kaisaiInfo.kai,
        nichi: kaisaiInfo.nichi,
        raceNumber: currentRaceNumber,
      };
      paddockUrl = generatePaddockUrl(params);
      raceUrl = generateRaceUrl(params);
      patrolUrl = generatePatrolUrl(params);
    }
  }

  // 競馬場切り替え時に同じレース番号を維持するためのヘルパー
  const getTrackRaceId = (targetTrack: string, raceNumber: number): string => {
    if (!navigation) return '';
    const trackInfo = navigation.tracks.find((t) => t.name === targetTrack);
    if (!trackInfo) return '';
    // 同じレース番号があればそれを、なければ最も近いレース番号を使用
    if (trackInfo.raceByNumber[raceNumber]) {
      return trackInfo.raceByNumber[raceNumber];
    }
    // 最も近いレース番号を探す
    const availableNumbers = Object.keys(trackInfo.raceByNumber).map(Number).sort((a, b) => a - b);
    const closest = availableNumbers.reduce((prev, curr) =>
      Math.abs(curr - raceNumber) < Math.abs(prev - raceNumber) ? curr : prev
    );
    return trackInfo.raceByNumber[closest] || trackInfo.firstRaceId;
  };

  return (
    <div className="container py-6">
      {/* レースナビゲーション */}
      {navigation && (
        <div className="race-navigation mb-4 p-3 bg-muted/30 rounded-lg border">
          {/* 出走時間順ナビ（前後のレース） */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              {navigation.prevRace ? (
                <Link
                  href={`/races/${date}/${encodeURIComponent(navigation.prevRace.track)}/${navigation.prevRace.raceId}`}
                  className="px-3 py-1.5 text-sm rounded-md bg-secondary hover:bg-secondary/80 transition-colors flex items-center gap-1"
                >
                  ← 前のレース
                </Link>
              ) : (
                <span className="px-3 py-1.5 text-sm rounded-md bg-muted text-muted-foreground cursor-not-allowed">
                  ← 前のレース
                </span>
              )}
            </div>
            <span className="text-xs text-muted-foreground">
              出走時間順
            </span>
            <div className="flex items-center gap-2">
              {navigation.nextRace ? (
                <Link
                  href={`/races/${date}/${encodeURIComponent(navigation.nextRace.track)}/${navigation.nextRace.raceId}`}
                  className="px-3 py-1.5 text-sm rounded-md bg-secondary hover:bg-secondary/80 transition-colors flex items-center gap-1"
                >
                  次のレース →
                </Link>
              ) : (
                <span className="px-3 py-1.5 text-sm rounded-md bg-muted text-muted-foreground cursor-not-allowed">
                  次のレース →
                </span>
              )}
            </div>
          </div>

          {/* 競馬場切り替え（同レース番号を維持） */}
          <div className="flex items-center gap-2 mb-2">
            <span className="text-sm font-medium text-muted-foreground">🏟️</span>
            <div className="flex gap-1">
              {navigation.tracks.map((t) => {
                const targetRaceId = t.name === track 
                  ? id 
                  : getTrackRaceId(t.name, currentRaceNumber);
                return (
                  <Link
                    key={t.name}
                    href={`/races/${date}/${encodeURIComponent(t.name)}/${targetRaceId}`}
                    className={`px-3 py-1 text-sm rounded-md transition-colors border track-nav-item ${
                      t.name === track ? 'track-nav-active' : 'track-nav-inactive'
                    }`}
                  >
                    {t.name}
                  </Link>
                );
              })}
            </div>
          </div>

          {/* レース番号ナビ */}
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-muted-foreground">🏇</span>
            <div className="flex flex-wrap gap-1">
              {navigation.races.map((r) => (
                <Link
                  key={r.raceId}
                  href={`/races/${date}/${encodeURIComponent(track)}/${r.raceId}`}
                  className={`px-2 py-1 text-xs rounded transition-colors border race-nav-item ${
                    r.raceId === id ? 'race-nav-active' : 'race-nav-inactive'
                  }`}
                  title={`${r.raceName} (${r.startTime})`}
                >
                  {r.raceNumber}R
                </Link>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* パンくずリスト */}
      <nav className="flex items-center space-x-2 text-sm text-muted-foreground mb-4">
        <Link href="/" className="hover:underline">
          トップ
        </Link>
        <span>/</span>
        <Link href={`/?date=${date}`} className="hover:underline">
          {date}
        </Link>
        <span>/</span>
        <span>{track}</span>
        <span>/</span>
        <span className="text-foreground">{race.raceNumber}R</span>
      </nav>

      {/* ヘッダー */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <Badge variant="outline" className="text-lg font-mono px-3 py-1">
            {race.raceNumber}R
          </Badge>
          <h1 className="text-2xl font-bold">{race.raceName}</h1>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-muted-foreground mb-3">
          <span>📅 {race.date}</span>
          <span>🏟️ {race.track}競馬場</span>
          <span>🏃 {race.distance}</span>
          {race.startTime && <span>⏰ {race.startTime}</span>}
          {race.className && (
            <Badge variant="secondary">{race.className}</Badge>
          )}
        </div>
        {/* JRAレーシングビュアーリンク */}
        <JraViewerLinks paddockUrl={paddockUrl} raceUrl={raceUrl} patrolUrl={patrolUrl} />
      </div>

      <Separator className="my-6" />

      {/* 予想メモ編集 */}
      <RaceMemoEditor date={date} raceId={id} />

      {/* レース内容（Markdown変換済みHTML + Mermaid対応） */}
      <RaceContentWithMermaid htmlContent={race.htmlContent} />

      {/* 戻るボタン */}
      <div className="mt-8 flex gap-4">
        <Button variant="outline" asChild>
          <Link href="/">← レース一覧に戻る</Link>
        </Button>
      </div>
    </div>
  );
}
