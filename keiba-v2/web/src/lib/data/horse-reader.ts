import fs from 'fs';
import path from 'path';
import { remark } from 'remark';
import html from 'remark-html';
import gfm from 'remark-gfm';
import { PATHS } from '../config';
import type { HorseSummary, HorseProfile } from '@/types';

/**
 * 全角数字を半角に変換
 */
function fullWidthToHalfWidth(str: string): string {
  return str.replace(/[０-９]/g, (char) =>
    String.fromCharCode(char.charCodeAt(0) - 0xFEE0)
  );
}

export interface PastRace {
  date: string;       // 2025/11/02
  track: string;      // 4東京11
  raceName: string;   // 天皇賞（秋）
  raceNumber?: number; // 11 (レース番号が分かる場合のみ)
  result: string;     // 着順
  distance: string;   // 芝2000
  umaban: string;     // 馬番（出走番号）
}

/**
 * 馬IDからプロファイルを取得
 */
export async function getHorseProfile(horseId: string): Promise<HorseProfile | null> {
  const horsesPath = PATHS.horses;

  if (!fs.existsSync(horsesPath)) {
    return null;
  }

  // ファイル名のパターン: {馬ID}_{馬名}.md
  const files = fs.readdirSync(horsesPath);
  const targetFile = files.find((f) => f.startsWith(`${horseId}_`) && f.endsWith('.md'));

  if (!targetFile) {
    return null;
  }

  const filePath = path.join(horsesPath, targetFile);
  const content = fs.readFileSync(filePath, 'utf-8');

  // 基本情報を抽出
  const nameMatch = targetFile.match(/^\d+_(.+)\.md$/);
  const name = nameMatch ? nameMatch[1] : '';

  // 性齢を抽出
  const ageMatch = content.match(/性齢[:\s]*\*?\*?(\S+)\*?\*?/);
  const age = ageMatch ? ageMatch[1] : '';

  // ローカルパスをURLに変換
  const processedContent = convertLocalPaths(content);

  // MarkdownをHTMLに変換
  const result = await remark().use(gfm).use(html).process(processedContent);
  const htmlContent = result.toString();

  return {
    id: horseId,
    name,
    age,
    filePath,
    content,
    htmlContent,
  };
}

/**
 * 馬名で検索
 */
export async function searchHorses(query: string): Promise<HorseSummary[]> {
  const horsesPath = PATHS.horses;

  if (!fs.existsSync(horsesPath)) {
    return [];
  }

  const files = fs.readdirSync(horsesPath);
  const results: HorseSummary[] = [];

  const normalizedQuery = query.toLowerCase();

  for (const file of files) {
    if (!file.endsWith('.md')) continue;

    const match = file.match(/^(\d+)_(.+)\.md$/);
    if (!match) continue;

    const [, id, name] = match;

    // 馬名で部分一致検索
    if (name.toLowerCase().includes(normalizedQuery)) {
      const filePath = path.join(horsesPath, file);
      const content = fs.readFileSync(filePath, 'utf-8');

      // 性齢を抽出
      const ageMatch = content.match(/性齢[:\s]*\*?\*?(\S+)\*?\*?/);
      const age = ageMatch ? ageMatch[1] : '';

      results.push({
        id,
        name,
        age,
        filePath,
      });
    }

    // 最大50件まで
    if (results.length >= 50) break;
  }

  return results;
}

/**
 * ローカルファイルパスをWebアプリURLに変換
 */
function convertLocalPaths(content: string): string {
  // レースへのリンクを変換
  const racePattern =
    /\[([^\]]+)\]\((?:Z:|\/)?[^)]*races\/(\d{4})\/(\d{2})\/(\d{2})\/([^/]+)\/(\d+)\.md\)/g;
  content = content.replace(racePattern, '[$1](/races/$2-$3-$4/$5/$6)');

  // 馬プロファイルへのリンクを変換
  const horsePattern =
    /\[([^\]]+)\]\((?:Z:|\/)?[^)]*horses\/profiles\/(\d+)_[^)]+\.md\)/g;
  content = content.replace(horsePattern, '[$1](/horses/$2)');

  return content;
}

/**
 * 馬プロファイルMDから過去成績を抽出
 */
export function extractPastRaces(content: string): PastRace[] {
  const races: PastRace[] = [];
  
  // 完全成績テーブルの行を探す
  // 形式: | コメント | 本誌 | 日付 | 競馬場 | レース | クラス | 距離 | ... | 馬番 | ... | 着順 | ...
  const lines = content.split('\n');
  
  let inTable = false;
  let inCompleteResultSection = false;
  let headerIndexes: { date: number; track: number; race: number; distance: number; result: number; umaban: number } | null = null;
  
  for (const line of lines) {
    if (line.startsWith('## ')) {
      inCompleteResultSection = line.trim() === '## 完全成績';
      inTable = false;
      continue;
    }
    if (!inCompleteResultSection) continue;
    if (!line.startsWith('|')) continue;
    
    const cells = line.split('|').slice(1, -1).map(c => c.trim());
    
    // ヘッダー行を検出
    if (cells.some(c => c === '日付' || c === '年月日') && cells.some(c => c === '競馬場' || c === '開催')) {
      const dateIdx = cells.findIndex(c => c === '日付' || c === '年月日');
      const trackIdx = cells.findIndex(c => c === '競馬場' || c === '開催');
      const raceIdx = cells.findIndex(c => c === 'レース');
      const distanceIdx = cells.findIndex(c => c === '距離');
      const resultIdx = cells.findIndex(c => c === '着順');
      const umabanIdx = cells.findIndex(c => c === '馬番');
      
      if (dateIdx >= 0 && trackIdx >= 0) {
        headerIndexes = {
          date: dateIdx,
          track: trackIdx,
          race: raceIdx >= 0 ? raceIdx : trackIdx + 1,
          distance: distanceIdx,
          result: resultIdx,
          umaban: umabanIdx,
        };
        inTable = true;
        continue;
      }
    }
    
    // セパレータ行をスキップ
    if (cells.every(c => /^[-:\s]+$/.test(c))) continue;
    
    // データ行を処理
    if (inTable && headerIndexes && cells.length > Math.max(headerIndexes.date, headerIndexes.track)) {
      const date = cells[headerIndexes.date] || '';
      const track = cells[headerIndexes.track] || '';
      const raceName = cells[headerIndexes.race] || '';
      const distance = headerIndexes.distance >= 0 ? (cells[headerIndexes.distance] || '') : '';
      const result = headerIndexes.result >= 0 ? (cells[headerIndexes.result] || '').replace(/\D/g, '') : '';
      const umaban = headerIndexes.umaban >= 0 ? (cells[headerIndexes.umaban] || '') : '';
      const normalizedRaceName = fullWidthToHalfWidth(raceName);
      const raceNumberMatch =
        normalizedRaceName.match(/(?:^|\s)(\d{1,2})R\b/) ||
        normalizedRaceName.match(/第(\d{1,2})R/) ||
        normalizedRaceName.match(/第(\d{1,2})レース/) ||
        normalizedRaceName.match(/(?:^|\s)(\d{1,2})レース/);
      const raceNumber = raceNumberMatch ? parseInt(raceNumberMatch[1], 10) : undefined;
      
      // 日付形式のチェック（YYYY/MM/DD）
      if (/^\d{4}\/\d{1,2}\/\d{1,2}$/.test(date)) {
        races.push({ date, track, raceName, raceNumber, result, distance, umaban });
      }
    }
  }
  
  return races;
}

/**
 * 馬プロファイルと過去成績を取得
 */
export async function getHorseProfileWithRaces(horseId: string): Promise<(HorseProfile & { pastRaces: PastRace[] }) | null> {
  const profile = await getHorseProfile(horseId);
  if (!profile) return null;
  
  const pastRaces = extractPastRaces(profile.content);
  
  return {
    ...profile,
    pastRaces,
  };
}
