'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Download, RefreshCw } from 'lucide-react';
import StrategyBetsTable from './StrategyBetsTable';
import { MyBetsResponse, StrategyResult } from './types';
import { downloadFfCsv, downloadStrategyCsv } from './csv-export';

interface Props {
  raceId: string;
  markSet: number;
}

export default function MyBetsView({ raceId, markSet }: Props) {
  const [data, setData] = useState<MyBetsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/my-bets/${raceId}?markSet=${markSet}`, {
        cache: 'no-store',
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(`HTTP ${res.status}: ${t.slice(0, 200)}`);
      }
      setData((await res.json()) as MyBetsResponse);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [raceId, markSet]);

  if (loading) {
    return <div className="text-muted-foreground">読み込み中...</div>;
  }
  if (error) {
    return (
      <div className="text-red-600 space-y-2">
        <div>エラー: {error}</div>
        <Button onClick={load} variant="outline" size="sm">
          再読込
        </Button>
      </div>
    );
  }
  if (!data) return null;

  const activatedStrategies = data.strategies.filter((s) => s.activated);
  const inactiveStrategies = data.strategies.filter((s) => !s.activated);

  // FFCSV を /api/target-marks/auto-bet 経由で書き込む
  const handleSubmitToTarget = async (
    strategy: StrategyResult | 'all'
  ): Promise<void> => {
    const id = typeof strategy === 'string' ? 'all' : strategy.strategyId;
    setSubmitting(id);
    try {
      const bets =
        strategy === 'all'
          ? data.strategies
              .filter((s) => s.activated)
              .flatMap((s) => s.bets)
          : strategy.bets;
      await downloadFfCsv(data.raceId, bets);
    } catch (e) {
      alert(`CSV出力失敗: ${e instanceof Error ? e.message : e}`);
    } finally {
      setSubmitting(null);
    }
  };

  return (
    <div className="space-y-4">
      {/* ヘッダー */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <div>
              <CardTitle className="text-xl">
                My印買い目 — {data.venue} {data.raceNumber}R{' '}
                {data.raceName && (
                  <span className="text-base font-normal text-muted-foreground ml-2">
                    {data.raceName}
                  </span>
                )}
              </CardTitle>
              <div className="text-xs text-muted-foreground mt-1">
                {data.date} / raceId: {data.raceId} / 印セット: My{data.markSet}
              </div>
            </div>
            <div className="flex gap-2">
              <Button onClick={load} variant="outline" size="sm">
                <RefreshCw className="w-4 h-4 mr-1" />
                再読込
              </Button>
              <Button
                onClick={() => handleSubmitToTarget('all')}
                disabled={
                  submitting !== null || activatedStrategies.length === 0
                }
                size="sm"
              >
                <Download className="w-4 h-4 mr-1" />
                全戦略まとめCSV
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2 text-sm">
            {(['◎', '○', '▲', '△', '★', '穴'] as const).map((m) => {
              const cnt = data.markCounts[m] ?? 0;
              if (cnt === 0)
                return (
                  <Badge
                    key={m}
                    variant="outline"
                    className="text-muted-foreground"
                  >
                    {m}: 0
                  </Badge>
                );
              return (
                <Badge key={m} variant="default">
                  {m}: {cnt}頭
                </Badge>
              );
            })}
            <Badge variant="outline">
              無印: {data.markCounts['無印'] ?? 0}頭
            </Badge>
          </div>
          <div className="mt-2 text-xs text-muted-foreground">
            オッズ取得: 単{data.oddsAvailable.tansho} / 複
            {data.oddsAvailable.fukusho} / 馬連{data.oddsAvailable.umaren} / 馬単
            {data.oddsAvailable.umatan} / ワイド{data.oddsAvailable.wide} / 三複
            {data.oddsAvailable.sanrenpuku} / 三単
            {data.oddsAvailable.sanrentan} | 候補総数:{' '}
            {data.candidates.total.toLocaleString()}
          </div>
        </CardContent>
      </Card>

      {/* 戦略タブ */}
      {activatedStrategies.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            発動する戦略がありません。My印を見直してください。
          </CardContent>
        </Card>
      ) : (
        <Tabs defaultValue={activatedStrategies[0].strategyId}>
          <TabsList className="flex flex-wrap h-auto">
            {activatedStrategies.map((s) => (
              <TabsTrigger
                key={s.strategyId}
                value={s.strategyId}
                className="text-xs"
              >
                {s.name}
                <Badge variant="secondary" className="ml-1">
                  {s.totalBets}
                </Badge>
              </TabsTrigger>
            ))}
          </TabsList>

          {activatedStrategies.map((s) => (
            <TabsContent key={s.strategyId} value={s.strategyId}>
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div>
                      <CardTitle className="text-lg">{s.name}</CardTitle>
                      <div className="text-xs text-muted-foreground mt-0.5">
                        {s.description}
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="text-sm space-x-3">
                        <span>{s.totalBets}点</span>
                        <span className="font-semibold">
                          ¥{s.totalCost.toLocaleString()}
                        </span>
                        <span className="text-muted-foreground">
                          平均EV {s.avgEv.toFixed(2)}
                        </span>
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={submitting !== null || s.bets.length === 0}
                        onClick={() => downloadStrategyCsv(data.raceId, s)}
                      >
                        <Download className="w-3.5 h-3.5 mr-1" />
                        CSV
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <StrategyBetsTable
                    bets={s.bets}
                    horseNames={data.horseNames}
                  />
                </CardContent>
              </Card>
            </TabsContent>
          ))}
        </Tabs>
      )}

      {/* 非発動戦略リスト */}
      {inactiveStrategies.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">
              非発動戦略 ({inactiveStrategies.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {inactiveStrategies.map((s) => (
                <Badge
                  key={s.strategyId}
                  variant="outline"
                  className="text-muted-foreground"
                  title={s.description}
                >
                  {s.name}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
