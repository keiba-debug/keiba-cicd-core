#!/usr/bin/env python3
"""
JV-VAN HR（払戻）レコードパーサー

HRレコード構造（JV-Data仕様推定）:
- 0-1: レコード種別 (HR)
- 2: データ区分
- 3-10: 日付 (YYYYMMDD)
- 11-26: レースID (16桁)
- 27-28: 登録頭数
- 29-30: 出走頭数
- 31以降: 配当データ

配当データ構造（推定）:
- 単勝 (97-): 組数 + [馬番(2) + 払戻(6) + 人気(2)] × 3
- 複勝 (137-): 組数 + [馬番(2) + 払戻(5) + 人気(2)] × 5
- 枠連 (197-): 組数 + [枠番(2) + 払戻(6) + 人気(2)] × 3
- 馬連 (237-): 組数 + [馬番(4) + 払戻(7) + 人気(2)] × 3
- ワイド (287-): 組数 + [馬番(4) + 払戻(7) + 人気(2)] × 3
- 馬単 (447-): 組数 + [馬番(4) + 払戻(8) + 人気(2)] × 1
- 3連複 (547-): 組数 + [馬番(6) + 払戻(8) + 人気(3)] × 1
- 3連単 (600-): 組数 + [馬番(6) + 払戻(9) + 人気(3)] × 1
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional
import re

SE_DATA_DIR = os.environ.get("JV_DATA_ROOT_DIR", r"C:\TFJV") + r"\SE_DATA"


@dataclass
class PayoutInfo:
    """払戻情報"""
    bet_type: int           # 馬券種別コード (0=単勝, 1=複勝, 2=枠連, 3=馬連, 4=ワイド, 5=馬単, 6=3連複, 7=3連単)
    bet_type_name: str      # 馬券種別名
    selection: str          # 的中組み合わせ (例: "01-09")
    payout: int             # 払戻金額 (100円あたり)
    popularity: int         # 人気


def _parse_payout_block(data: str, horse_len: int, payout_len: int, pop_len: int, max_count: int = 3) -> List[PayoutInfo]:
    """
    配当ブロックをパース
    
    JV-Data仕様書に基づく構造（C# JVData_Struct.cs参照）:
    - PAY_INFO1 (単勝/複勝/枠連): 馬番(2) + 払戻(9) + 人気(2) = 13バイト
    - PAY_INFO2 (馬連/ワイド/馬単): 組番(4) + 払戻(9) + 人気(3) = 16バイト
    - PAY_INFO3 (3連複): 組番(6) + 払戻(9) + 人気(3) = 18バイト
    - PAY_INFO4 (3連単): 組番(6) + 払戻(9) + 人気(4) = 19バイト
    
    Args:
        data: 配当データ文字列
        horse_len: 馬番/組番フィールド長
        payout_len: 払戻フィールド長
        pop_len: 人気フィールド長
        max_count: 最大組数
    
    Returns:
        PayoutInfo のリスト
    """
    results = []
    
    if not data:
        return results
    
    block_len = horse_len + payout_len + pop_len
    
    # 最大組数まで読み取り
    for i in range(max_count):
        offset = i * block_len
        if offset + block_len > len(data):
            break
        
        block = data[offset:offset + block_len]
        
        horse_str = block[:horse_len]
        payout_str = block[horse_len:horse_len + payout_len]
        pop_str = block[horse_len + payout_len:horse_len + payout_len + pop_len]
        
        # 空白のみの場合はスキップ
        if not horse_str.strip():
            continue
        
        # 馬番をパース
        if horse_len == 2:
            selection = horse_str.strip().zfill(2)
        elif horse_len == 4:
            h1 = horse_str[:2].strip().zfill(2)
            h2 = horse_str[2:4].strip().zfill(2)
            selection = f"{h1}-{h2}"
        elif horse_len == 6:
            h1 = horse_str[:2].strip().zfill(2)
            h2 = horse_str[2:4].strip().zfill(2)
            h3 = horse_str[4:6].strip().zfill(2)
            selection = f"{h1}-{h2}-{h3}"
        else:
            selection = horse_str.strip()
        
        # 払戻をパース（円単位で記録されている、10円単位ではない）
        try:
            payout = int(payout_str.strip()) if payout_str.strip() else 0
        except ValueError:
            payout = 0
        
        # 人気をパース
        try:
            popularity = int(pop_str.strip()) if pop_str.strip() else 0
        except ValueError:
            popularity = 0
        
        if payout > 0:
            results.append(PayoutInfo(
                bet_type=0,  # 後で設定
                bet_type_name="",  # 後で設定
                selection=selection,
                payout=payout,
                popularity=popularity,
            ))
    
    return results


def parse_hr_record(line: str) -> Dict[str, List[PayoutInfo]]:
    """
    HRレコードをパースして払戻情報を返す
    
    JV-Data仕様書に基づくHR構造（C# JVData_Struct.cs参照、0ベースインデックス）:
    - 位置0-11: レコードヘッダー (HR + dataKubun等)
    - 位置11-27: レースID (16バイト)
    - 位置27-31: 登録/出走頭数 (各2バイト)
    - 位置31-40: 不成立フラグ (9バイト)
    - 位置40-49: 特払フラグ (9バイト)
    - 位置49-58: 返還フラグ (9バイト)
    - 位置58-86: 返還馬番情報 (28バイト)
    - 位置86-94: 返還枠番情報 (8バイト)
    - 位置94-102: 返還同枠情報 (8バイト)
    - 位置102-: 単勝払戻 [馬番(2)+払戻(9)+人気(2)=13] × 3 = 39バイト
    - 位置141-: 複勝払戻 [馬番(2)+払戻(9)+人気(2)=13] × 5 = 65バイト
    - 位置206-: 枠連払戻 [馬番(2)+払戻(9)+人気(2)=13] × 3 = 39バイト
    - 位置245-: 馬連払戻 [組番(4)+払戻(9)+人気(3)=16] × 3 = 48バイト
    - 位置293-: ワイド払戻 [組番(4)+払戻(9)+人気(3)=16] × 7 = 112バイト
    - 位置405-: 予備 [組番(4)+払戻(9)+人気(3)=16] × 3 = 48バイト
    - 位置453-: 馬単払戻 [組番(4)+払戻(9)+人気(3)=16] × 6 = 96バイト
    - 位置549-: 3連複払戻 [組番(6)+払戻(9)+人気(3)=18] × 3 = 54バイト
    - 位置603-: 3連単払戻 [組番(6)+払戻(9)+人気(4)=19] × 6 = 114バイト
    
    払戻金額は円単位で記録
    
    Returns:
        {
            "単勝": [PayoutInfo, ...],
            "複勝": [PayoutInfo, ...],
            ...
        }
    """
    result = {
        "単勝": [],
        "複勝": [],
        "枠連": [],
        "馬連": [],
        "ワイド": [],
        "馬単": [],
        "3連複": [],
        "3連単": [],
    }
    
    if len(line) < 600:
        return result
    
    # 単勝 (位置102-): 馬番(2) + 払戻(9) + 人気(2) = 13バイト × 3
    tan_data = line[102:141]
    tan_payouts = _parse_payout_block(tan_data, 2, 9, 2, 3)
    for p in tan_payouts:
        p.bet_type = 0
        p.bet_type_name = "単勝"
    result["単勝"] = tan_payouts
    
    # 複勝 (位置141-): 馬番(2) + 払戻(9) + 人気(2) = 13バイト × 5
    fuku_data = line[141:206]
    fuku_payouts = _parse_payout_block(fuku_data, 2, 9, 2, 5)
    for p in fuku_payouts:
        p.bet_type = 1
        p.bet_type_name = "複勝"
    result["複勝"] = fuku_payouts
    
    # 枠連 (位置206-): 枠番(2) + 払戻(9) + 人気(2) = 13バイト × 3
    waku_data = line[206:245]
    waku_payouts = _parse_payout_block(waku_data, 2, 9, 2, 3)
    for p in waku_payouts:
        p.bet_type = 2
        p.bet_type_name = "枠連"
    result["枠連"] = waku_payouts
    
    # 馬連 (位置245-): 組番(4) + 払戻(9) + 人気(3) = 16バイト × 3
    umaren_data = line[245:293]
    umaren_payouts = _parse_payout_block(umaren_data, 4, 9, 3, 3)
    for p in umaren_payouts:
        p.bet_type = 3
        p.bet_type_name = "馬連"
    result["馬連"] = umaren_payouts
    
    # ワイド (位置293-): 組番(4) + 払戻(9) + 人気(3) = 16バイト × 7
    wide_data = line[293:405]
    wide_payouts = _parse_payout_block(wide_data, 4, 9, 3, 7)
    for p in wide_payouts:
        p.bet_type = 4
        p.bet_type_name = "ワイド"
    result["ワイド"] = wide_payouts
    
    # 馬単 (位置453-): 組番(4) + 払戻(9) + 人気(3) = 16バイト × 6
    umatan_data = line[453:549]
    umatan_payouts = _parse_payout_block(umatan_data, 4, 9, 3, 6)
    for p in umatan_payouts:
        p.bet_type = 5
        p.bet_type_name = "馬単"
    result["馬単"] = umatan_payouts
    
    # 3連複 (位置549-): 組番(6) + 払戻(9) + 人気(3) = 18バイト × 3
    sanrenpuku_data = line[549:603]
    sanrenpuku_payouts = _parse_payout_block(sanrenpuku_data, 6, 9, 3, 3)
    for p in sanrenpuku_payouts:
        p.bet_type = 6
        p.bet_type_name = "3連複"
    result["3連複"] = sanrenpuku_payouts
    
    # 3連単 (位置603-): 組番(6) + 払戻(9) + 人気(4) = 19バイト × 6
    sanrentan_data = line[603:717]
    sanrentan_payouts = _parse_payout_block(sanrentan_data, 6, 9, 4, 6)
    for p in sanrentan_payouts:
        p.bet_type = 7
        p.bet_type_name = "3連単"
    result["3連単"] = sanrentan_payouts
    
    return result


def get_payout_for_race(race_id: str) -> Optional[Dict[str, List[PayoutInfo]]]:
    """
    レースIDから払戻情報を取得
    
    Args:
        race_id: レースID（TARGET形式: 2026013105010210 または JV形式: 2026013105010110）
    
    Returns:
        払戻情報辞書
    """
    # レースIDをJV-VAN形式に変換（必要に応じて）
    # TARGET: 2026013105010210 (東京1回2日10R)
    # JV-VAN: 2026013105010110 (東京1回1日10R) -- 日目の数え方が違う可能性
    
    date_str = race_id[:8]  # YYYYMMDD
    venue = race_id[8:10]   # 場コード
    
    # 該当する年月のSHファイルを検索
    year = date_str[:4]
    se_year_dir = os.path.join(SE_DATA_DIR, year)
    
    if not os.path.exists(se_year_dir):
        return None
    
    # SHファイルを検索
    for filename in os.listdir(se_year_dir):
        if filename.startswith("SH") and filename.endswith(".DAT"):
            filepath = os.path.join(se_year_dir, filename)
            
            with open(filepath, 'r', encoding='cp932') as f:
                for line in f:
                    if line.startswith("HR") and race_id in line:
                        return parse_hr_record(line)
    
    return None


def check_bet_hit(bet_type: int, selection: str, payouts: Dict[str, List[PayoutInfo]]) -> Optional[PayoutInfo]:
    """
    買い目が的中したかチェック
    
    Args:
        bet_type: 馬券種別コード
        selection: 買い目 (例: "1-9", "01-09")
        payouts: 払戻情報
    
    Returns:
        的中した場合はPayoutInfo、外れた場合はNone
    """
    bet_type_map = {
        0: "単勝",
        1: "複勝",
        2: "枠連",
        3: "馬連",
        4: "ワイド",
        5: "馬単",
        6: "3連複",
        7: "3連単",
    }
    
    bet_type_name = bet_type_map.get(bet_type)
    if not bet_type_name or bet_type_name not in payouts:
        return None
    
    # 選択馬番を正規化（ゼロパディング）
    normalized_selection = "-".join(
        part.zfill(2) for part in selection.split("-")
    )
    
    for payout in payouts[bet_type_name]:
        # ワイド・馬連・枠連は順序不問
        if bet_type in [2, 3, 4]:  # 枠連、馬連、ワイド
            payout_parts = set(payout.selection.split("-"))
            selection_parts = set(normalized_selection.split("-"))
            if payout_parts == selection_parts:
                return payout
        else:
            if payout.selection == normalized_selection:
                return payout
    
    return None


if __name__ == "__main__":
    # テスト: 東京10R
    race_id = "2026013105010110"  # JV-VAN形式
    print(f"レース: {race_id}")
    print("=" * 60)
    
    payouts = get_payout_for_race(race_id)
    
    if payouts:
        for bet_type, payout_list in payouts.items():
            if payout_list:
                print(f"\n【{bet_type}】")
                for p in payout_list:
                    print(f"  {p.selection}: {p.payout}円 ({p.popularity}番人気)")
        
        # 買い目チェック
        print("\n" + "=" * 60)
        print("【買い目照合テスト】")
        
        test_bets = [
            (0, "1", "単勝1番"),
            (0, "6", "単勝6番"),
            (4, "1-6", "ワイド1-6"),
            (4, "1-9", "ワイド1-9"),
            (6, "1-6-9", "3連複1-6-9"),
        ]
        
        for bet_type, selection, desc in test_bets:
            hit = check_bet_hit(bet_type, selection, payouts)
            if hit:
                print(f"  {desc}: ★的中 → {hit.payout}円")
            else:
                print(f"  {desc}: 外れ")
    else:
        print("払戻情報が見つかりませんでした")
