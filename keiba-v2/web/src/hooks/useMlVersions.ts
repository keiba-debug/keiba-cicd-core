import useSWR from 'swr';
import { fetcher } from '@/lib/fetcher';
import type { VersionEntry } from '@/lib/data/version-utils';

export function useMlVersions() {
  return useSWR<VersionEntry[]>('/api/ml/versions', fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 300_000,
  });
}
