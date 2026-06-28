'use client';

/**
 * 展開予想コンポーネント（新方式）
 */

import React from 'react';
import { TenkaiData, HorseEntry, toCircleNumber } from '@/types/race-data';
import { Badge } from '@/components/ui/badge';
import { Flame, Timer, Turtle } from 'lucide-react';
import type { LegProfile } from '@/lib/data/leg-profile-reader';

interface TenkaiSectionProps {
  tenkaiData: TenkaiData | null;
  entries: HorseEntry[];
  /** Regulus 脚質・能力プロファイル（馬番→profile） */
  legProfiles?: Record<number, LegProfile>;
}

export default function TenkaiSection({ tenkaiData, entries, legProfiles }: TenkaiSectionProps) {
  if (!tenkaiData && !legProfiles) return null;

  const pace = tenkaiData?.pace || 'M';
  const description = tenkaiData?.description;
  // positions が欠けているデータがあるため安全にフォールバック
  const positions = (tenkaiData?.positions ?? {}) as TenkaiData['positions'];

  // 馬番から馬名を取得するマップ
  const horseNameMap = new Map<string, string>();
  entries.forEach(e => {
    horseNameMap.set(String(e.horse_number), e.horse_name);
  });

  return (
    <div className="border rounded-lg p-4">
      <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
        🏃 展開予想
      </h3>

      {tenkaiData && (
        <>
          {/* ペース予想 */}
          <div className="mb-4">
            <PaceBadge pace={pace} />
            <span className="ml-2 text-xs text-gray-400">競馬ブック展開</span>
          </div>

          {/* 展開ポジション表 */}
          <div className="grid grid-cols-4 gap-2 mb-4">
            <PositionCard label="逃げ" horseNumbers={positions.逃げ || []} horseNameMap={horseNameMap}
              color="bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800" />
            <PositionCard label="好位" horseNumbers={positions.好位 || []} horseNameMap={horseNameMap}
              color="bg-orange-50 dark:bg-orange-900/20 border-orange-200 dark:border-orange-800" />
            <PositionCard label="中位" horseNumbers={positions.中位 || []} horseNameMap={horseNameMap}
              color="bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800" />
            <PositionCard label="後方" horseNumbers={positions.後方 || []} horseNameMap={horseNameMap}
              color="bg-gray-50 dark:bg-gray-800/50 border-gray-200 dark:border-gray-700" />
          </div>

          {/* 展開解説 */}
          {description && (
            <div className="mt-4 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
              <div className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">💭 展開解説</div>
              <p className="text-sm text-gray-800 dark:text-gray-200">{description}</p>
            </div>
          )}

          {/* ビジュアル展開図 */}
          <TenkaiVisual positions={positions} horseNameMap={horseNameMap} />
        </>
      )}

      {/* ⭐ Regulus 脚質・能力プロファイル（データ駆動・上がり3軸=JRDB指数ベース） */}
      {legProfiles && <LegProfileLayer entries={entries} legProfiles={legProfiles} />}
    </div>
  );
}

interface PaceBadgeProps {
  pace: string;
}

function PaceBadge({ pace }: PaceBadgeProps) {
  const paceInfo: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
    'H': { 
      label: 'ハイペース', 
      icon: <Flame className="w-4 h-4" />, 
      color: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300' 
    },
    'M-H': { 
      label: 'ややハイ', 
      icon: <Flame className="w-4 h-4" />, 
      color: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300' 
    },
    'M': { 
      label: '平均ペース', 
      icon: <Timer className="w-4 h-4" />, 
      color: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300' 
    },
    'M-S': { 
      label: 'ややスロー', 
      icon: <Turtle className="w-4 h-4" />, 
      color: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300' 
    },
    'S': { 
      label: 'スローペース', 
      icon: <Turtle className="w-4 h-4" />, 
      color: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300' 
    },
  };

  const info = paceInfo[pace] || paceInfo['M'];

  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full ${info.color}`}>
      {info.icon}
      <span className="font-medium">{info.label}</span>
      <span className="text-xs opacity-70">({pace})</span>
    </div>
  );
}

interface PositionCardProps {
  label: string;
  horseNumbers: string[];
  horseNameMap: Map<string, string>;
  color: string;
}

function PositionCard({ label, horseNumbers, horseNameMap, color }: PositionCardProps) {
  return (
    <div className={`border rounded-lg p-3 ${color}`}>
      <div className="text-sm font-medium mb-2 text-center">{label}</div>
      <div className="flex flex-wrap justify-center gap-1">
        {horseNumbers.length > 0 ? (
          horseNumbers.map((num) => (
            <span 
              key={num}
              className="inline-flex items-center justify-center w-7 h-7 bg-white dark:bg-gray-900 rounded-full text-sm font-bold border"
              title={horseNameMap.get(num) || ''}
            >
              {toCircleNumber(parseInt(num, 10))}
            </span>
          ))
        ) : (
          <span className="text-xs text-gray-400">-</span>
        )}
      </div>
    </div>
  );
}

interface TenkaiVisualProps {
  positions?: TenkaiData['positions'] | null;
  horseNameMap: Map<string, string>;
}

function TenkaiVisual({ positions, horseNameMap }: TenkaiVisualProps) {
  const safePositions = (positions ?? {}) as TenkaiData['positions'];
  // 位置ごとの馬を取得
  const nige = safePositions.逃げ || [];
  const koi = safePositions.好位 || [];
  const chui = safePositions.中位 || [];
  const koho = safePositions.後方 || [];

  if (nige.length === 0 && koi.length === 0 && chui.length === 0 && koho.length === 0) {
    return null;
  }

  return (
    <div className="mt-4">
      <div className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">
        📊 予想隊列図
      </div>
      <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 font-mono text-sm">
        {/* ゴール方向 */}
        <div className="text-center text-xs text-gray-500 mb-2">
          ← ゴール
        </div>
        
        {/* 隊列 */}
        <div className="flex items-start gap-4 justify-center overflow-x-auto pb-2">
          {/* 逃げ */}
          {nige.length > 0 && (
            <div className="text-center">
              <div className="text-xs text-red-600 mb-1">逃げ</div>
              <div className="flex flex-col gap-1">
                {nige.map(num => (
                  <HorseMarker key={num} num={num} name={horseNameMap.get(num)} />
                ))}
              </div>
            </div>
          )}
          
          {/* 好位 */}
          {koi.length > 0 && (
            <div className="text-center">
              <div className="text-xs text-orange-600 mb-1">好位</div>
              <div className="flex flex-col gap-1">
                {koi.map(num => (
                  <HorseMarker key={num} num={num} name={horseNameMap.get(num)} />
                ))}
              </div>
            </div>
          )}
          
          {/* 中位 */}
          {chui.length > 0 && (
            <div className="text-center">
              <div className="text-xs text-blue-600 mb-1">中位</div>
              <div className="flex flex-col gap-1">
                {chui.map(num => (
                  <HorseMarker key={num} num={num} name={horseNameMap.get(num)} />
                ))}
              </div>
            </div>
          )}
          
          {/* 後方 */}
          {koho.length > 0 && (
            <div className="text-center">
              <div className="text-xs text-gray-600 mb-1">後方</div>
              <div className="flex flex-col gap-1">
                {koho.map(num => (
                  <HorseMarker key={num} num={num} name={horseNameMap.get(num)} />
                ))}
              </div>
            </div>
          )}
        </div>
        
        {/* スタート方向 */}
        <div className="text-center text-xs text-gray-500 mt-2">
          スタート →
        </div>
      </div>
    </div>
  );
}

function HorseMarker({ num, name }: { num: string; name?: string }) {
  const circleNum = toCircleNumber(parseInt(num, 10));

  return (
    <div
      className="inline-flex items-center gap-1 px-2 py-0.5 bg-white dark:bg-gray-900 rounded border text-xs"
      title={name}
    >
      <span className="font-bold">{circleNum}</span>
      {name && <span className="text-gray-600 dark:text-gray-400 truncate max-w-16">{name}</span>}
    </div>
  );
}

// ============================================================
// ⭐ Regulus 脚質・能力プロファイル レイヤー (上がり3軸=JRDB指数ベース・表示専用)
// ============================================================

/** 偏差値(平均50)の色分け — 高い=良い */
const hensColor = (v?: number | null): string =>
  v == null ? 'text-gray-400' :
  v >= 60 ? 'text-red-600 dark:text-red-400 font-bold' :
  v >= 55 ? 'text-orange-600 dark:text-orange-400 font-semibold' :
  v <= 42 ? 'text-gray-400' : 'text-gray-700 dark:text-gray-300';

/** 脚質バッジ色 */
const ksColor = (k: string): string =>
  k === '逃げ' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300' :
  k === '先行' ? 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300' :
  k === '差し' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300' :
  k === '追込' ? 'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300' :
  'bg-gray-100 text-gray-500';

interface LegRow { num: number; name: string; lp: LegProfile; }

function LegProfileLayer({ entries, legProfiles }: { entries: HorseEntry[]; legProfiles: Record<number, LegProfile> }) {
  const rows: LegRow[] = entries
    .map(e => ({ num: e.horse_number, name: e.horse_name, lp: legProfiles[e.horse_number] }))
    .filter((r): r is LegRow => !!r.lp);
  if (rows.length === 0) return null;

  // --- データ駆動ペース読み（先行密度 × テン力） ---
  const front = rows.filter(r => r.lp.kyakushitsu === '逃げ' || r.lp.kyakushitsu === '先行');
  const highTenFront = front.filter(r => (r.lp.ten ?? 0) >= 55);
  let paceLabel: string, paceDetail: string, paceColor: string;
  if (front.length >= 4 || highTenFront.length >= 3) {
    paceLabel = '速め想定';
    paceColor = 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300';
    paceDetail = `先行型${front.length}頭（テン偏差55+が${highTenFront.length}頭）→ ペース上がりやすく、差し・追込＆末脚上位に展開利`;
  } else if (front.length <= 1) {
    paceLabel = '緩み想定';
    paceColor = 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300';
    paceDetail = `先行型${front.length}頭 → スロー濃厚。逃げ・先行＆内枠が止まりにくい`;
  } else {
    paceLabel = '平均的';
    paceColor = 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300';
    paceDetail = `先行型${front.length}頭 → 大きな偏りなし。能力上位が素直に出やすい`;
  }

  // --- キー馬 ---
  const topBy = (sel: (lp: LegProfile) => number | null | undefined): LegRow =>
    [...rows].sort((a, b) => (sel(b.lp) ?? -1) - (sel(a.lp) ?? -1))[0];
  const hana = topBy(lp => lp.kyakushitsu === '逃げ' || lp.kyakushitsu === '先行' ? lp.ten : (lp.ten ?? 0) - 100) ;
  const kire = topBy(lp => lp.agari);
  const tough = topBy(lp => lp.sustain);

  // --- テーブル: テン力降順（前に行きそうな順≒隊列の前から） ---
  const sorted = [...rows].sort((a, b) => (b.lp.ten ?? -1) - (a.lp.ten ?? -1));

  return (
    <div className="mt-5 pt-4 border-t">
      <h4 className="text-base font-semibold mb-1 flex items-center gap-2">
        ⭐ 脚質・能力プロファイル
        <span className="text-[11px] font-normal text-gray-400">Regulus・上がり3軸（JRDB指数→偏差値50基準）</span>
      </h4>

      {/* データ駆動ペース読み */}
      <div className="mb-3 flex items-start gap-2 flex-wrap">
        <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-sm font-medium ${paceColor}`}>
          脚質構成読み: {paceLabel}
        </span>
        <span className="text-xs text-gray-600 dark:text-gray-400 flex-1 min-w-[200px] pt-1">{paceDetail}</span>
      </div>

      {/* キー馬カラム */}
      <div className="grid grid-cols-3 gap-2 mb-3">
        <KeyHorse label="🏇 想定ハナ" sub="テン力最上位" row={hana} metric={hana.lp.ten} />
        <KeyHorse label="⚡ 最強末脚" sub="上がり力最上位" row={kire} metric={kire.lp.agari} />
        <KeyHorse label="🛡 渋太い持続" sub="持続力最上位" row={tough} metric={tough.lp.sustain} />
      </div>

      {/* 脚質・能力テーブル（テン力降順） */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="bg-gray-50 dark:bg-gray-800/50 text-xs text-gray-500">
              <th className="px-2 py-1.5 text-left border-b">馬</th>
              <th className="px-2 py-1.5 text-center border-b w-12">脚質</th>
              <th className="px-2 py-1.5 text-center border-b w-14" title="前半スピード/先行力">テン</th>
              <th className="px-2 py-1.5 text-center border-b w-14" title="瞬発/末脚">上がり</th>
              <th className="px-2 py-1.5 text-center border-b w-14" title="後半の粘り/スタミナ">持続</th>
              <th className="px-2 py-1.5 text-left border-b">タイプ</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(r => (
              <tr key={r.num} className="border-b hover:bg-blue-50/40 dark:hover:bg-blue-900/10">
                <td className="px-2 py-1 whitespace-nowrap">
                  <span className="font-bold mr-1">{toCircleNumber(r.num)}</span>
                  <span className="text-xs">{r.name}</span>
                </td>
                <td className="px-2 py-1 text-center">
                  <span className={`inline-block px-1.5 py-0.5 rounded text-[11px] font-medium ${ksColor(r.lp.kyakushitsu)}`}>
                    {r.lp.kyakushitsu}
                  </span>
                </td>
                <td className={`px-2 py-1 text-center font-mono ${hensColor(r.lp.ten)}`}>{r.lp.ten ?? '–'}</td>
                <td className={`px-2 py-1 text-center font-mono ${hensColor(r.lp.agari)}`}>{r.lp.agari ?? '–'}</td>
                <td className={`px-2 py-1 text-center font-mono ${hensColor(r.lp.sustain)}`}>{r.lp.sustain ?? '–'}</td>
                <td className="px-2 py-1 text-[11px] text-violet-600 dark:text-violet-300">
                  {r.lp.tags.length > 0 ? r.lp.tags.join('・') : <span className="text-gray-300">—</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-[11px] text-gray-400 leading-relaxed">
        テン=前半スピード/先行力・上がり=瞬発/末脚・持続=後半の粘り（バテにくさ）。JRDB指数(ten_idx/agari_idx/前後半3F)を偏差値化（平均50・近5走）。
        脚質構成読みは「対象レースより前の走」から算出。表示専用で買い目には影響しません。
      </p>
    </div>
  );
}

function KeyHorse({ label, sub, row, metric }: { label: string; sub: string; row: LegRow; metric?: number | null }) {
  return (
    <div className="border rounded-lg p-2.5 bg-gray-50/60 dark:bg-gray-800/40">
      <div className="text-[11px] font-medium text-gray-500 dark:text-gray-400">{label}</div>
      <div className="text-sm font-bold mt-0.5 flex items-center gap-1 truncate">
        <span>{toCircleNumber(row.num)}</span>
        <span className="truncate">{row.name}</span>
      </div>
      <div className="text-[11px] text-gray-400 mt-0.5">
        {sub} <span className={`font-mono ${hensColor(metric)}`}>{metric ?? '–'}</span>
      </div>
    </div>
  );
}
