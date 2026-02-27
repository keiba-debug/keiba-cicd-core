import useSWR from 'swr';
import { fetcher } from '@/lib/fetcher';
import type { SimulationData } from '@/app/analysis/simulation/types';

export function useSimulationResult() {
  const { data, error, isLoading } = useSWR<SimulationData>(
    '/api/simulation/result',
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 60_000 },
  );
  return { data: data ?? null, isLoading, error };
}
