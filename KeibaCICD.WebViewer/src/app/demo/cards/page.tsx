import { HorseCard, HorseCardGrid } from '@/components/horse-card';
import type { HorseEntry } from '@/types';

// デモ用のサンプルデータ
const sampleHorses: HorseEntry[] = [
  {
    number: 1,
    frame: 1,
    name: 'ブラックハヤテ',
    horseId: '0123456',
    jockey: '丹内祐',
    weight: 57,
    age: '牡3',
    odds: 36.6,
    aiIndex: 177.0,
    rate: 55.3,
    mark: '○',
    shortComment: '経験積んだが、まだ時間必要',
    trainingComment: '攻め意欲的も',
    training: '→',
  },
  {
    number: 2,
    frame: 2,
    name: 'ポッドクロス',
    horseId: '0123457',
    jockey: '大久保友',
    weight: 57,
    age: '牡3',
    odds: 55.9,
    aiIndex: 162.8,
    rate: 55.4,
    mark: '△',
    shortComment: '前走倦れずに',
    trainingComment: 'やや頭が高く',
    training: '→',
  },
  {
    number: 3,
    frame: 2,
    name: 'ステラスペース',
    horseId: '0123458',
    jockey: '武藤雅',
    weight: 57,
    age: '牡3',
    odds: 57.9,
    aiIndex: 187.0,
    rate: 56.9,
    mark: '◎',
    shortComment: 'ハナ切れぬと',
    trainingComment: '動き軽快',
    training: '→',
    stats: {
      speed: 85,
      stamina: 72,
      power: 78,
      stability: 65,
      growth: 80,
    },
    recentResults: [
      { date: '2025-12-28', track: '中山', distance: '2000m', position: 2, margin: '0.3' },
      { date: '2025-11-24', track: '東京', distance: '2000m', position: 1, margin: '' },
      { date: '2025-10-14', track: '東京', distance: '1800m', position: 3, margin: '0.5' },
      { date: '2025-09-15', track: '中山', distance: '1800m', position: 1, margin: '' },
      { date: '2025-08-03', track: '新潟', distance: '1800m', position: 2, margin: '0.1' },
    ],
  },
  {
    number: 4,
    frame: 3,
    name: 'グリーンエナジー',
    horseId: '0123459',
    jockey: '戸崎圭',
    weight: 57,
    age: '牡3',
    odds: 5.7,
    aiIndex: 279.3,
    rate: 55.0,
    mark: '▲',
    shortComment: '快勝中山でも',
    trainingComment: 'フットワーク軽快',
    training: '→',
    stats: {
      speed: 75,
      stamina: 80,
      power: 82,
      stability: 70,
      growth: 75,
    },
  },
  {
    number: 5,
    frame: 3,
    name: 'ショウグンマサムネ',
    horseId: '0123460',
    jockey: '荻野極',
    weight: 57,
    age: '牡3',
    odds: 26.8,
    aiIndex: 204.6,
    rate: 56.0,
    mark: '△',
    shortComment: '経験積む場に',
    trainingComment: '一息入るも好気配',
    training: '→',
  },
  {
    number: 6,
    frame: 4,
    name: 'アッカン',
    horseId: '0123461',
    jockey: '池添謙',
    weight: 57,
    age: '牡3',
    odds: 8.8,
    aiIndex: 238.2,
    rate: 58.3,
    mark: '☆',
    shortComment: '強敵を下して',
    trainingComment: '久々も好仕上がり',
    training: '↗',
    stats: {
      speed: 88,
      stamina: 75,
      power: 90,
      stability: 68,
      growth: 85,
    },
    recentResults: [
      { date: '2025-12-15', track: '阪神', distance: '2000m', position: 1, margin: '' },
      { date: '2025-10-27', track: '京都', distance: '2000m', position: 2, margin: '0.2' },
      { date: '2025-09-21', track: '中山', distance: '1800m', position: 1, margin: '' },
    ],
  },
  {
    number: 7,
    frame: 5,
    name: 'ゴールデンスター',
    horseId: '0123462',
    jockey: 'ルメール',
    weight: 57,
    age: '牡3',
    odds: 2.1,
    aiIndex: 320.5,
    rate: 59.8,
    mark: '◎',
    shortComment: '圧倒的な末脚',
    trainingComment: '絶好調をキープ',
    training: '↗↗',
    stats: {
      speed: 95,
      stamina: 88,
      power: 92,
      stability: 85,
      growth: 90,
    },
    recentResults: [
      { date: '2025-12-22', track: '中山', distance: '2000m', position: 1, margin: '' },
      { date: '2025-11-10', track: '東京', distance: '2400m', position: 1, margin: '' },
      { date: '2025-10-06', track: '京都', distance: '2000m', position: 1, margin: '' },
      { date: '2025-09-01', track: '新潟', distance: '2000m', position: 1, margin: '' },
      { date: '2025-07-20', track: '函館', distance: '1800m', position: 2, margin: '0.1' },
    ],
  },
  {
    number: 8,
    frame: 6,
    name: 'シルバームーン',
    horseId: '0123463',
    jockey: '川田将',
    weight: 55,
    age: '牝3',
    odds: 12.5,
    aiIndex: 195.0,
    rate: 54.5,
    mark: '○',
    shortComment: '牝馬の勢い',
    trainingComment: '軽快な動き',
    training: '→',
  },
];

export default function CardDemoPage() {
  return (
    <div className="container py-6">
      <h1 className="text-3xl font-bold mb-2">🃏 トレーディングカード風デモ</h1>
      <p className="text-muted-foreground mb-6">
        カードをクリックすると裏面（詳細情報）が表示されます。
        レアリティはAI指数に基づいて自動判定されます。
      </p>

      {/* レアリティ説明 */}
      <div className="flex flex-wrap gap-4 mb-8 p-4 bg-muted/30 rounded-lg">
        <div className="flex items-center gap-2">
          <span className="px-2 py-0.5 rounded text-xs font-bold bg-gradient-to-r from-yellow-400 to-amber-500 text-black">SSR</span>
          <span className="text-sm">AI指数 57以上</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="px-2 py-0.5 rounded text-xs font-bold bg-gradient-to-r from-purple-500 to-pink-500 text-white">SR</span>
          <span className="text-sm">AI指数 54以上</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="px-2 py-0.5 rounded text-xs font-bold bg-gradient-to-r from-blue-500 to-cyan-500 text-white">R</span>
          <span className="text-sm">AI指数 51以上</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="px-2 py-0.5 rounded text-xs font-bold bg-gray-400 text-white">N</span>
          <span className="text-sm">AI指数 51未満</span>
        </div>
      </div>

      {/* カードグリッド */}
      <HorseCardGrid horses={sampleHorses} />

      {/* 将来のデータ拡張について */}
      <div className="mt-12 p-6 bg-blue-50 rounded-lg border border-blue-200">
        <h2 className="text-xl font-bold mb-4 text-blue-800">📊 将来のデータ拡張予定</h2>
        <div className="grid md:grid-cols-2 gap-4 text-sm">
          <div>
            <h3 className="font-bold text-blue-700 mb-2">✅ 現在利用可能</h3>
            <ul className="list-disc list-inside text-gray-700 space-y-1">
              <li>馬名、馬番、枠番</li>
              <li>騎手、斤量、性齢</li>
              <li>オッズ、AI指数、レート</li>
              <li>本誌印、短評、調教短評</li>
            </ul>
          </div>
          <div>
            <h3 className="font-bold text-blue-700 mb-2">🔮 将来追加予定</h3>
            <ul className="list-disc list-inside text-gray-700 space-y-1">
              <li>能力値（スピード、スタミナ、瞬発力）</li>
              <li>過去成績グラフ</li>
              <li>血統情報</li>
              <li>馬場適性</li>
              <li>勝率・連対率</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
