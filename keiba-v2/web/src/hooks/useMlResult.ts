import useSWR from 'swr';
import { fetcher } from '@/lib/fetcher';
import { normalizeResult } from '@/app/analysis/ml/utils';
import type { MlExperimentResultV2 } from '@/app/analysis/ml/types';

export function useMlResult(version?: string | null) {
  const url = version ? `/api/ml/result?version=${version}` : '/api/ml/result';

  const { data, error, isLoading } = useSWR<MlExperimentResultV2>(
    url,
    async (u: string) => {
      const raw = await fetcher(u);
      const v = raw.version ?? '';
      if (!v.startsWith('2.') && !v.startsWith('3.') && !v.startsWith('4.')) {
        throw new Error(`対応バージョン: 2.x〜4.x (got: ${v})`);
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
