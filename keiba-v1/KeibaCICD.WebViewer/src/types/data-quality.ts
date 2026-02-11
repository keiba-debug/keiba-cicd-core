/**
 * データ品質基盤 - 型定義
 *
 * Phase 1a で使用する全ての型定義
 */

// ============================================
// API 1: データ状況 (GET /api/data/status)
// ============================================

export interface DataStatusParams {
  date?: string; // YYYY-MM-DD (単一日付)
  startDate?: string; // YYYY-MM-DD (範囲開始)
  endDate?: string; // YYYY-MM-DD (範囲終了)
}

export interface DataStatusResponse {
  success: true;
  query: {
    type: 'single' | 'range';
    date?: string;
    startDate?: string;
    endDate?: string;
  };
  summary: {
    totalDates: number;
    datesWithData: number;
    datesWithoutData: number;
    coveragePercent: number;
  };
  dates: DateStatus[];
  diskUsage: {
    totalSizeMB: number;
    fileCount: number;
  };
}

export interface DateStatus {
  date: string;
  displayDate: string;
  hasData: boolean;
  tracks: TrackStatus[];
  files: {
    raceInfo: boolean; // race_info.json
    tempNittei: boolean; // temp/nittei_*.json
    navigationIndex: boolean; // temp/navigation_index.json
  };
}

export interface TrackStatus {
  track: string;
  raceCount: number;
  hasRaceInfo: boolean;
  hasMdFiles: boolean;
}

// ============================================
// API 2: データ検証 (GET /api/data/validation)
// ============================================

export interface ValidationParams {
  date?: string;
  startDate?: string;
  endDate?: string;
  deep?: boolean; // 詳細検証モード
}

export interface ValidationResponse {
  success: true;
  query: {
    type: 'single' | 'range';
    date?: string;
    startDate?: string;
    endDate?: string;
    deep: boolean;
  };
  validation: {
    overallStatus: 'healthy' | 'warning' | 'error';
    totalIssues: number;
    criticalIssues: number;
    warnings: number;
  };
  dates: DateValidation[];
}

export interface DateValidation {
  date: string;
  status: 'healthy' | 'warning' | 'error';
  issues: ValidationIssue[];
  checks: {
    raceInfoExists: boolean;
    raceInfoValid: boolean;
    trackDirectories: boolean;
    mdFilesPresent: boolean;
    cacheUpToDate: boolean;
  };
}

export interface ValidationIssue {
  level: 'critical' | 'warning' | 'info';
  type: 'missing_file' | 'incomplete_data' | 'invalid_format' | 'stale_cache';
  message: string;
  details?: string;
}

// ============================================
// API 3: ヘルスチェック (GET /api/health)
// ============================================

export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  checks: {
    directories: DirectoryHealthCheck;
    diskSpace: DiskSpaceHealthCheck;
    indexHealth: IndexHealthCheck;
    memory: MemoryHealthCheck;
  };
  warnings: string[];
  errors: string[];
}

export interface DirectoryHealthCheck {
  status: 'ok' | 'error';
  details: {
    keibaDataRoot: {
      path: string;
      exists: boolean;
      writable: boolean;
    };
    jvDataRoot: {
      path: string;
      exists: boolean;
      accessible: boolean;
    };
    racesDir: {
      path: string;
      exists: boolean;
      dateCount: number;
    };
    cacheDir: {
      path: string;
      exists: boolean;
      sizeMB: number;
    };
  };
}

export interface DiskSpaceHealthCheck {
  status: 'ok' | 'warning' | 'critical';
  details: {
    racesDataSizeMB: number;
    cacheSizeMB: number;
    totalSizeMB: number;
  };
}

export interface IndexHealthCheck {
  status: 'ok' | 'stale' | 'missing';
  details: {
    exists: boolean;
    dateCount: number;
    raceCount: number;
    builtAt: string;
    ageHours: number;
  };
}

export interface MemoryHealthCheck {
  status: 'ok' | 'warning';
  details: {
    usedMB: number;
    heapUsedMB: number;
    heapTotalMB: number;
  };
}

// ============================================
// 共通エラーレスポンス
// ============================================

export interface ErrorResponse {
  error: string;
  details?: string;
}
