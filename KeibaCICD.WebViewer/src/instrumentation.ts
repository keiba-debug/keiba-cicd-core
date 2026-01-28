/**
 * Next.js Instrumentation
 * アプリ起動時に実行される初期化処理
 */

export async function register() {
  // サーバーサイドのみで実行
  if (process.env.NEXT_RUNTIME === 'nodejs') {
    console.log('[Instrumentation] Server starting...');
    
    // インデックスの事前構築
    try {
      const { preloadHorseIndex } = await import('./lib/data/target-horse-reader');
      const { preloadTargetRaceIndex } = await import('./lib/data/target-race-result-reader');
      const { buildHorseRaceIndex } = await import('./lib/data/horse-race-index');
      const { buildRaceDateIndex } = await import('./lib/data/race-date-index');
      
      // 非同期で実行（起動をブロックしない）
      setTimeout(async () => {
        console.log('[Instrumentation] Building indexes...');
        const start = Date.now();
        
        // 並列でインデックス構築
        await Promise.all([
          // 馬IDインデックス構築（UM_DATA）
          (async () => {
            preloadHorseIndex();
          })(),
          // 馬レース成績インデックス構築（SE_DATA）
          (async () => {
            preloadTargetRaceIndex();
          })(),
          // 馬→レースマッピングインデックス構築（integrated_*.json）
          buildHorseRaceIndex(),
          // レース日付インデックス構築
          buildRaceDateIndex(),
        ]);
        
        console.log(`[Instrumentation] All indexes ready in ${Date.now() - start}ms`);
      }, 1000);
    } catch (error) {
      console.error('[Instrumentation] Index build error:', error);
    }
  }
}
