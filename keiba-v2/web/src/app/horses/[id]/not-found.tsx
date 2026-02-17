import Link from 'next/link';
import { Button } from '@/components/ui/button';

export default function HorseNotFound() {
  return (
    <div className="container py-12 text-center">
      <h1 className="text-4xl font-bold mb-4">🐴 馬が見つかりません</h1>
      <p className="text-muted-foreground mb-8">
        指定された馬IDのプロファイルは存在しないか、データがありません。
      </p>
      <div className="flex gap-4 justify-center">
        <Button asChild variant="outline">
          <Link href="/">レース一覧へ</Link>
        </Button>
        <Button asChild>
          <Link href="/horses">馬検索へ</Link>
        </Button>
      </div>
    </div>
  );
}
