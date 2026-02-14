'use client';

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useMlVersions } from '@/hooks/useMlVersions';

interface Props {
  value: string | null;
  onChange: (version: string | null) => void;
}

export default function VersionSelector({ value, onChange }: Props) {
  const { data: versions } = useMlVersions();

  if (!versions || versions.length === 0) return null;

  return (
    <Select
      value={value ?? 'latest'}
      onValueChange={(v) => onChange(v === 'latest' ? null : v)}
    >
      <SelectTrigger className="w-[180px]">
        <SelectValue placeholder="バージョン" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="latest">最新</SelectItem>
        {versions.map((v) => (
          <SelectItem key={v.version} value={v.version}>
            v{v.version}
            {v.created_at ? ` (${v.created_at.slice(0, 10)})` : ''}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
