'use client';

import { useState, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { Star, Mountain, Sun, ChevronDown } from 'lucide-react';

interface ModelVersion {
  version: string;
  dir: string | null;
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
  result_file: string | null;
  meta_file: string | null;
  versions: ModelVersion[];
}

interface Registry {
  models: Record<string, ModelEntry>;
  categories: Record<string, { label: string; description: string }>;
}

export interface ModelSelection {
  modelId: string;
  version: string | null; // null = active (latest)
}

interface Props {
  selected: ModelSelection;
  onChange: (sel: ModelSelection) => void;
}

const ICONS: Record<string, typeof Star> = {
  star: Star,
  mountain: Mountain,
  sun: Sun,
};

export default function ModelSelector({ selected, onChange }: Props) {
  const [registry, setRegistry] = useState<Registry | null>(null);

  useEffect(() => {
    fetch('/api/ml/registry')
      .then(r => r.json())
      .then(setRegistry)
      .catch(() => null);
  }, []);

  if (!registry) return null;

  const models = registry.models;
  const modelIds = Object.keys(models);

  return (
    <div className="flex items-center gap-3 flex-wrap">
      {modelIds.map(id => {
        const model = models[id];
        const isActive = selected.modelId === id;
        const Icon = ICONS[model.icon] ?? Star;
        const currentVersion = isActive && selected.version
          ? selected.version
          : model.active_version;

        return (
          <div key={id} className="flex items-center gap-1">
            {/* モデルボタン */}
            <button
              onClick={() => onChange({ modelId: id, version: null })}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary text-primary-foreground border-primary'
                  : 'bg-muted/40 text-muted-foreground border-transparent hover:bg-muted',
              )}
            >
              <Icon className="h-3.5 w-3.5" />
              {model.name}
            </button>

            {/* バージョンセレクター（アクティブモデルのみ） */}
            {isActive && model.versions.length > 1 && (
              <div className="relative">
                <select
                  value={selected.version ?? ''}
                  onChange={(e) => onChange({
                    modelId: id,
                    version: e.target.value || null,
                  })}
                  className="text-xs rounded border border-gray-300 bg-background pl-2 pr-6 py-1 appearance-none dark:border-gray-600"
                >
                  <option value="">{model.active_version} (active)</option>
                  {model.versions
                    .filter(v => v.version !== model.active_version)
                    .map(v => (
                      <option key={v.version} value={v.version}>
                        {v.version}
                        {v.p_auc ? ` (AUC ${v.p_auc.toFixed(3)})` : ''}
                      </option>
                    ))
                  }
                </select>
                <ChevronDown className="absolute right-1.5 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground pointer-events-none" />
              </div>
            )}

            {/* ミニメトリクス */}
            {isActive && (() => {
              const v = model.versions.find(ver => ver.version === currentVersion);
              if (!v?.p_auc) return null;
              return (
                <span className="text-xs text-muted-foreground tabular-nums">
                  AUC {v.p_auc.toFixed(3)}
                  {v.features ? ` / ${v.features}feat` : ''}
                </span>
              );
            })()}
          </div>
        );
      })}
    </div>
  );
}
