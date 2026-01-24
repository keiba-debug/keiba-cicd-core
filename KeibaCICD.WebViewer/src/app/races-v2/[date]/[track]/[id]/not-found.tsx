import Link from 'next/link';

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-4xl font-bold mb-4">レースが見つかりません</h1>
        <p className="text-gray-600 dark:text-gray-400 mb-6">
          指定されたレースデータが存在しないか、まだ取得されていません。
        </p>
        <Link 
          href="/" 
          className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          レース一覧に戻る
        </Link>
      </div>
    </div>
  );
}
