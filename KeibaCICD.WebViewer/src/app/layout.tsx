import React from "react"
import type { Metadata } from 'next'

import Link from 'next/link'
import './globals.css'

import { Noto_Sans_JP, JetBrains_Mono, Libre_Baskerville as V0_Font_Libre_Baskerville, IBM_Plex_Mono as V0_Font_IBM_Plex_Mono, Lora as V0_Font_Lora } from 'next/font/google'

// Initialize fonts
const _libreBaskerville = V0_Font_Libre_Baskerville({ subsets: ['latin'], weight: ["400","700"] })
const _ibmPlexMono = V0_Font_IBM_Plex_Mono({ subsets: ['latin'], weight: ["100","200","300","400","500","600","700"] })
const _lora = V0_Font_Lora({ subsets: ['latin'], weight: ["400","500","600","700"] })

const notoSansJP = Noto_Sans_JP({
  variable: '--font-noto-sans-jp',
  subsets: ['latin'],
  weight: ['400', '500', '700'],
});

const jetBrainsMono = JetBrains_Mono({
  variable: '--font-jetbrains-mono',
  subsets: ['latin'],
});

export const metadata: Metadata = {
  title: 'KEIBA Data Viewer',
  description: '競馬データビューアー',
  generator: 'v0.app',
  icons: {
    icon: [
      {
        url: '/icon-light-32x32.png',
        media: '(prefers-color-scheme: light)',
      },
      {
        url: '/icon-dark-32x32.png',
        media: '(prefers-color-scheme: dark)',
      },
      {
        url: '/icon.svg',
        type: 'image/svg+xml',
      },
    ],
    apple: '/apple-icon.png',
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="ja">
      <body className={`${notoSansJP.variable} ${jetBrainsMono.variable} font-sans antialiased bg-background text-foreground`}>
        <div className="min-h-screen flex flex-col">
          {/* Header */}
          <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <div className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex h-14 items-center gap-4">
              <Link href="/" className="flex items-center gap-2 font-bold text-lg">
                <span className="text-primary">K</span>
                <span>KEIBA CICD</span>
              </Link>
              <nav className="flex items-center gap-4 text-sm">
                <Link href="/" className="px-3 py-1.5 bg-primary text-primary-foreground rounded-md font-medium">
                  レース一覧
                </Link>
                <Link href="/horses" className="text-muted-foreground hover:text-foreground transition-colors">
                  馬検索
                </Link>
                <Link href="/multi-view" className="text-muted-foreground hover:text-foreground transition-colors">
                  ツール
                </Link>
                <Link href="/demo/course" className="text-muted-foreground hover:text-foreground transition-colors">
                  コースDemo
                </Link>
                <Link href="/admin" className="text-muted-foreground hover:text-foreground transition-colors">
                  データ登録
                </Link>
              </nav>
              <div className="ml-auto flex items-center gap-2 text-sm text-muted-foreground">
                <span className="w-2 h-2 rounded-full bg-green-500" />
                システム稼働中
              </div>
            </div>
          </header>

          {/* Main */}
          <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            {children}
          </main>

          {/* Footer */}
          <footer className="border-t py-4 mt-auto">
            <div className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center text-sm text-muted-foreground">
              KEIBA Data Viewer - ローカル競馬データ閲覧ツール
            </div>
          </footer>
        </div>
      </body>
    </html>
  )
}
