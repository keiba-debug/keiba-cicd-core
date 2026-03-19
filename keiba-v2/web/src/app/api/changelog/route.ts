import { NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';

const DOCS_DIR = path.join(process.cwd(), '..', 'docs', 'ml-experiments');

export interface ChangelogEntry {
  file: string;
  version: string;
  title: string;
  date: string;
  summary: string;
  tags: string[];
  category: 'version' | 'analysis' | 'design';
}

/**
 * docs/ml-experiments/ のmdファイルをスキャンしてchangelogインデックスを返す
 * ファイル名とコンテンツから自動推定
 */
export async function GET() {
  try {
    const files = await fs.readdir(DOCS_DIR);
    const mdFiles = files.filter(f => f.endsWith('.md') && f !== 'README.md');

    const entries: ChangelogEntry[] = [];

    for (const file of mdFiles) {
      const filePath = path.join(DOCS_DIR, file);
      const content = await fs.readFile(filePath, 'utf-8');
      const stat = await fs.stat(filePath);

      // Title: first # line
      let title = file.replace('.md', '');
      for (const line of content.split('\n')) {
        if (line.startsWith('# ')) {
          title = line.slice(2).trim();
          break;
        }
      }

      // Version from filename (e.g. v5.3_comment_nlp.md → "5.3")
      const verMatch = file.match(/^v(\d+\.\d+\S*?)_/);
      const version = verMatch ? verMatch[1] : '';

      // Date: from file modification time
      const date = stat.mtime.toISOString().slice(0, 10);

      // Summary: first non-empty, non-heading, non-blockquote line
      let summary = '';
      const lines = content.split('\n');
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        if (trimmed.startsWith('#')) continue;
        if (trimmed.startsWith('>')) continue;
        if (trimmed.startsWith('---')) continue;
        if (trimmed.startsWith('|')) continue;
        if (trimmed.startsWith('```')) continue;
        if (trimmed.startsWith('- **')) {
          // Often the first bullet has key info
          summary = trimmed.replace(/^- \*\*/, '').replace(/\*\*.*/, '').trim();
          if (summary.length > 10) break;
          summary = '';
          continue;
        }
        summary = trimmed.replace(/\*\*/g, '').slice(0, 120);
        break;
      }

      // Tags: auto-detect from content
      const tags: string[] = [];
      const lc = content.toLowerCase();
      if (lc.includes('特徴量') && (lc.includes('追加') || lc.includes('+') || lc.includes('拡張'))) {
        tags.push('特徴量');
      }
      if (lc.includes('auc') || lc.includes('brier') || lc.includes('キャリブレーション') || lc.includes('calibra')) {
        tags.push('モデル改善');
      }
      if (lc.includes('bet_engine') || lc.includes('roi') || lc.includes('バックテスト') || lc.includes('戦略')) {
        tags.push('戦略');
      }
      if (lc.includes('バグ') || lc.includes('修正') || lc.includes('fix')) {
        tags.push('修正');
      }
      if (lc.includes('血統') || lc.includes('pedigree')) {
        tags.push('血統');
      }
      if (lc.includes('障害') || lc.includes('obstacle')) {
        tags.push('障害');
      }
      if (lc.includes('jrdb') || lc.includes('idm')) {
        tags.push('JRDB');
      }
      // Deduplicate
      const uniqueTags = [...new Set(tags)];

      // Category
      let category: ChangelogEntry['category'] = 'analysis';
      if (version) category = 'version';
      if (file.includes('design') || file.includes('roadmap') || file.includes('提案')) {
        category = 'design';
      }

      entries.push({ file, version, title, date, summary, tags: uniqueTags, category });
    }

    // Sort: versioned first (by version desc), then others by date desc
    entries.sort((a, b) => {
      // versioned entries first
      if (a.version && !b.version) return -1;
      if (!a.version && b.version) return 1;

      if (a.version && b.version) {
        // Compare version numbers
        const pa = a.version.split('.').map(s => {
          const n = parseInt(s);
          return isNaN(n) ? 0 : n;
        });
        const pb = b.version.split('.').map(s => {
          const n = parseInt(s);
          return isNaN(n) ? 0 : n;
        });
        for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
          const diff = (pb[i] || 0) - (pa[i] || 0);
          if (diff !== 0) return diff;
        }
        // Sub-version suffix (e.g. 5.2b > 5.2)
        return b.version.localeCompare(a.version);
      }

      // Non-versioned: by date desc
      return b.date.localeCompare(a.date);
    });

    return NextResponse.json({ entries, total: entries.length });
  } catch (error) {
    console.error('[Changelog] Error:', error);
    return NextResponse.json({ entries: [], total: 0 });
  }
}
