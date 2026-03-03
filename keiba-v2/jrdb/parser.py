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

    base_odds = _safe_float(line[95:100].decode('ascii', errors='replace'))  # 基準オッズ
    base_popularity = _safe_int(line[100:102].decode('ascii', errors='replace'))  # 基準人気

    training_idx = _safe_float(line[144:149].decode('ascii', errors='replace'))  # 調教指数
    stable_idx = _safe_float(line[149:154].decode('ascii', errors='replace'))  # 厩舎指数

    jockey_code = line[335:340].decode('ascii', errors='replace').strip()
    trainer_code = line[340:345].decode('ascii', errors='replace').strip()

    # 展開予想データ (第6版)
    pred_ten_idx = _safe_float(line[358:363].decode('ascii', errors='replace'))
    pred_pace_idx = _safe_float(line[363:368].decode('ascii', errors='replace'))
    pred_agari_idx = _safe_float(line[368:373].decode('ascii', errors='replace'))
    pred_position_idx = _safe_float(line[373:378].decode('ascii', errors='replace'))
    pred_pace = line[378:379].decode('ascii', errors='replace').strip()  # H/M/S

    # 馬スタート指数・出遅率 (第9版)
    start_idx = _safe_float(line[519:523].decode('ascii', errors='replace'))
    deokure_rate = _safe_float(line[523:527].decode('ascii', errors='replace'))

    # 激走指数 (第3版)
    gekisou_idx = _safe_int(line[160:163].decode('ascii', errors='replace'))

    # フラグ (第11版) — 初芝/初ダ/初障害等
    flags = line[543:559].decode('ascii', errors='replace').strip()

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
        # 展開予想
        'pred_ten_idx': pred_ten_idx,
        'pred_pace_idx': pred_pace_idx,
        'pred_agari_idx': pred_agari_idx,
        'pred_position_idx': pred_position_idx,
        'pred_pace': pred_pace,
        # 脚質・適性
        'kyakushitsu': kyakushitsu,
        'distance_aptitude': distance_aptitude,
        # 基準オッズ
        'base_odds': base_odds,
        'base_popularity': base_popularity,
        # スタート
        'start_idx': start_idx,
        'deokure_rate': deokure_rate,
        # フラグ
        'flags': flags,
        # リンクキー
        'jockey_code': jockey_code,
        'trainer_code': trainer_code,
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
