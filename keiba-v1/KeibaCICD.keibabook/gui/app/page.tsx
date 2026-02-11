'use client';

import { useState } from 'react';
import CommandRunner from '@/components/CommandRunner';
import JobList from '@/components/JobList';
import LogViewer from '@/components/LogViewer';
import HealthStatus from '@/components/HealthStatus';

export default function Home() {
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center space-x-6">
              <h1 className="text-xl font-semibold">🏇 KeibaCICD Control Panel</h1>
              <HealthStatus />
            </div>
            <div className="flex items-center space-x-4">
              <a 
                href="/preview" 
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm"
              >
                📰 MDプレビュー
              </a>
              <span className="text-sm text-gray-500">v0.1.0</span>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* 左側: 実行フォームとジョブ一覧 */}
          <div className="space-y-6">
            <CommandRunner onJobCreated={setSelectedJobId} />
            <JobList onSelectJob={setSelectedJobId} selectedJobId={selectedJobId} />
          </div>

          {/* 右側: ログビューア */}
          <div>
            <LogViewer jobId={selectedJobId} />
          </div>
        </div>
      </main>
    </div>
  );
}