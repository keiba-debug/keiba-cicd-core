export default function IDMCompareLoading() {
  return (
    <div className="container max-w-7xl mx-auto px-4 py-6">
      <div className="h-6 w-32 bg-muted rounded animate-pulse mb-6" />
      <div className="h-8 w-64 bg-muted rounded animate-pulse mb-2" />
      <div className="h-4 w-48 bg-muted rounded animate-pulse mb-6" />

      {/* 凡例スケルトン */}
      <div className="flex flex-wrap gap-2 mb-4">
        {Array.from({ length: 12 }).map((_, i) => (
          <div key={i} className="h-6 w-24 bg-muted rounded animate-pulse" />
        ))}
      </div>

      {/* チャートスケルトン */}
      <div className="bg-white dark:bg-gray-900 rounded-lg border p-4 mb-4">
        <div className="h-[600px] bg-muted/30 rounded animate-pulse" />
      </div>

      {/* テーブルスケルトン */}
      <div className="bg-white dark:bg-gray-900 rounded-lg border">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="flex items-center gap-3 px-3 py-2 border-b">
            <div className="w-3 h-3 rounded-full bg-muted animate-pulse" />
            <div className="w-8 h-4 bg-muted rounded animate-pulse" />
            <div className="w-24 h-4 bg-muted rounded animate-pulse" />
            <div className="w-12 h-4 bg-muted rounded animate-pulse ml-auto" />
            <div className="w-12 h-4 bg-muted rounded animate-pulse" />
            <div className="w-12 h-4 bg-muted rounded animate-pulse" />
          </div>
        ))}
      </div>
    </div>
  );
}
