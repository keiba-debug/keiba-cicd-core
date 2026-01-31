/**
 * 資金管理API
 * 
 * GET /api/bankroll/fund - 資金履歴を取得
 * POST /api/bankroll/fund - 入金/出金を記録
 */

import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs/promises';
import path from 'path';
import type { FundHistory, FundEntry, FundConfig } from '@/types/bankroll';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

// 資金履歴ファイルのパス
const getFundHistoryPath = () => {
  const dataRoot = process.env.KEIBA_DATA_ROOT_DIR || 'E:\\share\\KEIBA-CICD\\data2';
  return path.join(dataRoot, 'userdata', 'fund_history.json');
};

// 初期データを作成
const createInitialData = (): FundHistory => {
  const now = new Date().toISOString();
  return {
    config: {
      initial_balance: 100000, // デフォルト10万円
      created_at: now,
      updated_at: now,
    },
    entries: [],
  };
};

// 資金履歴を読み込み
async function loadFundHistory(): Promise<FundHistory> {
  const filePath = getFundHistoryPath();
  
  try {
    const content = await fs.readFile(filePath, 'utf-8');
    return JSON.parse(content);
  } catch {
    // ファイルがない場合は初期データを返す
    return createInitialData();
  }
}

// 資金履歴を保存
async function saveFundHistory(data: FundHistory): Promise<void> {
  const filePath = getFundHistoryPath();
  const dir = path.dirname(filePath);
  
  // ディレクトリがなければ作成
  await fs.mkdir(dir, { recursive: true });
  
  // 更新日時を更新
  data.config.updated_at = new Date().toISOString();
  
  await fs.writeFile(filePath, JSON.stringify(data, null, 2), 'utf-8');
}

// 現在の残高を計算
function calculateCurrentBalance(history: FundHistory): number {
  let balance = history.config.initial_balance;
  for (const entry of history.entries) {
    balance += entry.amount;
  }
  return balance;
}

// 新しいエントリIDを生成
function generateEntryId(date: string, entries: FundEntry[]): string {
  const todayEntries = entries.filter(e => e.date === date);
  const index = todayEntries.length + 1;
  return `${date}-${String(index).padStart(3, '0')}`;
}

// GET: 資金履歴を取得
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const checkDate = searchParams.get('check_date');
    
    // 特定日付の同期状態チェック
    if (checkDate) {
      const history = await loadFundHistory();
      const existingEntry = history.entries.find(
        e => e.date === checkDate && e.type === 'betting_result'
      );
      return NextResponse.json({
        is_synced: !!existingEntry,
        entry: existingEntry || null,
      });
    }
    const history = await loadFundHistory();
    const currentBalance = calculateCurrentBalance(history);
    
    // グラフ用データを生成（日付順）
    const chartData: { date: string; balance: number; profit: number }[] = [];
    let runningBalance = history.config.initial_balance;
    
    // 日付ごとに集計
    const dailyMap = new Map<string, number>();
    for (const entry of history.entries) {
      const current = dailyMap.get(entry.date) || 0;
      dailyMap.set(entry.date, current + entry.amount);
    }
    
    // 日付順にソート
    const sortedDates = [...dailyMap.keys()].sort();
    for (const date of sortedDates) {
      const profit = dailyMap.get(date) || 0;
      runningBalance += profit;
      chartData.push({
        date,
        balance: runningBalance,
        profit,
      });
    }
    
    // 期間別サマリーを計算
    const now = new Date();
    const thisMonth = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}`;
    const lastMonth = now.getMonth() === 0
      ? `${now.getFullYear() - 1}12`
      : `${now.getFullYear()}${String(now.getMonth()).padStart(2, '0')}`;
    
    const periodSummaries = [
      calculatePeriodSummary(history.entries, '全期間', '', ''),
      calculatePeriodSummary(history.entries, '今月', thisMonth, ''),
      calculatePeriodSummary(history.entries, '先月', lastMonth, ''),
    ];
    
    return NextResponse.json({
      config: history.config,
      entries: history.entries.slice().reverse(), // 新しい順
      current_balance: currentBalance,
      total_profit: currentBalance - history.config.initial_balance,
      chart_data: chartData,
      period_summaries: periodSummaries,
    });
  } catch (error) {
    console.error('[FundAPI] GET Error:', error);
    return NextResponse.json(
      { error: '資金履歴の取得に失敗しました' },
      { status: 500 }
    );
  }
}

// 期間別サマリーを計算
function calculatePeriodSummary(
  entries: FundEntry[],
  periodName: string,
  monthPrefix: string,
  _endPrefix: string
) {
  const filtered = monthPrefix
    ? entries.filter(e => e.date.startsWith(monthPrefix))
    : entries;
  
  const bettingEntries = filtered.filter(e => e.type === 'betting_result');
  
  let totalBet = 0;
  let totalPayout = 0;
  let raceCount = 0;
  let winCount = 0;
  
  for (const entry of bettingEntries) {
    if (entry.betting_detail) {
      totalBet += entry.betting_detail.total_bet;
      totalPayout += entry.betting_detail.total_payout;
      raceCount += entry.betting_detail.race_count;
      winCount += entry.betting_detail.win_count;
    }
  }
  
  const profit = totalPayout - totalBet;
  const recoveryRate = totalBet > 0 ? (totalPayout / totalBet) * 100 : 0;
  
  // 入金/出金も含めた総変動
  const totalChange = filtered.reduce((sum, e) => sum + e.amount, 0);
  
  return {
    period: periodName,
    total_bet: totalBet,
    total_payout: totalPayout,
    profit,
    recovery_rate: recoveryRate,
    race_count: raceCount,
    win_count: winCount,
    total_change: totalChange, // 入金/出金含む
  };
}

// POST: 入金/出金/競馬収支同期を記録
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { type, amount, description, action, date, betting_detail } = body;

    // 競馬収支同期アクション
    if (action === 'sync_betting') {
      return await syncBettingResult(date, betting_detail);
    }
    
    if (!type || !['deposit', 'withdraw'].includes(type)) {
      return NextResponse.json(
        { error: 'typeは deposit または withdraw を指定してください' },
        { status: 400 }
      );
    }
    
    if (typeof amount !== 'number' || amount <= 0) {
      return NextResponse.json(
        { error: '金額は正の数を指定してください' },
        { status: 400 }
      );
    }
    
    const history = await loadFundHistory();
    const currentBalance = calculateCurrentBalance(history);
    
    // 出金の場合、残高チェック
    if (type === 'withdraw' && amount > currentBalance) {
      return NextResponse.json(
        { error: '残高が不足しています' },
        { status: 400 }
      );
    }
    
    const now = new Date();
    const dateStr = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}`;
    
    const entryAmount = type === 'deposit' ? amount : -amount;
    const newBalance = currentBalance + entryAmount;
    
    const newEntry: FundEntry = {
      id: generateEntryId(dateStr, history.entries),
      date: dateStr,
      type,
      amount: entryAmount,
      balance: newBalance,
      description: description || (type === 'deposit' ? '入金' : '出金'),
      created_at: now.toISOString(),
    };
    
    history.entries.push(newEntry);
    await saveFundHistory(history);
    
    return NextResponse.json({
      success: true,
      entry: newEntry,
      current_balance: newBalance,
    });
  } catch (error) {
    console.error('[FundAPI] POST Error:', error);
    return NextResponse.json(
      { error: '資金の記録に失敗しました' },
      { status: 500 }
    );
  }
}

// 競馬収支を同期
async function syncBettingResult(
  date: string,
  bettingDetail: {
    total_bet: number;
    total_payout: number;
    profit: number;
    recovery_rate: number;
    race_count: number;
    win_count: number;
  }
) {
  try {
    if (!date || date.length !== 8) {
      return NextResponse.json(
        { error: '日付を指定してください（YYYYMMDD形式）' },
        { status: 400 }
      );
    }

    const history = await loadFundHistory();
    
    // 同じ日付の競馬収支が既に登録されているかチェック
    const existingEntry = history.entries.find(
      e => e.date === date && e.type === 'betting_result'
    );
    
    if (existingEntry) {
      return NextResponse.json(
        { error: `${date}の競馬収支は既に登録されています`, existing: existingEntry },
        { status: 409 }
      );
    }

    const currentBalance = calculateCurrentBalance(history);
    const profit = bettingDetail.profit;
    const newBalance = currentBalance + profit;

    const newEntry: FundEntry = {
      id: generateEntryId(date, history.entries),
      date,
      type: 'betting_result',
      amount: profit,
      balance: newBalance,
      description: `競馬収支 (${bettingDetail.race_count}R, 的中${bettingDetail.win_count})`,
      reference_date: date,
      betting_detail: bettingDetail,
      created_at: new Date().toISOString(),
    };

    history.entries.push(newEntry);
    
    // 日付順にソート
    history.entries.sort((a, b) => a.date.localeCompare(b.date));
    
    await saveFundHistory(history);

    return NextResponse.json({
      success: true,
      entry: newEntry,
      current_balance: newBalance,
      message: `${date}の競馬収支を反映しました`,
    });
  } catch (error) {
    console.error('[FundAPI] syncBettingResult Error:', error);
    return NextResponse.json(
      { error: '競馬収支の同期に失敗しました' },
      { status: 500 }
    );
  }
}
