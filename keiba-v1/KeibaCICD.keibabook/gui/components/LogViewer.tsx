'use client';

import { useEffect, useState, useRef } from 'react';
import { Terminal, Download } from 'lucide-react';

interface LogViewerProps {
  jobId: string | null;
}

export default function LogViewer({ jobId }: LogViewerProps) {
  const [logs, setLogs] = useState<string[]>([]);
  const [status, setStatus] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const logContainerRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  useEffect(() => {
    if (!jobId) {
      setLogs([]);
      setStatus('');
      return;
    }

    const fetchLogs = async () => {
      setIsLoading(true);
      try {
        const response = await fetch(`http://localhost:8000/logs/${jobId}`);
        const data = await response.json();
        setLogs(data.logs || []);
        setStatus(data.status || '');
        
        // 自動スクロール
        if (autoScroll && logContainerRef.current) {
          logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
        }
      } catch (error) {
        console.error('Failed to fetch logs:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchLogs();
    
    // ポーリング（実行中の場合は頻繁に、完了後は停止）
    const interval = setInterval(() => {
      if (status !== 'completed' && status !== 'failed' && status !== 'error') {
        fetchLogs();
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [jobId, status, autoScroll]);

  const downloadLogs = async () => {
    if (!jobId) return;
    
    // APIからダウンロード
    try {
      const response = await fetch(`http://localhost:8000/logs/download/${jobId}`);
      if (!response.ok) throw new Error('Download failed');
      
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `job_${jobId}.log`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Failed to download logs:', error);
      // フォールバック: 現在表示中のログをダウンロード
      if (logs.length > 0) {
        const content = logs.join('');
        const blob = new Blob([content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `job-${jobId}-logs.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }
    }
  };

  if (!jobId) {
    return (
      <div className="bg-white rounded-lg shadow h-full min-h-[600px] flex items-center justify-center">
        <div className="text-center text-gray-500">
          <Terminal className="h-12 w-12 mx-auto mb-3 text-gray-400" />
          <p>ジョブを選択してください</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow h-full min-h-[600px] flex flex-col">
      <div className="px-6 py-4 border-b flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <Terminal className="h-5 w-5" />
          <h2 className="text-lg font-semibold">ログ出力</h2>
          {status && (
            <span className={`px-2 py-1 text-xs rounded-full ${
              status === 'running' ? 'bg-blue-100 text-blue-700' :
              status === 'completed' ? 'bg-green-100 text-green-700' :
              'bg-red-100 text-red-700'
            }`}>
              {status}
            </span>
          )}
        </div>
        <div className="flex items-center space-x-2">
          <label className="flex items-center text-sm">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              className="mr-1"
            />
            自動スクロール
          </label>
          <button
            onClick={downloadLogs}
            className="p-1 hover:bg-gray-100 rounded"
            title="ログをダウンロード"
          >
            <Download className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div 
        ref={logContainerRef}
        className="flex-1 p-4 overflow-auto bg-gray-900 text-gray-100 font-mono text-xs"
        style={{ minHeight: '500px' }}
      >
        {isLoading && logs.length === 0 ? (
          <div className="text-gray-500">ログを読み込み中...</div>
        ) : logs.length === 0 ? (
          <div className="text-gray-500">ログがありません</div>
        ) : (
          <pre className="whitespace-pre-wrap">
            {logs.map((line, index) => (
              <div key={index} className="hover:bg-gray-800">
                {line}
              </div>
            ))}
          </pre>
        )}
      </div>
    </div>
  );
}