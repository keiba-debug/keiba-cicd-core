'use client';

import { useState } from 'react';
import Link from 'next/link';
import type { HorseEntry, CardRarity } from '@/types';

// 枠色の定義
const FRAME_COLORS: Record<number, { bg: string; text: string; gradient: string }> = {
  1: { bg: '#ffffff', text: '#000000', gradient: 'from-gray-100 to-white' },
  2: { bg: '#000000', text: '#ffffff', gradient: 'from-gray-900 to-gray-700' },
  3: { bg: '#ff0000', text: '#ffffff', gradient: 'from-red-600 to-red-400' },
  4: { bg: '#0066ff', text: '#ffffff', gradient: 'from-blue-600 to-blue-400' },
  5: { bg: '#ffff00', text: '#000000', gradient: 'from-yellow-400 to-yellow-200' },
  6: { bg: '#00aa00', text: '#ffffff', gradient: 'from-green-600 to-green-400' },
  7: { bg: '#ff6600', text: '#ffffff', gradient: 'from-orange-500 to-orange-300' },
  8: { bg: '#ff00ff', text: '#ffffff', gradient: 'from-pink-500 to-purple-400' },
};

// レアリティの色定義
const RARITY_STYLES: Record<CardRarity, { border: string; glow: string; badge: string }> = {
  SSR: { 
    border: 'border-yellow-400', 
    glow: 'shadow-[0_0_20px_rgba(234,179,8,0.5)]',
    badge: 'bg-gradient-to-r from-yellow-400 to-amber-500 text-black'
  },
  SR: { 
    border: 'border-purple-400', 
    glow: 'shadow-[0_0_15px_rgba(168,85,247,0.4)]',
    badge: 'bg-gradient-to-r from-purple-500 to-pink-500 text-white'
  },
  R: { 
    border: 'border-blue-400', 
    glow: 'shadow-[0_0_10px_rgba(59,130,246,0.3)]',
    badge: 'bg-gradient-to-r from-blue-500 to-cyan-500 text-white'
  },
  N: { 
    border: 'border-gray-300', 
    glow: '',
    badge: 'bg-gray-400 text-white'
  },
};

// 印のスタイル
const MARK_STYLES: Record<string, string> = {
  '◎': 'text-red-600 font-black text-2xl',
  '○': 'text-blue-600 font-bold text-xl',
  '▲': 'text-green-600 font-bold text-xl',
  '△': 'text-yellow-600 font-bold text-xl',
  '☆': 'text-purple-600 font-bold text-xl',
};

function getRarity(aiIndex?: number, rate?: number): CardRarity {
  const score = aiIndex || rate || 50;
  if (score >= 57) return 'SSR';
  if (score >= 54) return 'SR';
  if (score >= 51) return 'R';
  return 'N';
}

// スタッツバーコンポーネント
function StatBar({ label, value, maxValue = 100, color = 'blue' }: { 
  label: string; 
  value: number; 
  maxValue?: number;
  color?: string;
}) {
  const percentage = Math.min((value / maxValue) * 100, 100);
  const colorClass = {
    blue: 'bg-blue-500',
    green: 'bg-green-500',
    red: 'bg-red-500',
    yellow: 'bg-yellow-500',
    purple: 'bg-purple-500',
  }[color] || 'bg-blue-500';

  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-12 text-gray-500">{label}</span>
      <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
        <div 
          className={`h-full ${colorClass} transition-all duration-500`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <span className="w-8 text-right font-mono text-gray-700">{value}</span>
    </div>
  );
}

interface HorseCardProps {
  horse: HorseEntry;
  isFlipped?: boolean;
  onFlip?: () => void;
}

export function HorseCard({ horse, isFlipped = false, onFlip }: HorseCardProps) {
  const [flipped, setFlipped] = useState(isFlipped);
  const frameColor = FRAME_COLORS[horse.frame] || FRAME_COLORS[1];
  const rarity = getRarity(horse.aiIndex, horse.rate);
  const rarityStyle = RARITY_STYLES[rarity];

  const handleFlip = () => {
    setFlipped(!flipped);
    onFlip?.();
  };

  return (
    <div 
      className="perspective-1000 w-64 h-96 cursor-pointer group"
      onClick={handleFlip}
    >
      <div 
        className={`relative w-full h-full transition-transform duration-500 transform-style-3d ${
          flipped ? 'rotate-y-180' : ''
        }`}
      >
        {/* カード表面 */}
        <div className={`absolute inset-0 backface-hidden rounded-xl border-2 ${rarityStyle.border} ${rarityStyle.glow} overflow-hidden bg-white`}>
          {/* ヘッダー（枠色グラデーション） */}
          <div className={`h-16 bg-gradient-to-r ${frameColor.gradient} p-3 flex items-center justify-between`}>
            <div className="flex items-center gap-2">
              <span 
                className="w-8 h-8 rounded-full flex items-center justify-center font-bold text-lg"
                style={{ backgroundColor: frameColor.bg, color: frameColor.text }}
              >
                {horse.number}
              </span>
              <div>
                <div className="font-bold text-sm truncate max-w-32" style={{ color: frameColor.text === '#ffffff' ? '#333' : frameColor.text }}>
                  {horse.name}
                </div>
                <div className="text-xs text-gray-500">{horse.age}</div>
              </div>
            </div>
            {/* 印 */}
            {horse.mark && (
              <span className={MARK_STYLES[horse.mark] || 'text-gray-600'}>
                {horse.mark}
              </span>
            )}
          </div>

          {/* レアリティバッジ */}
          <div className="absolute top-2 right-2">
            <span className={`px-2 py-0.5 rounded text-xs font-bold ${rarityStyle.badge}`}>
              {rarity}
            </span>
          </div>

          {/* メインコンテンツ */}
          <div className="p-4 space-y-3">
            {/* AI指数 & レート */}
            <div className="flex justify-center gap-4">
              {horse.aiIndex && (
                <div className="text-center">
                  <div className="text-2xl font-bold text-blue-600">{horse.aiIndex.toFixed(1)}</div>
                  <div className="text-xs text-gray-500">AI指数</div>
                </div>
              )}
              {horse.rate && (
                <div className="text-center">
                  <div className="text-2xl font-bold text-green-600">{horse.rate.toFixed(1)}</div>
                  <div className="text-xs text-gray-500">レート</div>
                </div>
              )}
              {horse.odds && (
                <div className="text-center">
                  <div className="text-2xl font-bold text-orange-600">{horse.odds}</div>
                  <div className="text-xs text-gray-500">オッズ</div>
                </div>
              )}
            </div>

            {/* 能力値バー（仮データ or 実データ） */}
            <div className="space-y-1.5 pt-2 border-t">
              {horse.stats ? (
                <>
                  <StatBar label="スピード" value={horse.stats.speed} color="red" />
                  <StatBar label="スタミナ" value={horse.stats.stamina} color="green" />
                  <StatBar label="瞬発力" value={horse.stats.power} color="blue" />
                  <StatBar label="安定感" value={horse.stats.stability} color="yellow" />
                </>
              ) : (
                // 仮の能力値（AI指数ベースで生成）
                <>
                  <StatBar label="スピード" value={Math.min(100, (horse.aiIndex || 50) * 1.7)} color="red" />
                  <StatBar label="スタミナ" value={Math.min(100, (horse.rate || 50) * 1.6)} color="green" />
                  <StatBar label="瞬発力" value={Math.min(100, ((horse.aiIndex || 50) + (horse.rate || 50)) / 2 * 1.5)} color="blue" />
                </>
              )}
            </div>

            {/* 騎手 */}
            <div className="flex items-center justify-between pt-2 border-t text-sm">
              <span className="text-gray-500">🏇 騎手</span>
              <span className="font-medium">{horse.jockey}</span>
            </div>

            {/* 短評（1行） */}
            {horse.shortComment && (
              <div className="text-xs text-gray-600 line-clamp-1 italic">
                "{horse.shortComment}"
              </div>
            )}
          </div>

          {/* フッター */}
          <div className="absolute bottom-0 left-0 right-0 p-2 bg-gray-50 text-center text-xs text-gray-400">
            タップで詳細を見る 🔄
          </div>
        </div>

        {/* カード裏面（ダッシュボード） */}
        <div className={`absolute inset-0 backface-hidden rotate-y-180 rounded-xl border-2 ${rarityStyle.border} overflow-hidden bg-gradient-to-br from-gray-50 to-gray-100`}>
          {/* ヘッダー */}
          <div className="h-12 bg-gray-800 text-white p-2 flex items-center gap-2">
            <span 
              className="w-6 h-6 rounded-full flex items-center justify-center text-sm font-bold"
              style={{ backgroundColor: frameColor.bg, color: frameColor.text }}
            >
              {horse.number}
            </span>
            <span className="font-bold truncate">{horse.name}</span>
            {horse.mark && (
              <span className="ml-auto text-lg">{horse.mark}</span>
            )}
          </div>

          {/* 詳細コンテンツ */}
          <div className="p-3 space-y-3 text-sm">
            {/* 基本情報 */}
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="bg-white rounded p-2">
                <div className="text-gray-500">性齢</div>
                <div className="font-bold">{horse.age || '-'}</div>
              </div>
              <div className="bg-white rounded p-2">
                <div className="text-gray-500">斤量</div>
                <div className="font-bold">{horse.weight}kg</div>
              </div>
              <div className="bg-white rounded p-2">
                <div className="text-gray-500">騎手</div>
                <div className="font-bold truncate">{horse.jockey}</div>
              </div>
              <div className="bg-white rounded p-2">
                <div className="text-gray-500">調教</div>
                <div className="font-bold">{horse.training || '-'}</div>
              </div>
            </div>

            {/* 短評 */}
            {horse.shortComment && (
              <div className="bg-white rounded p-2">
                <div className="text-gray-500 text-xs mb-1">📝 短評</div>
                <div className="text-xs leading-relaxed">{horse.shortComment}</div>
              </div>
            )}

            {/* 調教コメント */}
            {horse.trainingComment && (
              <div className="bg-white rounded p-2">
                <div className="text-gray-500 text-xs mb-1">🏃 調教短評</div>
                <div className="text-xs leading-relaxed">{horse.trainingComment}</div>
              </div>
            )}

            {/* 過去成績グラフ（将来実装） */}
            {horse.recentResults && horse.recentResults.length > 0 && (
              <div className="bg-white rounded p-2">
                <div className="text-gray-500 text-xs mb-1">📊 過去5走</div>
                <div className="flex items-end justify-between h-12 gap-1">
                  {horse.recentResults.slice(0, 5).map((result, i) => (
                    <div key={i} className="flex-1 flex flex-col items-center">
                      <div 
                        className={`w-full rounded-t ${result.position <= 3 ? 'bg-blue-500' : 'bg-gray-300'}`}
                        style={{ height: `${Math.max(10, 100 - (result.position - 1) * 15)}%` }}
                      />
                      <span className="text-xs mt-0.5">{result.position}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 馬詳細リンク */}
            {horse.horseId && (
              <Link 
                href={`/horses/${horse.horseId}`}
                target="_blank"
                className="block text-center py-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition text-xs"
                onClick={(e) => e.stopPropagation()}
              >
                馬の詳細ページへ →
              </Link>
            )}
          </div>

          {/* フッター */}
          <div className="absolute bottom-0 left-0 right-0 p-2 bg-gray-200 text-center text-xs text-gray-500">
            タップで表に戻る 🔄
          </div>
        </div>
      </div>
    </div>
  );
}

// カード一覧表示用
export function HorseCardGrid({ horses }: { horses: HorseEntry[] }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 p-4">
      {horses.map((horse) => (
        <HorseCard key={horse.number} horse={horse} />
      ))}
    </div>
  );
}
