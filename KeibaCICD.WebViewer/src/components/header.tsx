'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Calendar, Search, Wrench, ShieldCheck, MapPin } from 'lucide-react';

export function Header() {
  const pathname = usePathname();

  const navItems = [
    { href: '/', label: 'レース一覧', icon: Calendar },
    { href: '/horses', label: '馬検索', icon: Search },
    { href: '/multi-view', label: 'ツール', icon: Wrench },
    { href: '/demo/course', label: 'コースDemo', icon: MapPin },
    { href: '/admin', label: 'データ登録', icon: ShieldCheck },
  ];

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex h-16 items-center">
        <Link href="/" className="flex items-center gap-2 mr-8">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground font-bold text-lg">
            K
          </div>
          <span className="text-xl font-bold tracking-tight">KEIBA CICD</span>
        </Link>
        
        <nav className="flex items-center gap-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href));
            
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                  isActive 
                    ? 'bg-muted text-foreground' 
                    : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground'
                }`}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto flex items-center gap-2 text-sm text-muted-foreground">
          <span className="relative flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500"></span>
          </span>
          システム稼働中
        </div>
      </div>
    </header>
  );
}
