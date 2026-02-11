import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // IISデプロイ用のスタンドアロンビルド設定
  output: 'standalone',

  // 実験的機能による最適化
  experimental: {
    // 大きなパッケージのインポートを最適化（Tree Shaking強化）
    optimizePackageImports: [
      'lucide-react',
      'date-fns',
      '@radix-ui/react-tabs',
      '@radix-ui/react-select',
      '@radix-ui/react-popover',
      '@radix-ui/react-collapsible',
    ],
    // Router Cacheの保持時間（タブ切り替え時の不要な再描画を抑制）
    // 更新は各ページの更新ボタンで明示的に行う運用
    staleTimes: {
      dynamic: 180,  // 動的ページ: 3分保持
      static: 300,   // 静的ページ: 5分保持
    },
  },

  // コンパイラ最適化
  compiler: {
    // 本番環境でconsole.logを削除（パフォーマンス向上）
    removeConsole: process.env.NODE_ENV === 'production' 
      ? { exclude: ['error', 'warn'] } 
      : false,
  },

  // 画像最適化設定
  images: {
    // 画像フォーマットの優先順位
    formats: ['image/avif', 'image/webp'],
    // 外部画像ドメインの許可（競馬ブック等のfaviconがある場合）
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'p.keibabook.co.jp',
      },
    ],
  },

  // 開発時のログ設定
  logging: {
    fetches: {
      fullUrl: process.env.NODE_ENV === 'development',
    },
  },

  // サーバー外部パッケージ（Node.js専用パッケージを明示）
  serverExternalPackages: ['gray-matter', 'remark', 'remark-html', 'remark-gfm'],

  // ページ単位のランタイム設定
  // experimental.ppr: true, // Partial Pre-Rendering（Next.js 15+）

  // TypeScript設定
  typescript: {
    // ビルド時の型チェックをスキップ（CIで別途チェックする場合）
    // ignoreBuildErrors: true,
  },

  // Note: Next.js 16ではeslint設定はnext.config.tsから削除されました
  // ESLint設定は .eslintrc.json または package.json で行ってください
};

export default nextConfig;
