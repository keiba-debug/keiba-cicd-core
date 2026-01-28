/**
 * UM_DATA デバッグAPI
 */

import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import iconv from 'iconv-lite';

const JV_DATA_ROOT = process.env.JV_DATA_ROOT_DIR || 'Y:/';
const UM_DATA_PATH = path.join(JV_DATA_ROOT, 'UM_DATA');
const UM_RECORD_LEN = 1609;

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const kettoNum = searchParams.get('ketto') || '';
  const searchName = searchParams.get('name') || '';
  
  const results: Record<string, unknown> = {
    kettoNum,
    searchName,
    UM_DATA_PATH,
    files: [],
    found: null,
  };
  
  try {
    // UM_DATAディレクトリ一覧
    const years = fs.readdirSync(UM_DATA_PATH).filter(f => /^\d{4}$/.test(f));
    results.years = years.slice(-5);  // 最新5年
    
    // 血統登録番号から生年を抽出
    const birthYear = parseInt(kettoNum.substring(0, 4), 10);
    results.birthYear = birthYear;
    
    // 検索対象年
    let searchYears: number[];
    if (searchName) {
      // 馬名検索の場合は全年を検索
      searchYears = [2024, 2023, 2022, 2021, 2020];
    } else {
      searchYears = [birthYear, 2024, 2023, 2022].filter((v, i, a) => a.indexOf(v) === i);
    }
    
    for (const year of searchYears) {
      for (let half = 2; half >= 1; half--) {
        const fileName = `UM${year}${half}.DAT`;
        const filePath = path.join(UM_DATA_PATH, String(year), fileName);
        
        const fileInfo: Record<string, unknown> = {
          path: filePath,
          exists: fs.existsSync(filePath),
        };
        
        if (fileInfo.exists) {
          const data = fs.readFileSync(filePath);
          fileInfo.size = data.length;
          fileInfo.records = Math.floor(data.length / UM_RECORD_LEN);
          
          // 血統登録番号で検索
          const numRecords = fileInfo.records as number;
          for (let i = 0; i < numRecords; i++) {
            const offset = i * UM_RECORD_LEN;
            const recordKettoNum = iconv.decode(data.subarray(offset + 11, offset + 21), 'Shift_JIS').trim();
            
            const horseName = iconv.decode(data.subarray(offset + 46, offset + 82), 'Shift_JIS')
              .replace(/\u3000/g, '')
              .trim();
            
            // 血統登録番号または馬名で検索
            const matchKetto = kettoNum && recordKettoNum === kettoNum;
            const matchName = searchName && horseName.includes(searchName);
            
            if (matchKetto || matchName) {
              results.found = {
                file: filePath,
                recordIndex: i,
                kettoNum: recordKettoNum,
                horseName,
              };
              break;
            }
          }
          
          // サンプル（最初の3件）
          const samples: Array<{ketto: string; name: string; nameBytes: number[]}> = [];
          for (let i = 0; i < Math.min(3, numRecords); i++) {
            const offset = i * UM_RECORD_LEN;
            const ketto = iconv.decode(data.subarray(offset + 11, offset + 21), 'Shift_JIS').trim();
            const nameBuffer = data.subarray(offset + 46, offset + 82);
            const name = iconv.decode(nameBuffer, 'Shift_JIS')
              .replace(/\u3000/g, '')
              .trim();
            samples.push({ 
              ketto, 
              name,
              nameBytes: Array.from(nameBuffer.subarray(0, 10))
            });
          }
          fileInfo.samples = samples;
        }
        
        (results.files as Array<unknown>).push(fileInfo);
        
        if (results.found) break;
      }
      if (results.found) break;
    }
    
  } catch (error) {
    results.error = error instanceof Error ? error.message : String(error);
  }
  
  return NextResponse.json(results);
}
