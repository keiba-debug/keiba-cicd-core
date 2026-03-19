'use client';

import { useState, useEffect, useCallback } from 'react';
import useSWR from 'swr';
import Link from 'next/link';
import { ChevronDown, ChevronRight, Tag, FileText, ArrowLeft } from 'lucide-react';

// ============================================================
// Types
// ============================================================
interface ChangelogEntry {
  file: string;
  version: string;
  title: string;
  date: string;
  summary: string;
  tags: string[];
  category: 'version' | 'analysis' | 'design';
}

// ============================================================
// Helpers
// ============================================================
const fetcher = (url: string) => fetch(url).then(r => r.json());

const TAG_COLORS: Record<string, string> = {
  '特徴量': 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300',
  'モデル改善': 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300',
  '戦略': 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300',
  '修正': 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
  '血統': 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300',
  '障害': 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300',
  'JRDB': 'bg-cyan-100 text-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-300',
};

function TagBadge({ tag }: { tag: string }) {
  const color = TAG_COLORS[tag] || 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300';
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium ${color}`}>
      {tag}
    </span>
  );
}

function formatDate(dateStr: string) {
  const [y, m, d] = dateStr.split('-');
  return `${y}/${m}/${d}`;
}

// ============================================================
// Major version grouping
// ============================================================
function getMajorVersion(version: string): string {
  const match = version.match(/^(\d+)\./);
  return match ? `v${match[1]}` : 'other';
}

function groupByMajor(entries: ChangelogEntry[]): { major: string; entries: ChangelogEntry[] }[] {
  const groups = new Map<string, ChangelogEntry[]>();
  for (const entry of entries) {
    const key = entry.version ? getMajorVersion(entry.version) : 'other';
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(entry);
  }
  // Sort major versions descending
  const sorted = Array.from(groups.entries()).sort((a, b) => {
    if (a[0] === 'other') return 1;
    if (b[0] === 'other') return -1;
    const na = parseInt(a[0].slice(1));
    const nb = parseInt(b[0].slice(1));
    return nb - na;
  });
  return sorted.map(([major, entries]) => ({ major, entries }));
}

// ============================================================
// Markdown Detail Viewer
// ============================================================
function MarkdownViewer({ file }: { file: string }) {
  const { data, error, isLoading } = useSWR<{ content: string }>(
    `/api/changelog/${encodeURIComponent(file)}`,
    fetcher
  );

  if (isLoading) return <div className="p-4 text-sm text-muted-foreground">読み込み中...</div>;
  if (error || !data) return <div className="p-4 text-sm text-red-500">読み込みエラー</div>;

  return (
    <div className="border-t mt-3 pt-3">
      <pre className="text-xs leading-relaxed whitespace-pre-wrap font-mono text-muted-foreground max-h-[500px] overflow-y-auto">
        {data.content}
      </pre>
    </div>
  );
}

// ============================================================
// Entry Card
// ============================================================
function EntryCard({ entry }: { entry: ChangelogEntry }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="relative pl-8 pb-6">
      {/* Timeline dot */}
      <div className={`absolute left-0 top-1 w-3 h-3 rounded-full border-2 ${
        entry.version
          ? 'border-emerald-500 bg-emerald-500/20'
          : 'border-muted-foreground/40 bg-muted/50'
      }`} />

      <div
        className="group cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-start gap-2">
          {/* Expand icon */}
          <span className="mt-0.5 text-muted-foreground/50 group-hover:text-foreground transition-colors">
            {expanded
              ? <ChevronDown className="h-4 w-4" />
              : <ChevronRight className="h-4 w-4" />
            }
          </span>

          <div className="flex-1 min-w-0">
            {/* Title row */}
            <div className="flex items-center gap-2 flex-wrap">
              {entry.version && (
                <span className="text-sm font-bold text-emerald-600 dark:text-emerald-400 font-mono">
                  v{entry.version}
                </span>
              )}
              <h3 className="text-sm font-semibold truncate group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors">
                {entry.title}
              </h3>
            </div>

            {/* Meta row */}
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              <span className="text-xs text-muted-foreground">{formatDate(entry.date)}</span>
              {entry.tags.map(tag => (
                <TagBadge key={tag} tag={tag} />
              ))}
            </div>

            {/* Summary */}
            {entry.summary && !expanded && (
              <p className="text-xs text-muted-foreground mt-1 line-clamp-1">{entry.summary}</p>
            )}
          </div>
        </div>
      </div>

      {/* Expanded content */}
      {expanded && <MarkdownViewer file={entry.file} />}
    </div>
  );
}

// ============================================================
// Main Page
// ============================================================
export default function ChangelogPage() {
  const { data, error, isLoading } = useSWR<{ entries: ChangelogEntry[]; total: number }>(
    '/api/changelog',
    fetcher
  );

  const [filter, setFilter] = useState<string>('all');
  const [search, setSearch] = useState('');

  const entries = data?.entries ?? [];

  // Collect all tags
  const allTags = [...new Set(entries.flatMap(e => e.tags))].sort();

  // Filter
  const filtered = entries.filter(e => {
    if (filter === 'version' && !e.version) return false;
    if (filter === 'other' && e.version) return false;
    if (filter !== 'all' && filter !== 'version' && filter !== 'other') {
      if (!e.tags.includes(filter)) return false;
    }
    if (search) {
      const q = search.toLowerCase();
      return e.title.toLowerCase().includes(q)
        || e.version.includes(q)
        || e.summary.toLowerCase().includes(q)
        || e.tags.some(t => t.includes(q));
    }
    return true;
  });

  const versionedEntries = filtered.filter(e => e.version);
  const otherEntries = filtered.filter(e => !e.version);
  const majorGroups = groupByMajor(versionedEntries);

  if (isLoading) {
    return (
      <div className="w-full max-w-4xl mx-auto px-4 py-12">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-muted rounded w-48" />
          <div className="h-4 bg-muted rounded w-96" />
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-16 bg-muted rounded" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-4xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold">Changelog</h1>
        <p className="text-sm text-muted-foreground mt-1">
          MLモデル・戦略の改善履歴 — {data?.total ?? 0}件のレポート
        </p>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2 flex-wrap mb-6">
        <input
          type="text"
          placeholder="検索..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="px-3 py-1.5 text-sm border rounded-lg bg-background w-48"
        />
        <button
          onClick={() => setFilter('all')}
          className={`px-3 py-1.5 text-xs rounded-full border transition-colors ${
            filter === 'all' ? 'bg-foreground text-background' : 'hover:bg-muted'
          }`}
        >
          全て
        </button>
        <button
          onClick={() => setFilter('version')}
          className={`px-3 py-1.5 text-xs rounded-full border transition-colors ${
            filter === 'version' ? 'bg-foreground text-background' : 'hover:bg-muted'
          }`}
        >
          バージョン
        </button>
        <button
          onClick={() => setFilter('other')}
          className={`px-3 py-1.5 text-xs rounded-full border transition-colors ${
            filter === 'other' ? 'bg-foreground text-background' : 'hover:bg-muted'
          }`}
        >
          分析・設計
        </button>
        {allTags.map(tag => (
          <button
            key={tag}
            onClick={() => setFilter(filter === tag ? 'all' : tag)}
            className={`px-3 py-1.5 text-xs rounded-full border transition-colors ${
              filter === tag ? 'bg-foreground text-background' : 'hover:bg-muted'
            }`}
          >
            {tag}
          </button>
        ))}
      </div>

      {/* Timeline */}
      <div className="relative">
        {/* Timeline line */}
        <div className="absolute left-[5px] top-0 bottom-0 w-px bg-border" />

        {/* Version groups */}
        {majorGroups.map(({ major, entries: groupEntries }) => (
          <div key={major} className="mb-8">
            <div className="flex items-center gap-2 mb-4 pl-8">
              <span className="text-lg font-bold text-emerald-600 dark:text-emerald-400 font-mono">
                {major === 'other' ? 'その他' : major}
              </span>
              <span className="text-xs text-muted-foreground">
                ({groupEntries.length}件)
              </span>
            </div>
            {groupEntries.map(entry => (
              <EntryCard key={entry.file} entry={entry} />
            ))}
          </div>
        ))}

        {/* Non-versioned entries */}
        {otherEntries.length > 0 && (
          <div className="mb-8">
            <div className="flex items-center gap-2 mb-4 pl-8">
              <FileText className="h-5 w-5 text-muted-foreground" />
              <span className="text-lg font-bold">分析・設計レポート</span>
              <span className="text-xs text-muted-foreground">
                ({otherEntries.length}件)
              </span>
            </div>
            {otherEntries.map(entry => (
              <EntryCard key={entry.file} entry={entry} />
            ))}
          </div>
        )}
      </div>

      {filtered.length === 0 && (
        <div className="text-center py-12 text-muted-foreground">
          該当するレポートがありません
        </div>
      )}
    </div>
  );
}
