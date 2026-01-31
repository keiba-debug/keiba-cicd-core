/**
 * 購入API
 * 
 * GET /api/purchases/{date} - 当日の購入リスト取得
 * POST /api/purchases/{date} - 購入追加
 * PUT /api/purchases/{date}?id=xxx - 購入更新
 * DELETE /api/purchases/{date}?id=xxx - 購入削除
 */

import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

interface PurchaseItem {
  id: string;
  race_id: string;
  race_name: string;
  venue: string;
  race_number: number;
  bet_type: string;
  selection: string;
  amount: number;
  odds: number | null;
  expected_value: number | null;
  status: 'planned' | 'purchased' | 'result_win' | 'result_lose';
  payout: number;
  confidence: '高' | '中' | '低';
  reason: string;
  created_at: string;
  updated_at: string;
}

interface DailyPurchases {
  date: string;
  budget: number;
  total_planned: number;
  total_purchased: number;
  total_payout: number;
  items: PurchaseItem[];
  updated_at: string;
}

// データディレクトリのパス
const DATA_DIR = path.join(
  process.cwd(),
  '..',
  '..',
  'keiba-ai',
  'data',
  'purchases'
);

/**
 * ファイルパスを取得
 */
function getFilePath(date: string): string {
  return path.join(DATA_DIR, `${date}.json`);
}

/**
 * 購入データを読み込む
 */
async function loadPurchases(date: string): Promise<DailyPurchases> {
  const filePath = getFilePath(date);
  
  try {
    const content = await fs.readFile(filePath, 'utf-8');
    return JSON.parse(content);
  } catch (error) {
    // ファイルが存在しない場合は空のデータを返す
    return {
      date,
      budget: 20000,
      total_planned: 0,
      total_purchased: 0,
      total_payout: 0,
      items: [],
      updated_at: new Date().toISOString(),
    };
  }
}

/**
 * 購入データを保存
 */
async function savePurchases(data: DailyPurchases): Promise<void> {
  const filePath = getFilePath(data.date);
  
  // ディレクトリが存在しない場合は作成
  await fs.mkdir(DATA_DIR, { recursive: true });
  
  // 合計を再計算
  data.total_planned = data.items
    .filter(i => i.status === 'planned')
    .reduce((sum, i) => sum + i.amount, 0);
  data.total_purchased = data.items
    .filter(i => i.status === 'purchased' || i.status === 'result_win' || i.status === 'result_lose')
    .reduce((sum, i) => sum + i.amount, 0);
  data.total_payout = data.items
    .filter(i => i.status === 'result_win')
    .reduce((sum, i) => sum + i.payout, 0);
  data.updated_at = new Date().toISOString();
  
  await fs.writeFile(filePath, JSON.stringify(data, null, 2), 'utf-8');
}

/**
 * GET: 購入リストを取得
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ date: string }> }
) {
  try {
    const { date } = await params;
    
    const purchases = await loadPurchases(date);
    return NextResponse.json(purchases);
  } catch (error) {
    console.error('[PurchasesAPI] GET Error:', error);
    return NextResponse.json(
      { error: '購入リストの取得に失敗しました', message: String(error) },
      { status: 500 }
    );
  }
}

/**
 * POST: 購入を追加
 */
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ date: string }> }
) {
  try {
    const { date } = await params;
    const body = await request.json();
    
    const {
      race_id,
      race_name = '',
      venue = '',
      race_number = 0,
      bet_type,
      selection,
      amount,
      odds = null,
      confidence = '中',
      reason = '',
      status = 'planned',
    } = body;
    
    if (!race_id || !bet_type || !selection || !amount) {
      return NextResponse.json(
        { error: '必須項目が不足しています' },
        { status: 400 }
      );
    }
    
    const purchases = await loadPurchases(date);
    
    // 期待値を計算
    const expected_value = odds ? (odds * 100 / amount) : null;
    
    // 新規アイテムを作成
    const newItem: PurchaseItem = {
      id: `${date}_${Date.now()}`,
      race_id,
      race_name,
      venue,
      race_number,
      bet_type,
      selection,
      amount: Number(amount),
      odds,
      expected_value,
      status,
      payout: 0,
      confidence,
      reason,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    
    purchases.items.push(newItem);
    await savePurchases(purchases);
    
    return NextResponse.json({
      success: true,
      item: newItem,
      total_planned: purchases.total_planned,
      total_purchased: purchases.total_purchased,
    });
  } catch (error) {
    console.error('[PurchasesAPI] POST Error:', error);
    return NextResponse.json(
      { error: '購入の追加に失敗しました', message: String(error) },
      { status: 500 }
    );
  }
}

/**
 * PUT: 購入を更新
 */
export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ date: string }> }
) {
  try {
    const { date } = await params;
    const searchParams = request.nextUrl.searchParams;
    const id = searchParams.get('id');
    const body = await request.json();
    
    if (!id) {
      return NextResponse.json(
        { error: 'IDが必要です' },
        { status: 400 }
      );
    }
    
    const purchases = await loadPurchases(date);
    const itemIndex = purchases.items.findIndex(i => i.id === id);
    
    if (itemIndex === -1) {
      return NextResponse.json(
        { error: '指定された購入が見つかりません' },
        { status: 404 }
      );
    }
    
    // 更新を適用
    purchases.items[itemIndex] = {
      ...purchases.items[itemIndex],
      ...body,
      updated_at: new Date().toISOString(),
    };
    
    // 期待値を再計算
    if (body.odds !== undefined || body.amount !== undefined) {
      const item = purchases.items[itemIndex];
      item.expected_value = item.odds ? (item.odds * 100 / item.amount) : null;
    }
    
    await savePurchases(purchases);
    
    return NextResponse.json({
      success: true,
      item: purchases.items[itemIndex],
      total_planned: purchases.total_planned,
      total_purchased: purchases.total_purchased,
      total_payout: purchases.total_payout,
    });
  } catch (error) {
    console.error('[PurchasesAPI] PUT Error:', error);
    return NextResponse.json(
      { error: '購入の更新に失敗しました', message: String(error) },
      { status: 500 }
    );
  }
}

/**
 * DELETE: 購入を削除
 */
export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ date: string }> }
) {
  try {
    const { date } = await params;
    const searchParams = request.nextUrl.searchParams;
    const id = searchParams.get('id');
    
    if (!id) {
      return NextResponse.json(
        { error: 'IDが必要です' },
        { status: 400 }
      );
    }
    
    const purchases = await loadPurchases(date);
    const itemIndex = purchases.items.findIndex(i => i.id === id);
    
    if (itemIndex === -1) {
      return NextResponse.json(
        { error: '指定された購入が見つかりません' },
        { status: 404 }
      );
    }
    
    purchases.items.splice(itemIndex, 1);
    await savePurchases(purchases);
    
    return NextResponse.json({
      success: true,
      total_planned: purchases.total_planned,
      total_purchased: purchases.total_purchased,
    });
  } catch (error) {
    console.error('[PurchasesAPI] DELETE Error:', error);
    return NextResponse.json(
      { error: '購入の削除に失敗しました', message: String(error) },
      { status: 500 }
    );
  }
}
