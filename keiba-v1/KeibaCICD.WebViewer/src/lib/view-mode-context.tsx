'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import type { ViewMode } from '@/types';

interface ViewModeContextType {
  viewMode: ViewMode;
  setViewMode: (mode: ViewMode) => void;
}

const ViewModeContext = createContext<ViewModeContextType | undefined>(undefined);

export function ViewModeProvider({ children }: { children: ReactNode }) {
  // デフォルトを新聞風に設定
  const [viewMode, setViewMode] = useState<ViewMode>('newspaper');

  // LocalStorageから読み込み（互換性のため残すが、新聞風を優先）
  useEffect(() => {
    // 常に新聞風モードを使用
    setViewMode('newspaper');
    localStorage.setItem('viewMode', 'newspaper');
  }, []);

  // viewModeが変更されたらbodyにクラスを適用
  useEffect(() => {
    if (viewMode === 'newspaper') {
      document.body.classList.remove('card-mode');
      document.body.classList.add('newspaper-mode');
    } else {
      document.body.classList.remove('newspaper-mode');
      document.body.classList.add('card-mode');
    }
  }, [viewMode]);

  // LocalStorageに保存
  const handleSetViewMode = (mode: ViewMode) => {
    setViewMode(mode);
    localStorage.setItem('viewMode', mode);
  };

  return (
    <ViewModeContext.Provider value={{ viewMode, setViewMode: handleSetViewMode }}>
      {children}
    </ViewModeContext.Provider>
  );
}

export function useViewMode() {
  const context = useContext(ViewModeContext);
  if (!context) {
    throw new Error('useViewMode must be used within ViewModeProvider');
  }
  return context;
}
