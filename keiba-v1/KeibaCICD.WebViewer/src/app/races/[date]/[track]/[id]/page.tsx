import Link from 'next/link';
import Image from 'next/image';
import { notFound } from 'next/navigation';
import { ChevronLeft, ChevronRight, MessageCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { getRaceDetail, getRaceNavigation, getRaceInfo } from '@/lib/data';
import { RaceMemoEditor } from '@/components/race-memo-editor';
import { RaceContentWithMermaid } from '@/components/race-content-with-mermaid';
import { RaceFetchDropdown } from '@/components/race-fetch-dropdown';
import { generatePaddockUrl, generateRaceUrl, generatePatrolUrl, getKaisaiInfoFromRaceInfo } from '@/lib/jra-viewer-url';
import { formatTrainerName } from '@/types/race-data';

interface PageProps {
  params: Promise<{
    date: string;
    track: string;
    id: string;
  }>;
}

// 競馬場テキストカラー（CSS変数を使用）
const getTrackTextClass = (trackName: string) => {
  const map: Record<string, string> = {
    '中山': 'text-[var(--color-venue-nakayama)]',
    '京都': 'text-[var(--color-venue-kyoto)]',
    '小倉': 'text-[var(--color-venue-kokura)]',
    '東京': 'text-[var(--color-venue-tokyo)]',
    '阪神': 'text-[var(--color-venue-hanshin)]',
  };
  return map[trackName] || 'text-primary';
};

// 競馬場背景カラー（タブ用）
const getTrackBgClass = (trackName: string) => {
  const map: Record<string, string> = {
    '中山': 'bg-[var(--color-venue-nakayama)]',
    '京都': 'bg-[var(--color-venue-kyoto)]',
    '小倉': 'bg-[var(--color-venue-kokura)]',
    '東京': 'bg-[var(--color-venue-tokyo)]',
    '阪神': 'bg-[var(--color-venue-hanshin)]',
  };
  return map[trackName] || 'bg-primary';
};

// コース条件フォーマット
const formatCondition = (distance?: string) => {
  if (!distance) return '';
  const normalized = distance.replace('：', ':').replace('・', ' ').trim();
  const withSpace = normalized.replace(':', ' ');
  return withSpace.replace(/m/gi, 'M').replace(/\s+/g, ' ');
};

// コースバッジのスタイル
const getCourseBadgeClass = (distance?: string) => {
  if (!distance) return 'text-muted-foreground bg-muted';
  if (distance.startsWith('芝')) {
    return 'text-[var(--color-surface-turf)] bg-[var(--color-surface-turf)]/10';
  }
  if (distance.startsWith('ダ')) {
    return 'text-[var(--color-surface-dirt)] bg-[var(--color-surface-dirt)]/10';
  }
  if (distance.startsWith('障')) {
    return 'text-[var(--color-surface-steeplechase)] bg-[var(--color-surface-steeplechase)]/10';
  }
  return 'text-muted-foreground bg-muted';
};

// 枠番カラー（1-8枠）
const getWakuColor = (waku: number) => {
  const colors: Record<number, { bg: string; text: string; border: string }> = {
    1: { bg: 'bg-white', text: 'text-gray-900', border: 'border-gray-300' },
    2: { bg: 'bg-gray-900', text: 'text-white', border: 'border-gray-900' },
    3: { bg: 'bg-red-600', text: 'text-white', border: 'border-red-600' },
    4: { bg: 'bg-blue-600', text: 'text-white', border: 'border-blue-600' },
    5: { bg: 'bg-yellow-400', text: 'text-gray-900', border: 'border-yellow-400' },
    6: { bg: 'bg-green-600', text: 'text-white', border: 'border-green-600' },
    7: { bg: 'bg-orange-500', text: 'text-white', border: 'border-orange-500' },
    8: { bg: 'bg-pink-500', text: 'text-white', border: 'border-pink-500' },
  };
  return colors[waku] || colors[1];
};

// Markdownから馬データを抽出するヘルパー関数
function extractHorsesFromMarkdown(content: string) {
  const horses: any[] = [];
  
  // 出走表セクションを探す
  // より柔軟な正規表現: "枠" を含むヘッダー行を探す
  const tableMatch = content.match(/\|[^|]*枠[^|]*\|[\s\S]*?(?=\n\n|\n#|$)/);
  if (!tableMatch) return horses;

  const tableLines = tableMatch[0].split('\n').filter(line => line.trim().startsWith('|'));
  // ヘッダーと区切り行をスキップ
  // 区切り行は通常 |---|---| のような形式
  const dataLines = tableLines.filter(line => !line.match(/^\|\s*:?-+:?\s*\|/)).slice(1);

  dataLines.forEach(line => {
    const cols = line.split('|').map(c => c.trim()).filter((_, i, arr) => i > 0 && i < arr.length - 1);
    if (cols.length < 3) return;

    // 数値パース用ヘルパー
    const parseIntSafe = (v: string) => {
      const n = parseInt(v?.replace(/[^0-9]/g, '') || '0', 10);
      return isNaN(n) ? 0 : n;
    };
    const parseFloatSafe = (v: string) => {
      const n = parseFloat(v?.replace(/[^0-9.]/g, '') || '0');
      return isNaN(n) ? 0 : n;
    };

    // カラムインデックスの推定（Markdownの構造に依存）
    // 一般的な形式: | 枠 | 番 | 馬名 | 性齢 | 斤量 | 騎手 | 調教師 | ...
    const waku = parseIntSafe(cols[0]);
    const umaban = parseIntSafe(cols[1]);
    
    // 馬名処理: [馬名](/horses/...) リンク形式を除去して名前だけ取得
    let nameData = cols[2];
    const nameMatch = nameData.match(/\[(.*?)\]/);
    const name = nameMatch ? nameMatch[1] : nameData.replace(/<[^>]+>/g, ''); // HTMLタグも除去

    const sexAge = cols[3] || '';
    const sex = sexAge.charAt(0) || '';
    const age = parseIntSafe(sexAge);
    const weight = parseFloatSafe(cols[4]);
    const jockey = cols[5] || '';
    const trainer = cols[6] || '';
    
    // オッズと人気（ある場合）
    // データ量によってカラム位置が変わる可能性があるため、末尾から取得する戦略も考慮
    // ここでは標準的なフォーマットを仮定
    let odds = 0;
    let popularity = 0;
    
    if (cols.length >= 8) {
       // オッズ列を探す（数値っぽい列）
       const possibleOdds = parseFloatSafe(cols[7]);
       if (possibleOdds > 0) odds = possibleOdds;
       
       const possiblePop = parseIntSafe(cols[8]);
       if (possiblePop > 0) popularity = possiblePop;
    }

    if (name) {
      horses.push({
        waku,
        umaban,
        name,
        sex,
        age,
        weight,
        jockey,
        trainer,
        odds,
        popularity
      });
    }
  });

  return horses;
}

export default async function RaceDetailPage({ params }: PageProps) {
  const { date, track: encodedTrack, id } = await params;
  const track = decodeURIComponent(encodedTrack);
  
  // レースIDからレース番号を抽出
  const currentRaceNumber = parseInt(id.slice(-2), 10);

  const [raceData, navigation, raceInfo] = await Promise.all([
    getRaceDetail(date, track, id),
    getRaceNavigation(date, track, currentRaceNumber),
    getRaceInfo(date),
  ]);

  if (!raceData) {
    notFound();
  }

  // Markdownから馬データを抽出
  const horses = extractHorsesFromMarkdown(raceData.content);
  // raceDataにhorsesをマージしたオブジェクトを作成
  const race = { ...raceData, horses };

  // もしhorsesが抽出できたら、HTMLコンテンツからテーブル部分を除去する
  let displayHtmlContent = race.htmlContent;
  if (horses.length > 0) {
    // <table>...</table> を空文字に置換
    // 注: 複数のテーブルがある場合（払戻金など）、最初のテーブル（出走表）だけを消したい
    // 出走表は通常一番上にあるが、念のため内容で判断できればベスト
    // ここでは単純に最初のtableを消す（出走表と仮定）
    displayHtmlContent = displayHtmlContent.replace(/<table[\s\S]*?<\/table>/, '');
  }

  // JRAビュアーURL生成
  let paddockUrl: string | null = null;
  let raceUrl: string | null = null;
  let patrolUrl: string | null = null;
  let kaisaiKai: number | undefined;
  let kaisaiNichi: number | undefined;

  if (raceInfo) {
    const kaisaiInfo = getKaisaiInfoFromRaceInfo(raceInfo.kaisai_data, id);
    if (kaisaiInfo) {
      kaisaiKai = kaisaiInfo.kai;
      kaisaiNichi = kaisaiInfo.nichi;
      const [year, month, day] = date.split('-').map(Number);
      const urlParams = {
        year,
        month,
        day,
        track: kaisaiInfo.track,
        kai: kaisaiInfo.kai,
        nichi: kaisaiInfo.nichi,
        raceNumber: currentRaceNumber,
      };
      paddockUrl = generatePaddockUrl(urlParams);
      raceUrl = generateRaceUrl(urlParams);
      patrolUrl = generatePatrolUrl(urlParams);
    }
  }

  // 外部リンクURL生成
  const [year, month, day] = date.split('-');
  const keibabookUrl = `https://p.keibabook.co.jp/cyuou/syutsuba/${year}${month}${day}${id.slice(-4, -2)}${id.slice(-2).padStart(2, '0')}`;
  // netkeiba race_id: YYYY + 場コード(2) + 回(2) + 日(2) + レース番号(2) = 12桁
  const trackCodesV1: Record<string, string> = {
    '札幌': '01', '函館': '02', '福島': '03', '新潟': '04', '東京': '05',
    '中山': '06', '中京': '07', '京都': '08', '阪神': '09', '小倉': '10',
  };
  const trackCodeV1 = trackCodesV1[track];
  const netkeibaRaceId = kaisaiKai && kaisaiNichi && trackCodeV1
    ? `${year}${trackCodeV1}${String(kaisaiKai).padStart(2, '0')}${String(kaisaiNichi).padStart(2, '0')}${String(currentRaceNumber).padStart(2, '0')}`
    : null;
  const netkeibaUrl = netkeibaRaceId ? `https://race.netkeiba.com/race/shutuba.html?race_id=${netkeibaRaceId}&rf=race_submenu` : null;
  const netkeibaBbsUrl = netkeibaRaceId ? `https://yoso.netkeiba.com/?pid=race_board&id=c${netkeibaRaceId}` : null;

  // 競馬場切り替え時に同じレース番号を維持するためのヘルパー
  const getTrackRaceId = (targetTrack: string, raceNumber: number): string => {
    if (!navigation) return '';
    const trackInfo = navigation.tracks.find((t) => t.name === targetTrack);
    if (!trackInfo) return '';
    if (trackInfo.raceByNumber[raceNumber]) {
      return trackInfo.raceByNumber[raceNumber];
    }
    const availableNumbers = Object.keys(trackInfo.raceByNumber).map(Number).sort((a, b) => a - b);
    const closest = availableNumbers.reduce((prev, curr) =>
      Math.abs(curr - raceNumber) < Math.abs(prev - raceNumber) ? curr : prev
    );
    return trackInfo.raceByNumber[closest] || trackInfo.firstRaceId;
  };

  const trackColor = getTrackTextClass(track);

  return (
    <div className="race-detail-page py-6">
      {/* レースナビゲーション - 改善版 */}
      {navigation && (
        <div className="mb-4 p-3 bg-card rounded-xl border shadow-sm">
          <div className="flex items-center gap-3">
            {/* 前のレースボタン */}
            {navigation.prevRace ? (
              <Link
                href={`/races/${date}/${encodeURIComponent(navigation.prevRace.track)}/${navigation.prevRace.raceId}`}
                className="w-9 h-9 rounded-full bg-gray-100 hover:bg-gray-200 active:bg-gray-300 transition-all duration-150 flex items-center justify-center shadow-sm hover:shadow"
                title="前のレース"
              >
                <ChevronLeft className="w-5 h-5 text-gray-600" />
              </Link>
            ) : (
              <span className="w-9 h-9 rounded-full bg-gray-50 text-gray-300 flex items-center justify-center cursor-not-allowed">
                <ChevronLeft className="w-5 h-5" />
              </span>
            )}

            {/* 競馬場タブ */}
            <div className="flex gap-1.5 bg-gray-100 p-1 rounded-lg">
              {navigation.tracks.map((t) => {
                const isActive = t.name === track;
                return (
                  <Link
                    key={t.name}
                    href={`/races/${date}/${encodeURIComponent(t.name)}/${t.firstRaceId}`}
                    className={`px-4 py-2 text-sm font-bold rounded-md transition-all duration-200 ${
                      isActive 
                        ? `${getTrackBgClass(t.name)} text-white shadow-md scale-105` 
                        : 'bg-white hover:bg-gray-50 text-gray-600 hover:text-gray-900 shadow-sm hover:shadow'
                    }`}
                  >
                    {t.name}
                  </Link>
                );
              })}
            </div>

            {/* 区切り線 */}
            <div className="w-px h-8 bg-gray-200" />

            {/* レース番号タブ */}
            <div className="flex gap-1 flex-wrap bg-gray-50 p-1.5 rounded-lg">
              {navigation.races.map((r) => {
                const isActive = r.raceId === id;
                return (
                  <Link
                    key={r.raceId}
                    href={`/races/${date}/${encodeURIComponent(track)}/${r.raceId}`}
                    className={`w-8 h-8 text-xs font-bold rounded-md transition-all duration-150 flex items-center justify-center ${
                      isActive 
                        ? 'bg-gray-800 text-white shadow-md scale-110' 
                        : 'bg-white hover:bg-gray-100 text-gray-600 hover:text-gray-900 shadow-sm hover:shadow'
                    }`}
                    title={`${r.raceName} (${r.startTime})`}
                  >
                    {r.raceNumber}
                  </Link>
                );
              })}
            </div>

            {/* 次のレースボタン */}
            {navigation.nextRace ? (
              <Link
                href={`/races/${date}/${encodeURIComponent(navigation.nextRace.track)}/${navigation.nextRace.raceId}`}
                className="w-9 h-9 rounded-full bg-gray-100 hover:bg-gray-200 active:bg-gray-300 transition-all duration-150 flex items-center justify-center ml-auto shadow-sm hover:shadow"
                title="次のレース"
              >
                <ChevronRight className="w-5 h-5 text-gray-600" />
              </Link>
            ) : (
              <span className="w-9 h-9 rounded-full bg-gray-50 text-gray-300 flex items-center justify-center cursor-not-allowed ml-auto">
                <ChevronRight className="w-5 h-5" />
              </span>
            )}
          </div>
        </div>
      )}

      {/* パンくずリスト */}
      <nav className="flex items-center space-x-2 text-sm text-muted-foreground mb-4">
        <Link href="/" className="hover:underline">トップ</Link>
        <span>/</span>
        <Link href={`/?date=${date}`} className="hover:underline">{date}</Link>
        <span>/</span>
        <span className={trackColor}>{track}</span>
        <span>/</span>
        <span className="text-foreground font-medium">{race.raceNumber}R</span>
      </nav>

      {/* レースヘッダー - 2行コンパクト */}
      <div className="mb-6 p-4 bg-card rounded-lg border">
        <div className="flex items-start justify-between gap-4">
          {/* 左側: レース情報 */}
          <div className="flex-1">
            {/* 1行目: レース番号 + レース名 */}
            <div className="flex items-center gap-3 mb-2">
              <span className={`text-2xl font-bold ${trackColor}`}>{race.raceNumber}R</span>
              <h1 className="text-xl font-bold">{race.raceName}</h1>
            </div>
            {/* 2行目: 競馬場 + コース + 発走時刻 + クラス */}
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className={`font-bold ${trackColor}`}>{track}</span>
              {race.distance && (
                <span className={`text-xs font-bold px-1.5 py-0.5 rounded-sm ${getCourseBadgeClass(race.distance)}`}>
                  {formatCondition(race.distance)}
                </span>
              )}
              {race.startTime && (
                <span className="text-muted-foreground text-xs font-mono">{race.startTime}発走</span>
              )}
              {race.className && (
                <span className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded-sm">
                  {race.className}
                </span>
              )}
            </div>
          </div>

          {/* 右側: リンク群 */}
          <div className="flex items-center gap-3">
            {/* JRAビュアーリンク */}
            <div className="flex items-center gap-1">
              {paddockUrl && (
                <a
                  href={paddockUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-8 h-8 rounded-full bg-orange-500 text-white flex items-center justify-center text-xs font-bold hover:opacity-80 transition-opacity"
                  title="JRAレーシングビュアー パドック"
                >
                  パ
                </a>
              )}
              {raceUrl && (
                <a
                  href={raceUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-8 h-8 rounded-full bg-green-600 text-white flex items-center justify-center text-xs font-bold hover:opacity-80 transition-opacity"
                  title="JRAレーシングビュアー レース"
                >
                  レ
                </a>
              )}
              {patrolUrl && (
                <a
                  href={patrolUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-8 h-8 rounded-full bg-rose-500 text-white flex items-center justify-center text-xs font-bold hover:opacity-80 transition-opacity"
                  title="JRAレーシングビュアー パトロール"
                >
                  T
                </a>
              )}
            </div>

            {/* 区切り線 */}
            <div className="w-px h-6 bg-border" />

            {/* 外部リンク */}
            <div className="flex items-center gap-1">
              <a
                href={keibabookUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="w-6 h-6 rounded hover:opacity-80 transition-opacity flex items-center justify-center overflow-hidden"
                title="競馬ブック"
              >
                <Image src="/keibabook.ico" alt="競馬ブック" width={24} height={24} className="rounded" />
              </a>
              {netkeibaUrl && (
                <a
                  href={netkeibaUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-6 h-6 rounded hover:opacity-80 transition-opacity flex items-center justify-center overflow-hidden"
                  title="netkeiba"
                >
                  <Image src="/netkeiba.png" alt="netkeiba" width={24} height={24} className="rounded" />
                </a>
              )}
              {netkeibaBbsUrl && (
                <a
                  href={netkeibaBbsUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-6 h-6 rounded hover:opacity-80 transition-opacity flex items-center justify-center"
                  title="netkeiba BBS"
                >
                  <MessageCircle className="w-5 h-5 text-blue-500" />
                </a>
              )}
            </div>

            {/* 区切り線 */}
            <div className="w-px h-6 bg-border" />

            {/* データ取得ドロップダウン */}
            <RaceFetchDropdown date={date} raceNumber={currentRaceNumber} />
          </div>
        </div>
      </div>

      {/* 予想メモ編集 */}
      <RaceMemoEditor date={date} raceId={id} />

      {/* 出走馬テーブル (データがある場合のみ表示) */}
      {race.horses.length > 0 && (
        <div className="bg-card rounded-lg border overflow-hidden mt-6 mb-6">
          <div className="bg-gradient-to-r from-gray-800 to-gray-700 text-white px-4 py-3">
            <h2 className="font-bold text-lg">出走馬一覧</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-100 border-b">
                  <th className="px-2 py-2.5 text-center font-bold w-10">枠</th>
                  <th className="px-2 py-2.5 text-center font-bold w-10">番</th>
                  <th className="px-3 py-2.5 text-left font-bold min-w-[140px]">馬名</th>
                  <th className="px-2 py-2.5 text-center font-bold w-14">性齢</th>
                  <th className="px-2 py-2.5 text-center font-bold w-14">斤量</th>
                  <th className="px-3 py-2.5 text-left font-bold min-w-[80px]">騎手</th>
                  <th className="px-3 py-2.5 text-left font-bold min-w-[80px]">調教師</th>
                  <th className="px-2 py-2.5 text-right font-bold w-16">オッズ</th>
                  <th className="px-2 py-2.5 text-center font-bold w-10">人</th>
                </tr>
              </thead>
              <tbody>
                {race.horses.map((horse, index) => {
                  const wakuColor = getWakuColor(horse.waku);
                  return (
                    <tr 
                      key={horse.umaban}
                      className={`border-b transition-colors hover:bg-blue-50/50 ${
                        index % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'
                      }`}
                    >
                      {/* 枠番 */}
                      <td className="px-2 py-2 text-center">
                        <span className={`inline-flex items-center justify-center w-7 h-7 rounded-sm text-xs font-bold border ${wakuColor.bg} ${wakuColor.text} ${wakuColor.border}`}>
                          {horse.waku}
                        </span>
                      </td>
                      {/* 馬番 */}
                      <td className="px-2 py-2 text-center">
                        <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-white border-2 border-gray-300 text-xs font-bold">
                          {horse.umaban}
                        </span>
                      </td>
                      {/* 馬名 */}
                      <td className="px-3 py-2">
                        <Link 
                          href={`/horses/${horse.name}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-bold text-gray-900 hover:text-blue-600 hover:underline transition-colors"
                        >
                          {horse.name}
                        </Link>
                      </td>
                      {/* 性齢 */}
                      <td className="px-2 py-2 text-center text-gray-600">
                        {horse.sex}{horse.age}
                      </td>
                      {/* 斤量 */}
                      <td className="px-2 py-2 text-center font-mono text-gray-700">
                        {horse.weight.toFixed(1)}
                      </td>
                      {/* 騎手 */}
                      <td className="px-3 py-2">
                        <Link 
                          href={`/jockeys/${horse.jockey}`}
                          className="text-gray-700 hover:text-blue-600 hover:underline transition-colors"
                        >
                          {horse.jockey}
                        </Link>
                      </td>
                      {/* 調教師 */}
                      <td className="px-3 py-2 text-gray-600">
                        {formatTrainerName(horse.trainer)}
                      </td>
                      {/* オッズ */}
                      <td className="px-2 py-2 text-right font-mono">
                        <span className={`font-bold ${
                          horse.odds < 5 ? 'text-red-600' : 
                          horse.odds < 10 ? 'text-orange-600' : 
                          'text-gray-700'
                        }`}>
                          {horse.odds.toFixed(1)}
                        </span>
                      </td>
                      {/* 人気 */}
                      <td className="px-2 py-2 text-center">
                        <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold ${
                          horse.popularity === 1 ? 'bg-red-500 text-white' :
                          horse.popularity === 2 ? 'bg-blue-500 text-white' :
                          horse.popularity === 3 ? 'bg-green-500 text-white' :
                          'bg-gray-200 text-gray-700'
                        }`}>
                          {horse.popularity}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* レース内容（Markdown変換済みHTML、テーブル除去済み） */}
      <RaceContentWithMermaid htmlContent={displayHtmlContent} />

      {/* 戻るボタン */}
      <div className="mt-8 flex gap-4">
        <Button variant="outline" className="rounded-lg" asChild>
          <Link href="/">
            <ChevronLeft className="w-4 h-4 mr-1" />
            レース一覧に戻る
          </Link>
        </Button>
      </div>
    </div>
  );
}