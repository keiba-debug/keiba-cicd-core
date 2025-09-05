'use client';

import { useState } from 'react';
import { Play, Loader2 } from 'lucide-react';

interface CommandRunnerProps {
  onJobCreated: (jobId: string) => void;
}

const COMMANDS = [
  { value: 'fast_batch', label: 'Fast Batch (データ取得)', hasDate: true, hasDataTypes: true },
  { value: 'integrator', label: 'Integrator (統合)', hasDate: true },
  { value: 'markdown', label: 'Markdown (MD生成)', hasDate: true },
  { value: 'accumulator', label: 'Accumulator (履歴蓄積)', hasDate: true },
  { value: 'organizer', label: 'Organizer (整理)', hasDate: true }
];

const DATA_TYPES = [
  'shutsuba', 'seiseki', 'cyokyo', 'danwa', 'syoin', 'paddok'
];

export default function CommandRunner({ onJobCreated }: CommandRunnerProps) {
  const [command, setCommand] = useState('fast_batch');
  const [date, setDate] = useState(new Date().toISOString().split('T')[0].replace(/-/g, '/'));
  const [dataTypes, setDataTypes] = useState<string[]>(['shutsuba']);
  const [isRunning, setIsRunning] = useState(false);

  const selectedCommand = COMMANDS.find(c => c.value === command);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsRunning(true);

    try {
      const args: any = {};
      
      // コマンド別の引数設定
      if (command === 'fast_batch') {
        args.subcommand = 'data';
        args.start = date;
        args.end = date;
        args['data-types'] = dataTypes.join(',');
        args.delay = '0.5';
        args['max-workers'] = '8';
      } else if (command === 'integrator') {
        args.subcommand = 'batch';
        args.date = date.replace(/\//g, '');
      } else if (command === 'markdown') {
        args.subcommand = 'batch';
        args.date = date.replace(/\//g, '');
        args.organized = true;
      } else if (command === 'accumulator') {
        args.subcommand = 'horse-history';
        args.date = date;
        args.runs = '3';
        args.source = 'organized';
      }

      const response = await fetch('http://localhost:8000/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command, args })
      });

      const data = await response.json();
      onJobCreated(data.job_id);
    } catch (error) {
      console.error('Failed to run command:', error);
      alert('コマンド実行に失敗しました');
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-lg font-semibold mb-4">コマンド実行</h2>
      
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            処理選択
          </label>
          <select 
            value={command}
            onChange={(e) => setCommand(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {COMMANDS.map(cmd => (
              <option key={cmd.value} value={cmd.value}>
                {cmd.label}
              </option>
            ))}
          </select>
        </div>

        {selectedCommand?.hasDate && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              対象日 (YYYY/MM/DD)
            </label>
            <input
              type="text"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="2025/08/23"
            />
          </div>
        )}

        {selectedCommand?.hasDataTypes && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              データタイプ
            </label>
            <div className="space-y-1">
              {DATA_TYPES.map(type => (
                <label key={type} className="flex items-center">
                  <input
                    type="checkbox"
                    value={type}
                    checked={dataTypes.includes(type)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setDataTypes([...dataTypes, type]);
                      } else {
                        setDataTypes(dataTypes.filter(t => t !== type));
                      }
                    }}
                    className="mr-2"
                  />
                  <span className="text-sm">{type}</span>
                </label>
              ))}
            </div>
          </div>
        )}

        <button
          type="submit"
          disabled={isRunning}
          className="w-full flex items-center justify-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isRunning ? (
            <>
              <Loader2 className="animate-spin mr-2 h-4 w-4" />
              実行中...
            </>
          ) : (
            <>
              <Play className="mr-2 h-4 w-4" />
              実行
            </>
          )}
        </button>
      </form>
    </div>
  );
}