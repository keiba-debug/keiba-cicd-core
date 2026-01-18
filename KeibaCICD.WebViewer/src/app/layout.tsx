import type { Metadata } from 'next';
import { Noto_Sans_JP, JetBrains_Mono } from 'next/font/google';
import './globals.css';
import { Providers } from '@/components/providers';
import { Header } from '@/components/header';

const notoSansJP = Noto_Sans_JP({
  variable: '--font-sans',
  subsets: ['latin'],
  weight: ['400', '500', '700'],
});

const jetBrainsMono = JetBrains_Mono({
  variable: '--font-mono',
  subsets: ['latin'],
});

export const metadata: Metadata = {
  title: 'KEIBA Data Viewer',
  description: '競馬データビューアー',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ja">
      <body className={`${notoSansJP.variable} ${jetBrainsMono.variable} font-sans antialiased bg-background text-foreground`}>
        <Providers>
          <div className="min-h-screen flex flex-col">
            <Header />

            {/* Main */}
            <main className="flex-1">{children}</main>

            {/* Footer */}
            <footer className="border-t py-4">
              <div className="container text-center text-sm text-muted-foreground">
                KEIBA Data Viewer - ローカル競馬データ閲覧ツール
              </div>
            </footer>
          </div>
        </Providers>
      </body>
    </html>
  );
}
