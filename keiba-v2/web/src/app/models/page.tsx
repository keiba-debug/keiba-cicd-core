'use client';

import { useState } from 'react';
import useSWR from 'swr';
import Link from 'next/link';
import {
  Star, Mountain, Sun, Waves, CloudLightning, Sparkles,
  ChevronDown, ChevronRight, ArrowLeft, Zap, Eye, Telescope,
} from 'lucide-react';

// ============================================================
// Types
// ============================================================
interface ModelVersion {
  version: string;
  dir?: string | null;
  description?: string;
  p_auc?: number;
  w_auc?: number;
  features?: number;
}

interface ModelEntry {
  name: string;
  category: string;
  description: string;
  icon: string;
  active_version: string;
  model_dir?: string;
  versions: ModelVersion[];
}

interface Registry {
  schema_version?: number;
  models: Record<string, ModelEntry>;
  categories: Record<string, { label: string; description: string }>;
}

// ============================================================
// Constants
// ============================================================
const fetcher = (url: string) => fetch(url).then(r => r.json());

const ICON_MAP: Record<string, React.ReactNode> = {
  star: <Star className="w-5 h-5" />,
  mountain: <Mountain className="w-5 h-5" />,
  sun: <Sun className="w-5 h-5" />,
  waves: <Waves className="w-5 h-5" />,
  lightning: <CloudLightning className="w-5 h-5" />,
  sparkles: <Sparkles className="w-5 h-5" />,
  zap: <Zap className="w-5 h-5" />,
  eye: <Eye className="w-5 h-5" />,
  telescope: <Telescope className="w-5 h-5" />,
};

const CATEGORY_STYLES: Record<string, { bg: string; border: string; icon: string; dot: string }> = {
  stars: {
    bg: 'bg-indigo-50 dark:bg-indigo-950/30',
    border: 'border-indigo-200 dark:border-indigo-800',
    icon: 'text-indigo-600 dark:text-indigo-400',
    dot: 'bg-indigo-500',
  },
  nebula: {
    bg: 'bg-amber-50 dark:bg-amber-950/30',
    border: 'border-amber-200 dark:border-amber-800',
    icon: 'text-amber-600 dark:text-amber-400',
    dot: 'bg-amber-500',
  },
};

const STATUS_BADGE: Record<string, { label: string; style: string }> = {
  active: { label: 'Active', style: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300' },
  planned: { label: 'Planned', style: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300' },
  concept: { label: 'Concept', style: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400' },
};

// 将来モデル候補（model_registry.jsonに未登録のもの）
const FUTURE_MODELS = [
  {
    id: 'sirius', name: 'Sirius', category: 'stars', icon: 'sparkles',
    role: '激走馬抽出', status: 'planned',
    description: '人気薄で好走する馬を特定。ARd偏差値×市場乖離で「見つかっていない実力馬」を検出。',
  },
  {
    id: 'vega', name: 'Vega', category: 'stars', icon: 'telescope',
    role: '血統特化', status: 'concept',
    description: '血統データに特化した評価モデル。ダム系統×コース適性で血統バイアスを定量化。',
  },
  {
    id: 'nova', name: 'Nova', category: 'stars', icon: 'zap',
    role: '残差モデル（市場過小評価）', status: 'concept',
    description: 'Polarisの残差を学習し、モデルと市場が共に見落とすパターンを捕捉。',
  },
  {
    id: 'tide', name: 'Tide', category: 'nebula', icon: 'waves',
    role: 'ペース予測', status: 'concept',
    description: 'レースのペース展開を事前予測。逃げ先行有利/差し追込有利を定量判定。',
  },
  {
    id: 'corona', name: 'Corona', category: 'nebula', icon: 'sun',
    role: '馬場・環境予測', status: 'concept',
    description: 'クッション値・天候・含水率からトラックコンディションの影響を予測。',
  },
  {
    id: 'aurora', name: 'Aurora', category: 'nebula', icon: 'lightning',
    role: '荒れ度予測', status: 'concept',
    description: 'レースの荒れやすさを予測。人気馬の信頼度と波乱確率の事前推定。',
  },
];

// ============================================================
// Components
// ============================================================

function StatusBadge({ status }: { status: string }) {
  const badge = STATUS_BADGE[status] || STATUS_BADGE.concept;
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold ${badge.style}`}>
      {badge.label}
    </span>
  );
}

function ActiveModelCard({ id, model }: { id: string; model: ModelEntry }) {
  const [expanded, setExpanded] = useState(false);
  const catStyle = CATEGORY_STYLES[model.category] || CATEGORY_STYLES.stars;

  return (
    <div className={`rounded-lg border ${catStyle.border} ${catStyle.bg} overflow-hidden`}>
      <div
        className="flex items-center gap-3 p-4 cursor-pointer hover:bg-white/40 dark:hover:bg-white/5 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className={`${catStyle.icon}`}>
          {ICON_MAP[model.icon] || <Star className="w-5 h-5" />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-base font-bold">{model.name}</h3>
            <code className="text-xs text-muted-foreground">{id}</code>
            <StatusBadge status="active" />
          </div>
          <p className="text-sm text-muted-foreground mt-0.5">{model.description}</p>
        </div>
        <div className="text-right shrink-0">
          <div className="text-sm font-mono font-semibold">{model.active_version}</div>
          {model.versions[0]?.p_auc && (
            <div className="text-xs text-muted-foreground">
              P AUC {model.versions[0].p_auc.toFixed(4)}
            </div>
          )}
        </div>
        <div className="text-muted-foreground">
          {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </div>
      </div>

      {expanded && model.versions.length > 0 && (
        <div className="border-t border-inherit px-4 py-3 bg-white/50 dark:bg-black/20">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-muted-foreground">
                <th className="text-left py-1 font-medium">Version</th>
                <th className="text-left py-1 font-medium">Description</th>
                <th className="text-right py-1 font-medium">P AUC</th>
                <th className="text-right py-1 font-medium">W AUC</th>
                <th className="text-right py-1 font-medium">Features</th>
              </tr>
            </thead>
            <tbody>
              {model.versions.map((v) => (
                <tr
                  key={v.version}
                  className={v.version === model.active_version ? 'font-semibold' : 'text-muted-foreground'}
                >
                  <td className="py-1 font-mono">
                    {v.version}
                    {v.version === model.active_version && (
                      <span className="ml-1.5 text-emerald-600 dark:text-emerald-400 text-[10px]">LIVE</span>
                    )}
                  </td>
                  <td className="py-1">{v.description || '-'}</td>
                  <td className="py-1 text-right font-mono">{v.p_auc?.toFixed(4) || '-'}</td>
                  <td className="py-1 text-right font-mono">{v.w_auc?.toFixed(4) || '-'}</td>
                  <td className="py-1 text-right font-mono">{v.features || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function FutureModelCard({ model }: { model: typeof FUTURE_MODELS[0] }) {
  const catStyle = CATEGORY_STYLES[model.category] || CATEGORY_STYLES.stars;

  return (
    <div className={`rounded-lg border border-dashed ${catStyle.border} p-4 opacity-80`}>
      <div className="flex items-center gap-3">
        <div className={`${catStyle.icon} opacity-50`}>
          {ICON_MAP[model.icon] || <Star className="w-5 h-5" />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold">{model.name}</h3>
            <code className="text-xs text-muted-foreground">{model.id}</code>
            <StatusBadge status={model.status} />
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">{model.role}</p>
        </div>
      </div>
      <p className="text-xs text-muted-foreground mt-2 pl-8">{model.description}</p>
    </div>
  );
}

// ============================================================
// Page
// ============================================================
export default function ModelsPage() {
  const { data: registry } = useSWR<Registry>('/api/ml/registry', fetcher);

  if (!registry) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-200 dark:bg-gray-800 rounded w-48" />
          <div className="h-32 bg-gray-200 dark:bg-gray-800 rounded" />
          <div className="h-32 bg-gray-200 dark:bg-gray-800 rounded" />
        </div>
      </div>
    );
  }

  const models = registry.models || {};
  const categories = registry.categories || {};

  // Separate active models by category
  const starModels = Object.entries(models).filter(([, m]) => m.category === 'stars');
  const nebulaModels = Object.entries(models).filter(([, m]) => m.category === 'nebula');
  const futureStars = FUTURE_MODELS.filter(m => m.category === 'stars');
  const futureNebula = FUTURE_MODELS.filter(m => m.category === 'nebula');

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-8">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3 mb-1">
          <Link href="/changelog" className="text-muted-foreground hover:text-foreground">
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <h1 className="text-2xl font-bold">Model Architecture</h1>
        </div>
        <p className="text-sm text-muted-foreground pl-7">
          KeibaCICD MLモデル体系 — 天体名コードによるマルチモデル管理
        </p>
      </div>

      {/* Stars Category */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <div className={`w-2.5 h-2.5 rounded-full ${CATEGORY_STYLES.stars.dot}`} />
          <h2 className="text-lg font-bold">{categories.stars?.label || 'Stars'}</h2>
          <span className="text-xs text-muted-foreground">{categories.stars?.description}</span>
        </div>

        <div className="space-y-3">
          {starModels.map(([id, model]) => (
            <ActiveModelCard key={id} id={id} model={model} />
          ))}
          {futureStars.map((m) => (
            <FutureModelCard key={m.id} model={m} />
          ))}
        </div>
      </section>

      {/* Nebula Category */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <div className={`w-2.5 h-2.5 rounded-full ${CATEGORY_STYLES.nebula.dot}`} />
          <h2 className="text-lg font-bold">{categories.nebula?.label || 'Nebula'}</h2>
          <span className="text-xs text-muted-foreground">{categories.nebula?.description}</span>
        </div>

        <div className="space-y-3">
          {nebulaModels.map(([id, model]) => (
            <ActiveModelCard key={id} id={id} model={model} />
          ))}
          {futureNebula.map((m) => (
            <FutureModelCard key={m.id} model={m} />
          ))}
        </div>
      </section>

      {/* Architecture Overview */}
      <section className="border rounded-lg p-5 bg-muted/30">
        <h2 className="text-base font-bold mb-3">Architecture Overview</h2>
        <div className="text-sm space-y-2 text-muted-foreground">
          <p>
            <strong className="text-foreground">Stars</strong> = 馬単位の評価モデル。
            「この馬が走るか」を判定。Polaris(base) + 専門モデルの組み合わせで多角評価。
          </p>
          <p>
            <strong className="text-foreground">Nebula</strong> = レース単位の判定モデル。
            「このレースがどうなるか」を予測。展開・荒れ度・馬場をレース全体視点で分析。
          </p>
          <p>
            各モデルは独立してバージョン管理される。Polaris 3.0 に上げても Enif は v2.5b のまま、
            のように個別進化が可能。
            <code className="text-xs ml-1">session_id</code> でどの組み合わせで予測したかを追跡。
          </p>
        </div>
      </section>

      {/* Technical Details */}
      <section className="text-xs text-muted-foreground border-t pt-4">
        <div className="flex items-center gap-4 flex-wrap">
          <span>Registry: <code>model_registry.json</code> (schema v{registry.schema_version || '?'})</span>
          <span>Loader: <code>ml/model_loader.py</code></span>
          <span>Dir: <code>data3/ml/models/&lt;name&gt;/live/</code></span>
        </div>
      </section>
    </div>
  );
}
