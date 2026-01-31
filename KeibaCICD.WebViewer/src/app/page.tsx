import Link from 'next/link';
import { getAvailableDates, getRacesByDate } from '@/lib/data';
import { getVenueBabaSummary, type VenueBabaSummary } from '@/lib/data/baba-reader';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { JraViewerMiniLinks } from '@/components/jra-viewer-mini-links';
import { BabaInputForm } from '@/components/baba/BabaInputForm';
import { BabaSummaryBadges } from '@/components/baba/BabaSummaryBadges';
import { ChevronLeft, ChevronRight, MessageCircle, TrendingUp } from 'lucide-react';

// 日付を年月でグループ化
function groupDatesByYearMonth(dates: string[]): Map<string, string[]> {
  const groups = new Map<string, string[]>();
  for (const date of dates) {
    const [year, month] = date.split('-');
    const key = `${year}-${month}`;
    if (!groups.has(key)) {
      groups.set(key, []);
    }
    groups.get(key)!.push(date);
  }
  return groups;
}

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<{ year?: string; month?: string }>;
}) {
  const params = await searchParams;
  const dates = await getAvailableDates();

  // 年月でグループ化
  const groupedDates = groupDatesByYearMonth(dates);
  const yearMonths = Array.from(groupedDates.keys()).sort().reverse();

  // 現在の年月を取得
  const now = new Date();
  const currentYear = now.getFullYear().toString();
  const currentMonth = (now.getMonth() + 1).toString().padStart(2, '0');

  // データがある年を取得
  const dataYears = [...new Set(yearMonths.map((ym) => ym.split('-')[0]))];

  // 選択された年月を取得（デフォルトは最新データがある年月、またはクエリパラメータ）
  const selectedYear = params.year || dataYears[0] || currentYear;

  // 表示する年のリスト（データがある年 + 選択された年の前後 + 現在年を含む）
  const yearNum = parseInt(selectedYear);
  const adjacentYears = [
    (yearNum - 1).toString(),
    selectedYear,
    (yearNum + 1).toString()
  ];
  const years = [...new Set([...dataYears, ...adjacentYears, currentYear])].sort().reverse();
  const availableMonthsInYear = yearMonths
    .filter((ym) => ym.startsWith(selectedYear))
    .map((ym) => ym.split('-')[1]);
  
  // 月は1-12月全て表示（データの有無に関わらず）
  const allMonths = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12'];
  const selectedMonth = params.month || availableMonthsInYear[0] || currentMonth;
  const selectedYearMonth = `${selectedYear}-${selectedMonth}`;

  // 選択された年月の日付を取得
  const datesInMonth = groupedDates.get(selectedYearMonth) || [];

  // 最新日付のデータを取得
  const latestDate = datesInMonth[0];

  // 前月・次月の計算
  const selectedMonthNum = parseInt(selectedMonth);
  const selectedYearNum = parseInt(selectedYear);
  const prevMonth = selectedMonthNum === 1 
    ? { year: (selectedYearNum - 1).toString(), month: '12' }
    : { year: selectedYear, month: (selectedMonthNum - 1).toString().padStart(2, '0') };
  const nextMonth = selectedMonthNum === 12
    ? { year: (selectedYearNum + 1).toString(), month: '01' }
    : { year: selectedYear, month: (selectedMonthNum + 1).toString().padStart(2, '0') };

  // データがある月かどうかをチェック
  const hasDataInMonth = (year: string, month: string) => {
    return groupedDates.has(`${year}-${month}`);
  };

  // 曜日取得ヘルパー
  const getDayOfWeek = (dateStr: string) => {
    const date = new Date(dateStr);
    const days = ['日', '月', '火', '水', '木', '金', '土'];
    return days[date.getDay()];
  };

  const getDayColorClass = (dateStr: string) => {
    const date = new Date(dateStr);
    const day = date.getDay();
    if (day === 0) return 'text-red-500'; // 日
    if (day === 6) return 'text-blue-500'; // 土
    return 'text-muted-foreground';
  };

  return (
    <div className="py-6">
      <h1 className="text-3xl font-bold mb-6">レース一覧</h1>

      {/* 年月選択エリア */}
      <div className="flex flex-col md:flex-row items-start md:items-center gap-4 mb-8 p-1">
        {/* 年選択（ステッパー形式） */}
        <div className="flex items-center gap-2 bg-background border rounded-lg p-1 shadow-sm">
          <Link
            href={`/?year=${yearNum - 1}`}
            className="p-2 hover:bg-muted rounded-md transition-colors text-muted-foreground hover:text-foreground"
            title="前の年へ"
          >
            <ChevronLeft className="h-5 w-5" />
          </Link>
          <span className="text-xl font-bold px-4 tabular-nums min-w-[5rem] text-center">
            {selectedYear}年
          </span>
          <Link
            href={`/?year=${yearNum + 1}`}
            className="p-2 hover:bg-muted rounded-md transition-colors text-muted-foreground hover:text-foreground"
            title="次の年へ"
          >
            <ChevronRight className="h-5 w-5" />
          </Link>
        </div>

        {/* 月選択 */}
        <div className="flex-1 w-full overflow-x-auto pb-2 md:pb-0">
          <div className="flex items-center gap-1 min-w-max">
            {/* 前月ボタン */}
            <Link
              href={`/?year=${prevMonth.year}&month=${prevMonth.month}`}
              className="p-2 hover:bg-muted rounded-md transition-colors border mr-2"
              title="前月へ"
            >
              <ChevronLeft className="h-4 w-4" />
            </Link>
            
            <div className="flex bg-muted/30 p-1 rounded-lg border">
              {allMonths.map((month) => {
                const hasData = hasDataInMonth(selectedYear, month);
                const isSelected = month === selectedMonth;
                return (
                  <Link
                    key={month}
                    href={`/?year=${selectedYear}&month=${month}`}
                    className={`px-3 py-1.5 text-sm rounded-md transition-all ${
                      isSelected
                        ? 'bg-primary text-primary-foreground shadow-sm font-bold'
                        : hasData
                          ? 'text-foreground hover:bg-muted font-medium'
                          : 'text-muted-foreground/40 hover:text-muted-foreground/70'
                    }`}
                  >
                    {parseInt(month)}月
                  </Link>
                );
              })}
            </div>
            
            {/* 次月ボタン */}
            <Link
              href={`/?year=${nextMonth.year}&month=${nextMonth.month}`}
              className="p-2 hover:bg-muted rounded-md transition-colors border ml-2"
              title="次月へ"
            >
              <ChevronRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </div>

      {/* 日付タブ */}
      {datesInMonth.length > 0 ? (
        <Tabs defaultValue={latestDate} className="w-full">
          <TabsList className="mb-6 flex-wrap h-auto gap-2 bg-transparent p-0 justify-start">
            {datesInMonth.map((date) => {
              const [, month, day] = date.split('-');
              return (
                <TabsTrigger
                  key={date}
                  value={date}
                  className="px-5 py-2.5 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-md border bg-background hover:bg-muted/50 transition-all flex flex-col items-center min-w-[4.5rem]"
                >
                  <span className="text-lg font-bold leading-none">
                    {parseInt(day)}
                  </span>
                  <span className={`text-xs font-bold mt-1 ${getDayColorClass(date)} group-data-[state=active]:text-primary-foreground/90`}>
                    {getDayOfWeek(date)}曜
                  </span>
                </TabsTrigger>
              );
            })}
          </TabsList>

          {datesInMonth.map((date) => (
            <TabsContent key={date} value={date} className="mt-0">
              <DateRaces date={date} />
            </TabsContent>
          ))}
        </Tabs>
      ) : (
        <div className="text-center py-12 text-muted-foreground">
          <p>この月にはレースデータがありません</p>
        </div>
      )}

      {dates.length === 0 && (
        <div className="text-center py-12 text-muted-foreground">
          <p>レースデータがありません</p>
          <p className="text-sm mt-2">KEIBA_DATA_ROOT_DIR で指定したフォルダにデータを配置してください</p>
        </div>
      )}
    </div>
  );
}

async function DateRaces({ date }: { date: string }) {
  const data = await getRacesByDate(date);

  if (!data) {
    return <p className="text-muted-foreground">データが見つかりません</p>;
  }

  // 競馬場ごとの馬場情報を取得
  const babaSummaryMap = new Map<string, VenueBabaSummary | null>();
  for (const trackGroup of data.tracks) {
    const firstRace = trackGroup.races[0];
    if (firstRace?.kai && firstRace?.nichi) {
      const summary = getVenueBabaSummary(date, trackGroup.track, firstRace.kai, firstRace.nichi);
      babaSummaryMap.set(trackGroup.track, summary);
    }
  }

  const trackCodes: Record<string, string> = {
    '札幌': '01',
    '函館': '02',
    '福島': '03',
    '新潟': '04',
    '東京': '05',
    '中山': '06',
    '中京': '07',
    '京都': '08',
    '阪神': '09',
    '小倉': '10',
  };

  const netkeibaRaceId = (race: { track: string; raceNumber: number; kai?: number; nichi?: number; date: string }) => {
    if (!race.kai || !race.nichi) return null;
    const code = trackCodes[race.track];
    if (!code) return null;
    const [year] = race.date.split('-');
    const raceNo = String(race.raceNumber).padStart(2, '0');
    const kai = String(race.kai).padStart(2, '0');
    const nichi = String(race.nichi).padStart(2, '0');
    return `${year}${code}${kai}${nichi}${raceNo}`;
  };

  // JRA 16桁形式のレースID (YYYYMMDD + 場コード + 回 + 日 + レース番号)
  const jraRaceId = (race: { track: string; raceNumber: number; kai?: number; nichi?: number; date: string }) => {
    if (!race.kai || !race.nichi) return null;
    const code = trackCodes[race.track];
    if (!code) return null;
    const dateNoDash = race.date.replace(/-/g, '');
    const raceNo = String(race.raceNumber).padStart(2, '0');
    const kai = String(race.kai).padStart(2, '0');
    const nichi = String(race.nichi).padStart(2, '0');
    return `${dateNoDash}${code}${kai}${nichi}${raceNo}`;
  };

  const formatCondition = (distance?: string) => {
    if (!distance) return '';
    const normalized = distance.replace('：', ':').replace('・', ' ').trim();
    const withSpace = normalized.replace(':', ' ');
    return withSpace.replace(/m/gi, 'M').replace(/\s+/g, ' ');
  };

  const getTrackBorderClass = (trackName: string) => {
    const map: Record<string, string> = {
      '中山': 'border-l-[var(--color-venue-nakayama)]',
      '京都': 'border-l-[var(--color-venue-kyoto)]',
      '小倉': 'border-l-[var(--color-venue-kokura)]',
      '東京': 'border-l-[var(--color-venue-tokyo)]',
      '阪神': 'border-l-[var(--color-venue-hanshin)]',
    };
    return map[trackName] || 'border-l-primary';
  };

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

  const getKaisaiLabel = (track: string, races: typeof data.tracks[0]['races']) => {
    const firstRace = races[0];
    if (firstRace?.kai && firstRace?.nichi) {
      return `${firstRace.kai}回${track}${firstRace.nichi}日目`;
    }
    return `${track}`;
  };

  return (
    <div className="space-y-6">
      {/* 日付ヘッダー */}
      <div className="flex items-center gap-2">
        <h2 className="text-xl font-bold">
          {data.displayDate}
        </h2>
        <Badge variant="outline" className="text-muted-foreground font-normal">
          {data.tracks.length}場開催
        </Badge>
      </div>

      {/* 競馬場ごとのグリッド */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        {data.tracks.map((trackGroup) => (
          <Card 
            key={trackGroup.track} 
            className={`overflow-hidden shadow-sm border-0 border-l-4 ring-1 ring-border/50 ${getTrackBorderClass(trackGroup.track)}`}
          >
            {/* 開催ヘッダー */}
            <CardHeader 
              className="py-3 px-4 border-b bg-muted/10 space-y-0"
            >
              <div className="flex flex-row items-center justify-between">
                <div className="flex items-baseline gap-2">
                  <CardTitle className={`text-lg font-bold ${getTrackTextClass(trackGroup.track)}`}>
                    {trackGroup.track}
                  </CardTitle>
                  <span className="text-xs text-muted-foreground">
                    {getKaisaiLabel(trackGroup.track, trackGroup.races).replace(trackGroup.track, '')}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <BabaInputForm
                    date={date}
                    track={trackGroup.track}
                    kai={trackGroup.races[0]?.kai}
                    nichi={trackGroup.races[0]?.nichi}
                  />
                  <div className="text-xs font-mono text-muted-foreground">
                    12R
                  </div>
                </div>
              </div>
              {/* 馬場情報バッジ */}
              {babaSummaryMap.get(trackGroup.track)?.hasData && (
                <div className="mt-2 pt-2 border-t border-border/30">
                  <BabaSummaryBadges summary={babaSummaryMap.get(trackGroup.track) ?? null} />
                </div>
              )}
            </CardHeader>
            
            <CardContent className="p-0">
              <div className="divide-y divide-border/50">
                {trackGroup.races.map((race) => {
                  return (
                    <div
                      key={race.id}
                      className="grid grid-cols-[60px_1fr_auto] gap-3 px-4 py-3 hover:bg-muted/50 transition-colors group items-start text-sm"
                    >
                      {/* レース番号 + 発走時刻 */}
                      <Link
                        href={`/races-v2/${date}/${trackGroup.track}/${race.id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex flex-col items-center justify-center pt-0.5"
                      >
                        <span 
                          className={`font-bold text-lg leading-none ${getTrackTextClass(trackGroup.track)}`}
                        >
                          {race.raceNumber}R
                        </span>
                        <span className="text-[11px] text-muted-foreground font-mono mt-1">
                          {race.startTime || '--:--'}
                        </span>
                      </Link>

                      {/* レース名 + コース + クラス */}
                      <Link
                        href={`/races-v2/${date}/${trackGroup.track}/${race.id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex flex-col justify-start min-w-0"
                      >
                        <div className="mb-1">
                          <span className="font-bold text-base leading-tight block" title={race.raceName}>
                            {race.raceName}
                          </span>
                        </div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <span 
                            className={`text-[10px] font-bold px-1.5 py-0.5 rounded-sm whitespace-nowrap ${
                              race.distance?.startsWith('芝') 
                                ? 'text-[var(--color-surface-turf)] bg-[var(--color-surface-turf)]/10' 
                                : race.distance?.startsWith('ダ') 
                                  ? 'text-[var(--color-surface-dirt)] bg-[var(--color-surface-dirt)]/10' 
                                  : race.distance?.startsWith('障') 
                                    ? 'text-[var(--color-surface-steeplechase)] bg-[var(--color-surface-steeplechase)]/10' 
                                    : 'text-muted-foreground bg-muted'
                            }`}
                          >
                            {formatCondition(race.distance)}
                          </span>
                          {race.className && (
                            <span className="text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded-sm whitespace-nowrap">
                              {race.className}
                            </span>
                          )}
                          {/* ペース分析バッジ */}
                          {race.paceType && (
                            <span 
                              className={`text-[10px] font-medium px-1.5 py-0.5 rounded-sm whitespace-nowrap ${
                                race.paceType === 'sprint' 
                                  ? 'text-orange-600 bg-orange-100 dark:text-orange-400 dark:bg-orange-950' 
                                  : race.paceType === 'stamina' 
                                    ? 'text-blue-600 bg-blue-100 dark:text-blue-400 dark:bg-blue-950' 
                                    : 'text-gray-600 bg-gray-100 dark:text-gray-400 dark:bg-gray-800'
                              }`}
                              title={`前半${race.winnerFirst3f ?? '-'}s / 後半${race.winnerLast3f ?? '-'}s (差: ${race.paceDiff != null ? (race.paceDiff > 0 ? '+' : '') + race.paceDiff : '-'}s)`}
                            >
                              {race.paceType === 'sprint' ? '🔥瞬発' : race.paceType === 'stamina' ? '💪持続' : '⚖️平均'}
                            </span>
                          )}
                        </div>
                      </Link>

                      {/* 外部リンク + JRAビュアーリンク */}
                      <div className="flex flex-col gap-1 pt-0.5">
                        {/* 1行目: 外部サービスリンク */}
                        <div className="flex items-center gap-1">
                          <a
                            href={`https://p.keibabook.co.jp/cyuou/syutuba/${race.id}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="w-5 h-5 rounded hover:opacity-80 transition-opacity flex items-center justify-center overflow-hidden"
                            title="競馬ブック"
                          >
                            <img src="/keibabook.ico" alt="競馬ブック" className="w-4 h-4 object-contain opacity-80" />
                          </a>
                          {netkeibaRaceId(race) && (
                            <>
                              <a
                                href={`https://race.netkeiba.com/race/shutuba.html?race_id=${netkeibaRaceId(race)}&rf=race_submenu`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="w-5 h-5 rounded hover:opacity-80 transition-opacity flex items-center justify-center overflow-hidden"
                                title="netkeiba"
                              >
                                <img src="/netkeiba.png" alt="netkeiba" className="w-4 h-4 object-contain opacity-80" />
                              </a>
                              <a
                                href={`https://race.netkeiba.com/race/bbs.html?race_id=${netkeibaRaceId(race)}&rf=race_submenu`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="w-5 h-5 rounded hover:opacity-80 transition-opacity flex items-center justify-center"
                                title="netkeiba BBS"
                              >
                                <MessageCircle className="w-4 h-4 text-blue-500" />
                              </a>
                            </>
                          )}
                          {/* オッズ分析リンク */}
                          {jraRaceId(race) && (
                            <Link
                              href={`/odds-race/${jraRaceId(race)}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="w-5 h-5 rounded hover:opacity-80 transition-opacity flex items-center justify-center"
                              title="オッズ分析"
                            >
                              <TrendingUp className="w-4 h-4 text-emerald-500" />
                            </Link>
                          )}
                        </div>
                        {/* 2行目: JRAビュアーリンク */}
                        <JraViewerMiniLinks
                          date={date}
                          track={trackGroup.track}
                          raceNumber={race.raceNumber}
                          raceName={race.raceName}
                          kai={race.kai}
                          nichi={race.nichi}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
