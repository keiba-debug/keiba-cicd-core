export const fetcher = async (url: string) => {
  const res = await fetch(url);
  if (!res.ok) throw new Error('APIリクエストに失敗しました');
  return res.json();
};
