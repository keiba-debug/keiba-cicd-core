/**
 * レースメモAPI
 * GET /api/memos/[raceId] - メモ取得
 * POST /api/memos/[raceId] - メモ保存/更新
 */

import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs/promises';
import path from 'path';
import { USER_DATA_DIR } from '@/lib/config';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

interface Memo {
  type: 'pre' | 'post';
  text: string;
  created_at: string;
  updated_at: string;
}

interface MemoData {
  race_id: string;
  race_date: string;
  race_name: string;
  memos: Memo[];
}

/**
 * 日付文字列をYYYY-MM-DD形式に変換
 */
function formatDateDir(dateStr: string): string {
  // YYYY-MM-DD 形式ならそのまま
  if (dateStr.includes('-')) {
    return dateStr;
  }
  // YYYYMMDD 形式の場合
  if (dateStr.length === 8) {
    return `${dateStr.substring(0, 4)}-${dateStr.substring(4, 6)}-${dateStr.substring(6, 8)}`;
  }
  return dateStr;
}

/**
 * メモファイルのパスを取得
 * @param raceId レースID
 * @param dateOverride 日付指定（YYYY-MM-DD または YYYYMMDD）
 */
function getMemoFilePath(raceId: string, dateOverride?: string): string {
  let dateDir: string;
  
  if (dateOverride) {
    // 明示的な日付指定がある場合はそれを使用
    dateDir = formatDateDir(dateOverride);
  } else {
    // フォールバック: raceIdから日付を抽出（レガシー対応）
    const raceDate = raceId.substring(0, 8);
    dateDir = formatDateDir(raceDate);
  }
  
  return path.join(USER_DATA_DIR, 'memos', dateDir, `${raceId}.json`);
}

/**
 * メモを読み込む
 */
async function loadMemo(raceId: string, dateOverride?: string): Promise<MemoData | null> {
  const filePath = getMemoFilePath(raceId, dateOverride);
  
  try {
    const content = await fs.readFile(filePath, 'utf-8');
    return JSON.parse(content) as MemoData;
  } catch {
    return null;
  }
}

/**
 * メモを保存する
 */
async function saveMemo(data: MemoData, dateOverride?: string): Promise<void> {
  const filePath = getMemoFilePath(data.race_id, dateOverride);
  const dir = path.dirname(filePath);
  
  // ディレクトリを作成
  await fs.mkdir(dir, { recursive: true });
  
  // ファイルに保存
  await fs.writeFile(filePath, JSON.stringify(data, null, 2), 'utf-8');
}

/**
 * GET: メモを取得
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ raceId: string }> }
) {
  try {
    const { raceId } = await params;
    const { searchParams } = new URL(request.url);
    const dateParam = searchParams.get('date'); // YYYY-MM-DD形式
    
    if (!raceId) {
      return NextResponse.json(
        { error: 'raceId は必須です' },
        { status: 400 }
      );
    }
    
    const memo = await loadMemo(raceId, dateParam || undefined);
    
    if (!memo) {
      // メモが存在しない場合は空のデータを返す
      const raceDate = dateParam 
        ? dateParam.replace(/-/g, '') 
        : raceId.substring(0, 8);
      return NextResponse.json({
        race_id: raceId,
        race_date: raceDate,
        race_name: '',
        memos: [],
      });
    }
    
    return NextResponse.json(memo);
  } catch (error) {
    console.error('[MemoAPI] GET Error:', error);
    return NextResponse.json(
      { error: 'メモの取得に失敗しました' },
      { status: 500 }
    );
  }
}

/**
 * POST: メモを保存/更新
 */
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ raceId: string }> }
) {
  try {
    const { raceId } = await params;
    const { searchParams } = new URL(request.url);
    const dateParam = searchParams.get('date'); // YYYY-MM-DD形式
    const body = await request.json();
    
    if (!raceId) {
      return NextResponse.json(
        { error: 'raceId は必須です' },
        { status: 400 }
      );
    }
    
    const { type, text, race_name, race_date: bodyRaceDate } = body as {
      type: 'pre' | 'post';
      text: string;
      race_name?: string;
      race_date?: string; // YYYYMMDD形式
    };
    
    // 日付の決定: クエリパラメータ > ボディ > raceIdから抽出
    const effectiveDate = dateParam || (bodyRaceDate ? formatDateDir(bodyRaceDate) : undefined);
    
    if (!type || !['pre', 'post'].includes(type)) {
      return NextResponse.json(
        { error: 'type は "pre" または "post" である必要があります' },
        { status: 400 }
      );
    }
    
    if (typeof text !== 'string') {
      return NextResponse.json(
        { error: 'text は文字列である必要があります' },
        { status: 400 }
      );
    }
    
    // 既存のメモを読み込む
    let memoData = await loadMemo(raceId, effectiveDate);
    const now = new Date().toISOString();
    
    if (!memoData) {
      // 新規作成
      const raceDate = effectiveDate 
        ? effectiveDate.replace(/-/g, '') 
        : raceId.substring(0, 8);
      memoData = {
        race_id: raceId,
        race_date: raceDate,
        race_name: race_name || '',
        memos: [],
      };
    }
    
    // race_name が指定されていれば更新
    if (race_name) {
      memoData.race_name = race_name;
    }
    
    // race_date を更新（正しい日付に修正）
    if (effectiveDate) {
      memoData.race_date = effectiveDate.replace(/-/g, '');
    }
    
    // 同じtypeのメモを探す
    const existingMemoIndex = memoData.memos.findIndex((m) => m.type === type);
    
    if (existingMemoIndex >= 0) {
      // 既存メモを更新
      memoData.memos[existingMemoIndex].text = text;
      memoData.memos[existingMemoIndex].updated_at = now;
    } else {
      // 新規メモを追加
      memoData.memos.push({
        type,
        text,
        created_at: now,
        updated_at: now,
      });
    }
    
    // 保存
    await saveMemo(memoData, effectiveDate);
    
    return NextResponse.json({
      success: true,
      data: memoData,
    });
  } catch (error) {
    console.error('[MemoAPI] POST Error:', error);
    return NextResponse.json(
      { error: 'メモの保存に失敗しました' },
      { status: 500 }
    );
  }
}
