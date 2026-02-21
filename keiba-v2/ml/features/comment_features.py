#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
コメントNLP特徴量 (v5.3)

keibabookの3種コメント（厩舎談話、前走インタビュー、次走メモ）を
辞書ベースでスコアリングし、ML特徴量として出力する。

データソース: data3/keibabook/YYYY/MM/DD/kb_ext_{race_id}.json
  → entries[umaban].stable_comment.comment       (厩舎談話)
  → entries[umaban].previous_race_interview.interview   (前走騎手インタビュー)
  → entries[umaban].previous_race_interview.next_race_memo  (次走メモ)
"""

import re

# ============================================================
# 辞書定義
# ============================================================

# --- 仕上がり度（condition）: 全ソース共通 ---
CONDITION_POSITIVE = {
    # +3: 絶好の状態
    '絶好調': 3, '充実': 3, '万全': 3, '申し分': 3, '文句なし': 3,
    '好気配': 3, '最高の状態': 3, '完璧': 3, '好仕上': 3,
    # +2: 好調
    '順調': 2, '仕上がった': 2, '仕上がり': 2, '上向き': 2, '好馬体': 2,
    '整った': 2, '良化': 2, 'いい状態': 2, '動きがいい': 2, '好調': 2,
    'いい感じ': 2, '態勢は整': 2, '上々': 2, '成長': 2, '元気': 2,
    # +1: まずまず
    'まずまず': 1, '変わりない': 1, '悪くない': 1, '安定': 1,
    '落ち着いて': 1, '大きな問題はない': 1, 'キープ': 1, '維持': 1,
}

CONDITION_NEGATIVE = {
    # -1: やや不安
    '余裕残し': -1, '休み明け': -1, '久々': -1, '八分': -1, '緩い': -1,
    '緩さ': -1, '実戦向き': -1,
    # -2: 不安材料あり
    '太め': -2, '叩き台': -2, '物足りない': -2, 'ピリッとしない': -2,
    '不安': -2, '重い': -2, 'ズブい': -2, '使いながら': -2, '使いつつ': -2,
    'ひと叩き': -2, '叩いてから': -2, 'もうひと追い': -2,
    # -3: 明らかに不調
    '調子落ち': -3, '不調': -3, 'ガレ': -3,
}

# --- 自信度（confidence）: 全ソース共通 ---
CONFIDENCE_POSITIVE = {
    # +3: 高い自信
    '楽しみ': 3, '自信': 3, '勝負': 3,
    # +2: 期待感
    '期待': 2, 'やれる': 2, 'チャンス': 2, '面白い': 2, '能力': 2,
    '通用': 2, '狙える': 2, '十分': 2,
    # +1: 控えめな期待
    '見せ場': 1, '頑張': 1, '秘めて': 1,
}

CONFIDENCE_NEGATIVE = {
    # -1: やや弱気
    '展開次第': -1, '恵まれれば': -1, '何とか': -1,
    '相手が強い': -1,
    # -2: 弱気
    '厳しい': -2, '苦しい': -2, '不安': -2, '微妙': -2,
    '力差': -2, '未知数': -2,
    # -3: 諦め
    '静観': -3,
}

# --- 言い訳/エクスキューズ（excuse）: 厩舎談話用 ---
EXCUSE_KEYWORDS = [
    '叩き台', '経験', '勉強', '次に', '次走以降', '様子見',
    '久々なので', '初めてなので', '試し', '使いつつ', '慣らし',
    '上がっていけば',
]

# --- 前走不利・敗因（interview用） ---
INTERVIEW_EXCUSE = {
    # 3: 明確な不利
    '不利': 3, '挟まれ': 3, '壁になっ': 3, '進路': 3, '塞がっ': 3,
    # 2: 不利・ロス
    '出遅れ': 2, '出負け': 2, '包まれ': 2, '外を回': 2, 'ロス': 2,
    '大外': 2, '躓い': 2, '接触': 2,
    # 1: 軽い不利
    '掛かっ': 1, '折り合い': 1, '馬場が': 1, 'モタれ': 1,
    '惜しい': 1, 'スムーズさを欠': 1,
}

# --- レーストラブル/評価（next_race_memo用） ---
MEMO_TROUBLE = {
    # 正: トラブル・不利あり
    '不利': 3, '接触': 3, '落鉄': 3,
    '出遅れ': 2, '挟まれ': 2, '塞がっ': 2, '包まれ': 2,
    '掛かり': 1, '力み': 1,
}

MEMO_POSITIVE = {
    # 負: ポジティブ評価
    '完勝': 3, '快勝': 3, '圧勝': 3,
    '余力': 2, '楽しみ': 2, '通用': 2, '突き抜け': 2,
    '堅実': 1, '渋太': 1,
}

# --- 否定表現 ---
NEGATION_WORDS = ['ない', 'なく', 'なさ', 'ず', '不足', 'いまいち', '今ひとつ', '今いち']
NEGATION_WINDOW = 5  # キーワード末尾から何文字以内の否定を検出するか
NEGATION_REVERSAL = 0.5  # 否定時のスコア反転係数

# --- ヘッダーマーク ---
HEADER_MARK_SCORES = {'◎': 4, '○': 3, '▲': 2, '△': 1}


# ============================================================
# パーサー関数
# ============================================================

def _parse_stable_comment(text: str):
    """厩舎談話をパースして (mark_score, body_text) を返す

    Format例:
      "◎メビウスロマンス【矢嶋師】前走は久々で..."
      "○セディバン【高島助手】もっと走れていい馬..."
    """
    if not text or not text.strip():
        return 0, ''

    text = text.strip()

    # ヘッダーマーク
    mark_score = HEADER_MARK_SCORES.get(text[0], 0)

    # 【】以降をbody（調教師名は除外）
    bracket_match = re.search(r'【[^】]+】', text)
    if bracket_match:
        body = text[bracket_match.end():].strip()
    else:
        # 【】がない場合はマーク+馬名を除去（最初の空白以降）
        body = re.sub(r'^[◎○▲△]?\S*\s*', '', text, count=1).strip()

    return mark_score, body


def _parse_interview(text: str) -> str:
    """前走インタビューからbodyテキストを抽出

    Format例:
      "スーパーガール（４着）Ｒ．キング騎手　スタートはまずまず..."
    """
    if not text or not text.strip():
        return ''

    text = text.strip()

    # 「馬名（着順）騎手名騎手　」パターンを除去
    match = re.match(r'^.+?（\d+着）.+?騎手\s*', text)
    if match:
        return text[match.end():].strip()

    # パターンにマッチしない場合はそのまま
    return text


def _parse_memo(text: str) -> str:
    """次走メモからbodyテキストを抽出

    Format例:
      "トヨサカエ……初出走。太めなく仕上がる。..."
    """
    if not text or not text.strip():
        return ''

    text = text.strip()

    # 「馬名……」プレフィクスを除去
    if '……' in text:
        idx = text.index('……')
        return text[idx + 2:].strip()

    return text


def _check_negation(text: str, keyword: str, match_pos: int) -> bool:
    """キーワードマッチ位置の後方に否定表現があるかチェック"""
    end_pos = match_pos + len(keyword)
    window = text[end_pos:end_pos + NEGATION_WINDOW]
    return any(neg in window for neg in NEGATION_WORDS)


def _score_text(text: str, pos_dict: dict, neg_dict: dict):
    """テキストを辞書でスコアリング

    Returns:
        (net_score, pos_count, neg_count)
    """
    if not text:
        return 0.0, 0, 0

    pos_scores = []
    neg_scores = []

    # ポジティブキーワード検索
    for keyword, score in pos_dict.items():
        idx = text.find(keyword)
        if idx >= 0:
            if _check_negation(text, keyword, idx):
                # 否定されている → 反転して軽減
                neg_scores.append(-score * NEGATION_REVERSAL)
            else:
                pos_scores.append(score)

    # ネガティブキーワード検索
    for keyword, score in neg_dict.items():
        idx = text.find(keyword)
        if idx >= 0:
            if _check_negation(text, keyword, idx):
                # 否定されている → 反転して軽減
                pos_scores.append(-score * NEGATION_REVERSAL)
            else:
                neg_scores.append(score)

    # 集約: 同極性は最大絶対値を採用
    pos_max = max(pos_scores) if pos_scores else 0.0
    neg_max = min(neg_scores) if neg_scores else 0.0

    return pos_max + neg_max, len(pos_scores), len(neg_scores)


def _score_excuse_keywords(text: str, keyword_list: list) -> int:
    """言い訳キーワードの存在チェック (0 or 1)"""
    if not text:
        return 0
    return 1 if any(kw in text for kw in keyword_list) else 0


def _score_interview_excuse(text: str) -> float:
    """前走インタビューの不利/敗因スコア"""
    if not text:
        return 0.0
    scores = []
    for keyword, score in INTERVIEW_EXCUSE.items():
        if keyword in text:
            scores.append(score)
    return max(scores) if scores else 0.0


def _score_memo_trouble(text: str) -> float:
    """次走メモのトラブル/ポジティブスコア

    正=トラブルあり、負=ポジティブ評価
    """
    if not text:
        return 0.0
    trouble_scores = [s for kw, s in MEMO_TROUBLE.items() if kw in text]
    positive_scores = [s for kw, s in MEMO_POSITIVE.items() if kw in text]
    trouble = max(trouble_scores) if trouble_scores else 0.0
    positive = max(positive_scores) if positive_scores else 0.0
    return trouble - positive


# ============================================================
# メイン関数
# ============================================================

def compute_comment_features(
    umaban: str,
    kb_ext: dict | None,
) -> dict:
    """1頭のコメントNLP特徴量を計算

    Args:
        umaban: 馬番（文字列）
        kb_ext: kb_ext JSONの内容（Noneならデータなし）

    Returns:
        dict: 特徴量辞書 (10特徴量)
    """
    default = {
        'comment_stable_condition': None,
        'comment_stable_confidence': None,
        'comment_stable_mark': None,
        'comment_stable_excuse_flag': None,
        'comment_interview_condition': None,
        'comment_interview_excuse_score': None,
        'comment_memo_condition': None,
        'comment_memo_trouble_score': None,
        'comment_has_stable': None,
        'comment_has_interview': None,
    }

    if not kb_ext:
        return default

    entries = kb_ext.get('entries', {})
    entry = entries.get(str(umaban))
    if not entry:
        return default

    result = dict(default)

    # --- 厩舎談話 ---
    stable_data = entry.get('stable_comment') or {}
    stable_text = stable_data.get('comment', '')

    if stable_text and stable_text.strip():
        mark_score, body = _parse_stable_comment(stable_text)
        condition_score, _, _ = _score_text(body, CONDITION_POSITIVE, CONDITION_NEGATIVE)
        confidence_score, _, _ = _score_text(body, CONFIDENCE_POSITIVE, CONFIDENCE_NEGATIVE)
        excuse_flag = _score_excuse_keywords(body, EXCUSE_KEYWORDS)

        result['comment_stable_condition'] = condition_score
        result['comment_stable_confidence'] = confidence_score
        result['comment_stable_mark'] = mark_score
        result['comment_stable_excuse_flag'] = excuse_flag
        result['comment_has_stable'] = 1
    else:
        result['comment_has_stable'] = 0

    # --- 前走インタビュー ---
    interview_data = entry.get('previous_race_interview') or {}
    interview_text = interview_data.get('interview', '')

    if interview_text and interview_text.strip():
        body = _parse_interview(interview_text)
        condition_score, _, _ = _score_text(body, CONDITION_POSITIVE, CONDITION_NEGATIVE)
        excuse_score = _score_interview_excuse(body)

        result['comment_interview_condition'] = condition_score
        result['comment_interview_excuse_score'] = excuse_score
        result['comment_has_interview'] = 1
    else:
        result['comment_has_interview'] = 0

    # --- 次走メモ ---
    memo_text = interview_data.get('next_race_memo', '')

    if memo_text and memo_text.strip():
        body = _parse_memo(memo_text)
        condition_score, _, _ = _score_text(body, CONDITION_POSITIVE, CONDITION_NEGATIVE)
        trouble_score = _score_memo_trouble(body)

        result['comment_memo_condition'] = condition_score
        result['comment_memo_trouble_score'] = trouble_score

    return result
