'use client';

import Link from 'next/link';
import { ViewModeToggle } from './view-mode-toggle';

export function Header() {
  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-14 items-center">
        <Link href="/" className="flex items-center space-x-2">
          <span className="text-xl font-bold">🏇 KEIBA Data Viewer</span>
        </Link>
        
        <nav className="ml-8 flex items-center space-x-4">
          <Link href="/" className="text-sm font-medium hover:underline">
            レース一覧
          </Link>
          <Link href="/horses" className="text-sm font-medium hover:underline">
            馬検索
          </Link>
          <span className="text-gray-300">|</span>
          <Link href="/admin" className="text-sm font-medium text-orange-600 hover:underline">
            📊 管理
          </Link>
          <span className="text-gray-300">|</span>
          <Link href="/multi-view" className="text-sm font-medium text-purple-600 hover:underline">
            📺 マルチビュー
          </Link>
          <Link href="/demo/cards" className="text-sm font-medium text-blue-600 hover:underline">
            🃏 カードDemo
          </Link>
          <Link href="/demo/course" className="text-sm font-medium text-green-600 hover:underline">
            🏟️ コースDemo
          </Link>
        </nav>

        <div className="ml-auto">
          <ViewModeToggle />
        </div>
      </div>
    </header>
  );
}
