/**
 * 馬券種別統計API
 * 
 * GET /api/bankroll/stats?year=2026&month=1
 * GET /api/bankroll/stats?period=3months
 */

import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

type PeriodType = 'current_month' | '3months' | '6months' | '1year';

interface BetTypeStat {
  bet_type: string;
  total_bet: number;
  total_payout: number;
  profit: number;
  count: number;
  win_count: number;
  recovery_rate: number;
  win_rate: number;
}

/**
 * Pythonスクリプトを実行してJSONを取得
 */
function executePythonScript(
  scriptPath: string,
  args: string[],
  cwd?: string
): Promise<any> {
  return new Promise((resolve, reject) => {
    const pythonPath = process.env.PYTHON_PATH || 'python';
    const scriptFullPath = path.resolve(scriptPath);
    const workingDir = cwd || process.cwd();

    const child = spawn(pythonPath, [scriptFullPath, ...args], {
      cwd: workingDir,
      shell: true,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    });

    let stdout = '';
    let stderr = '';

    child.stdout?.on('data', (data: Buffer) => {
      stdout += data.toString('utf-8');
    });

    child.stderr?.on('data', (data: Buffer) => {
      stderr += data.toString('utf-8');
    });

    child.on('close', (code: number | null) => {
      if (code !== 0) {
        // エラーでも空のデータを返す（ファイルが存在しない場合など）
        resolve({ _meta: { has_data: false, file_exists: false } });
        return;
      }

      try {
        const jsonStr = stdout.trim();
        if (!jsonStr) {
          resolve({ _meta: { has_data: false, file_exists: true } });
          return;
        }

        const jsonMatch = jsonStr.match(/\{[\s\S]*\}/);
        if (!jsonMatch) {
          resolve({ _meta: { has_data: false, file_exists: true } });
          return;
        }

        const result = JSON.parse(jsonMatch[0]);
        resolve(result);
      } catch (error) {
        resolve({ _meta: { has_data: false, file_exists: true } });
      }
    });

    child.on('error', (error: Error) => {
      reject(error);
    });
  });
}

/**
 * 期間に応じた月リストを取得
 */
function getMonthsForPeriod(period: PeriodType): { year: number; month: number }[] {
  const now = new Date();
  const currentYear = now.getFullYear();
  const currentMonth = now.getMonth() + 1;
  const months: { year: number; month: number }[] = [];

  let monthCount = 1;
  switch (period) {
    case '3months':
      monthCount = 3;
      break;
    case '6months':
      monthCount = 6;
      break;
    case '1year':
      monthCount = 12;
      break;
    default:
      monthCount = 1;
  }

  for (let i = 0; i < monthCount; i++) {
    let year = currentYear;
    let month = currentMonth - i;
    
    while (month <= 0) {
      month += 12;
      year -= 1;
    }
    
    months.push({ year, month });
  }

  return months.reverse(); // 古い順にソート
}

/**
 * 複数月の統計を集計
 */
function aggregateStats(statsArray: any[]): { [key: string]: BetTypeStat } {
  const aggregated: { [key: string]: BetTypeStat } = {};

  for (const monthStats of statsArray) {
    if (!monthStats || typeof monthStats !== 'object') continue;

    for (const [betType, stats] of Object.entries(monthStats)) {
      if (betType === '_meta') continue;
      
      const s = stats as any;
      if (!aggregated[betType]) {
        aggregated[betType] = {
          bet_type: betType,
          total_bet: 0,
          total_payout: 0,
          profit: 0,
          count: 0,
          win_count: 0,
          recovery_rate: 0,
          win_rate: 0,
        };
      }

      aggregated[betType].total_bet += s.total_bet || 0;
      aggregated[betType].total_payout += s.total_payout || 0;
      aggregated[betType].count += s.count || 0;
      aggregated[betType].win_count += s.win_count || 0;
    }
  }

  // 回収率と的中率を再計算
  for (const betType of Object.keys(aggregated)) {
    const stat = aggregated[betType];
    stat.profit = stat.total_payout - stat.total_bet;
    stat.recovery_rate = stat.total_bet > 0 ? (stat.total_payout / stat.total_bet) * 100 : 0;
    stat.win_rate = stat.count > 0 ? (stat.win_count / stat.count) * 100 : 0;
  }

  return aggregated;
}

/**
 * 期間のラベルを取得
 */
function getPeriodLabel(period: PeriodType): string {
  switch (period) {
    case '3months':
      return '直近3ヶ月';
    case '6months':
      return '直近6ヶ月';
    case '1year':
      return '過去1年';
    default:
      return '今月';
  }
}

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const periodParam = searchParams.get('period') as PeriodType | null;
    const yearStr = searchParams.get('year');
    const monthStr = searchParams.get('month');

    const scriptPath = path.join(
      process.cwd(),
      '..',
      'KeibaCICD.AI',
      'tools',
      'target_reader.py'
    );

    // period パラメータが指定された場合
    if (periodParam) {
      const validPeriods: PeriodType[] = ['current_month', '3months', '6months', '1year'];
      const period = validPeriods.includes(periodParam) ? periodParam : 'current_month';
      const months = getMonthsForPeriod(period);

      // 各月のデータを取得
      const statsPromises = months.map((m) =>
        executePythonScript(scriptPath, [
          '--year',
          m.year.toString(),
          '--month',
          m.month.toString(),
          '--stats',
        ])
      );

      const statsResults = await Promise.all(statsPromises);

      // 統計を集計
      const aggregatedStats = aggregateStats(statsResults);

      // 総件数を計算
      const totalCount = Object.values(aggregatedStats).reduce((sum, s) => sum + s.count, 0);

      // 日付範囲を計算
      const firstMonth = months[0];
      const lastMonth = months[months.length - 1];
      const dateRange = {
        from: `${firstMonth.year}-${String(firstMonth.month).padStart(2, '0')}-01`,
        to: `${lastMonth.year}-${String(lastMonth.month).padStart(2, '0')}-${new Date(lastMonth.year, lastMonth.month, 0).getDate()}`,
      };

      return NextResponse.json({
        period,
        period_label: getPeriodLabel(period),
        date_range: dateRange,
        total_count: totalCount,
        stats: aggregatedStats,
        _meta: {
          has_data: totalCount > 0,
          file_exists: true,
        },
      });
    }

    // 従来の year/month パラメータ
    if (!yearStr || !monthStr) {
      // パラメータなしの場合は今月のデータを返す
      const now = new Date();
      const year = now.getFullYear();
      const month = now.getMonth() + 1;

      const result = await executePythonScript(scriptPath, [
        '--year',
        year.toString(),
        '--month',
        month.toString(),
        '--stats',
      ]);

      return NextResponse.json(result);
    }

    const year = parseInt(yearStr, 10);
    const month = parseInt(monthStr, 10);

    if (isNaN(year) || isNaN(month) || month < 1 || month > 12) {
      return NextResponse.json(
        { error: '年または月が不正です。' },
        { status: 400 }
      );
    }

    const result = await executePythonScript(scriptPath, [
      '--year',
      yearStr,
      '--month',
      monthStr,
      '--stats',
    ]);

    return NextResponse.json(result);
  } catch (error) {
    console.error('[BankrollStatsAPI] Error:', error);
    return NextResponse.json(
      {
        error: '馬券種別統計の取得に失敗しました',
        message: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
