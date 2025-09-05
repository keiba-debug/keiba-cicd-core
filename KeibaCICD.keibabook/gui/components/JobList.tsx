'use client';

import { useEffect, useState } from 'react';
import { CheckCircle, XCircle, Clock, RefreshCw, RotateCcw } from 'lucide-react';

interface Job {
  id: string;
  command: string;
  status: string;
  created_at: string;
  retry_count?: number;
  original_job_id?: string;
}

interface JobListProps {
  onSelectJob: (jobId: string) => void;
  selectedJobId: string | null;
}

export default function JobList({ onSelectJob, selectedJobId }: JobListProps) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const fetchJobs = async () => {
    setIsLoading(true);
    try {
      const response = await fetch('http://localhost:8000/jobs');
      const data = await response.json();
      setJobs(data);
    } catch (error) {
      console.error('Failed to fetch jobs:', error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(fetchJobs, 5000); // 5秒ごとに更新
    return () => clearInterval(interval);
  }, []);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'failed':
      case 'error':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'running':
        return <Clock className="h-4 w-4 text-blue-500 animate-pulse" />;
      default:
        return <Clock className="h-4 w-4 text-gray-400" />;
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString('ja-JP', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const handleRetry = async (e: React.MouseEvent, jobId: string) => {
    e.stopPropagation(); // ジョブ選択を防ぐ
    try {
      const response = await fetch(`http://localhost:8000/retry/${jobId}`, {
        method: 'POST'
      });
      if (response.ok) {
        const newJob = await response.json();
        // 新しいジョブを選択
        onSelectJob(newJob.job_id);
        // ジョブリストを更新
        fetchJobs();
      }
    } catch (error) {
      console.error('Failed to retry job:', error);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="px-6 py-4 border-b flex items-center justify-between">
        <h2 className="text-lg font-semibold">ジョブ履歴</h2>
        <button
          onClick={fetchJobs}
          disabled={isLoading}
          className="p-1 hover:bg-gray-100 rounded"
        >
          <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      <div className="divide-y">
        {jobs.length === 0 ? (
          <div className="px-6 py-8 text-center text-gray-500">
            ジョブがありません
          </div>
        ) : (
          jobs.map(job => (
            <div
              key={job.id}
              onClick={() => onSelectJob(job.id)}
              className={`px-6 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors cursor-pointer ${
                selectedJobId === job.id ? 'bg-blue-50' : ''
              }`}
            >
              <div className="flex items-center space-x-3">
                {getStatusIcon(job.status)}
                <div className="text-left">
                  <div className="font-medium text-sm">
                    {job.command}
                    {job.retry_count !== undefined && job.retry_count > 0 && (
                      <span className="ml-2 text-xs text-orange-600">
                        (リトライ {job.retry_count}回)
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-gray-500">
                    {formatDate(job.created_at)}
                    {job.original_job_id && (
                      <span className="ml-2 text-gray-400">
                        (再試行)
                      </span>
                    )}
                  </div>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                {(job.status === 'failed' || job.status === 'error') && (
                  <button
                    onClick={(e) => handleRetry(e, job.id)}
                    className="p-1.5 bg-red-100 hover:bg-red-200 rounded-md transition-colors"
                    title="ジョブを再試行"
                  >
                    <RotateCcw className="h-3.5 w-3.5 text-red-600" />
                  </button>
                )}
                <div className="text-xs text-gray-500">
                  {job.id.slice(0, 8)}...
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}