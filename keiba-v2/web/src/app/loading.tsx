import { Skeleton } from '@/components/ui/skeleton';

export default function Loading() {
  return (
    <div className="container mx-auto px-4 py-6 max-w-7xl space-y-6">
      {/* 日付タブ */}
      <div className="flex gap-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-9 w-24" />
        ))}
      </div>

      {/* 日付ヘッダー */}
      <div className="flex items-center gap-2">
        <Skeleton className="h-7 w-40" />
        <Skeleton className="h-5 w-16 rounded-full" />
      </div>

      {/* 競馬場カード */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="rounded-lg border bg-card shadow-sm overflow-hidden">
            <div className="py-3 px-4 border-b bg-muted/10">
              <div className="flex items-center justify-between">
                <Skeleton className="h-6 w-24" />
                <Skeleton className="h-5 w-12" />
              </div>
            </div>
            <div className="divide-y">
              {Array.from({ length: 6 }).map((_, j) => (
                <div key={j} className="px-4 py-3 flex items-center gap-3">
                  <Skeleton className="h-4 w-12" />
                  <Skeleton className="h-4 w-48 flex-1" />
                  <Skeleton className="h-4 w-16" />
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
