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
      const v = (raw.version ?? '').replace(/^v/, '');
      const major = parseInt(v.split('.')[0], 10);
      // 数値バージョンは2.x以上のみ対応、非数値(cv1等)はv3フォーマットなので許可
      if (!isNaN(major) && major < 2) {
        throw new Error(`対応バージョン: 2.x以上 (got: ${raw.version})`);
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
