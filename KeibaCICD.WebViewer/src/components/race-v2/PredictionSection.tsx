'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Star,
  Save,
  ChevronDown,
  ChevronUp,
  Check,
  Edit2,
  Trash2,
} from 'lucide-react';

interface Entry {
  horse_number: number;
  horse_name: string;
  jockey_name?: string;
  odds?: number;
}

interface Prediction {
  race_id: string;
  race_date: string;
  race_name: string;
  venue: string;
  race_number: number;
  created_at: string;
  updated_at: string;
  marks: { [horseNumber: string]: string };
  scores: { [horseNumber: string]: number };
  comment: string;
  confidence: '高' | '中' | '低';
  status: 'draft' | 'confirmed';
}

interface PredictionSectionProps {
  raceId: string;
  raceDate: string;
  raceName: string;
  venue: string;
  raceNumber: number;
  entries: Entry[];
}

const MARK_OPTIONS = ['', '◎', '○', '▲', '△', '×'];
const MARK_COLORS: { [key: string]: string } = {
  '◎': 'bg-red-500 text-white',
  '○': 'bg-blue-500 text-white',
  '▲': 'bg-green-500 text-white',
  '△': 'bg-yellow-500 text-black',
  '×': 'bg-gray-500 text-white',
};

export function PredictionSection({
  raceId,
  raceDate,
  raceName,
  venue,
  raceNumber,
  entries,
}: PredictionSectionProps) {
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [editMode, setEditMode] = useState(false);

  // フォームデータ
  const [marks, setMarks] = useState<{ [key: string]: string }>({});
  const [scores, setScores] = useState<{ [key: string]: number }>({});
  const [comment, setComment] = useState('');
  const [confidence, setConfidence] = useState<'高' | '中' | '低'>('中');

  // 予想を取得
  const fetchPrediction = useCallback(async () => {
    try {
      const res = await fetch(`/api/predictions/${raceDate}/${raceId}`);
      if (res.ok) {
        const data = await res.json();
        if (data.exists && data.prediction) {
          setPrediction(data.prediction);
          setMarks(data.prediction.marks || {});
          setScores(data.prediction.scores || {});
          setComment(data.prediction.comment || '');
          setConfidence(data.prediction.confidence || '中');
        }
      }
    } catch (error) {
      console.error('予想取得エラー:', error);
    } finally {
      setLoading(false);
    }
  }, [raceDate, raceId]);

  useEffect(() => {
    fetchPrediction();
  }, [fetchPrediction]);

  // 印を設定
  const setMark = (horseNumber: number, mark: string) => {
    setMarks((prev) => {
      const newMarks = { ...prev };
      if (mark === '') {
        delete newMarks[String(horseNumber)];
      } else {
        // 同じ印が既にある場合は削除
        Object.keys(newMarks).forEach((key) => {
          if (newMarks[key] === mark) {
            delete newMarks[key];
          }
        });
        newMarks[String(horseNumber)] = mark;
      }
      return newMarks;
    });
  };

  // スコアを設定
  const setScore = (horseNumber: number, score: number) => {
    setScores((prev) => ({
      ...prev,
      [String(horseNumber)]: Math.max(0, Math.min(100, score)),
    }));
  };

  // 保存
  const handleSave = async (status: 'draft' | 'confirmed' = 'draft') => {
    setSaving(true);
    try {
      const res = await fetch(`/api/predictions/${raceDate}/${raceId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          race_name: raceName,
          venue,
          race_number: raceNumber,
          marks,
          scores,
          comment,
          confidence,
          status,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setPrediction(data.prediction);
        setEditMode(false);
      } else {
        alert('保存に失敗しました');
      }
    } catch (error) {
      console.error('保存エラー:', error);
      alert('保存に失敗しました');
    } finally {
      setSaving(false);
    }
  };

  // 削除
  const handleDelete = async () => {
    if (!confirm('予想を削除しますか？')) return;

    try {
      const res = await fetch(`/api/predictions/${raceDate}/${raceId}`, {
        method: 'DELETE',
      });

      if (res.ok) {
        setPrediction(null);
        setMarks({});
        setScores({});
        setComment('');
        setConfidence('中');
        setEditMode(false);
      }
    } catch (error) {
      console.error('削除エラー:', error);
    }
  };

  // 印付きの馬を取得
  const getMarkedHorses = () => {
    return Object.entries(marks)
      .map(([num, mark]) => {
        const entry = entries.find((e) => e.horse_number === parseInt(num));
        return { number: num, mark, name: entry?.horse_name || '' };
      })
      .sort((a, b) => {
        const order = ['◎', '○', '▲', '△', '×'];
        return order.indexOf(a.mark) - order.indexOf(b.mark);
      });
  };

  if (loading) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center gap-2">
            <Star className="h-5 w-5" />
            予想入力
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">読み込み中...</p>
        </CardContent>
      </Card>
    );
  }

  // サマリー表示（予想がある場合で編集モードでない場合）
  if (prediction && !editMode) {
    const markedHorses = getMarkedHorses();

    return (
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg flex items-center gap-2">
              <Star className="h-5 w-5 text-yellow-500" />
              予想
              {prediction.status === 'confirmed' ? (
                <Badge className="bg-green-500">確定</Badge>
              ) : (
                <Badge variant="outline">下書き</Badge>
              )}
            </CardTitle>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setEditMode(true)}
              >
                <Edit2 className="h-4 w-4" />
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setExpanded(!expanded)}
              >
                {expanded ? (
                  <ChevronUp className="h-4 w-4" />
                ) : (
                  <ChevronDown className="h-4 w-4" />
                )}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {/* 印のサマリー */}
          <div className="flex flex-wrap gap-2 mb-3">
            {markedHorses.map(({ number, mark, name }) => (
              <Badge
                key={number}
                className={`${MARK_COLORS[mark] || 'bg-gray-200'} text-sm`}
              >
                {mark}
                {number}
                {name}
              </Badge>
            ))}
            {markedHorses.length === 0 && (
              <span className="text-sm text-muted-foreground">
                印なし
              </span>
            )}
          </div>

          {/* 詳細 */}
          {expanded && (
            <div className="space-y-2 pt-2 border-t">
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">自信度:</span>
                <Badge
                  variant={
                    prediction.confidence === '高'
                      ? 'default'
                      : prediction.confidence === '中'
                      ? 'secondary'
                      : 'outline'
                  }
                >
                  {prediction.confidence}
                </Badge>
              </div>
              {prediction.comment && (
                <p className="text-sm">{prediction.comment}</p>
              )}
              <p className="text-xs text-muted-foreground">
                更新: {new Date(prediction.updated_at).toLocaleString('ja-JP')}
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    );
  }

  // 編集フォーム
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            <Star className="h-5 w-5" />
            予想入力
          </CardTitle>
          <div className="flex items-center gap-2">
            {prediction && (
              <Button size="sm" variant="ghost" onClick={handleDelete}>
                <Trash2 className="h-4 w-4 text-red-500" />
              </Button>
            )}
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {expanded ? (
          <div className="space-y-4">
            {/* 印入力テーブル */}
            <div className="border rounded-lg overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-muted">
                  <tr>
                    <th className="px-2 py-1 text-left w-12">No</th>
                    <th className="px-2 py-1 text-left">馬名</th>
                    <th className="px-2 py-1 text-center w-32">印</th>
                    <th className="px-2 py-1 text-center w-20">点数</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((entry) => (
                    <tr key={entry.horse_number} className="border-t">
                      <td className="px-2 py-1 font-mono">
                        {entry.horse_number}
                      </td>
                      <td className="px-2 py-1">{entry.horse_name}</td>
                      <td className="px-2 py-1">
                        <div className="flex justify-center gap-1">
                          {MARK_OPTIONS.map((mark) => (
                            <button
                              key={mark || 'none'}
                              onClick={() => setMark(entry.horse_number, mark)}
                              className={`w-6 h-6 rounded text-xs font-bold ${
                                marks[String(entry.horse_number)] === mark
                                  ? MARK_COLORS[mark] || 'bg-gray-200 ring-2 ring-primary'
                                  : 'bg-gray-100 hover:bg-gray-200'
                              }`}
                            >
                              {mark || '−'}
                            </button>
                          ))}
                        </div>
                      </td>
                      <td className="px-2 py-1">
                        <Input
                          type="number"
                          min="0"
                          max="100"
                          value={scores[String(entry.horse_number)] || ''}
                          onChange={(e) =>
                            setScore(
                              entry.horse_number,
                              parseInt(e.target.value) || 0
                            )
                          }
                          placeholder="0-100"
                          className="w-16 h-7 text-center text-xs"
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* コメント・自信度 */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-muted-foreground">自信度</label>
                <select
                  value={confidence}
                  onChange={(e) =>
                    setConfidence(e.target.value as '高' | '中' | '低')
                  }
                  className="w-full h-9 rounded-md border bg-background px-2 text-sm"
                >
                  <option value="高">高</option>
                  <option value="中">中</option>
                  <option value="低">低</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-muted-foreground">
                  コメント
                </label>
                <Input
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder="予想理由など"
                  className="h-9"
                />
              </div>
            </div>

            {/* ボタン */}
            <div className="flex gap-2">
              <Button
                onClick={() => handleSave('draft')}
                disabled={saving}
                variant="outline"
                className="flex-1"
              >
                <Save className="h-4 w-4 mr-2" />
                下書き保存
              </Button>
              <Button
                onClick={() => handleSave('confirmed')}
                disabled={saving}
                className="flex-1"
              >
                <Check className="h-4 w-4 mr-2" />
                確定
              </Button>
            </div>
          </div>
        ) : (
          <div className="text-center py-4">
            <Button variant="outline" onClick={() => setExpanded(true)}>
              予想を入力する
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
