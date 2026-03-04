'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Calendar, Brain, Wallet, MapPin, Search, ShieldCheck } from 'lucide-react';
import { RemainingBudget } from '@/components/bankroll/RemainingBudget';
import { useEffect, useRef } from 'react';

export function Header() {
  const pathname = usePathname();
  const raceMenuRef = useRef<HTMLDetailsElement | null>(null);
  const vbMenuRef = useRef<HTMLDetailsElement | null>(null);
  const analysisMenuRef = useRef<HTMLDetailsElement | null>(null);
  const searchMenuRef = useRef<HTMLDetailsElement | null>(null);
  const adminMenuRef = useRef<HTMLDetailsElement | null>(null);

  const allMenuRefs = [raceMenuRef, vbMenuRef, analysisMenuRef, searchMenuRef, adminMenuRef];

  const closeMenus = () => {
    for (const ref of allMenuRefs) {
      if (ref.current) ref.current.open = false;
    }
  };

  useEffect(() => {
    closeMenus();
  }, [pathname]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node | null;
      if (!target) return;
      for (const ref of allMenuRefs) {
        if (ref.current?.contains(target)) return;
      }
      closeMenus();
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeMenus();
    };

    document.addEventListener('click', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('click', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  const navItemsRight = [
    { href: '/bankroll', label: '収支', icon: Wallet },
  ];

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-gradient-to-b from-background/95 to-background/70 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center gap-3">
          {/* Brand */}
          <Link href="/" className="flex items-center gap-3">
            <img
              src="/keibacicd-mark.svg"
              alt="KeibaCICD"
              width={34}
              height={34}
              className="h-[34px] w-[34px] rounded-xl shadow-sm"
            />
            <div className="leading-tight">
              <div className="flex items-center gap-2">
                <span className="text-lg sm:text-xl font-bold tracking-tight">KeibaCICD</span>
                <span className="hidden sm:inline-flex text-[11px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-500/20">
                  競馬を楽しむ新聞
                </span>
              </div>
              <div className="hidden md:block text-xs text-muted-foreground">
                自分で集める、調べる、楽しむ
              </div>
            </div>
          </Link>

          {/* Nav */}
          <nav className="ml-2 flex items-center gap-1 rounded-full bg-muted/40 p-1 border">
            {/* レース ドロップダウン */}
            <details className="relative group" ref={raceMenuRef}>
              <summary className="list-none cursor-pointer text-muted-foreground hover:text-foreground flex items-center gap-2 px-3 py-2 text-sm font-semibold rounded-full transition-colors hover:bg-background/60">
                <Calendar className="h-4 w-4" />
                <span className="hidden sm:inline whitespace-nowrap">レース</span>
              </summary>
              <div className="absolute left-0 mt-2 w-56 rounded-xl border bg-background shadow-lg overflow-hidden">
                <Link
                  href="/"
                  onClick={() => { if (raceMenuRef.current) raceMenuRef.current.open = false; }}
                  className="block px-4 py-2.5 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                >
                  <span className="flex items-center gap-2">
                    <span>📋</span>
                    <span>
                      <span className="font-medium">出馬表</span>
                      <span className="block text-xs text-muted-foreground mt-0.5">当日の出走馬・レース情報</span>
                    </span>
                  </span>
                </Link>
                <Link
                  href="/odds-board"
                  onClick={() => { if (raceMenuRef.current) raceMenuRef.current.open = false; }}
                  className="block px-4 py-2.5 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                >
                  <span className="flex items-center gap-2">
                    <span>💰</span>
                    <span>
                      <span className="font-medium">オッズ</span>
                      <span className="block text-xs text-muted-foreground mt-0.5">リアルタイムオッズ一覧</span>
                    </span>
                  </span>
                </Link>
                <Link
                  href="/registration"
                  onClick={() => { if (raceMenuRef.current) raceMenuRef.current.open = false; }}
                  className="block px-4 py-2.5 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                >
                  <span className="flex items-center gap-2">
                    <span>📝</span>
                    <span>
                      <span className="font-medium">特別登録</span>
                      <span className="block text-xs text-muted-foreground mt-0.5">今週の登録馬・近走成績</span>
                    </span>
                  </span>
                </Link>
              </div>
            </details>

            {/* Value Bet ドロップダウン */}
            <details className="relative group" ref={vbMenuRef}>
              <summary className="list-none cursor-pointer text-muted-foreground hover:text-foreground flex items-center gap-2 px-3 py-2 text-sm font-semibold rounded-full transition-colors hover:bg-background/60">
                <Brain className="h-4 w-4" />
                <span className="hidden sm:inline whitespace-nowrap">Value Bet</span>
              </summary>
              <div className="absolute left-0 mt-2 w-56 rounded-xl border bg-background shadow-lg overflow-hidden">
                <Link
                  href="/predictions"
                  onClick={() => { if (vbMenuRef.current) vbMenuRef.current.open = false; }}
                  className="block px-4 py-2.5 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                >
                  <span className="flex items-center gap-2">
                    <span>🎯</span>
                    <span>
                      <span className="font-medium">Value Bet</span>
                      <span className="block text-xs text-muted-foreground mt-0.5">購入プラン・全レース予測</span>
                    </span>
                  </span>
                </Link>
                <Link
                  href="/analysis/ml"
                  onClick={() => { if (vbMenuRef.current) vbMenuRef.current.open = false; }}
                  className="block px-4 py-2.5 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                >
                  <span className="flex items-center gap-2">
                    <span>🤖</span>
                    <span>
                      <span className="font-medium">ML Report</span>
                      <span className="block text-xs text-muted-foreground mt-0.5">モデル精度・VB統計レポート</span>
                    </span>
                  </span>
                </Link>
                <Link
                  href="/analysis/simulation"
                  onClick={() => { if (vbMenuRef.current) vbMenuRef.current.open = false; }}
                  className="block px-4 py-2.5 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                >
                  <span className="flex items-center gap-2">
                    <span>📈</span>
                    <span>
                      <span className="font-medium">Simulation</span>
                      <span className="block text-xs text-muted-foreground mt-0.5">バンクロール・配分戦略比較</span>
                    </span>
                  </span>
                </Link>
                <Link
                  href="/win5"
                  onClick={() => { if (vbMenuRef.current) vbMenuRef.current.open = false; }}
                  className="block px-4 py-2.5 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                >
                  <span className="flex items-center gap-2">
                    <span>5</span>
                    <span>
                      <span className="font-medium">WIN5</span>
                      <span className="block text-xs text-muted-foreground mt-0.5">推奨馬・可変点数戦略</span>
                    </span>
                  </span>
                </Link>
              </div>
            </details>

            {/* 収支 */}
            {navItemsRight.map((item) => {
              const Icon = item.icon;
              const isActive = pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-2 px-3 py-2 text-sm font-semibold rounded-full transition-colors ${
                    isActive
                      ? 'bg-background text-foreground shadow-sm'
                      : 'text-muted-foreground hover:text-foreground hover:bg-background/60'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  <span className="hidden sm:inline">{item.label}</span>
                </Link>
              );
            })}

            {/* 分析 ドロップダウン */}
            <details className="relative group" ref={analysisMenuRef}>
              <summary className="list-none cursor-pointer text-muted-foreground hover:text-foreground flex items-center gap-2 px-3 py-2 text-sm font-semibold rounded-full transition-colors hover:bg-background/60">
                <MapPin className="h-4 w-4" />
                <span className="hidden sm:inline whitespace-nowrap">分析</span>
              </summary>
              <div className="absolute left-0 mt-2 w-64 rounded-xl border bg-background shadow-lg overflow-hidden">
                <Link
                  href="/analysis/rpci"
                  onClick={() => { if (analysisMenuRef.current) analysisMenuRef.current.open = false; }}
                  className="block px-4 py-2.5 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                >
                  <span className="flex items-center gap-2">
                    <span>📊</span>
                    <span>
                      <span className="font-medium">レースペース分析</span>
                      <span className="block text-xs text-muted-foreground mt-0.5">RPCI・33ラップ・傾向分類</span>
                    </span>
                  </span>
                </Link>
                <Link
                  href="/analysis/rating"
                  onClick={() => { if (analysisMenuRef.current) analysisMenuRef.current.open = false; }}
                  className="block px-4 py-2.5 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                >
                  <span className="flex items-center gap-2">
                    <span>📈</span>
                    <span>
                      <span className="font-medium">レイティング分析</span>
                      <span className="block text-xs text-muted-foreground mt-0.5">能力値の推移を可視化</span>
                    </span>
                  </span>
                </Link>
                <Link
                  href="/analysis/obstacle"
                  onClick={() => { if (analysisMenuRef.current) analysisMenuRef.current.open = false; }}
                  className="block px-4 py-2.5 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                >
                  <span className="flex items-center gap-2">
                    <span>🏇</span>
                    <span>
                      <span className="font-medium">障害レース分析</span>
                      <span className="block text-xs text-muted-foreground mt-0.5">障害戦の傾向を分析</span>
                    </span>
                  </span>
                </Link>
                <Link
                  href="/demo/course"
                  onClick={() => { if (analysisMenuRef.current) analysisMenuRef.current.open = false; }}
                  className="block px-4 py-2.5 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                >
                  <span className="flex items-center gap-2">
                    <span>🗺️</span>
                    <span>
                      <span className="font-medium">コースデータ</span>
                      <span className="block text-xs text-muted-foreground mt-0.5">競馬場・コース情報</span>
                    </span>
                  </span>
                </Link>
                <Link
                  href="/analysis/trainer-patterns"
                  onClick={() => { if (analysisMenuRef.current) analysisMenuRef.current.open = false; }}
                  className="block px-4 py-2.5 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                >
                  <span className="flex items-center gap-2">
                    <span>🔬</span>
                    <span>
                      <span className="font-medium">調教分析</span>
                      <span className="block text-xs text-muted-foreground mt-0.5">調教データの統合分析</span>
                    </span>
                  </span>
                </Link>
                <Link
                  href="/analysis/slow-start"
                  onClick={() => { if (analysisMenuRef.current) analysisMenuRef.current.open = false; }}
                  className="block px-4 py-2.5 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                >
                  <span className="flex items-center gap-2">
                    <span>🐢</span>
                    <span>
                      <span className="font-medium">出遅れ分析</span>
                      <span className="block text-xs text-muted-foreground mt-0.5">騎手・馬の出遅れ傾向</span>
                    </span>
                  </span>
                </Link>
                <Link
                  href="/analysis/pedigree"
                  onClick={() => { if (analysisMenuRef.current) analysisMenuRef.current.open = false; }}
                  className="block px-4 py-2.5 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                >
                  <span className="flex items-center gap-2">
                    <span>🧬</span>
                    <span>
                      <span className="font-medium">血統分析</span>
                      <span className="block text-xs text-muted-foreground mt-0.5">種牡馬・母父の成績傾向</span>
                    </span>
                  </span>
                </Link>
              </div>
            </details>

            {/* データ検索 ドロップダウン */}
            <details className="relative group" ref={searchMenuRef}>
              <summary className="list-none cursor-pointer text-muted-foreground hover:text-foreground flex items-center gap-2 px-3 py-2 text-sm font-semibold rounded-full transition-colors hover:bg-background/60">
                <Search className="h-4 w-4" />
                <span className="hidden sm:inline whitespace-nowrap">データ検索</span>
              </summary>
              <div className="absolute left-0 mt-2 w-56 rounded-xl border bg-background shadow-lg overflow-hidden">
                <Link
                  href="/multi-view"
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={() => { if (searchMenuRef.current) searchMenuRef.current.open = false; }}
                  className="block px-4 py-2.5 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                >
                  <span className="flex items-center gap-2">
                    <span>🏁</span>
                    <span>
                      <span className="font-medium">レーシングビュアー</span>
                      <span className="block text-xs text-muted-foreground mt-0.5">複数レースを同時表示</span>
                    </span>
                  </span>
                </Link>
                <Link
                  href="/races-search"
                  onClick={() => { if (searchMenuRef.current) searchMenuRef.current.open = false; }}
                  className="block px-4 py-2.5 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                >
                  <span className="flex items-center gap-2">
                    <span>📋</span>
                    <span>
                      <span className="font-medium">レース検索</span>
                      <span className="block text-xs text-muted-foreground mt-0.5">条件でレースを検索</span>
                    </span>
                  </span>
                </Link>
                <Link
                  href="/horses"
                  onClick={() => { if (searchMenuRef.current) searchMenuRef.current.open = false; }}
                  className="block px-4 py-2.5 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                >
                  <span className="flex items-center gap-2">
                    <span>🐴</span>
                    <span>
                      <span className="font-medium">馬検索</span>
                      <span className="block text-xs text-muted-foreground mt-0.5">馬名で検索・詳細表示</span>
                    </span>
                  </span>
                </Link>
              </div>
            </details>

            {/* 管理 ドロップダウン */}
            <details className="relative group" ref={adminMenuRef}>
              <summary className="list-none cursor-pointer text-muted-foreground hover:text-foreground flex items-center gap-2 px-3 py-2 text-sm font-semibold rounded-full transition-colors hover:bg-background/60">
                <ShieldCheck className="h-4 w-4" />
                <span className="hidden sm:inline whitespace-nowrap">管理</span>
              </summary>
              <div className="absolute right-0 mt-2 w-56 rounded-xl border bg-background shadow-lg overflow-hidden">
                <Link
                  href="/admin"
                  onClick={() => { if (adminMenuRef.current) adminMenuRef.current.open = false; }}
                  className="block px-4 py-2.5 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                >
                  <span className="flex items-center gap-2">
                    <span>⚙️</span>
                    <span>
                      <span className="font-medium">データ登録</span>
                      <span className="block text-xs text-muted-foreground mt-0.5">スクレイプ・構築・ML実行</span>
                    </span>
                  </span>
                </Link>
              </div>
            </details>
          </nav>

          {/* Status */}
          <div className="ml-auto hidden sm:flex items-center gap-4 text-sm text-muted-foreground">
            <RemainingBudget />
          </div>
        </div>
      </div>
    </header>
  );
}
