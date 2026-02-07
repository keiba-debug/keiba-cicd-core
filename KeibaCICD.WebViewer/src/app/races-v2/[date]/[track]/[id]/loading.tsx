import { Skeleton } from '@/components/ui/skeleton';

export default function Loading() {
  return (
    <div className="container mx-auto px-4 py-6 max-w-7xl space-y-6">
      {/* レースヘッダー */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Skeleton className="h-5 w-16" />
          <Skeleton className="h-5 w-8" />
          <Skeleton className="h-5 w-16" />
        </div>
        <Skeleton className="h-8 w-64" />
        <div className="flex gap-2">
          <Skeleton className="h-5 w-20 rounded-full" />
          <Skeleton className="h-5 w-20 rounded-full" />
          <Skeleton className="h-5 w-20 rounded-full" />
        </div>
      </div>

      {/* 出走表テーブル */}
      <div className="rounded-lg border bg-card overflow-hidden">
        <div className="overflow-x-auto">
          <div className="min-w-[1200px]">
            {/* ヘッダー */}
            <div className="flex gap-2 px-4 py-2 bg-muted/30 border-b">
              {Array.from({ length: 10 }).map((_, i) => (
                <Skeleton key={i} className="h-4 w-12" />
              ))}
            </div>
            {/* 行 */}
            {Array.from({ length: 12 }).map((_, i) => (
              <div key={i} className="flex gap-2 px-4 py-3 border-b">
                <Skeleton className="h-5 w-6 rounded-full" />
                <Skeleton className="h-5 w-24" />
                <Skeleton className="h-5 w-16" />
                <Skeleton className="h-5 w-12" />
                <Skeleton className="h-5 w-32 flex-1" />
                <Skeleton className="h-5 w-16" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
