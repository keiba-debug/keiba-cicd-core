import React from "react"
import type { Metadata } from 'next'

import './globals.css'
import { Header } from '@/components/header'

import { Noto_Sans_JP, JetBrains_Mono } from 'next/font/google'

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
  title: {
    template: '%s | 競馬CICD',
    default: '出馬表 | 競馬CICD',
  },
  description: '競馬データビューアー',
  generator: 'v0.app',
  icons: {
    icon: [
      {
        url: '/icon-light-32x32.svg',
        type: 'image/svg+xml',
        media: '(prefers-color-scheme: light)',
      },
      {
        url: '/icon-dark-32x32.svg',
        type: 'image/svg+xml',
        media: '(prefers-color-scheme: dark)',
      },
      {
        url: '/icon.svg',
        type: 'image/svg+xml',
      },
    ],
    apple: '/icon.svg',
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
          <Header />

          {/* Main */}
          <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            {children}
          </main>

          {/* Footer */}
          <footer className="border-t py-4 mt-auto">
            <div className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center text-sm text-muted-foreground">
              KeibaCICD — Value Bet で競馬をもっと面白く
            </div>
          </footer>
        </div>
      </body>
    </html>
  )
}
