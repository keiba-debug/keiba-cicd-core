'use client';

import React, { useState, useEffect } from 'react';
import { AlertCircle, X } from 'lucide-react';
import { Card } from '@/components/ui/card';

interface Alert {
  type: 'warning' | 'error' | 'info';
  message: string;
  severity: 'low' | 'medium' | 'high';
}

export function AlertBar() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        const res = await fetch('/api/bankroll/alerts');
        if (res.ok) {
          const data = await res.json();
          setAlerts(data.alerts || []);
        }
      } catch (error) {
        console.error('アラート取得エラー:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchAlerts();
    const interval = setInterval(fetchAlerts, 60000); // 1分ごとに更新

    return () => clearInterval(interval);
  }, []);

  if (loading || alerts.length === 0) {
    return null;
  }

  const getAlertColor = (type: string, severity: string) => {
    if (type === 'error' || severity === 'high') {
      return 'border-red-500 bg-red-50 dark:bg-red-950/20';
    }
    if (type === 'warning' || severity === 'medium') {
      return 'border-yellow-500 bg-yellow-50 dark:bg-yellow-950/20';
    }
    return 'border-blue-500 bg-blue-50 dark:bg-blue-950/20';
  };

  const getTextColor = (type: string, severity: string) => {
    if (type === 'error' || severity === 'high') {
      return 'text-red-700 dark:text-red-400';
    }
    if (type === 'warning' || severity === 'medium') {
      return 'text-yellow-700 dark:text-yellow-400';
    }
    return 'text-blue-700 dark:text-blue-400';
  };

  return (
    <div className="space-y-2 mb-6">
      {alerts.map((alert, index) => (
        <Card
          key={index}
          className={`border-2 ${getAlertColor(alert.type, alert.severity)}`}
        >
          <div className="flex items-start gap-3 p-4">
            <AlertCircle
              className={`h-5 w-5 mt-0.5 flex-shrink-0 ${getTextColor(
                alert.type,
                alert.severity
              )}`}
            />
            <div className="flex-1">
              <p className={`font-medium ${getTextColor(alert.type, alert.severity)}`}>
                {alert.message}
              </p>
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}
