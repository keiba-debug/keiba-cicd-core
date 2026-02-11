/**
 * TARGET馬印API
 * 
 * GET: 指定レースの馬印を取得
 * POST: 馬印を更新
 */

import { NextRequest, NextResponse } from 'next/server';
import { getRaceMarks, writeHorseMark, VALID_MARKS, type MarkSymbol } from '@/lib/data/target-mark-reader';

interface GetParams {
  year: number;
  kai: number;
  nichi: number;
  raceNumber: number;
  venue: string;
  markSet?: number;
}

interface PostParams extends GetParams {
  horseNumber: number;
  mark: string;
}

/**
 * GET: 馬印を取得
 * Query: year, kai, nichi, raceNumber, venue, markSet
 */
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    
    const year = parseInt(searchParams.get('year') || '', 10);
    const kai = parseInt(searchParams.get('kai') || '', 10);
    const nichi = parseInt(searchParams.get('nichi') || '', 10);
    const raceNumber = parseInt(searchParams.get('raceNumber') || '', 10);
    const venue = searchParams.get('venue') || '';
    const markSet = parseInt(searchParams.get('markSet') || '1', 10);
    
    if (!year || !kai || !nichi || !raceNumber || !venue) {
      return NextResponse.json(
        { error: 'Missing required parameters: year, kai, nichi, raceNumber, venue' },
        { status: 400 }
      );
    }
    
    const marks = getRaceMarks(year, kai, nichi, raceNumber, venue, markSet);
    
    return NextResponse.json({
      success: true,
      data: marks || { raceMark: '', colorCode: '', horseMarks: {} },
      params: { year, kai, nichi, raceNumber, venue, markSet },
    });
  } catch (error) {
    console.error('[target-marks API] GET error:', error);
    return NextResponse.json(
      { error: 'Failed to get marks', details: String(error) },
      { status: 500 }
    );
  }
}

/**
 * POST: 馬印を更新
 * Body: { year, kai, nichi, raceNumber, venue, horseNumber, mark, markSet }
 */
export async function POST(request: NextRequest) {
  try {
    const body: PostParams = await request.json();
    
    const { year, kai, nichi, raceNumber, venue, horseNumber, mark, markSet = 1 } = body;
    
    if (!year || !kai || !nichi || !raceNumber || !venue || !horseNumber) {
      return NextResponse.json(
        { error: 'Missing required parameters' },
        { status: 400 }
      );
    }
    
    // 印のバリデーション
    if (!VALID_MARKS.includes(mark as MarkSymbol)) {
      return NextResponse.json(
        { error: `Invalid mark: ${mark}. Valid marks: ${VALID_MARKS.join(', ')}` },
        { status: 400 }
      );
    }
    
    const success = writeHorseMark(
      year,
      kai,
      nichi,
      raceNumber,
      venue,
      horseNumber,
      mark,
      markSet
    );
    
    if (!success) {
      return NextResponse.json(
        { error: 'Failed to write mark' },
        { status: 500 }
      );
    }
    
    // 更新後のデータを返す
    const updatedMarks = getRaceMarks(year, kai, nichi, raceNumber, venue, markSet);
    
    return NextResponse.json({
      success: true,
      data: updatedMarks || { raceMark: '', colorCode: '', horseMarks: {} },
      updated: { horseNumber, mark, markSet },
    });
  } catch (error) {
    console.error('[target-marks API] POST error:', error);
    return NextResponse.json(
      { error: 'Failed to update mark', details: String(error) },
      { status: 500 }
    );
  }
}

/**
 * PUT: 複数の馬印を一括更新
 * Body: { year, kai, nichi, raceNumber, venue, marks: { horseNumber: mark, ... }, markSet }
 */
export async function PUT(request: NextRequest) {
  try {
    const body = await request.json();
    
    const { year, kai, nichi, raceNumber, venue, marks, markSet = 1 } = body;
    
    if (!year || !kai || !nichi || !raceNumber || !venue || !marks) {
      return NextResponse.json(
        { error: 'Missing required parameters' },
        { status: 400 }
      );
    }
    
    const results: { horseNumber: number; mark: string; success: boolean }[] = [];
    
    for (const [horseNumberStr, mark] of Object.entries(marks)) {
      const horseNumber = parseInt(horseNumberStr, 10);
      
      if (isNaN(horseNumber) || !VALID_MARKS.includes(mark as MarkSymbol)) {
        results.push({ horseNumber, mark: String(mark), success: false });
        continue;
      }
      
      const success = writeHorseMark(
        year,
        kai,
        nichi,
        raceNumber,
        venue,
        horseNumber,
        mark as string,
        markSet
      );
      
      results.push({ horseNumber, mark: String(mark), success });
    }
    
    // 更新後のデータを返す
    const updatedMarks = getRaceMarks(year, kai, nichi, raceNumber, venue, markSet);
    
    return NextResponse.json({
      success: true,
      data: updatedMarks || { raceMark: '', colorCode: '', horseMarks: {} },
      results,
    });
  } catch (error) {
    console.error('[target-marks API] PUT error:', error);
    return NextResponse.json(
      { error: 'Failed to update marks', details: String(error) },
      { status: 500 }
    );
  }
}
