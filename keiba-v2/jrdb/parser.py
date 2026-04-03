#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
JRDB固定長テキストパーサー

SED（成績データ）とKYI（競走馬データ）をパースし、
既存のKeibaCICD race_id / ketto_numと結合可能な形式で返す。

JRDBレースキー: 場コード(2) + 年(2) + 回(1) + 日(1,hex) + R(2) = 8バイト
KeibaCICD race_id: YYYYMMDDJJKKNNRR = 16桁

結合方式:
  - 血統登録番号(8桁) → KeibaCICDのketto_num(10桁)の末尾8桁 or 先頭2桁="00"+8桁
  - レースキー → 日付+場コード+R番号で既存race_idとマッチ
  - 最も確実: 日付 + 馬番 + 馬名 でクロスチェック
"""

from pathlib import Path
from typing import Dict, List, Optional

# JRDB場コード → JRA-VAN場コード / 場名
JRDB_VENUE_MAP = {
    '01': ('01', '札幌'), '02': ('02', '函館'), '03': ('03', '福島'),
    '04': ('04', '新潟'), '05': ('05', '東京'), '06': ('06', '中山'),
    '07': ('07', '中京'), '08': ('08', '京都'), '09': ('09', '阪神'),
    '10': ('10', '小倉'),
}

RAW_DIR = Path('C:/KEIBA-CICD/data3/jrdb/raw')


def _safe_int(s: str, default: int = 0) -> int:
    """安全なint変換"""
    s = s.strip()
    if not s or s == '-':
        return default
    try:
        return int(s)
    except ValueError:
        return default


def _safe_float(s: str, default: float = None) -> Optional[float]:
    """安全なfloat変換"""
    s = s.strip()
    if not s or s == '-':
        return default
    try:
        return float(s)
    except ValueError:
        return default


def _hex_to_int(s: str) -> int:
    """16進数1桁→int (JRDB日フィールド用)
    '1'-'9'→1-9, 'a'→10, 'b'→11, ..., 'f'→15
    """
    try:
        return int(s, 16)
    except ValueError:
        return 0


def parse_jrdb_race_key(key: str) -> dict:
    """JRDBレースキー(8バイト) → 構造化

    場コード(2) + 年(2) + 回(1) + 日(1,hex) + R(2)
    例: "06250101" → 場=中山, 年=25(2025), 回=1, 日=1, R=01
    """
    venue_code = key[0:2]
    year_2d = key[2:4]
    kai = key[4:5]
    nichi_hex = key[5:6]
    race_num = key[6:8]

    year = 2000 + int(year_2d) if int(year_2d) < 80 else 1900 + int(year_2d)
    nichi = _hex_to_int(nichi_hex)

    venue_info = JRDB_VENUE_MAP.get(venue_code, (venue_code, '不明'))

    return {
        'jrdb_race_key': key,
        'venue_code': venue_code,
        'venue_name': venue_info[1],
        'year': year,
        'kai': int(kai),
        'nichi': nichi,
        'race_num': int(race_num),
    }


def parse_sed_line(line: bytes) -> Optional[dict]:
    """SED固定長1行(376バイト) → dict

    成績データ: レース事後のIDM・各種指数を含む
    """
    if len(line) < 370:
        return None

    race_key = line[0:8].decode('ascii', errors='replace')
    umaban = _safe_int(line[8:10].decode('ascii', errors='replace'))
    ketto_num = line[10:18].decode('ascii', errors='replace').strip()
    date_str = line[18:26].decode('ascii', errors='replace').strip()
    horse_name = line[26:62].decode('shift_jis', errors='replace').strip()

    # レース条件
    distance = _safe_int(line[62:66].decode('ascii', errors='replace'))
    track_code = _safe_int(line[66:67].decode('ascii', errors='replace'))  # 1:芝,2:ダ,3:障
    baba_code = _safe_int(line[69:71].decode('ascii', errors='replace'))
    grade = _safe_int(line[79:80].decode('ascii', errors='replace'))
    num_runners = _safe_int(line[130:132].decode('ascii', errors='replace'))

    # 成績
    finish_position = _safe_int(line[140:142].decode('ascii', errors='replace'))
    abnormal = _safe_int(line[142:143].decode('ascii', errors='replace'))  # 異常区分
    time_raw = line[143:147].decode('ascii', errors='replace').strip()
    futan = _safe_float(line[147:150].decode('ascii', errors='replace'))  # 0.1kg単位
    if futan:
        futan = futan / 10.0

    # 確定オッズ
    odds_str = line[174:180].decode('ascii', errors='replace').strip()
    odds = _safe_float(odds_str)
    popularity = _safe_int(line[180:182].decode('ascii', errors='replace'))

    # === JRDB指数 (事後IDM) ===
    idm = _safe_int(line[182:185].decode('ascii', errors='replace'))
    soten = _safe_int(line[185:188].decode('ascii', errors='replace'))  # 素点
    baba_sa = _safe_int(line[188:191].decode('ascii', errors='replace'))  # 馬場差
    pace_adj = _safe_int(line[191:194].decode('ascii', errors='replace'))  # ペース
    deokure = _safe_int(line[194:197].decode('ascii', errors='replace'))  # 出遅
    ichi_tori = _safe_int(line[197:200].decode('ascii', errors='replace'))  # 位置取
    furi = _safe_int(line[200:203].decode('ascii', errors='replace'))  # 不利
    mae_furi = _safe_int(line[203:206].decode('ascii', errors='replace'))  # 前不利
    naka_furi = _safe_int(line[206:209].decode('ascii', errors='replace'))  # 中不利
    ato_furi = _safe_int(line[209:212].decode('ascii', errors='replace'))  # 後不利
    race_adj = _safe_int(line[212:215].decode('ascii', errors='replace'))  # レース

    course_tori = _safe_int(line[215:216].decode('ascii', errors='replace'))  # コース取り
    joushou = _safe_int(line[216:217].decode('ascii', errors='replace'))  # 上昇度コード

    race_pace = line[221:222].decode('ascii', errors='replace').strip()  # H/M/S
    horse_pace = line[222:223].decode('ascii', errors='replace').strip()

    ten_idx = _safe_float(line[223:228].decode('ascii', errors='replace'))  # テン指数
    agari_idx = _safe_float(line[228:233].decode('ascii', errors='replace'))  # 上がり指数
    pace_idx = _safe_float(line[233:238].decode('ascii', errors='replace'))  # ペース指数
    race_pace_idx = _safe_float(line[238:243].decode('ascii', errors='replace'))  # レースP指数

    front_3f = _safe_int(line[258:261].decode('ascii', errors='replace'))  # 前3Fタイム (0.1秒)
    rear_3f = _safe_int(line[261:264].decode('ascii', errors='replace'))  # 後3Fタイム (0.1秒)

    # 第2版追加
    place_odds = _safe_float(line[290:296].decode('ascii', errors='replace'))  # 確定複勝オッズ下
    corner1 = _safe_int(line[308:310].decode('ascii', errors='replace'))
    corner2 = _safe_int(line[310:312].decode('ascii', errors='replace'))
    corner3 = _safe_int(line[312:314].decode('ascii', errors='replace'))
    corner4 = _safe_int(line[314:316].decode('ascii', errors='replace'))

    jockey_code = line[322:327].decode('ascii', errors='replace').strip()
    trainer_code = line[327:332].decode('ascii', errors='replace').strip()

    # 第3版追加
    horse_weight = _safe_int(line[332:335].decode('ascii', errors='replace'))

    # 日付パース
    race_date = ''
    if len(date_str) == 8:
        race_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

    return {
        'jrdb_race_key': race_key,
        'umaban': umaban,
        'ketto_num_jrdb': ketto_num,  # JRDB血統登録番号 (8桁)
        'race_date': race_date,
        'horse_name': horse_name,
        'distance': distance,
        'track_code': track_code,  # 1:芝, 2:ダート, 3:障害
        'num_runners': num_runners,
        'finish_position': finish_position,
        'abnormal': abnormal,
        'futan': futan,
        'odds': odds,
        'popularity': popularity,
        # === JRDB IDM & 指数 (事後) ===
        'idm': idm,
        'soten': soten,
        'baba_sa': baba_sa,
        'pace_adj': pace_adj,
        'deokure_adj': deokure,
        'ichi_tori_adj': ichi_tori,
        'furi_adj': furi,
        'mae_furi_adj': mae_furi,
        'naka_furi_adj': naka_furi,
        'ato_furi_adj': ato_furi,
        'race_adj': race_adj,
        'course_tori': course_tori,
        'joushou_code': joushou,
        'race_pace': race_pace,
        'horse_pace': horse_pace,
        'ten_idx': ten_idx,
        'agari_idx': agari_idx,
        'pace_idx': pace_idx,
        'race_pace_idx': race_pace_idx,
        'front_3f': front_3f / 10.0 if front_3f else None,
        'rear_3f': rear_3f / 10.0 if rear_3f else None,
        'corner1': corner1,
        'corner2': corner2,
        'corner3': corner3,
        'corner4': corner4,
        'jockey_code': jockey_code,
        'trainer_code': trainer_code,
        'horse_weight': horse_weight,
        'place_odds_low': place_odds,
    }


def parse_kyi_line(line: bytes) -> Optional[dict]:
    """KYI固定長1行(1024バイト) → dict

    競走馬データ: レース事前のIDM予測値・展開予想を含む
    仕様書は1-based、Python sliceは0-based (相対N → line[N-1:N-1+LEN])
    """
    if len(line) < 620:
        return None

    race_key = line[0:8].decode('ascii', errors='replace')
    umaban = _safe_int(line[8:10].decode('ascii', errors='replace'))
    ketto_num = line[10:18].decode('ascii', errors='replace').strip()
    horse_name = line[18:54].decode('shift_jis', errors='replace').strip()

    # === JRDB指数 (事前) ===
    idm = _safe_float(line[54:59].decode('ascii', errors='replace'))
    jockey_idx = _safe_float(line[59:64].decode('ascii', errors='replace'))
    info_idx = _safe_float(line[64:69].decode('ascii', errors='replace'))
    sogo_idx = _safe_float(line[84:89].decode('ascii', errors='replace'))  # 総合指数

    kyakushitsu = _safe_int(line[89:90].decode('ascii', errors='replace'))  # 脚質
    distance_aptitude = _safe_int(line[90:91].decode('ascii', errors='replace'))  # 距離適性
    rotation = _safe_int(line[92:95].decode('ascii', errors='replace'))  # ローテーション(金曜日数)

    base_odds = _safe_float(line[95:100].decode('ascii', errors='replace'))  # 基準オッズ
    base_popularity = _safe_int(line[100:102].decode('ascii', errors='replace'))  # 基準人気
    base_place_odds = _safe_float(line[102:107].decode('ascii', errors='replace'))  # 基準複勝オッズ
    base_place_popularity = _safe_int(line[107:109].decode('ascii', errors='replace'))  # 基準複勝人気

    # 特定情報印（専門紙の印数を集約）
    tokutei_mark_honmei = _safe_int(line[109:112].decode('ascii', errors='replace'))  # ◎の数
    tokutei_mark_taikou = _safe_int(line[112:115].decode('ascii', errors='replace'))  # ○の数
    tokutei_mark_tanana = _safe_int(line[115:118].decode('ascii', errors='replace'))  # ▲の数
    tokutei_mark_renka = _safe_int(line[118:121].decode('ascii', errors='replace'))   # △の数
    tokutei_mark_hoshi = _safe_int(line[121:124].decode('ascii', errors='replace'))   # ×の数
    # 総合情報印
    sogo_mark_honmei = _safe_int(line[124:127].decode('ascii', errors='replace'))     # ◎の数
    sogo_mark_taikou = _safe_int(line[127:130].decode('ascii', errors='replace'))     # ○の数
    sogo_mark_tanana = _safe_int(line[130:133].decode('ascii', errors='replace'))     # ▲の数
    sogo_mark_renka = _safe_int(line[133:136].decode('ascii', errors='replace'))      # △の数
    sogo_mark_hoshi = _safe_int(line[136:139].decode('ascii', errors='replace'))      # ×の数

    ninki_idx = _safe_int(line[139:144].decode('ascii', errors='replace'))  # 人気指数

    training_idx = _safe_float(line[144:149].decode('ascii', errors='replace'))  # 調教指数
    stable_idx = _safe_float(line[149:154].decode('ascii', errors='replace'))  # 厩舎指数

    # 第3版追加
    training_arrow = _safe_int(line[154:155].decode('ascii', errors='replace'))  # 調教矢印コード
    stable_eval = _safe_int(line[155:156].decode('ascii', errors='replace'))  # 厩舎評価コード
    jockey_rentairitsu = _safe_float(line[156:160].decode('ascii', errors='replace'))  # 騎手期待連対率
    gekisou_idx = _safe_int(line[160:163].decode('ascii', errors='replace'))  # 激走指数
    hizume_code = _safe_int(line[163:165].decode('ascii', errors='replace'))  # 蹄コード
    omo_tekisei = _safe_int(line[165:166].decode('ascii', errors='replace'))  # 重適正コード

    # 第4版追加
    blinker = line[170:171].decode('ascii', errors='replace').strip()  # ブリンカー 1:初,2:再,3:継続

    jockey_code = line[335:340].decode('ascii', errors='replace').strip()
    trainer_code = line[340:345].decode('ascii', errors='replace').strip()

    # 第5版追加 — 印コード
    mark_sogo = _safe_int(line[326:327].decode('ascii', errors='replace'))      # 総合印
    mark_idm = _safe_int(line[327:328].decode('ascii', errors='replace'))       # IDM印
    mark_info = _safe_int(line[328:329].decode('ascii', errors='replace'))      # 情報印
    mark_jockey = _safe_int(line[329:330].decode('ascii', errors='replace'))    # 騎手印
    mark_stable = _safe_int(line[330:331].decode('ascii', errors='replace'))    # 厩舎印
    mark_training = _safe_int(line[331:332].decode('ascii', errors='replace'))  # 調教印
    mark_gekisou = _safe_int(line[332:333].decode('ascii', errors='replace'))   # 激走印(1:激走馬)

    # 芝適性/ダ適性コード
    turf_aptitude = line[333:334].decode('ascii', errors='replace').strip()     # 1:◎, 2:○, 3:△
    dirt_aptitude = line[334:335].decode('ascii', errors='replace').strip()     # 1:◎, 2:○, 3:△

    # 展開予想データ (第6版)
    pred_ten_idx = _safe_float(line[358:363].decode('ascii', errors='replace'))
    pred_pace_idx = _safe_float(line[363:368].decode('ascii', errors='replace'))
    pred_agari_idx = _safe_float(line[368:373].decode('ascii', errors='replace'))
    pred_position_idx = _safe_float(line[373:378].decode('ascii', errors='replace'))
    pred_pace = line[378:379].decode('ascii', errors='replace').strip()  # H/M/S

    # 展開予想詳細 (第6版)
    pred_dochu_order = _safe_int(line[379:381].decode('ascii', errors='replace'))   # 道中順位
    pred_dochu_diff = _safe_int(line[381:383].decode('ascii', errors='replace'))    # 道中差(半馬身単位)
    pred_dochu_uchi_soto = _safe_int(line[383:384].decode('ascii', errors='replace'))  # 道中内外
    pred_3f_order = _safe_int(line[384:386].decode('ascii', errors='replace'))      # 後3F順位
    pred_3f_diff = _safe_int(line[386:388].decode('ascii', errors='replace'))       # 後3F差(半馬身単位)
    pred_3f_uchi_soto = _safe_int(line[388:389].decode('ascii', errors='replace'))  # 後3F内外
    pred_goal_order = _safe_int(line[389:391].decode('ascii', errors='replace'))    # ゴール順位
    pred_goal_diff = _safe_int(line[391:393].decode('ascii', errors='replace'))     # ゴール差(半馬身単位)
    pred_goal_uchi_soto = _safe_int(line[393:394].decode('ascii', errors='replace'))  # ゴール内外
    tenkai_kigou = line[394:395].decode('ascii', errors='replace').strip()           # 展開記号

    # 第6a版
    distance_aptitude2 = _safe_int(line[395:396].decode('ascii', errors='replace'))  # 距離適性2
    wakutei_weight = _safe_int(line[396:399].decode('ascii', errors='replace'))  # 枠確定馬体重
    wakutei_weight_diff = line[399:402].decode('ascii', errors='replace').strip()  # 枠確定馬体重増減

    # 第7版追加 — 各指数順位
    gekisou_rank = _safe_int(line[448:450].decode('ascii', errors='replace'))      # 激走順位
    ls_idx_rank = _safe_int(line[450:452].decode('ascii', errors='replace'))       # LS指数順位
    ten_idx_rank = _safe_int(line[452:454].decode('ascii', errors='replace'))      # テン指数順位
    pace_idx_rank = _safe_int(line[454:456].decode('ascii', errors='replace'))     # ペース指数順位
    agari_idx_rank = _safe_int(line[456:458].decode('ascii', errors='replace'))    # 上がり指数順位
    position_idx_rank = _safe_int(line[458:460].decode('ascii', errors='replace'))  # 位置指数順位

    # 第8版追加
    jockey_expected_win_rate = _safe_float(line[460:464].decode('ascii', errors='replace'))   # 騎手期待単勝率
    jockey_expected_place_rate = _safe_float(line[464:468].decode('ascii', errors='replace'))  # 騎手期待3着内率
    yusou_kubun = line[468:469].decode('ascii', errors='replace').strip()  # 輸送区分

    # 馬スタート指数・出遅率 (第9版)
    start_idx = _safe_float(line[519:523].decode('ascii', errors='replace'))
    deokure_rate = _safe_float(line[523:527].decode('ascii', errors='replace'))

    # 万券指数/万券印
    manken_idx = _safe_int(line[534:537].decode('ascii', errors='replace'))  # 万券指数
    manken_mark = _safe_int(line[537:538].decode('ascii', errors='replace'))  # 万券印

    # 第10版追加
    koukyu_flag = _safe_int(line[538:539].decode('ascii', errors='replace'))  # 降級フラグ 1:降級,2:2段階
    gekisou_type = line[539:541].decode('ascii', errors='replace').strip()  # 激走タイプ
    kyuuyou_reason = _safe_int(line[541:543].decode('ascii', errors='replace'))  # 休養理由分類コード

    # フラグ (第11版) — 初芝/初ダ/初障害等
    flags = line[543:559].decode('ascii', errors='replace').strip()

    # 入厩情報 (第11版)
    nyuukyuu_num_runs = _safe_int(line[559:561].decode('ascii', errors='replace'))  # 入厩何走目
    nyuukyuu_date = line[561:569].decode('ascii', errors='replace').strip()  # 入厩年月日(YYYYMMDD)
    nyuukyuu_days_before = _safe_int(line[569:572].decode('ascii', errors='replace'))  # 入厩何日前

    # 放牧先ランク/厩舎ランク
    houboku_rank = line[622:623].decode('ascii', errors='replace').strip()  # 放牧先ランク(A-E)
    kyuusha_rank = _safe_int(line[623:624].decode('ascii', errors='replace'))  # 厩舎ランク(1-9)

    return {
        'jrdb_race_key': race_key,
        'umaban': umaban,
        'ketto_num_jrdb': ketto_num,
        'horse_name': horse_name,
        # === JRDB指数 (事前) ===
        'pre_idm': idm,
        'jockey_idx': jockey_idx,
        'info_idx': info_idx,
        'sogo_idx': sogo_idx,
        'training_idx': training_idx,
        'stable_idx': stable_idx,
        'gekisou_idx': gekisou_idx,
        'ninki_idx': ninki_idx,
        # 調教・厩舎詳細
        'training_arrow': training_arrow,          # 調教矢印コード
        'stable_eval': stable_eval,                # 厩舎評価コード
        'jockey_rentairitsu': jockey_rentairitsu,  # 騎手期待連対率
        # 展開予想
        'pred_ten_idx': pred_ten_idx,
        'pred_pace_idx': pred_pace_idx,
        'pred_agari_idx': pred_agari_idx,
        'pred_position_idx': pred_position_idx,
        'pred_pace': pred_pace,
        # 展開予想詳細
        'pred_dochu_order': pred_dochu_order,          # 道中予想順位
        'pred_dochu_diff': pred_dochu_diff,            # 道中差(半馬身)
        'pred_dochu_uchi_soto': pred_dochu_uchi_soto,  # 道中内外
        'pred_3f_order': pred_3f_order,                # 後3F予想順位
        'pred_3f_diff': pred_3f_diff,                  # 後3F差(半馬身)
        'pred_3f_uchi_soto': pred_3f_uchi_soto,        # 後3F内外
        'pred_goal_order': pred_goal_order,            # ゴール予想順位
        'pred_goal_diff': pred_goal_diff,              # ゴール差(半馬身)
        'pred_goal_uchi_soto': pred_goal_uchi_soto,    # ゴール内外
        'tenkai_kigou': tenkai_kigou,                  # 展開記号
        # 脚質・適性
        'kyakushitsu': kyakushitsu,
        'distance_aptitude': distance_aptitude,
        'distance_aptitude2': distance_aptitude2,
        'turf_aptitude': turf_aptitude,    # 芝適性(1:◎,2:○,3:△)
        'dirt_aptitude': dirt_aptitude,     # ダ適性(1:◎,2:○,3:△)
        'omo_tekisei': omo_tekisei,        # 重適正コード
        'hizume_code': hizume_code,        # 蹄コード
        # 基準オッズ
        'base_odds': base_odds,
        'base_popularity': base_popularity,
        'base_place_odds': base_place_odds,
        'base_place_popularity': base_place_popularity,
        'rotation': rotation,              # ローテーション(金曜日数)
        # 専門紙印 — 特定情報
        'tokutei_honmei': tokutei_mark_honmei,  # ◎の数
        'tokutei_taikou': tokutei_mark_taikou,  # ○の数
        'tokutei_tanana': tokutei_mark_tanana,  # ▲の数
        'tokutei_renka': tokutei_mark_renka,    # △の数
        'tokutei_hoshi': tokutei_mark_hoshi,    # ×の数
        # 専門紙印 — 総合情報
        'sogo_honmei': sogo_mark_honmei,        # ◎の数
        'sogo_taikou': sogo_mark_taikou,        # ○の数
        'sogo_tanana': sogo_mark_tanana,        # ▲の数
        'sogo_renka': sogo_mark_renka,          # △の数
        'sogo_hoshi': sogo_mark_hoshi,          # ×の数
        # JRDB印コード
        'mark_sogo': mark_sogo,            # 総合印
        'mark_idm': mark_idm,              # IDM印
        'mark_info': mark_info,            # 情報印
        'mark_jockey': mark_jockey,        # 騎手印
        'mark_stable': mark_stable,        # 厩舎印
        'mark_training': mark_training,    # 調教印
        'mark_gekisou': mark_gekisou,      # 激走印(1:激走馬)
        # 馬具・装備
        'blinker': blinker,                # ブリンカー(1:初,2:再,3:継続)
        # 各指数順位
        'gekisou_rank': gekisou_rank,
        'ls_idx_rank': ls_idx_rank,
        'ten_idx_rank': ten_idx_rank,
        'pace_idx_rank': pace_idx_rank,
        'agari_idx_rank': agari_idx_rank,
        'position_idx_rank': position_idx_rank,
        # 騎手期待値
        'jockey_expected_win_rate': jockey_expected_win_rate,
        'jockey_expected_place_rate': jockey_expected_place_rate,
        'yusou_kubun': yusou_kubun,        # 輸送区分
        # スタート
        'start_idx': start_idx,
        'deokure_rate': deokure_rate,
        # 万券指数
        'manken_idx': manken_idx,          # 万券指数
        'manken_mark': manken_mark,        # 万券印
        # 降級・激走タイプ
        'koukyu_flag': koukyu_flag,        # 降級フラグ(1:降級,2:2段階)
        'gekisou_type': gekisou_type,      # 激走タイプ
        'kyuuyou_reason': kyuuyou_reason,  # 休養理由分類コード
        # フラグ
        'flags': flags,
        # 入厩情報
        'nyuukyuu_num_runs': nyuukyuu_num_runs,    # 入厩何走目
        'nyuukyuu_date': nyuukyuu_date,            # 入厩年月日
        'nyuukyuu_days_before': nyuukyuu_days_before,  # 入厩何日前
        # 放牧先・厩舎
        'houboku_rank': houboku_rank,      # 放牧先ランク(A-E)
        'kyuusha_rank': kyuusha_rank,      # 厩舎ランク(1-9)
        # 馬体重
        'wakutei_weight': wakutei_weight,          # 枠確定馬体重
        'wakutei_weight_diff': wakutei_weight_diff,  # 枠確定馬体重増減
        # リンクキー
        'jockey_code': jockey_code,
        'trainer_code': trainer_code,
    }


def parse_kaa_line(line: bytes) -> Optional[dict]:
    """KAA固定長1行(54バイト) → dict

    開催データ: 馬場状態・天候・トラックバイアスを含む
    スペック相対位置は1-based → Python 0-based に変換
    """
    if len(line) < 49:
        return None

    venue_code = line[0:2].decode('ascii', errors='replace').strip()
    yy = line[2:4].decode('ascii', errors='replace')
    kai = line[4:5].decode('ascii', errors='replace')
    nichi_hex = line[5:6].decode('ascii', errors='replace')
    date_str = line[6:14].decode('ascii', errors='replace').strip()  # YYYYMMDD

    if not date_str or len(date_str) != 8:
        return None

    # 日付をYYYY-MM-DD形式に
    race_date = '%s-%s-%s' % (date_str[:4], date_str[4:6], date_str[6:8])

    kaisai_kubun = _safe_int(line[14:15].decode('ascii', errors='replace'))  # 1:関東 2:関西 3:ローカル
    venue_name = line[17:21].decode('shift_jis', errors='replace').strip()
    weather_code = _safe_int(line[21:22].decode('ascii', errors='replace'))

    # 芝馬場
    turf_condition_code = _safe_int(line[22:24].decode('ascii', errors='replace'))
    turf_inner = _safe_int(line[24:25].decode('ascii', errors='replace'))   # 1:絶好 2:良 3:稍荒 4:荒
    turf_middle = _safe_int(line[25:26].decode('ascii', errors='replace'))
    turf_outer = _safe_int(line[26:27].decode('ascii', errors='replace'))
    turf_sa = _safe_int(line[27:30].decode('ascii', errors='replace'))      # 馬場差

    # 直線馬場差 (5ポジション: 最内/内/中/外/大外)
    straight_innermost = _safe_int(line[30:32].decode('ascii', errors='replace'))
    straight_inner = _safe_int(line[32:34].decode('ascii', errors='replace'))
    straight_middle = _safe_int(line[34:36].decode('ascii', errors='replace'))
    straight_outer = _safe_int(line[36:38].decode('ascii', errors='replace'))
    straight_outermost = _safe_int(line[38:40].decode('ascii', errors='replace'))

    # ダート馬場
    dirt_condition_code = _safe_int(line[40:42].decode('ascii', errors='replace'))
    dirt_inner = _safe_int(line[42:43].decode('ascii', errors='replace'))
    dirt_middle = _safe_int(line[43:44].decode('ascii', errors='replace'))
    dirt_outer = _safe_int(line[44:45].decode('ascii', errors='replace'))
    dirt_sa = _safe_int(line[45:48].decode('ascii', errors='replace'))

    data_kubun = _safe_int(line[48:49].decode('ascii', errors='replace'))   # 1:特別登録 2:想定確定 3:枠確定 4:前日

    return {
        'venue_code': venue_code,
        'venue_name': venue_name,
        'race_date': race_date,
        'kai': kai,
        'nichi_hex': nichi_hex,
        'kaisai_kubun': kaisai_kubun,
        'weather_code': weather_code,
        # 芝馬場
        'turf_condition_code': turf_condition_code,
        'turf_inner': turf_inner,
        'turf_middle': turf_middle,
        'turf_outer': turf_outer,
        'turf_sa': turf_sa,
        # 直線馬場差 (ポジション別バイアス)
        'straight_innermost': straight_innermost,
        'straight_inner': straight_inner,
        'straight_middle': straight_middle,
        'straight_outer': straight_outer,
        'straight_outermost': straight_outermost,
        # ダート馬場
        'dirt_condition_code': dirt_condition_code,
        'dirt_inner': dirt_inner,
        'dirt_middle': dirt_middle,
        'dirt_outer': dirt_outer,
        'dirt_sa': dirt_sa,
        # データ区分
        'data_kubun': data_kubun,
    }


def parse_srb_line(line: bytes) -> Optional[dict]:
    """SRB固定長1行(852バイト) → dict

    成績レースデータ: ハロンタイム・コーナー順位・トラックバイアス・レースコメント
    1レース/1レコード。SED.lzhに同梱。
    仕様書は1-based、Python sliceは0-based
    """
    if len(line) < 340:
        return None

    race_key = line[0:8].decode('ascii', errors='replace')

    # ハロンタイム 18区間 (3バイト×18 = 54バイト, 位置9-62 → 8:62)
    furlong_times = []
    for i in range(18):
        offset = 8 + i * 3
        t = _safe_int(line[offset:offset+3].decode('ascii', errors='replace'))
        furlong_times.append(t if t > 0 else None)  # 0.1秒単位, 0=データなし

    # コーナー位置取り (各64バイトの文字列)
    corner1_pos = line[62:126].decode('shift_jis', errors='replace').strip()
    corner2_pos = line[126:190].decode('shift_jis', errors='replace').strip()
    corner3_pos = line[190:254].decode('shift_jis', errors='replace').strip()
    corner4_pos = line[254:318].decode('shift_jis', errors='replace').strip()

    # ペースアップ位置 (残りハロン数)
    pace_up_position = _safe_int(line[318:320].decode('ascii', errors='replace'))

    # トラックバイアス (1角-直線 × 内中外)
    # 芝: 1:良好(伸びる), 2:硬い, 3:普通, 4:荒れ, 5:ボロボロ
    # ダート: 1:有利, 2:普通, 3:不利
    bias_1corner = line[320:323].decode('ascii', errors='replace').strip()  # 内中外
    bias_2corner = line[323:326].decode('ascii', errors='replace').strip()
    bias_mukousei = line[326:329].decode('ascii', errors='replace').strip()  # 向正面
    bias_3corner = line[329:332].decode('ascii', errors='replace').strip()
    bias_4corner = line[332:337].decode('ascii', errors='replace').strip()  # 最内内中外大外
    bias_straight = line[337:342].decode('ascii', errors='replace').strip()  # 最内内中外大外

    # レースコメント (500バイト)
    race_comment = ''
    if len(line) >= 842:
        race_comment = line[342:842].decode('shift_jis', errors='replace').strip()

    return {
        'jrdb_race_key': race_key,
        'furlong_times': furlong_times,          # 18区間のハロンタイム(0.1秒単位)
        'corner1_positions': corner1_pos,        # 1角通過順位
        'corner2_positions': corner2_pos,        # 2角通過順位
        'corner3_positions': corner3_pos,        # 3角通過順位
        'corner4_positions': corner4_pos,        # 4角通過順位
        'pace_up_position': pace_up_position,    # ペースアップ位置(残りハロン数)
        'bias_1corner': bias_1corner,            # 1角バイアス
        'bias_2corner': bias_2corner,            # 2角バイアス
        'bias_mukousei': bias_mukousei,          # 向正面バイアス
        'bias_3corner': bias_3corner,            # 3角バイアス
        'bias_4corner': bias_4corner,            # 4角バイアス(5区画)
        'bias_straight': bias_straight,          # 直線バイアス(5区画)
        'race_comment': race_comment,            # レースコメント(500字)
    }


def _parse_zz9x4(line: bytes, offset: int) -> list:
    """ZZ9*4 (12 bytes → 4 integers: 1着, 2着, 3着, 着外)"""
    return [
        _safe_int(line[offset:offset+3].decode('ascii', errors='replace')),
        _safe_int(line[offset+3:offset+6].decode('ascii', errors='replace')),
        _safe_int(line[offset+6:offset+9].decode('ascii', errors='replace')),
        _safe_int(line[offset+9:offset+12].decode('ascii', errors='replace')),
    ]


def parse_cyb_line(line: bytes) -> Optional[dict]:
    """CYB固定長1行(94バイト) → dict

    調教分析データ: 調教タイプ・追切指数・仕上指数を含む
    仕様書レコード長: 96バイト (94 + CRLF 2)
    """
    if len(line) < 90:
        return None

    race_key = line[0:8].decode('ascii', errors='replace')
    umaban = _safe_int(line[8:10].decode('ascii', errors='replace'))

    training_type = line[10:12].decode('ascii', errors='replace').strip()  # 01-11
    course_type = _safe_int(line[12:13].decode('ascii', errors='replace'))  # 1:坂路,2:コース,3:併用,4:障害,5:障害併,0:無

    # 調教回数 (各コース)
    turf = _safe_int(line[13:15].decode('ascii', errors='replace'))       # 芝
    wood = _safe_int(line[15:17].decode('ascii', errors='replace'))       # ウッド
    dirt = _safe_int(line[17:19].decode('ascii', errors='replace'))       # ダート
    obstacle = _safe_int(line[19:21].decode('ascii', errors='replace'))   # 障コース
    pool = _safe_int(line[21:23].decode('ascii', errors='replace'))       # プール
    obstacle_flat = _safe_int(line[23:25].decode('ascii', errors='replace'))  # 障害坂路
    polytrack = _safe_int(line[25:27].decode('ascii', errors='replace'))  # ポリトラック

    training_volume = _safe_int(line[27:28].decode('ascii', errors='replace'))   # 1:多量,2:普通,3:少量,4:2本,0:無
    training_emphasis = _safe_int(line[28:29].decode('ascii', errors='replace'))  # 1:テン,2:中間,3:終い,4:均一,0:無

    oikiri_idx = _safe_int(line[29:32].decode('ascii', errors='replace'))   # 追切指数 (基準60)
    shiage_idx = _safe_int(line[32:35].decode('ascii', errors='replace'))   # 仕上指数 (基準60)

    training_eval_class = line[35:36].decode('ascii', errors='replace').strip()  # A,B,C,D
    shiage_change = _safe_int(line[36:37].decode('ascii', errors='replace'))     # 1:++,2:+,3:不変,4:-

    training_comment = line[37:77].decode('shift_jis', errors='replace').strip()
    comment_date = line[77:85].decode('ascii', errors='replace').strip()

    training_eval = _safe_int(line[85:86].decode('ascii', errors='replace'))  # 1:良,2:可,3:悪

    oikiri_idx_prev_week = _safe_int(line[86:89].decode('ascii', errors='replace'))   # 一週前追切指数
    oikiri_course_prev_week = _safe_int(line[89:91].decode('ascii', errors='replace'))  # 一週前追切コース

    return {
        'jrdb_race_key': race_key,
        'umaban': umaban,
        'training_type': training_type,
        'course_type': course_type,
        'turf_count': turf,
        'wood_count': wood,
        'dirt_count': dirt,
        'obstacle_count': obstacle,
        'pool_count': pool,
        'obstacle_flat_count': obstacle_flat,
        'polytrack_count': polytrack,
        'training_volume': training_volume,
        'training_emphasis': training_emphasis,
        'oikiri_idx': oikiri_idx,
        'shiage_idx': shiage_idx,
        'training_eval_class': training_eval_class,
        'shiage_change': shiage_change,
        'training_comment': training_comment,
        'comment_date': comment_date,
        'training_eval': training_eval,
        'oikiri_idx_prev_week': oikiri_idx_prev_week,
        'oikiri_course_prev_week': oikiri_course_prev_week,
    }


def parse_cha_line(line: bytes) -> Optional[dict]:
    """CHA固定長1行(62バイト) → dict

    本追切データ: 追切タイム・指数を含む
    仕様書レコード長: 64バイト (62 + CRLF 2)
    """
    if len(line) < 55:
        return None

    race_key = line[0:8].decode('ascii', errors='replace')
    umaban = _safe_int(line[8:10].decode('ascii', errors='replace'))

    youbi = line[10:12].decode('shift_jis', errors='replace').strip()      # 土/日
    training_date = line[12:20].decode('ascii', errors='replace').strip()   # YYYYMMDD
    kai = _safe_int(line[20:21].decode('ascii', errors='replace'))          # 追切回数合計
    oikiri_course = line[21:23].decode('ascii', errors='replace').strip()   # コースコード
    oikiri_type = _safe_int(line[23:24].decode('ascii', errors='replace'))  # 1:馬なり,2:普通,3:一杯
    oikiri_aite = _safe_int(line[24:26].decode('ascii', errors='replace'))  # 追い切り相手コード
    nori = _safe_int(line[26:27].decode('ascii', errors='replace'))         # 1:調教,2:助手,3:本番騎乗,4:外部,5:見習
    training_content = _safe_int(line[27:28].decode('ascii', errors='replace'))  # 調教パターン

    # 追切タイム (0.1秒単位)
    ten_e = _safe_int(line[28:31].decode('ascii', errors='replace'))
    chukan_e = _safe_int(line[31:34].decode('ascii', errors='replace'))
    shimai_e = _safe_int(line[34:37].decode('ascii', errors='replace'))

    # 追切指数
    ten_e_idx = _safe_int(line[37:40].decode('ascii', errors='replace'))
    chukan_e_idx = _safe_int(line[40:43].decode('ascii', errors='replace'))
    shimai_e_idx = _safe_int(line[43:46].decode('ascii', errors='replace'))
    oikiri_idx = _safe_int(line[46:49].decode('ascii', errors='replace'))

    # 調教パターンデータ
    training_volume = line[49:50].decode('ascii', errors='replace').strip()  # 1:多量,2:普通,3:休み
    oikiri_type_pattern = _safe_int(line[50:51].decode('ascii', errors='replace'))  # 追切種類(パターン)

    return {
        'jrdb_race_key': race_key,
        'umaban': umaban,
        'youbi': youbi,
        'training_date': training_date,
        'kai': kai,
        'oikiri_course': oikiri_course,
        'oikiri_type': oikiri_type,
        'oikiri_aite': oikiri_aite,
        'nori': nori,
        'training_content': training_content,
        'ten_e': ten_e / 10.0 if ten_e else None,
        'chukan_e': chukan_e / 10.0 if chukan_e else None,
        'shimai_e': shimai_e / 10.0 if shimai_e else None,
        'ten_e_idx': ten_e_idx,
        'chukan_e_idx': chukan_e_idx,
        'shimai_e_idx': shimai_e_idx,
        'oikiri_idx': oikiri_idx,
        'training_volume': training_volume,
        'oikiri_type_pattern': oikiri_type_pattern,
    }


def parse_kka_line(line: bytes) -> Optional[dict]:
    """KKA固定長1行(322バイト) → dict

    競走馬拡張データ: 産駒成績・レベル集計を含む
    仕様書レコード長: 324バイト (322 + CRLF 2)
    """
    if len(line) < 300:
        return None

    race_key = line[0:8].decode('ascii', errors='replace')
    umaban = _safe_int(line[8:10].decode('ascii', errors='replace'))

    # 成績 (ZZ9*4 = [1着, 2着, 3着, 着外])
    jrdb_results = _parse_zz9x4(line, 10)
    exchange_results = _parse_zz9x4(line, 22)
    other_results = _parse_zz9x4(line, 34)

    # 産地産駒成績別レベル集計 (全て ZZ9*4)
    td_both_count = _parse_zz9x4(line, 46)        # 芝ダ両方成績
    td_both_win = _parse_zz9x4(line, 58)           # 芝ダ両方勝率
    track_results = _parse_zz9x4(line, 70)         # トラック成績
    rotation_results = _parse_zz9x4(line, 82)      # ローテ成績
    slow_pace_results = _parse_zz9x4(line, 94)     # Sペース成績
    fast_pace_results = _parse_zz9x4(line, 106)    # Hペース成績
    training_results = _parse_zz9x4(line, 118)     # 追切成績
    short_dist_results = _parse_zz9x4(line, 130)   # 短距離成績
    long_dist_results = _parse_zz9x4(line, 142)    # 長距離成績(不良含む)
    s_pace_level = _parse_zz9x4(line, 154)         # Sペース
    n_pace_level = _parse_zz9x4(line, 166)         # Nペース
    h_pace_level = _parse_zz9x4(line, 178)         # Hペース
    season_results = _parse_zz9x4(line, 190)       # 季節成績
    weight_results = _parse_zz9x4(line, 202)       # 馬体重成績

    # 産地成績別レベル
    turf_distance = _parse_zz9x4(line, 214)        # 芝距離成績
    turf_track = _parse_zz9x4(line, 226)           # 芝トラック成績
    turf_aptitude = _parse_zz9x4(line, 238)        # 芝適性別成績
    turf_surface = _parse_zz9x4(line, 250)         # 芝馬場別成績
    turf_blinker = _parse_zz9x4(line, 262)         # 芝ブリンカー成績
    dirt_surface = _parse_zz9x4(line, 274)         # ダート馬場別成績

    # その他
    dam_best_rentai = _safe_int(line[286:289].decode('ascii', errors='replace'))       # 母産駒最連対率(%)
    dam_place_rentai = _safe_int(line[289:292].decode('ascii', errors='replace'))      # 母産駒複連対率(%)
    dam_avg_distance = _safe_int(line[292:296].decode('ascii', errors='replace'))      # 母産駒連対平均距離
    bms_best_rentai = _safe_int(line[296:299].decode('ascii', errors='replace'))       # 母父産駒最連対率(%)
    bms_place_rentai = _safe_int(line[299:302].decode('ascii', errors='replace'))      # 母父産駒複連対率(%)
    bms_avg_distance = _safe_int(line[302:306].decode('ascii', errors='replace'))      # 母父産駒連対平均距離

    return {
        'jrdb_race_key': race_key,
        'umaban': umaban,
        # 成績
        'jrdb_results': jrdb_results,
        'exchange_results': exchange_results,
        'other_results': other_results,
        # 産地産駒成績別レベル集計
        'td_both_count': td_both_count,
        'td_both_win': td_both_win,
        'track_results': track_results,
        'rotation_results': rotation_results,
        'slow_pace_results': slow_pace_results,
        'fast_pace_results': fast_pace_results,
        'training_results': training_results,
        'short_dist_results': short_dist_results,
        'long_dist_results': long_dist_results,
        's_pace_level': s_pace_level,
        'n_pace_level': n_pace_level,
        'h_pace_level': h_pace_level,
        'season_results': season_results,
        'weight_results': weight_results,
        # 産地成績別レベル
        'turf_distance': turf_distance,
        'turf_track': turf_track,
        'turf_aptitude': turf_aptitude,
        'turf_surface': turf_surface,
        'turf_blinker': turf_blinker,
        'dirt_surface': dirt_surface,
        # その他
        'dam_best_rentai': dam_best_rentai,
        'dam_place_rentai': dam_place_rentai,
        'dam_avg_distance': dam_avg_distance,
        'bms_best_rentai': bms_best_rentai,
        'bms_place_rentai': bms_place_rentai,
        'bms_avg_distance': bms_avg_distance,
    }


def parse_ukc_line(line: bytes) -> Optional[dict]:
    """UKC固定長1行(290バイト) → dict

    馬基本データ: 馬名・血統・生年月日・馬主・生産者
    仕様書レコード長: 292バイト (290 + CRLF 2)
    """
    if len(line) < 270:
        return None

    ketto_num = line[0:8].decode('ascii', errors='replace').strip()      # 血統登録番号 (8桁)
    horse_name = line[8:44].decode('shift_jis', errors='replace').strip()  # 馬名 (全角18文字)

    sex_code = _safe_int(line[44:45].decode('ascii', errors='replace'))    # 1:牡,2:牝,3:セン
    coat_color = _safe_int(line[45:47].decode('ascii', errors='replace'))  # 毛色コード
    horse_symbol = _safe_int(line[47:49].decode('ascii', errors='replace'))  # 馬記号コード

    # 血統
    sire_name = line[49:85].decode('shift_jis', errors='replace').strip()          # 父馬名
    dam_name = line[85:121].decode('shift_jis', errors='replace').strip()          # 母馬名
    broodmare_sire = line[121:157].decode('shift_jis', errors='replace').strip()   # 母父馬名

    birth_date = line[157:165].decode('ascii', errors='replace').strip()  # YYYYMMDD

    # 第2版追加
    sire_birth_year = _safe_int(line[165:169].decode('ascii', errors='replace'))   # 父生年 YYYY
    dam_birth_year = _safe_int(line[169:173].decode('ascii', errors='replace'))    # 母生年 YYYY
    bms_birth_year = _safe_int(line[173:177].decode('ascii', errors='replace'))    # 母父生年 YYYY

    owner_name = line[177:217].decode('shift_jis', errors='replace').strip()       # 馬主名 (全角20文字)
    breeder_code = _safe_int(line[217:219].decode('ascii', errors='replace'))      # 馬産コード
    breeder_name = line[219:259].decode('shift_jis', errors='replace').strip()     # 生産者名
    origin = line[259:267].decode('shift_jis', errors='replace').strip()           # 産地名 (全角4文字)
    retired_flag = _safe_int(line[267:268].decode('ascii', errors='replace'))      # 0:現役,1:抹消
    data_date = line[268:276].decode('ascii', errors='replace').strip()            # データ年月日

    # 第3版追加
    sire_code = _safe_int(line[276:280].decode('ascii', errors='replace'))         # 父馬名コード
    bms_code = _safe_int(line[280:284].decode('ascii', errors='replace'))          # 母父馬名コード

    return {
        'ketto_num_jrdb': ketto_num,
        'horse_name': horse_name,
        'sex_code': sex_code,
        'coat_color': coat_color,
        'horse_symbol': horse_symbol,
        'sire_name': sire_name,
        'dam_name': dam_name,
        'broodmare_sire': broodmare_sire,
        'birth_date': birth_date,
        'sire_birth_year': sire_birth_year,
        'dam_birth_year': dam_birth_year,
        'bms_birth_year': bms_birth_year,
        'owner_name': owner_name,
        'breeder_code': breeder_code,
        'breeder_name': breeder_name,
        'origin': origin,
        'retired_flag': retired_flag,
        'data_date': data_date,
        'sire_code': sire_code,
        'bms_code': bms_code,
    }


def parse_joa_line(line: bytes) -> Optional[dict]:
    """JOA固定長1行(114バイト) → dict

    情報データ: CID(コンディションインデックス)・LS(ロングショット)指数
    仕様書レコード長: 116バイト (114 + CRLF 2)
    """
    if len(line) < 100:
        return None

    race_key = line[0:8].decode('ascii', errors='replace')
    umaban = _safe_int(line[8:10].decode('ascii', errors='replace'))
    ketto_num = line[10:18].decode('ascii', errors='replace').strip()     # 血統登録番号
    horse_name = line[18:54].decode('shift_jis', errors='replace').strip()

    # オッズ
    kakutei_odds = _safe_float(line[54:59].decode('ascii', errors='replace'))        # 確定単勝オッズ
    kakutei_place_odds = _safe_float(line[59:64].decode('ascii', errors='replace'))  # 確定複勝オッズ

    # CID (Condition Index)
    cid_choushi = _safe_float(line[64:69].decode('ascii', errors='replace'))     # CID調子素点
    cid_sani = _safe_float(line[69:74].decode('ascii', errors='replace'))        # CIDさに素点
    cid_score = _safe_float(line[74:79].decode('ascii', errors='replace'))       # CID素点
    cid = _safe_int(line[79:82].decode('ascii', errors='replace'))               # CID

    # LS (Long Shot)
    ls_idx = _safe_float(line[82:87].decode('ascii', errors='replace'))          # LS指数
    ls_eval = line[87:88].decode('ascii', errors='replace').strip()              # LS評価 A/B/C
    em = line[88:89].decode('ascii', errors='replace').strip()                   # EM 1:該当

    # 第2版追加 — BB (Blood Broodmare) 印
    bb_turf_dirt = _safe_int(line[89:90].decode('ascii', errors='replace'))      # スにBB印
    bb_turf_dirt_win = _safe_int(line[90:95].decode('ascii', errors='replace'))  # スにBB印単勝率(‰)
    bb_turf_dirt_place = _safe_int(line[95:100].decode('ascii', errors='replace'))  # スにBB印連対率(‰)
    bb_turf = _safe_int(line[100:101].decode('ascii', errors='replace'))         # 芝BB印
    bb_turf_win = _safe_int(line[101:106].decode('ascii', errors='replace'))     # 芝BB印単勝率(‰)
    bb_turf_place = _safe_int(line[106:111].decode('ascii', errors='replace'))   # 芝BB印連対率(‰)

    return {
        'jrdb_race_key': race_key,
        'umaban': umaban,
        'ketto_num_jrdb': ketto_num,
        'horse_name': horse_name,
        'kakutei_odds': kakutei_odds,
        'kakutei_place_odds': kakutei_place_odds,
        'cid_choushi': cid_choushi,
        'cid_sani': cid_sani,
        'cid_score': cid_score,
        'cid': cid,
        'ls_idx': ls_idx,
        'ls_eval': ls_eval,
        'em': em,
        'bb_turf_dirt': bb_turf_dirt,
        'bb_turf_dirt_win': bb_turf_dirt_win,
        'bb_turf_dirt_place': bb_turf_dirt_place,
        'bb_turf': bb_turf,
        'bb_turf_win': bb_turf_win,
        'bb_turf_place': bb_turf_place,
    }


def load_sed_files(year_range: range = None) -> List[dict]:
    """SED生ファイルをまとめてパース

    Args:
        year_range: 対象年範囲 (例: range(2020, 2026))
                   Noneなら全ファイル

    Returns:
        パースされたレコードのリスト
    """
    sed_dir = RAW_DIR / 'SED'
    if not sed_dir.exists():
        print(f"ERROR: {sed_dir} not found")
        return []

    records = []
    file_count = 0

    for f in sorted(sed_dir.glob('SED*.txt')):
        # ファイル名から年を推定: SED250301.txt → 20+25=2025
        fname = f.stem  # SED250301
        yy = fname[3:5]
        try:
            year = 2000 + int(yy) if int(yy) < 80 else 1900 + int(yy)
        except ValueError:
            continue

        if year_range and year not in year_range:
            continue

        data = f.read_bytes()
        for line in data.split(b'\r\n'):
            if len(line) < 370:
                continue
            rec = parse_sed_line(line)
            if rec:
                records.append(rec)

        file_count += 1

    print(f"[SED] {file_count} files, {len(records):,} records loaded")
    return records


def load_kyi_files(year_range: range = None) -> List[dict]:
    """KYI生ファイルをまとめてパース"""
    kyi_dir = RAW_DIR / 'KYI'
    if not kyi_dir.exists():
        print(f"ERROR: {kyi_dir} not found")
        return []

    records = []
    file_count = 0

    for f in sorted(kyi_dir.glob('KYI*.txt')):
        fname = f.stem
        yy = fname[3:5]
        try:
            year = 2000 + int(yy) if int(yy) < 80 else 1900 + int(yy)
        except ValueError:
            continue

        if year_range and year not in year_range:
            continue

        data = f.read_bytes()
        for line in data.split(b'\r\n'):
            if len(line) < 620:
                continue
            rec = parse_kyi_line(line)
            if rec:
                records.append(rec)

        file_count += 1

    print(f"[KYI] {file_count} files, {len(records):,} records loaded")
    return records


def load_kaa_files(year_range: range = None) -> List[dict]:
    """KAA生ファイルをまとめてパース"""
    kaa_dir = RAW_DIR / 'KAA'
    if not kaa_dir.exists():
        print(f"ERROR: {kaa_dir} not found")
        return []

    records = []
    file_count = 0

    for f in sorted(kaa_dir.glob('KAA*.txt')):
        fname = f.stem
        yy = fname[3:5]
        try:
            year = 2000 + int(yy) if int(yy) < 80 else 1900 + int(yy)
        except ValueError:
            continue

        if year_range and year not in year_range:
            continue

        data = f.read_bytes()
        for line in data.split(b'\r\n'):
            if len(line) < 49:
                continue
            rec = parse_kaa_line(line)
            if rec:
                records.append(rec)

        file_count += 1

    print(f"[KAA] {file_count} files, {len(records):,} records loaded")
    return records


def load_srb_files(year_range: range = None) -> List[dict]:
    """SRB生ファイルをまとめてパース（SED/rawディレクトリに同梱）"""
    # SRBファイルはSED.lzh/zipに同梱されてraw/SED/に展開される
    sed_dir = RAW_DIR / 'SED'
    if not sed_dir.exists():
        print(f"ERROR: {sed_dir} not found")
        return []

    records = []
    file_count = 0

    for f in sorted(sed_dir.glob('SRB*.txt')):
        fname = f.stem  # SRB250301
        yy = fname[3:5]
        try:
            year = 2000 + int(yy) if int(yy) < 80 else 1900 + int(yy)
        except ValueError:
            continue

        if year_range and year not in year_range:
            continue

        data = f.read_bytes()
        for line in data.split(b'\r\n'):
            if len(line) < 340:
                continue
            rec = parse_srb_line(line)
            if rec:
                records.append(rec)

        file_count += 1

    print(f"[SRB] {file_count} files, {len(records):,} records loaded")
    return records


def load_cyb_files(year_range: range = None) -> List[dict]:
    """CYB生ファイルをまとめてパース"""
    cyb_dir = RAW_DIR / 'CYB'
    if not cyb_dir.exists():
        print(f"ERROR: {cyb_dir} not found")
        return []

    records = []
    file_count = 0

    for f in sorted(cyb_dir.glob('CYB*.txt')):
        yy = f.stem[3:5]
        try:
            year = 2000 + int(yy) if int(yy) < 80 else 1900 + int(yy)
        except ValueError:
            continue
        if year_range and year not in year_range:
            continue

        data = f.read_bytes()
        for line in data.split(b'\r\n'):
            if len(line) < 90:
                continue
            rec = parse_cyb_line(line)
            if rec:
                records.append(rec)
        file_count += 1

    print(f"[CYB] {file_count} files, {len(records):,} records loaded")
    return records


def load_cha_files(year_range: range = None) -> List[dict]:
    """CHA生ファイルをまとめてパース"""
    cha_dir = RAW_DIR / 'CHA'
    if not cha_dir.exists():
        print(f"ERROR: {cha_dir} not found")
        return []

    records = []
    file_count = 0

    for f in sorted(cha_dir.glob('CHA*.txt')):
        yy = f.stem[3:5]
        try:
            year = 2000 + int(yy) if int(yy) < 80 else 1900 + int(yy)
        except ValueError:
            continue
        if year_range and year not in year_range:
            continue

        data = f.read_bytes()
        for line in data.split(b'\r\n'):
            if len(line) < 55:
                continue
            rec = parse_cha_line(line)
            if rec:
                records.append(rec)
        file_count += 1

    print(f"[CHA] {file_count} files, {len(records):,} records loaded")
    return records


def load_kka_files(year_range: range = None) -> List[dict]:
    """KKA生ファイルをまとめてパース"""
    kka_dir = RAW_DIR / 'KKA'
    if not kka_dir.exists():
        print(f"ERROR: {kka_dir} not found")
        return []

    records = []
    file_count = 0

    for f in sorted(kka_dir.glob('KKA*.txt')):
        yy = f.stem[3:5]
        try:
            year = 2000 + int(yy) if int(yy) < 80 else 1900 + int(yy)
        except ValueError:
            continue
        if year_range and year not in year_range:
            continue

        data = f.read_bytes()
        for line in data.split(b'\r\n'):
            if len(line) < 300:
                continue
            rec = parse_kka_line(line)
            if rec:
                records.append(rec)
        file_count += 1

    print(f"[KKA] {file_count} files, {len(records):,} records loaded")
    return records


def load_ukc_files(year_range: range = None) -> List[dict]:
    """UKC生ファイルをまとめてパース"""
    ukc_dir = RAW_DIR / 'UKC'
    if not ukc_dir.exists():
        print(f"ERROR: {ukc_dir} not found")
        return []

    records = []
    file_count = 0

    for f in sorted(ukc_dir.glob('UKC*.txt')):
        yy = f.stem[3:5]
        try:
            year = 2000 + int(yy) if int(yy) < 80 else 1900 + int(yy)
        except ValueError:
            continue
        if year_range and year not in year_range:
            continue

        data = f.read_bytes()
        for line in data.split(b'\r\n'):
            if len(line) < 270:
                continue
            rec = parse_ukc_line(line)
            if rec:
                records.append(rec)
        file_count += 1

    print(f"[UKC] {file_count} files, {len(records):,} records loaded")
    return records


def load_joa_files(year_range: range = None) -> List[dict]:
    """JOA生ファイルをまとめてパース"""
    joa_dir = RAW_DIR / 'JOA'
    if not joa_dir.exists():
        print(f"ERROR: {joa_dir} not found")
        return []

    records = []
    file_count = 0

    for f in sorted(joa_dir.glob('JOA*.txt')):
        yy = f.stem[3:5]
        try:
            year = 2000 + int(yy) if int(yy) < 80 else 1900 + int(yy)
        except ValueError:
            continue
        if year_range and year not in year_range:
            continue

        data = f.read_bytes()
        for line in data.split(b'\r\n'):
            if len(line) < 100:
                continue
            rec = parse_joa_line(line)
            if rec:
                records.append(rec)
        file_count += 1

    print(f"[JOA] {file_count} files, {len(records):,} records loaded")
    return records


if __name__ == '__main__':
    # テスト: 2025年のSEDをパースして基本統計
    print("=== SED Test ===")
    sed = load_sed_files(range(2025, 2026))
    if sed:
        idm_vals = [r['idm'] for r in sed if r['idm'] > 0]
        print(f"  IDM: count={len(idm_vals)}, "
              f"mean={sum(idm_vals)/len(idm_vals):.1f}, "
              f"min={min(idm_vals)}, max={max(idm_vals)}")

        # サンプル表示
        for r in sed[:3]:
            print(f"  {r['race_date']} {r['horse_name'][:8]} "
                  f"umaban={r['umaban']} IDM={r['idm']} "
                  f"finish={r['finish_position']}")

    print("\n=== KYI Test ===")
    kyi = load_kyi_files(range(2025, 2026))
    if kyi:
        idm_vals = [r['pre_idm'] for r in kyi if r['pre_idm'] and r['pre_idm'] > 0]
        print(f"  Pre-IDM: count={len(idm_vals)}, "
              f"mean={sum(idm_vals)/len(idm_vals):.1f}, "
              f"min={min(idm_vals)}, max={max(idm_vals)}")
