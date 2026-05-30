# W/P/ADR 強さ重み backtest — Session 140 宿題⑤

> 対象: `bettype_efficiency.compute_strengths` の composite 重み (既定 `DEFAULT_WEIGHTS=(1,1,1)`) が
> 軸◎ (= composite 最上位) 選定の品質という観点で最適かを検証。
> 方針 (ふくだ): **「等重みからの逸脱は ROI で正当化する」**。逸脱が walk-forward で頑健に勝てなければ等重み維持。
> スクリプト: `keiba-v2/ml/analyze/backtest_strength_weights.py`

## データ・手法
- `backtest_cache.json` = 本番予測+結果の結合。**2,934 races / 97 日 (2025-05-03〜2026-03-15)**。
- composite = `(wW·z(W) + wP·z(P) + wA·z(ADR)) / (wW+wP+wA)`。重み和で正規化＝**スケール不変**。
  - W = `pred_proba_w_cal`（cache に raw 無し→ `win_ev/odds` で復元、軸(1,1,1)が `compute_strengths` と **500/500 一致**で検証）
  - P = `pred_proba_p_raw` / ADR = `ar_deviation`
- z-score は重み非依存なので race ごとに 1 回算出し、重みスイープ (124通り, 各0/0.5/1/2/3) は composite 再計算のみ。
- 指標（軸◎の質の代理。**実運用は軸◎+ハーヴィルEV選択なので、これは「軸をフラット買いした場合」の proxy**）:
  win率 / top3率 / winROI=Σ(的中時odds)/n / placeROI=Σ(top3時place_odds_min)/n。

## 結果サマリ

### ① 的中率（win率 / top3率）では 等重み (1,1,1) で十分
| 重み W:P:A | win率 | top3率 | winROI | placeROI | 軸平均odds |
|---|---|---|---|---|---|
| **1:1:1 (baseline)** | 29.4% | 63.8% | 86.0% | 83.7% | 3.9倍 |
| top3最適 (例 1:0.5:3) | 〜30% | 64.6% | 〜86% | 〜84% | 〜4倍 |

- 全重みが極めて僅差にクラスタ（top3 63〜64.6%）。top3最適でも +0.8pt。
- walk-forward: train最適 (1,0.5,3) の **valid top3 = +0.15pt（ノイズ帯1pt未満＝有意でない）**。
- → **「最も当たる軸」を選ぶ目的なら等重み (1,1,1) は妥当**。シグナルは相補的で、重み替えで的中率は動かない。

### ② ROI/妙味では P（複勝モデル）寄せが頑健に勝つ
| 重み W:P:A | win率 | top3率 | winROI | placeROI | 軸平均odds |
|---|---|---|---|---|---|
| 1:1:1 (baseline) | 29.4% | 63.8% | 86.0% | 83.7% | 3.9倍 |
| **0:1:0 (pure-P)** | 22.5% | 56.4% | **102.6%** | **92.9%** | **9.6倍** |
| 1:0:0 (pure-W) | 29.9% | 63.0% | 85.5% | 80.9% | 3.6倍 |
| 0:0:1 (pure-ADR) | 28.8% | 62.4% | 84.4% | 81.6% | 4.2倍 |
| 0.5:2:0.5 (P寄せ) | 26.1% | 60.9% | 96.2% | 88.5% | 6.2倍 |

**機序**: P を重くすると軸が「複勝するが市場が過小評価する**高オッズ馬**」に寄る（軸平均 3.9→9.6倍）＝
**人気-longshotバイアス回避**（W は市場と同じく人気馬に張り付き過剰人気→-EV、P は別シグナルで妙味馬を拾う）。

**頑健性（複数 split で pure-P vs baseline、valid 期間）**:
| split>= | n | winROI base→pureP (Δ) | placeROI base→pureP (Δ) |
|---|---|---|---|
| 2025-10-01 | 1497 | 81.3→98.7 (**+17.4**) | 81.6→92.0 (**+10.4**) |
| 2025-11-01 | 1242 | 81.6→99.8 (+18.3) | 81.3→91.6 (+10.4) |
| 2025-12-01 | 943 | 82.6→112.4 (+29.8) | 79.2→92.1 (+12.8) |
| 2026-01-01 | 687 | 86.8→120.5 (+33.7) | 79.8→93.9 (+14.1) |
| 2026-02-01 | 422 | 83.8→141.0 (+57.2) | 78.8→95.4 (+16.5) |

- **placeROI（安定指標）の +10〜16pt は全 split で一貫＝頑健な実シグナル**。winROI の +17〜57pt は方向は正だが高分散（小サンプルほど誇張）。

## 結論・推奨（規律をもって）
1. **的中率目的: 等重み (1,1,1) で正当**（逸脱は有意でない）。現状維持。
2. **ROI/妙味目的: composite を P 寄せ（W 軽め）にすると軸が高オッズの妙味馬に寄り ROI 改善**。これが
   ふくだの「逸脱を ROI で正当化」に合致する唯一の頑健な逸脱方向。
3. **ただし即・既定変更はしない**。理由:
   - 本 backtest は**軸フラット買いの proxy**。本番は軸◎+ハーヴィルEV選択なので、重みを変える前に
     **full-selection ROI（実際に fund するプラン群を payout で決済）で再検証**が必須。
   - pure-P でも placeROI 93% は <100%（単独黒字ではない）。win率は大きく落ちる（29→22%）。
   - winROI>100% は単勝フラットの高分散で、額面通りの「黒字戦略」ではない。
4. **実装はプラガブル済**（`bettype_efficiency` / `bettype_selection` とも `--weights` 受付）。
   → 次アクション候補: ①**「妙味」プリセット**（例 W:P:A=0.5:2:0.5 等の中庸 P 寄せ）を「強さ」既定と別に用意
   ②full-selection ROI backtest を組んで P 寄せの最適点を確定 ③[[feedback_betting_philosophy]] の
   「自分にできない買い方」＝人気-longshotバイアス回避を hole_seeker / 妙味プリセットに接続。

## 再現
```
python -m ml.analyze.backtest_strength_weights --metric top3_rate  --split-date 2026-01-01
python -m ml.analyze.backtest_strength_weights --metric place_roi  --split-date 2026-01-01
python -m ml.analyze.backtest_strength_weights --metric win_roi    --split-date 2026-01-01
```
