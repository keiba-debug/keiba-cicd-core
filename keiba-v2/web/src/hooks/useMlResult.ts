import useSWR from 'swr';
import { fetcher } from '@/lib/fetcher';
import { normalizeResult } from '@/app/analysis/ml/utils';
import type { MlExperimentResultV2 } from '@/app/analysis/ml/types';

export function useMlResult() {
  const { data, error, isLoading } = useSWR<MlExperimentResultV2>(
    '/api/ml/result',
    async (url: string) => {
      const raw = await fetcher(url);
      if (!raw.version?.startsWith('2.') && !raw.version?.startsWith('3.')) {
        throw new Error(`対応バージョン: 2.x or 3.x (got: ${raw.version})`);
      }
      return normalizeResult(raw);
    },
    {
      revalidateOnFocus: false,
      dedupingInterval: 60_000,
    }
  );

  return { data: data ?? null, isLoading, error };
}
