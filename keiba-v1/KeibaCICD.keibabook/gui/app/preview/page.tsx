'use client';

import { useState, useEffect } from 'react';
import { Calendar, ChevronRight, RefreshCw, Eye, FileText } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

interface Venue {
  venue: string;
  venue_code: string;
  races: Race[];
  total_races: number;
}

interface Race {
  race_id: string;
  race_number: number;
  race_name: string;
  has_md: boolean;
  has_json: boolean;
}

export default function PreviewPage() {
  const [selectedDate, setSelectedDate] = useState(
    new Date().toISOString().split('T')[0]
  );
  const [venues, setVenues] = useState<Venue[]>([]);
  const [selectedVenue, setSelectedVenue] = useState<string>('');
  const [selectedRace, setSelectedRace] = useState<string>('');
  const [markdownContent, setMarkdownContent] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [viewMode, setViewMode] = useState<'markdown' | 'html'>('markdown');

  // 日付変更時に会場一覧を取得
  useEffect(() => {
    if (selectedDate) {
      fetchVenues();
    }
  }, [selectedDate]);

  const fetchVenues = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(
        `http://localhost:8000/artifacts?date=${selectedDate}`
      );
      const data = await response.json();
      setVenues(data.venues || []);
      setSelectedVenue('');
      setSelectedRace('');
      setMarkdownContent('');
    } catch (error) {
      console.error('Failed to fetch venues:', error);
      setVenues([]);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchMarkdown = async (raceId: string) => {
    setIsLoading(true);
    try {
      const response = await fetch(`http://localhost:8000/markdown/${raceId}`);
      const data = await response.json();
      setMarkdownContent(data.content || '');
    } catch (error) {
      console.error('Failed to fetch markdown:', error);
      setMarkdownContent('# エラー\nMarkdownの取得に失敗しました。');
    } finally {
      setIsLoading(false);
    }
  };

  const regenerateMarkdown = async () => {
    if (!selectedRace) return;
    
    setIsLoading(true);
    try {
      // 単一レースのMD再生成
      const response = await fetch('http://localhost:8000/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          command: 'markdown',
          args: {
            subcommand: 'single',
            'race-id': selectedRace
          }
        })
      });
      
      const job = await response.json();
      
      // ジョブ完了を待つ（簡易版：5秒待機）
      await new Promise(resolve => setTimeout(resolve, 5000));
      
      // 再取得
      await fetchMarkdown(selectedRace);
    } catch (error) {
      console.error('Failed to regenerate:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const selectedVenueData = venues.find(v => v.venue === selectedVenue);
  const selectedRaceData = selectedVenueData?.races.find(
    r => r.race_id === selectedRace
  );

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center space-x-4">
              <a href="/" className="text-gray-600 hover:text-gray-900">
                ← Back
              </a>
              <h1 className="text-xl font-semibold">📰 MD新聞プレビュー</h1>
            </div>
            <div className="flex items-center space-x-2">
              <button
                onClick={() => setViewMode('markdown')}
                className={`px-3 py-1 rounded ${
                  viewMode === 'markdown' 
                    ? 'bg-blue-600 text-white' 
                    : 'bg-gray-200 text-gray-700'
                }`}
              >
                <Eye className="inline h-4 w-4 mr-1" />
                Preview
              </button>
              <button
                onClick={() => setViewMode('html')}
                className={`px-3 py-1 rounded ${
                  viewMode === 'html' 
                    ? 'bg-blue-600 text-white' 
                    : 'bg-gray-200 text-gray-700'
                }`}
              >
                <FileText className="inline h-4 w-4 mr-1" />
                Raw
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-12 gap-6">
          {/* 左側: セレクタ */}
          <div className="col-span-3 space-y-4">
            {/* 日付選択 */}
            <div className="bg-white rounded-lg shadow p-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                <Calendar className="inline h-4 w-4 mr-1" />
                日付選択
              </label>
              <input
                type="date"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* 会場選択 */}
            <div className="bg-white rounded-lg shadow p-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                競馬場
              </label>
              <select
                value={selectedVenue}
                onChange={(e) => {
                  setSelectedVenue(e.target.value);
                  setSelectedRace('');
                  setMarkdownContent('');
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled={venues.length === 0}
              >
                <option value="">選択してください</option>
                {venues.map(venue => (
                  <option key={venue.venue} value={venue.venue}>
                    {venue.venue} ({venue.total_races}R)
                  </option>
                ))}
              </select>
            </div>

            {/* レース選択 */}
            {selectedVenueData && (
              <div className="bg-white rounded-lg shadow p-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  レース
                </label>
                <div className="space-y-1 max-h-96 overflow-y-auto">
                  {selectedVenueData.races.map(race => (
                    <button
                      key={race.race_id}
                      onClick={() => {
                        setSelectedRace(race.race_id);
                        fetchMarkdown(race.race_id);
                      }}
                      className={`w-full text-left px-3 py-2 rounded hover:bg-gray-100 flex items-center justify-between ${
                        selectedRace === race.race_id
                          ? 'bg-blue-50 border-blue-500 border'
                          : ''
                      }`}
                    >
                      <span className="flex items-center">
                        <span className="font-medium mr-2">
                          {race.race_number}R
                        </span>
                        <span className="text-sm text-gray-600">
                          {race.race_name}
                        </span>
                      </span>
                      <span className="flex space-x-1">
                        {race.has_md && (
                          <span className="text-xs bg-green-100 text-green-700 px-1 rounded">
                            MD
                          </span>
                        )}
                        {race.has_json && (
                          <span className="text-xs bg-blue-100 text-blue-700 px-1 rounded">
                            JSON
                          </span>
                        )}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* 再生成ボタン */}
            {selectedRace && (
              <button
                onClick={regenerateMarkdown}
                disabled={isLoading}
                className="w-full bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
              >
                <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
                MD再生成
              </button>
            )}
          </div>

          {/* 右側: プレビュー */}
          <div className="col-span-9">
            <div className="bg-white rounded-lg shadow" style={{ minHeight: '600px' }}>
              {isLoading ? (
                <div className="flex items-center justify-center h-96">
                  <div className="text-gray-500">読み込み中...</div>
                </div>
              ) : markdownContent ? (
                viewMode === 'markdown' ? (
                  <div className="p-6 prose prose-lg max-w-none">
                    <ReactMarkdown
                      components={{
                        table: ({ children }) => (
                          <table className="min-w-full divide-y divide-gray-200">
                            {children}
                          </table>
                        ),
                        thead: ({ children }) => (
                          <thead className="bg-gray-50">{children}</thead>
                        ),
                        tbody: ({ children }) => (
                          <tbody className="bg-white divide-y divide-gray-200">
                            {children}
                          </tbody>
                        ),
                        th: ({ children }) => (
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            {children}
                          </th>
                        ),
                        td: ({ children }) => (
                          <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-900">
                            {children}
                          </td>
                        ),
                        h1: ({ children }) => (
                          <h1 className="text-2xl font-bold text-gray-900 border-b-2 border-blue-500 pb-2 mb-4">
                            {children}
                          </h1>
                        ),
                        h2: ({ children }) => (
                          <h2 className="text-xl font-semibold text-gray-800 border-b border-gray-200 pb-1 mb-3 mt-6">
                            {children}
                          </h2>
                        ),
                        h3: ({ children }) => (
                          <h3 className="text-lg font-medium text-gray-700 mb-2 mt-4">
                            {children}
                          </h3>
                        ),
                      }}
                    >
                      {markdownContent}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <div className="p-6">
                    <pre className="whitespace-pre-wrap text-sm font-mono bg-gray-50 p-4 rounded overflow-x-auto">
                      {markdownContent}
                    </pre>
                  </div>
                )
              ) : (
                <div className="flex items-center justify-center h-96 text-gray-500">
                  {selectedRace 
                    ? 'Markdownを読み込めませんでした' 
                    : 'レースを選択してください'}
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}