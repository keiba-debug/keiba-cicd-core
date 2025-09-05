'use client';

import { useEffect, useState } from 'react';
import { Activity, AlertCircle, CheckCircle, Server } from 'lucide-react';

interface HealthData {
  status: string;
  timestamp: string;
  jobs: {
    total: number;
    running: number;
    completed: number;
    failed: number;
    error: number;
  };
  logs: {
    total_size_mb: number;
    retention_days: number;
  };
  system: {
    memory_usage_mb: number;
    cpu_percent: number;
  };
  environment: {
    data_dir_exists: boolean;
    project_dir_exists: boolean;
  };
}

export default function HealthStatus() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHealth = async () => {
    try {
      const response = await fetch('http://localhost:8000/health');
      if (!response.ok) throw new Error('Health check failed');
      const data = await response.json();
      setHealth(data);
      setError(null);
    } catch (err) {
      setError('API接続エラー');
      console.error('Health check error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 30000); // 30秒ごとに更新
    return () => clearInterval(interval);
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center space-x-2 text-sm text-gray-500">
        <Activity className="h-4 w-4 animate-pulse" />
        <span>確認中...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center space-x-2 text-sm text-red-600">
        <AlertCircle className="h-4 w-4" />
        <span>{error}</span>
      </div>
    );
  }

  if (!health) return null;

  const getStatusColor = () => {
    if (!health.environment.data_dir_exists || !health.environment.project_dir_exists) {
      return 'text-yellow-600';
    }
    if (health.jobs.failed > 5 || health.jobs.error > 3) {
      return 'text-orange-600';
    }
    return 'text-green-600';
  };

  const getStatusIcon = () => {
    if (!health.environment.data_dir_exists || !health.environment.project_dir_exists) {
      return <AlertCircle className="h-4 w-4" />;
    }
    return <CheckCircle className="h-4 w-4" />;
  };

  return (
    <div className="flex items-center space-x-4">
      <div className={`flex items-center space-x-2 text-sm ${getStatusColor()}`}>
        {getStatusIcon()}
        <span className="font-medium">
          {health.status === 'healthy' ? '正常' : '異常'}
        </span>
      </div>

      <div className="flex items-center space-x-3 text-xs text-gray-600">
        <div className="flex items-center space-x-1">
          <Server className="h-3 w-3" />
          <span>Jobs: {health.jobs.running}/{health.jobs.total}</span>
        </div>
        
        <div className="border-l pl-3">
          <span>Mem: {Math.round(health.system.memory_usage_mb)}MB</span>
        </div>
        
        <div className="border-l pl-3">
          <span>Logs: {health.logs.total_size_mb.toFixed(1)}MB</span>
        </div>

        {(health.jobs.failed > 0 || health.jobs.error > 0) && (
          <div className="border-l pl-3 text-red-600">
            <span>失敗: {health.jobs.failed + health.jobs.error}</span>
          </div>
        )}
      </div>
    </div>
  );
}