import Link from 'next/link';
import { notFound } from 'next/navigation';
import { getHorseProfileWithRaces } from '@/lib/data';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { HorseProfileMemoEditor } from '@/components/horse-profile-memo-editor';
import { HorseRaceSelector } from '@/components/horse-race-selector';

interface PageProps {
  params: Promise<{
    id: string;
  }>;
}

export default async function HorseProfilePage({ params }: PageProps) {
  const { id } = await params;
  const horse = await getHorseProfileWithRaces(id);

  if (!horse) {
    notFound();
  }

  return (
    <div className="container py-6">
      {/* パンくずリスト */}
      <nav className="flex items-center space-x-2 text-sm text-muted-foreground mb-4">
        <Link href="/" className="hover:underline">
          トップ
        </Link>
        <span>/</span>
        <Link href="/horses" className="hover:underline">
          馬検索
        </Link>
        <span>/</span>
        <span className="text-foreground">{horse.name}</span>
      </nav>

      {/* ヘッダー */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <span className="text-3xl">🐴</span>
          <h1 className="text-2xl font-bold">{horse.name}</h1>
          {horse.age && (
            <Badge variant="secondary" className="text-sm">
              {horse.age}
            </Badge>
          )}
        </div>
        <p className="text-sm text-muted-foreground">
          馬ID: {horse.id}
        </p>
      </div>

      <Separator className="my-6" />

      {/* 過去レース映像比較 */}
      {horse.pastRaces.length > 0 && (
        <HorseRaceSelector 
          horseId={id}
          horseName={horse.name} 
          pastRaces={horse.pastRaces} 
        />
      )}

      {/* ユーザーメモ編集 */}
      <HorseProfileMemoEditor horseId={id} horseName={horse.name} />

      {/* 馬プロファイル内容（Markdown変換済みHTML） */}
      <article
        className="prose prose-neutral dark:prose-invert max-w-none 
                   prose-headings:scroll-mt-20 
                   prose-table:w-full prose-table:text-sm
                   prose-th:bg-muted prose-th:text-left prose-th:p-2
                   prose-td:p-2 prose-td:border
                   prose-a:text-primary prose-a:no-underline hover:prose-a:underline"
        dangerouslySetInnerHTML={{ __html: horse.htmlContent }}
      />

      {/* 戻るボタン */}
      <div className="mt-8 flex gap-4">
        <Button variant="outline" asChild>
          <Link href="/">← レース一覧に戻る</Link>
        </Button>
        <Button variant="outline" asChild>
          <Link href="/horses">🔍 馬検索に戻る</Link>
        </Button>
      </div>
    </div>
  );
}
