'use client';

import { useViewMode } from '@/lib/view-mode-context';
import { Button } from '@/components/ui/button';

export function ViewModeToggle() {
  const { viewMode, setViewMode } = useViewMode();

  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="text-muted-foreground">表示:</span>
      <Button
        variant={viewMode === 'card' ? 'default' : 'outline'}
        size="sm"
        onClick={() => setViewMode('card')}
        className="h-7 px-2"
      >
        📇 カード
      </Button>
      <Button
        variant={viewMode === 'newspaper' ? 'default' : 'outline'}
        size="sm"
        onClick={() => setViewMode('newspaper')}
        className="h-7 px-2"
      >
        📰 新聞風
      </Button>
    </div>
  );
}
