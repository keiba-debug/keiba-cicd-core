import useSWR from 'swr';
import { fetcher } from '@/lib/fetcher';
import type { SimulationData } from '@/app/analysis/simulation/types';

export function useSimulationResult(version?: string | null) {
  const url = version
    ? `/api/simulation/result?version=${version}`
    : '/api/simulation/result';
  const { data, error, isLoading } = useSWR<SimulationData>(
    url,
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 60_000 },
  );
  return { data: data ?? null, isLoading, error };
}

export function useSimulationVersions() {
  const { data, error, isLoading } = useSWR<{ versions: string[] }>(
    '/api/simulation/versions',
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 300_000 },
  );
  return { versions: data?.versions ?? [], isLoading, error };
}
