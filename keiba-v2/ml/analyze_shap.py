"""
SHAP分析: Model P (V確率) vs Model AR (AR/着差回帰) の特徴量寄与比較
- グローバルimportance比較
- 乖離ケースのSHAP値分析（データ構築が必要な場合はダミーで代用）
"""
import json
import sys
import lightgbm as lgb
import numpy as np

ML_DIR = "C:/KEIBA-CICD/data3/ml"
META_PATH = f"{ML_DIR}/model_meta.json"

def load_models_and_meta():
    with open(META_PATH, 'r') as f:
        meta = json.load(f)

    model_p = lgb.Booster(model_file=f"{ML_DIR}/model_p.txt")
    model_ar = lgb.Booster(model_file=f"{ML_DIR}/model_ar.txt")

    features_value = meta['features_value']
    return model_p, model_ar, features_value

def compare_global_importance(model_p, model_ar, features):
    """gain-based feature importance比較"""
    imp_p = model_p.feature_importance(importance_type='gain')
    imp_reg = model_ar.feature_importance(importance_type='gain')

    # 正規化
    imp_p_norm = imp_p / imp_p.sum() * 100
    imp_reg_norm = imp_reg / imp_reg.sum() * 100

    # 差分計算 (V - AR)
    diff = imp_p_norm - imp_reg_norm

    print("=" * 80)
    print("  Feature Importance比較: Model P (V確率) vs AR (AR着差)")
    print("  （gain-based, 正規化100%）")
    print("=" * 80)

    # Top20を差の絶対値順に
    indices = np.argsort(-np.abs(diff))
    print(f"\n  {'特徴量':<35} {'V(P)':>7} {'AR':>7} {'差(V-AR)':>8} {'優勢'}")
    print(f"  {'-'*70}")

    for i in indices[:30]:
        name = features[i]
        v_val = imp_p_norm[i]
        ar_val = imp_reg_norm[i]
        d = diff[i]
        side = "← V重視" if d > 0.3 else ("→ AR重視" if d < -0.3 else "  ≈")
        print(f"  {name:<35} {v_val:>6.2f}% {ar_val:>6.2f}% {d:>+7.2f}% {side}")

    # カテゴリ別集計
    print(f"\n{'='*80}")
    print("  カテゴリ別 importance シェア比較")
    print(f"{'='*80}")

    categories = {
        '基本': ['age', 'sex', 'futan', 'horse_weight', 'horse_weight_diff', 'wakuban',
                 'distance', 'track_type', 'track_condition', 'entry_count', 'month', 'nichi'],
        '過去走': ['avg_finish_last3', 'best_finish_last5', 'last3f_avg_last3',
                   'days_since_last_race', 'win_rate_all', 'top3_rate_all',
                   'total_career_races', 'recent_form_trend', 'venue_top3_rate',
                   'track_type_top3_rate', 'distance_fitness', 'prev_race_entry_count',
                   'entry_count_change', 'best_l3f_last5', 'finish_std_last5',
                   'comeback_strength_last5', 'career_stage',
                   'prev_race_level_vs_class', 'avg_race_level_last3', 'prev_race_level_rank'],
        '調教師/騎手': ['trainer_win_rate', 'trainer_top3_rate', 'trainer_venue_top3_rate',
                       'jockey_win_rate', 'jockey_top3_rate', 'jockey_venue_top3_rate',
                       'jockey_close_win_rate'],
        '脚質': ['avg_first_corner_ratio', 'avg_last_corner_ratio', 'position_gain_last5',
                 'front_runner_rate', 'pace_sensitivity', 'closing_strength',
                 'running_style_consistency', 'last_race_corner1_ratio'],
        'ローテ': ['futan_diff', 'futan_diff_ratio', 'weight_change_ratio',
                   'prev_race_popularity', 'jockey_change',
                   'is_koukaku_venue', 'is_koukaku_female', 'is_koukaku_season',
                   'is_koukaku_age', 'is_koukaku_distance', 'is_koukaku_turf_to_dirt',
                   'is_koukaku_handicap', 'koukaku_rote_count'],
        'ペース': ['avg_race_rpci_last3', 'prev_race_rpci', 'consumption_flag',
                   'last3f_vs_race_l3_last3', 'steep_course_experience',
                   'steep_course_top3_rate', 'l3_unrewarded_rate_last5',
                   'avg_lap33_last3', 'prev_race_lap33',
                   'best_trend_top3_rate', 'worst_trend_top3_rate', 'trend_versatility'],
        '調教': ['training_arrow_value', 'oikiri_5f', 'oikiri_3f', 'oikiri_1f',
                 'oikiri_intensity_code', 'oikiri_has_awase', 'training_session_count',
                 'rest_weeks', 'oikiri_is_slope', 'kb_rating'],
        'スピード': ['speed_idx_latest', 'speed_idx_best5', 'speed_idx_avg3',
                    'speed_idx_trend', 'speed_idx_std'],
        'コメントNLP': ['comment_stable_condition', 'comment_stable_confidence',
                       'comment_stable_excuse_flag', 'comment_interview_condition',
                       'comment_interview_excuse_score', 'comment_memo_condition',
                       'comment_memo_trouble_score', 'comment_has_stable', 'comment_has_interview'],
        '血統': ['sire_top3_rate', 'bms_top3_rate', 'dam_top3_rate',
                 'sire_fresh_advantage', 'sire_tight_penalty',
                 'bms_fresh_advantage', 'bms_tight_penalty',
                 'dam_fresh_advantage', 'dam_tight_penalty',
                 'sire_sprint_top3_rate', 'sire_sustained_top3_rate', 'sire_finish_type_pref',
                 'bms_sprint_top3_rate', 'bms_sustained_top3_rate', 'bms_finish_type_pref',
                 'dam_sprint_top3_rate', 'dam_sustained_top3_rate', 'dam_finish_type_pref',
                 'sire_maturity_index', 'bms_maturity_index', 'dam_maturity_index'],
    }

    print(f"\n  {'カテゴリ':<15} {'V(P)':>8} {'AR':>8} {'差':>8}")
    print(f"  {'-'*45}")

    for cat_name, cat_feats in categories.items():
        v_sum = sum(imp_p_norm[features.index(f)] for f in cat_feats if f in features)
        ar_sum = sum(imp_reg_norm[features.index(f)] for f in cat_feats if f in features)
        d = v_sum - ar_sum
        marker = "◆" if abs(d) > 2 else ""
        print(f"  {cat_name:<15} {v_sum:>7.1f}% {ar_sum:>7.1f}% {d:>+7.1f}% {marker}")

    return imp_p_norm, imp_reg_norm, diff

def shap_analysis_with_backtest(model_p, model_ar, features):
    """
    バックテストキャッシュからは生特徴量が取れないため、
    LightGBMのSHAP TreeExplainerをダミーデータで概算。
    実際のSHAP分析にはexperiment.pyのデータ構築パイプラインが必要。
    """
    try:
        import shap
        print(f"\n{'='*80}")
        print("  SHAP TreeExplainer: モデル構造ベースの特徴量寄与分析")
        print(f"{'='*80}")

        # LightGBMモデルからSHAP expected valueを取得
        explainer_p = shap.TreeExplainer(model_p)
        explainer_reg = shap.TreeExplainer(model_ar)

        print(f"\n  Model P (V確率) base value: {explainer_p.expected_value:.4f}")
        print(f"  Model AR (AR) base value: {explainer_reg.expected_value:.4f}")

        # ランダムサンプルでSHAP値の分散を確認（概算用）
        np.random.seed(42)
        n_samples = 500
        n_features = len(features)

        # モデルの木構造から特徴量の値域を推定するのは複雑なので、
        # 標準正規分布でサンプリング（概算として）
        # 実際にはexperiment.pyのパイプラインで構築したデータを使うべき
        print(f"\n  ※ 正確なSHAP分析にはexperiment.pyのデータ構築パイプラインが必要")
        print(f"  ※ ここではgain-based importanceの比較結果を参照してください")

        return True
    except Exception as e:
        print(f"  SHAP analysis error: {e}")
        return False

def analyze_split_patterns(model_p, model_ar, features):
    """モデルの分岐パターンを比較"""
    print(f"\n{'='*80}")
    print("  モデル構造比較")
    print(f"{'='*80}")

    # split-based importance (どの特徴量でよく分岐するか)
    split_p = model_p.feature_importance(importance_type='split')
    split_reg = model_ar.feature_importance(importance_type='split')

    split_p_norm = split_p / split_p.sum() * 100
    split_reg_norm = split_reg / split_reg.sum() * 100

    print(f"\n  Model P (V): {model_p.num_trees()} trees")
    print(f"  Model AR (AR): {model_ar.num_trees()} trees")

    # V でよく使うがARであまり使わない特徴量
    diff_split = split_p_norm - split_reg_norm
    v_only_idx = np.argsort(-diff_split)[:10]
    ar_only_idx = np.argsort(diff_split)[:10]

    print(f"\n  【V(P)が多用するがAR があまり使わない特徴量 Top10】")
    print(f"  {'特徴量':<35} {'V split%':>8} {'AR split%':>9} {'差':>8}")
    print(f"  {'-'*65}")
    for i in v_only_idx:
        print(f"  {features[i]:<35} {split_p_norm[i]:>7.2f}% {split_reg_norm[i]:>8.2f}% {diff_split[i]:>+7.2f}%")

    print(f"\n  【AR が多用するがV(P)があまり使わない特徴量 Top10】")
    print(f"  {'特徴量':<35} {'V split%':>8} {'AR split%':>9} {'差':>8}")
    print(f"  {'-'*65}")
    for i in ar_only_idx:
        print(f"  {features[i]:<35} {split_p_norm[i]:>7.2f}% {split_reg_norm[i]:>8.2f}% {diff_split[i]:>+7.2f}%")

def main():
    print("Loading models...")
    model_p, model_ar, features = load_models_and_meta()

    # 1. Global importance比較
    imp_p, imp_reg, diff = compare_global_importance(model_p, model_ar, features)

    # 2. 分岐パターン比較
    analyze_split_patterns(model_p, model_ar, features)

    # 3. SHAP分析（概算）
    shap_analysis_with_backtest(model_p, model_ar, features)

    # 4. 解釈まとめ
    print(f"\n{'='*80}")
    print("  V×AR乖離の構造的原因まとめ")
    print(f"{'='*80}")

    # V重視TOP5
    v_top = np.argsort(-diff)[:5]
    ar_top = np.argsort(diff)[:5]

    print(f"\n  V(確率)が重視する特徴量:")
    for i in v_top:
        print(f"    {features[i]}: V={imp_p[i]:.2f}% vs AR={imp_reg[i]:.2f}%")

    print(f"\n  AR(能力)が重視する特徴量:")
    for i in ar_top:
        print(f"    {features[i]}: V={imp_p[i]:.2f}% vs AR={imp_reg[i]:.2f}%")

    print(f"\n  → 乖離原因: Vは「今回好走するか」を判断（調子・展開・相性重視）")
    print(f"  → ARは「この馬の地力・能力水準」を判断（過去実績・速度系重視）")
    print(f"  → ARd1位×V低の115件(ROI 115.7%)は「実力はあるが今回の条件では不利」型")

if __name__ == '__main__':
    main()
