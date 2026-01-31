/**
 * 購入予定API
 * 
 * GET /api/bankroll/plans?date=20260131 - 指定日の購入予定を取得
 * POST /api/bankroll/plans - 新規購入予定を追加
 * PUT /api/bankroll/plans - 購入予定を更新
 * DELETE /api/bankroll/plans?id=xxx - 購入予定を削除
 */

import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

interface PurchasePlan {
  id: string;
  race_id: string;
  race_name: string;
  venue: string;
  race_number: number;
  bet_type: string;
  selection: string;
  amount: number;
  confidence: '高' | '中' | '低';
  reason: string;
  status: 'pending' | 'purchased' | 'skipped';
  result?: 'win' | 'lose' | null;
  payout?: number;
  created_at: string;
  updated_at?: string;
}

interface DailyPlan {
  date: string;
  plans: PurchasePlan[];
  total_planned: number;
  total_purchased: number;
  updated_at: string;
}

// データディレクトリのパス
const DATA_DIR = path.join(
  process.cwd(),
  '..',
  '..',
  'keiba-ai',
  'data',
  'bankroll',
  'plans'
);

/**
 * 日付形式を検証
 */
function isValidDate(dateStr: string): boolean {
  if (dateStr.length !== 8) return false;
  const year = parseInt(dateStr.substring(0, 4));
  const month = parseInt(dateStr.substring(4, 6));
  const day = parseInt(dateStr.substring(6, 8));
  return year >= 2020 && month >= 1 && month <= 12 && day >= 1 && day <= 31;
}

/**
 * ファイルパスを取得
 */
function getFilePath(date: string): string {
  return path.join(DATA_DIR, `${date}.json`);
}

/**
 * 購入予定を読み込む
 */
async function loadPlans(date: string): Promise<DailyPlan> {
  const filePath = getFilePath(date);
  
  try {
    const content = await fs.readFile(filePath, 'utf-8');
    return JSON.parse(content);
  } catch (error) {
    // ファイルが存在しない場合は空のデータを返す
    return {
      date,
      plans: [],
      total_planned: 0,
      total_purchased: 0,
      updated_at: new Date().toISOString(),
    };
  }
}

/**
 * 購入予定を保存
 */
async function savePlans(data: DailyPlan): Promise<void> {
  const filePath = getFilePath(data.date);
  
  // ディレクトリが存在しない場合は作成
  await fs.mkdir(DATA_DIR, { recursive: true });
  
  // 合計を再計算
  data.total_planned = data.plans
    .filter(p => p.status === 'pending')
    .reduce((sum, p) => sum + p.amount, 0);
  data.total_purchased = data.plans
    .filter(p => p.status === 'purchased')
    .reduce((sum, p) => sum + p.amount, 0);
  data.updated_at = new Date().toISOString();
  
  await fs.writeFile(filePath, JSON.stringify(data, null, 2), 'utf-8');
}

/**
 * GET: 購入予定を取得
 */
export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    let dateStr = searchParams.get('date');
    
    // 日付が指定されていない場合は今日の日付
    if (!dateStr) {
      const today = new Date();
      dateStr = today.toISOString().slice(0, 10).replace(/-/g, '');
    }
    
    if (!isValidDate(dateStr)) {
      return NextResponse.json(
        { error: '日付形式が不正です。YYYYMMDD形式で指定してください。' },
        { status: 400 }
      );
    }
    
    const plans = await loadPlans(dateStr);
    return NextResponse.json(plans);
  } catch (error) {
    console.error('[PlansAPI] GET Error:', error);
    return NextResponse.json(
      { error: '購入予定の取得に失敗しました', message: String(error) },
      { status: 500 }
    );
  }
}

/**
 * POST: 新規購入予定を追加
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    
    const {
      date,
      race_id,
      race_name,
      venue,
      race_number,
      bet_type,
      selection,
      amount,
      confidence = '中',
      reason = '',
    } = body;
    
    if (!date || !race_id || !bet_type || !selection || !amount) {
      return NextResponse.json(
        { error: '必須項目が不足しています' },
        { status: 400 }
      );
    }
    
    if (!isValidDate(date)) {
      return NextResponse.json(
        { error: '日付形式が不正です' },
        { status: 400 }
      );
    }
    
    const plans = await loadPlans(date);
    
    // 新規プランを作成
    const newPlan: PurchasePlan = {
      id: `plan_${Date.now()}`,
      race_id,
      race_name: race_name || '',
      venue: venue || '',
      race_number: race_number || 0,
      bet_type,
      selection,
      amount: Number(amount),
      confidence,
      reason,
      status: 'pending',
      created_at: new Date().toISOString(),
    };
    
    plans.plans.push(newPlan);
    await savePlans(plans);
    
    return NextResponse.json({
      success: true,
      plan: newPlan,
      total_planned: plans.total_planned,
    });
  } catch (error) {
    console.error('[PlansAPI] POST Error:', error);
    return NextResponse.json(
      { error: '購入予定の追加に失敗しました', message: String(error) },
      { status: 500 }
    );
  }
}

/**
 * PUT: 購入予定を更新
 */
export async function PUT(request: NextRequest) {
  try {
    const body = await request.json();
    const { date, id, ...updates } = body;
    
    if (!date || !id) {
      return NextResponse.json(
        { error: '日付とIDが必要です' },
        { status: 400 }
      );
    }
    
    const plans = await loadPlans(date);
    const planIndex = plans.plans.findIndex(p => p.id === id);
    
    if (planIndex === -1) {
      return NextResponse.json(
        { error: '指定された購入予定が見つかりません' },
        { status: 404 }
      );
    }
    
    // 更新を適用
    plans.plans[planIndex] = {
      ...plans.plans[planIndex],
      ...updates,
      updated_at: new Date().toISOString(),
    };
    
    await savePlans(plans);
    
    return NextResponse.json({
      success: true,
      plan: plans.plans[planIndex],
      total_planned: plans.total_planned,
      total_purchased: plans.total_purchased,
    });
  } catch (error) {
    console.error('[PlansAPI] PUT Error:', error);
    return NextResponse.json(
      { error: '購入予定の更新に失敗しました', message: String(error) },
      { status: 500 }
    );
  }
}

/**
 * DELETE: 購入予定を削除
 */
export async function DELETE(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const date = searchParams.get('date');
    const id = searchParams.get('id');
    
    if (!date || !id) {
      return NextResponse.json(
        { error: '日付とIDが必要です' },
        { status: 400 }
      );
    }
    
    const plans = await loadPlans(date);
    const planIndex = plans.plans.findIndex(p => p.id === id);
    
    if (planIndex === -1) {
      return NextResponse.json(
        { error: '指定された購入予定が見つかりません' },
        { status: 404 }
      );
    }
    
    plans.plans.splice(planIndex, 1);
    await savePlans(plans);
    
    return NextResponse.json({
      success: true,
      total_planned: plans.total_planned,
      total_purchased: plans.total_purchased,
    });
  } catch (error) {
    console.error('[PlansAPI] DELETE Error:', error);
    return NextResponse.json(
      { error: '購入予定の削除に失敗しました', message: String(error) },
      { status: 500 }
    );
  }
}
