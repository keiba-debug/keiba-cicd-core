'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

interface HorseSummary {
  id: string;
  name: string;
  age: string;
}

export default function HorseSearchPage() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<HorseSummary[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  const handleSearch = async () => {
    if (!query.trim()) return;

    setIsSearching(true);
    setHasSearched(true);

    try {
      const res = await fetch(`/api/horses/search?q=${encodeURIComponent(query)}`);
      const data = await res.json();
      setResults(data.horses || []);
    } catch (error) {
      console.error('Search error:', error);
      setResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="container py-6">
      <h1 className="text-3xl font-bold mb-6">🔍 馬検索</h1>

      {/* 検索フォーム */}
      <div className="flex gap-2 mb-6">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          placeholder="馬名を入力..."
          className="flex-1 px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
        />
        <Button onClick={handleSearch} disabled={isSearching}>
          {isSearching ? '検索中...' : '検索'}
        </Button>
      </div>

      {/* 検索結果 */}
      {hasSearched && (
        <div>
          <p className="text-sm text-muted-foreground mb-4">
            {results.length}件の結果
          </p>

          {results.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {results.map((horse) => (
                <Link key={horse.id} href={`/horses-v2/${horse.id}`}>
                  <Card className="hover:bg-muted/50 transition-colors cursor-pointer">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-lg flex items-center gap-2">
                        <span>🐴</span>
                        {horse.name}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="flex items-center gap-2">
                        {horse.age && (
                          <Badge variant="secondary">{horse.age}</Badge>
                        )}
                        <span className="text-sm text-muted-foreground">
                          ID: {horse.id}
                        </span>
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground">
              該当する馬が見つかりませんでした
            </p>
          )}
        </div>
      )}

      {!hasSearched && (
        <p className="text-muted-foreground">
          馬名の一部を入力して検索してください
        </p>
      )}
    </div>
  );
}
