/**
 * 的中コレクションAPI
 * 
 * GET /api/bankroll/collection - 的中馬券コレクションを取得
 * 
 * TARGETデータから的中馬券を抽出し、統計情報と一緒に返す
 */

import { NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';
import { ADMIN_CONFIG } from '@/lib/admin/config';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

interface WinningTicket {
  id: string;
  date: string;
  venue: string;
  race_number: number;
  race_name: string;
  bet_type: string;
  selection: string;
  amount: number;
  payout: number;
  odds: number;
  profit: number;
}

/**
 * Pythonスクリプトを実行してJSONを取得
 */
function executePythonScript(
  scriptPath: string,
  args: string[]
): Promise<any> {
  return new Promise((resolve, reject) => {
    const pythonPath = process.env.PYTHON_PATH || 'python';
    const scriptFullPath = path.resolve(scriptPath);

    const child = spawn(pythonPath, [scriptFullPath, ...args], {
      shell: true,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    });

    let stdout = '';
    let stderr = '';

    child.stdout?.on('data', (data: Buffer) => {
      stdout += data.toString('utf-8');
    });

    child.stderr?.on('data', (data: Buffer) => {
      stderr += data.toString('utf-8');
    });

    child.on('close', (code: number | null) => {
      if (code !== 0) {
        reject(new Error(`プロセス終了コード: ${code}\n${stderr}`));
        return;
      }

      try {
        const jsonStr = stdout.trim();
        if (!jsonStr) {
          reject(new Error('スクリプトからの出力がありません'));
          return;
        }

        const jsonMatch = jsonStr.match(/\{[\s\S]*\}/);
        if (!jsonMatch) {
          reject(new Error('JSON出力が見つかりません'));
          return;
        }

        const result = JSON.parse(jsonMatch[0]);
        resolve(result);
      } catch (error) {
        reject(new Error(`JSON解析エラー: ${error}\n出力: ${stdout}`));
      }
    });

    child.on('error', (error: Error) => {
      reject(error);
    });
  });
}

export async function GET() {
  try {
    const scriptPath = path.join(ADMIN_CONFIG.aiToolsPath, 'target_reader.py');

    // 直近6ヶ月分のデータを取得
    const now = new Date();
    const winningTickets: WinningTicket[] = [];
    
    for (let i = 0; i < 6; i++) {
      const year = now.getFullYear();
      const month = now.getMonth() + 1 - i;
      const adjustedYear = month <= 0 ? year - 1 : year;
      const adjustedMonth = month <= 0 ? month + 12 : month;
      
      try {
        const result = await executePythonScript(scriptPath, [
          '--year', String(adjustedYear),
          '--month', String(adjustedMonth),
        ]);
        
        if (result.races && Array.isArray(result.races)) {
          for (const race of result.races) {
            if (race.bets && Array.isArray(race.bets)) {
              for (const bet of race.bets) {
                if (bet.is_hit && bet.payout > 0) {
                  winningTickets.push({
                    id: `${race.race_id}-${bet.bet_type}-${bet.selection}`,
                    date: race.date || result.date || '',
                    venue: race.venue || '',
                    race_number: race.race_number || 0,
                    race_name: race.race_name || '',
                    bet_type: bet.bet_type || '',
                    selection: bet.selection || '',
                    amount: bet.amount || 0,
                    payout: bet.payout || 0,
                    odds: bet.odds || 0,
                    profit: (bet.payout || 0) - (bet.amount || 0),
                  });
                }
              }
            }
          }
        }
      } catch {
        // この月のデータがない場合はスキップ
        continue;
      }
    }
    
    // 日付降順でソート
    winningTickets.sort((a, b) => b.date.localeCompare(a.date));
    
    // 統計を計算
    const totalWins = winningTickets.length;
    const totalProfit = winningTickets.reduce((sum, t) => sum + t.profit, 0);
    const totalPayout = winningTickets.reduce((sum, t) => sum + t.payout, 0);
    
    // 最高配当
    const highestPayout = winningTickets.length > 0
      ? winningTickets.reduce((max, t) => t.payout > max.payout ? t : max, winningTickets[0])
      : null;
    
    // 最高オッズ
    const highestOdds = winningTickets.length > 0
      ? winningTickets.reduce((max, t) => t.odds > max.odds ? t : max, winningTickets[0])
      : null;
    
    // 万馬券数（100倍以上）
    const manbaCount = winningTickets.filter(t => t.odds >= 100).length;
    
    // 高配当（50倍以上）
    const highPayouts = winningTickets.filter(t => t.odds >= 50);
    
    return NextResponse.json({
      tickets: winningTickets,
      stats: {
        total_wins: totalWins,
        total_profit: totalProfit,
        total_payout: totalPayout,
        highest_payout: highestPayout,
        highest_odds: highestOdds,
        manba_count: manbaCount,
        high_payout_count: highPayouts.length,
      },
      recent: winningTickets.slice(0, 10),
    });
  } catch (error) {
    console.error('[CollectionAPI] Error:', error);
    return NextResponse.json(
      {
        error: '的中コレクションの取得に失敗しました',
        tickets: [],
        stats: {
          total_wins: 0,
          total_profit: 0,
          total_payout: 0,
          highest_payout: null,
          highest_odds: null,
          manba_count: 0,
          high_payout_count: 0,
        },
        recent: [],
      },
      { status: 500 }
    );
  }
}
