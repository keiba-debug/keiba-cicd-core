import Link from 'next/link';
import { getAvailableDates, getRacesByDate, getRaceInfo } from '@/lib/data';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { JraViewerMiniLinks } from '@/components/jra-viewer-mini-links';
import { generatePaddockUrl, generateRaceUrl, generatePatrolUrl, parseKaisaiKey } from '@/lib/jra-viewer-url';

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

  return (
    <div className="container py-6">
      <h1 className="text-3xl font-bold mb-6">レース一覧</h1>

      {/* 年月選択 */}
      <div className="flex flex-wrap items-center gap-4 mb-6 p-4 bg-muted/30 rounded-lg border year-month-selector">
        {/* 年選択 */}
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-muted-foreground">年:</span>
          <div className="flex gap-1">
            {years.map((year) => (
              <Link
                key={year}
                href={`/?year=${year}`}
                className={`px-3 py-1.5 text-sm rounded-md transition-colors border ${
                  year === selectedYear
                    ? 'year-month-active'
                    : 'year-month-inactive'
                }`}
              >
                {year}年
              </Link>
            ))}
          </div>
        </div>

        {/* 月選択（前月・次月ナビゲーション付き） */}
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-muted-foreground">月:</span>
          
          {/* 前月ボタン */}
          <Link
            href={`/?year=${prevMonth.year}&month=${prevMonth.month}`}
            className="px-2 py-1 text-sm rounded-md transition-colors border hover:bg-muted"
            title={`${prevMonth.year}年${parseInt(prevMonth.month)}月へ`}
          >
            ◀
          </Link>
          
          <div className="flex flex-wrap gap-1">
            {allMonths.map((month) => {
              const hasData = hasDataInMonth(selectedYear, month);
              return (
                <Link
                  key={month}
                  href={`/?year=${selectedYear}&month=${month}`}
                  className={`px-3 py-1.5 text-sm rounded-md transition-colors border ${
                    month === selectedMonth
                      ? 'year-month-active'
                      : hasData
                        ? 'year-month-inactive'
                        : 'year-month-inactive opacity-40'
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
            className="px-2 py-1 text-sm rounded-md transition-colors border hover:bg-muted"
            title={`${nextMonth.year}年${parseInt(nextMonth.month)}月へ`}
          >
            ▶
          </Link>
        </div>
      </div>

      {/* 日付タブ */}
      {datesInMonth.length > 0 ? (
        <Tabs defaultValue={latestDate} className="w-full">
          <TabsList className="mb-4 flex-wrap h-auto gap-1 bg-muted/50 p-1">
            {datesInMonth.map((date) => {
              const [, month, day] = date.split('-');
              return (
                <TabsTrigger
                  key={date}
                  value={date}
                  className="px-4 py-2 data-[state=active]:bg-background data-[state=active]:shadow-sm"
                >
                  {parseInt(month)}/{parseInt(day)}
                </TabsTrigger>
              );
            })}
          </TabsList>

          {datesInMonth.map((date) => (
            <TabsContent key={date} value={date}>
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
          <p className="text-sm mt-2">data2フォルダにデータを配置してください</p>
        </div>
      )}
    </div>
  );
}

async function DateRaces({ date }: { date: string }) {
  const [data, raceInfo] = await Promise.all([
    getRacesByDate(date),
    getRaceInfo(date),
  ]);

  if (!data) {
    return <p className="text-muted-foreground">データが見つかりません</p>;
  }

  // 開催情報から回次・日次を取得するヘルパー
  const getKaisaiInfo = (track: string) => {
    if (!raceInfo?.kaisai_data) return null;
    for (const kaisaiKey of Object.keys(raceInfo.kaisai_data)) {
      const parsed = parseKaisaiKey(kaisaiKey);
      if (parsed && parsed.track === track) {
        return parsed;
      }
    }
    return null;
  };

  // JRAビュアーURL生成ヘルパー
  const generateUrls = (track: string, raceNumber: number) => {
    const kaisaiInfo = getKaisaiInfo(track);
    if (!kaisaiInfo) return { paddockUrl: null, raceUrl: null, patrolUrl: null };

    const [year, month, day] = date.split('-').map(Number);
    const params = {
      year,
      month,
      day,
      track: kaisaiInfo.track,
      kai: kaisaiInfo.kai,
      nichi: kaisaiInfo.nichi,
      raceNumber,
    };

    return {
      paddockUrl: generatePaddockUrl(params),
      raceUrl: generateRaceUrl(params),
      patrolUrl: generatePatrolUrl(params),
    };
  };

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold border-b-2 border-foreground/20 pb-2">
        📅 {data.displayDate}
      </h2>

      {/* 競馬場ごとのグリッド */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        {data.tracks.map((trackGroup) => (
          <Card key={trackGroup.track} className="overflow-hidden shadow-sm">
            <CardHeader className="py-3 bg-muted/70 border-b">
              <CardTitle className="text-base flex items-center gap-2">
                <span className="text-lg">🏟️</span>
                <span className="font-bold">{trackGroup.track}競馬場</span>
                <Badge variant="outline" className="ml-auto text-xs">
                  {trackGroup.races.length}レース
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="divide-y">
                {trackGroup.races.map((race) => {
                  const urls = generateUrls(trackGroup.track, race.raceNumber);
                  return (
                    <div
                      key={race.id}
                      className="flex flex-col gap-2 px-4 py-3 hover:bg-muted/40 transition-colors group"
                    >
                      <Link
                        href={`/races/${date}/${trackGroup.track}/${race.id}`}
                        className="flex items-center gap-3"
                      >
                        {/* レース番号 */}
                        <span className="w-10 h-10 flex items-center justify-center rounded bg-muted font-bold text-sm group-hover:bg-primary group-hover:text-primary-foreground transition-colors">
                          {race.raceNumber}R
                        </span>

                        {/* レース情報 */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-medium truncate">
                              {race.raceName}
                            </span>
                          </div>
                          <div className="flex items-center gap-2 mt-0.5 text-xs text-muted-foreground">
                            {race.className && (
                              <Badge
                                variant="secondary"
                                className="text-xs px-1.5 py-0"
                              >
                                {race.className}
                              </Badge>
                            )}
                            <span>{race.distance}</span>
                          </div>
                        </div>

                        {/* 発走時刻 */}
                        {race.startTime && (
                          <span className="text-sm text-muted-foreground whitespace-nowrap">
                            {race.startTime}
                          </span>
                        )}
                      </Link>

                      {/* JRAビュアーリンク */}
                      <JraViewerMiniLinks
                        paddockUrl={urls.paddockUrl}
                        raceUrl={urls.raceUrl}
                        patrolUrl={urls.patrolUrl}
                      />
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
