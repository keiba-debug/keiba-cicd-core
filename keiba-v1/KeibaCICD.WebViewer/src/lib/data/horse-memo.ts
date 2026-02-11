/**
 * 馬プロファイルのユーザーメモ読み書き機能
 * Markdownファイル内の「## ユーザーメモ」セクションを編集
 */

import fs from 'fs';
import path from 'path';
import { PATHS } from '../config';

/**
 * 馬プロファイルファイルのパスを取得
 */
export function getHorseProfilePath(horseId: string): string | null {
  const profilesDir = PATHS.horses;
  
  if (!fs.existsSync(profilesDir)) {
    return null;
  }

  // ファイル名は {horseId}_{馬名}.md の形式
  const files = fs.readdirSync(profilesDir);
  const matchingFile = files.find(f => f.startsWith(`${horseId}_`) && f.endsWith('.md'));
  
  if (!matchingFile) {
    return null;
  }

  return path.join(profilesDir, matchingFile);
}

/**
 * 馬プロファイルからユーザーメモセクションを抽出
 */
export async function getHorseMemo(horseId: string): Promise<string> {
  const filePath = getHorseProfilePath(horseId);
  
  if (!filePath || !fs.existsSync(filePath)) {
    return '';
  }

  const content = fs.readFileSync(filePath, 'utf-8');
  
  // ## ユーザーメモ セクションを探す
  const memoSectionMatch = content.match(/## ユーザーメモ\n([\s\S]*?)(?=\n---|\n## |$)/);
  
  if (!memoSectionMatch) {
    return '';
  }

  // プレースホルダーテキストを除去
  let memo = memoSectionMatch[1].trim();
  if (memo === '（ここに予想メモや注目ポイントを記入）') {
    return '';
  }

  return memo;
}

/**
 * 馬プロファイルのユーザーメモセクションを更新
 */
export async function updateHorseMemo(horseId: string, newMemo: string): Promise<boolean> {
  const filePath = getHorseProfilePath(horseId);
  
  if (!filePath || !fs.existsSync(filePath)) {
    return false;
  }

  let content = fs.readFileSync(filePath, 'utf-8');
  
  // ## ユーザーメモ セクションを探して置換
  const memoSectionRegex = /(## ユーザーメモ\n)([\s\S]*?)((?=\n---\n\*最終更新)|\n## |$)/;
  
  const match = content.match(memoSectionRegex);
  
  if (!match) {
    // セクションが見つからない場合は追加
    content = content.replace(
      /(\n---\n\*最終更新.*\*)?$/,
      `\n\n## ユーザーメモ\n${newMemo || '（ここに予想メモや注目ポイントを記入）'}\n\n---\n*最終更新: ${new Date().toISOString().split('T')[0]}*`
    );
  } else {
    // セクションを置換
    const memoContent = newMemo.trim() || '（ここに予想メモや注目ポイントを記入）';
    content = content.replace(
      memoSectionRegex,
      `$1${memoContent}\n$3`
    );
  }

  // ファイルを書き込み
  fs.writeFileSync(filePath, content, 'utf-8');
  
  return true;
}
