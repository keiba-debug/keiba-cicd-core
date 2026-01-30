#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
調教師IDインデックス構築スクリプト

競馬ブックの厩舎IDとJRA-VAN調教師コードの対応インデックスを構築します。
初期版は手動マッピングで、将来は自動名寄せロジックを実装予定。

Usage:
    # インデックス構築
    python build_trainer_index.py

    # インデックス情報表示
    python build_trainer_index.py --info
"""

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

# Pythonパスに親ディレクトリを追加（commonモジュールのインポート用）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# 環境変数読み込み
try:
    from dotenv import load_dotenv
    env_candidates = [
        Path(__file__).resolve().parents[2] / "KeibaCICD.keibabook" / ".env",
        Path(__file__).resolve().parents[1] / ".env",
    ]
    for env_path in env_candidates:
        if env_path.exists():
            load_dotenv(env_path)
            break
except ImportError:
    pass

# インデックスファイルのパス（環境変数を考慮）
from common.config import get_target_data_dir, get_jv_data_root
INDEX_FILE = get_target_data_dir() / "trainer_id_index.json"

# UM_DATAパーサーをインポート
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
try:
    from parse_jv_horse_data import (
        parse_um_record, 
        decode_sjis, 
        get_um_files,
        HorseRecord,
    )
    # UM_RECORD_LENはparse_jv_horse_data.pyから取得
    import parse_jv_horse_data as um_parser
    UM_RECORD_LEN = um_parser.UM_RECORD_LEN
    UM_PARSER_AVAILABLE = True
except ImportError as e:
    UM_PARSER_AVAILABLE = False
    print(f"警告: UM_DATAパーサーが利用できません: {e}")
    print("   手動マッピングのみ使用します。")

# 手動マッピング（初期データ）
# 競馬ブック厩舎ID → JRA-VAN調教師コード
# 注意: 競馬ブックの厩舎IDは実際のスクレイピングデータから取得する必要があります
# ここでは、調教師名からJRA-VANコードを取得するための一時的なマッピングです
MANUAL_MAPPING = {
    # 例: 競馬ブック厩舎ID → JRA-VAN調教師コード
    # "ｳ011": {"jvn_code": "01234", "name": "友道康夫", "tozai": "栗東"},
    # "ﾐ052": {"jvn_code": "05678", "name": "堀内岳志", "tozai": "美浦"},
}


def get_trainers_from_um_data() -> Dict[str, Dict]:
    """
    UM_DATAから調教師一覧を取得
    
    Returns:
        調教師名 → {jvn_code, name, tozai} の辞書
    """
    trainers = {}
    
    if not UM_PARSER_AVAILABLE:
        return trainers
    
    try:
        jv_data_root = get_jv_data_root()
        um_data_path = jv_data_root / "UM_DATA"
        
        if not um_data_path.exists():
            print(f"警告: UM_DATAディレクトリが見つかりません: {um_data_path}")
            return trainers
        
        # UM_DATAファイルを取得
        um_files = get_um_files()
        
        if not um_files:
            print(f"警告: UM_DATAファイルが見つかりません: {um_data_path}")
            return trainers
        
        # 最新2ファイルのみ処理（パフォーマンス考慮）
        um_files = um_files[:2]
        print(f"UM_DATAファイルを読み込み中: {len(um_files)} ファイル")
        
        for um_file in um_files:
            try:
                with open(um_file, 'rb') as f:
                    data = f.read()
                
                num_records = len(data) // UM_RECORD_LEN
                
                for i in range(num_records):
                    offset = i * UM_RECORD_LEN
                    record = parse_um_record(data, offset)
                    
                    if record and record.trainer_code and record.trainer_name:
                        # 調教師名を正規化（空白除去、置換文字除去など）
                        trainer_name = record.trainer_name.strip()
                        trainer_code = record.trainer_code.strip()
                        
                        # 文字化け文字（\ufffd）を除去
                        trainer_name = trainer_name.replace('\ufffd', '').strip()
                        trainer_code = trainer_code.replace('\ufffd', '').strip()
                        
                        # 調教師コードが数値でない、または5桁でない場合はスキップ
                        # デバッグ: 最初の数件で詳細を表示
                        if not trainer_code.isdigit() or len(trainer_code) != 5:
                            # 最初の5件のみデバッグ出力
                            if len([k for k in trainers.keys() if isinstance(k, str) and k.isdigit()]) < 5:
                                try:
                                    print(f"  [デバッグ] スキップ: code={repr(trainer_code)} (isdigit={trainer_code.isdigit()}, len={len(trainer_code)}), name={repr(trainer_name[:15])}")
                                except:
                                    pass
                            continue
                        
                        # 調教師名が空の場合はスキップ
                        if not trainer_name:
                            continue
                        
                        if trainer_name and trainer_code:
                            # 調教師コードをキーとして使用（一意性のため）
                            if trainer_code not in trainers:
                                trainers[trainer_code] = {
                                    "jvn_code": trainer_code,
                                    "name": trainer_name,
                                    "tozai": record.tozai_name
                                }
                            # 調教師名でもアクセス可能にする
                            # 注意: 同名の調教師が複数いる場合があるため、最初に見つかったものを優先
                            if trainer_name not in trainers:
                                trainers[trainer_name] = {
                                    "jvn_code": trainer_code,
                                    "name": trainer_name,
                                    "tozai": record.tozai_name
                                }
                            
                            # デバッグ: 最初の10件の調教師名を表示（エラー回避のためtry-except）
                            code_count = len([k for k in trainers.keys() if isinstance(k, str) and k.isdigit()])
                            if code_count <= 10:
                                try:
                                    # 文字化けチェック: 置換文字が含まれていないか確認
                                    has_replacement = '\ufffd' in trainer_code or '\ufffd' in trainer_name
                                    if not has_replacement and trainer_code.isdigit() and len(trainer_code) == 5:
                                        print(f"  UM_DATA: {trainer_code} → {trainer_name} ({record.tozai_name})")
                                    else:
                                        # 文字化けしている場合は詳細を表示（最初の3件のみ）
                                        if code_count <= 3:
                                            print(f"  UM_DATA: [スキップ] code={repr(trainer_code)} (len={len(trainer_code)}, isdigit={trainer_code.isdigit()}), name={repr(trainer_name[:20])}")
                                except UnicodeEncodeError:
                                    pass  # 文字コードエラーは無視
                            
                            # デバッグ: 最初の1件でバイト列を確認
                            if len([k for k in trainers.keys() if isinstance(k, str) and k.isdigit()]) == 1:
                                try:
                                    # レコードの生データから調教師名のバイト列を取得
                                    # 注意: これはparse_um_record内で処理されるため、ここでは直接アクセスできない
                                    # 代わりに、文字化けのパターンを確認
                                    if len(trainer_name) < 2 or trainer_name[0] in 'n形ﾉ錘ｖｺcヶｬ':
                                        print(f"  [デバッグ] 文字化けパターン検出: code={trainer_code}, name={repr(trainer_name)}")
                                except:
                                    pass
            except Exception as e:
                # 文字コードエラーは無視（UM_DATAの一部レコードに問題がある可能性）
                if 'codec' not in str(e).lower() or 'encode' not in str(e).lower():
                    print(f"警告: {um_file} の読み込みエラー: {e}")
                continue
        
        print(f"UM_DATAから {len(trainers)} 名の調教師を取得しました")
        return trainers
        
    except Exception as e:
        print(f"警告: UM_DATAからの調教師取得エラー: {e}")
        return {}


def find_trainer_by_name(trainer_name: str, trainers_dict: Dict[str, Dict]) -> Optional[Dict]:
    """
    調教師名からJRA-VAN調教師情報を検索
    
    Args:
        trainer_name: 調教師名（例: "美堀内"）
        trainers_dict: UM_DATAから取得した調教師辞書
    
    Returns:
        調教師情報辞書またはNone
    """
    if not trainer_name:
        return None
    
    # 「美」「栗」の接頭辞を除去
    name_without_prefix = trainer_name.replace("美", "").replace("栗", "").strip()
    
    # 完全一致で検索（接頭辞付き）
    if trainer_name in trainers_dict:
        return trainers_dict[trainer_name]
    
    # 接頭辞なしで検索
    if name_without_prefix in trainers_dict:
        return trainers_dict[name_without_prefix]
    
    # 部分一致で検索（より柔軟なマッチング）
    # 例: "美堀内" → "堀内" で検索
    best_match = None
    best_score = 0
    
    # 調教師名のキーで検索（コードではなく名前）
    for key, info in trainers_dict.items():
        # キーが調教師名の場合（文字列で、数字でない場合）
        if isinstance(key, str) and not key.isdigit() and len(key) > 1:
            name = key
            
            # 完全一致（接頭辞付き）
            if trainer_name == name:
                return info
            
            # 完全一致（接頭辞なし）
            if name_without_prefix == name:
                return info
            
            # 部分一致: name_without_prefix が name に含まれる
            # 例: "堀内" が "堀内岳志" に含まれる
            if name_without_prefix and name_without_prefix in name:
                match_len = len(name_without_prefix)
                if match_len > best_score:
                    best_score = match_len
                    best_match = info
            
            # 逆方向: name が name_without_prefix に含まれる
            # 例: "堀内" が "美堀内" に含まれる
            elif name and name in name_without_prefix:
                match_len = len(name)
                if match_len > best_score:
                    best_score = match_len
                    best_match = info
            
            # 末尾一致: name_without_prefix が name の末尾と一致
            # 例: "堀内" が "木辺堀内" の末尾と一致
            elif name_without_prefix and name.endswith(name_without_prefix):
                match_len = len(name_without_prefix)
                if match_len > best_score:
                    best_score = match_len
                    best_match = info
            
            # 先頭一致: name_without_prefix が name の先頭と一致
            # 例: "堀内" が "堀内岳志" の先頭と一致
            elif name_without_prefix and name.startswith(name_without_prefix):
                match_len = len(name_without_prefix)
                if match_len > best_score:
                    best_score = match_len
                    best_match = info
    
    return best_match


def load_trainer_csv() -> Dict[str, Dict]:
    """
    調教師CSVファイルから調教師情報を読み込む
    
    Returns:
        調教師コードをキーとした辞書
        {
            "01055": {
                "jvn_code": "01055",
                "name": "木辺薫彦",
                "tozai": "美浦",
                "comment": "コメントデータ..."
            }
        }
    """
    trainers = {}
    csv_file = get_target_data_dir() / "調教師.csv"
    
    if not csv_file.exists():
        print(f"警告: 調教師CSVファイルが見つかりません: {csv_file}")
        return trainers
    
    try:
        with open(csv_file, 'r', encoding='shift_jis') as f:
            reader = csv.reader(f)
            
            # ヘッダー行を読み込んで列の位置を特定
            header_row = next(reader, None)
            if not header_row:
                print("警告: CSVファイルにヘッダー行がありません")
                return trainers
            
            # ヘッダーから列のインデックスを取得
            header_map = {}
            for idx, header in enumerate(header_row):
                header_lower = header.strip().lower()
                if '調教師' in header or '名前' in header or 'name' in header_lower:
                    if 'name' not in header_map:
                        header_map['name'] = idx
                elif 'コード' in header or 'code' in header_lower:
                    if 'code' not in header_map:
                        header_map['code'] = idx
                elif '所属' in header or 'tozai' in header_lower or '美浦' in header or '栗東' in header:
                    if 'tozai' not in header_map:
                        header_map['tozai'] = idx
                elif 'コメント' in header or 'comment' in header_lower or '勝負' in header or '調教' in header:
                    if 'comment' not in header_map:
                        header_map['comment'] = idx
            
            # デバッグ: ヘッダーマッピングを表示
            print(f"  [CSVヘッダー] 検出された列: {header_map}")
            
            # データ行を処理
            for row_idx, row in enumerate(reader):
                if len(row) < 2:
                    continue
                
                # ヘッダーマップから値を取得
                trainer_name = ""
                trainer_code = None
                tozai = ""
                comment = ""
                
                if 'name' in header_map and header_map['name'] < len(row):
                    trainer_name = row[header_map['name']].strip()
                
                if 'code' in header_map and header_map['code'] < len(row):
                    code_value = row[header_map['code']].strip()
                    if code_value.isdigit() and len(code_value) == 5:
                        trainer_code = code_value
                
                # コードが見つからない場合は、5桁数値の列を探す
                if not trainer_code:
                    for col in row:
                        if col and col.strip().isdigit() and len(col.strip()) == 5:
                            trainer_code = col.strip()
                            break
                
                if 'tozai' in header_map and header_map['tozai'] < len(row):
                    tozai = row[header_map['tozai']].strip()
                
                if 'comment' in header_map and header_map['comment'] < len(row):
                    comment = row[header_map['comment']].strip()
                
                # デバッグ: 最初の5件で構造を確認
                if len(trainers) < 5:
                    try:
                        print(f"  [CSVデバッグ] 行{row_idx+2}: コード={trainer_code}, 名前={trainer_name[:10]}, 所属={tozai}, コメント長={len(comment)}")
                    except:
                        pass
                
                if trainer_code and trainer_name:
                    trainers[trainer_code] = {
                        "jvn_code": trainer_code,
                        "name": trainer_name,
                        "tozai": tozai if tozai in ["美浦", "栗東"] else "不明",
                        "comment": comment
                    }
        
        print(f"調教師CSVから {len(trainers)} 件の調教師情報を読み込みました")
        return trainers
        
    except Exception as e:
        print(f"警告: 調教師CSVファイルの読み込みエラー: {e}")
        return trainers


def build_index_from_data_files() -> Dict:
    """
    実際のデータファイルから調教師IDと調教師名の対応を取得してインデックスを構築
    
    Returns:
        構築されたインデックス辞書
    """
    index = {}
    unmatched_count = 0  # ローカル変数として管理
    
    # 調教師CSVファイルから読み込み（優先度: 最高）
    csv_trainers = load_trainer_csv()
    csv_trainer_by_code = {info["jvn_code"]: info for info in csv_trainers.values()}
    
    # UM_DATAから調教師一覧を取得
    trainers_dict = get_trainers_from_um_data()
    
    if not trainers_dict:
        print("警告: UM_DATAから調教師情報を取得できませんでした。")
        return index
    
    print(f"UM_DATAから {len(trainers_dict)} 件の調教師情報を取得しました")
    
    # デバッグ: 調教師名のサンプルを表示（最初の5件）
    name_samples = [key for key in trainers_dict.keys() if isinstance(key, str) and not key.isdigit()][:5]
    if name_samples:
        try:
            print(f"  調教師名サンプル: {name_samples}")
        except UnicodeEncodeError:
            pass  # 文字コードエラーは無視
    
    # 実際のデータファイルから調教師IDと調教師名の対応を取得
    from common.config import get_races_dir
    races_dir = get_races_dir()
    
    # 最新の統合データファイルを検索
    integrated_files = list(races_dir.glob("**/integrated_*.json"))
    integrated_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    
    # 最新10ファイルを処理
    processed_count = 0
    print(f"統合データファイルを検索中: {len(integrated_files)} ファイル見つかりました")
    for json_file in integrated_files[:10]:
        try:
            print(f"  処理中: {json_file.name}")
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            entries = data.get('entries', [])
            for entry in entries:
                entry_data = entry.get('entry_data', {})
                trainer_id = entry_data.get('trainer_id')
                trainer_name = entry_data.get('trainer')
                
                if trainer_id and trainer_name and trainer_id not in index:
                    # まずCSVから調教師コードを検索（優先度: 最高）
                    trainer_info = None
                    comment = ""
                    
                    # CSVから調教師コードを検索（調教師名でマッチング）
                    for csv_code, csv_info in csv_trainer_by_code.items():
                        csv_name = csv_info.get("name", "")
                        # 接頭辞を除去して比較
                        name_without_prefix = trainer_name.replace("美", "").replace("栗", "").strip()
                        csv_name_without_prefix = csv_name.replace("美", "").replace("栗", "").strip()
                        
                        if name_without_prefix == csv_name_without_prefix or name_without_prefix in csv_name_without_prefix or csv_name_without_prefix in name_without_prefix:
                            trainer_info = {
                                "jvn_code": csv_code,
                                "name": csv_name,
                                "tozai": csv_info.get("tozai", "不明")
                            }
                            comment = csv_info.get("comment", "")
                            break
                    
                    # CSVで見つからない場合は、UM_DATAから検索
                    if not trainer_info:
                        trainer_info_dict = find_trainer_by_name(trainer_name, trainers_dict)
                        if trainer_info_dict:
                            trainer_info = trainer_info_dict
                            # CSVからコメントデータを取得（あれば）
                            if trainer_info["jvn_code"] in csv_trainer_by_code:
                                csv_info = csv_trainer_by_code[trainer_info["jvn_code"]]
                                comment = csv_info.get("comment", "")
                    
                    if trainer_info:
                        index[trainer_id] = {
                            "keibabook_id": trainer_id,
                            "jvn_code": trainer_info["jvn_code"],
                            "name": trainer_info["name"],
                            "tozai": trainer_info["tozai"],
                            "comment": comment  # コメントデータを追加
                        }
                        processed_count += 1
                        # デバッグ: マッチ成功を表示（最初の10件のみ）
                        if processed_count <= 10:
                            try:
                                print(f"  [OK] {trainer_id} ({trainer_name}) -> {trainer_info['name']} ({trainer_info['jvn_code']})")
                            except UnicodeEncodeError:
                                pass  # 文字コードエラーは無視
                    else:
                        unmatched_count += 1
                        # デバッグ: マッチしなかった調教師名を表示（最初の20件のみ）
                        if unmatched_count <= 20:
                            try:
                                # 類似名を探す
                                name_without_prefix = trainer_name.replace("美", "").replace("栗", "").strip()
                                similar = [name for name in trainers_dict.keys() if name_without_prefix in name or name in name_without_prefix]
                                if similar:
                                    print(f"  [NG] {trainer_id} ({trainer_name}) - 類似候補: {similar[:3]}")
                                else:
                                    print(f"  [NG] {trainer_id} ({trainer_name}) - 候補なし")
                            except UnicodeEncodeError:
                                pass  # 文字コードエラーは無視
        except Exception as e:
            # 文字コードエラーは無視（print文の出力エラー）
            if 'codec' not in str(e).lower() or 'encode' not in str(e).lower():
                print(f"警告: {json_file} の読み込みエラー: {e}")
            continue
    
    print(f"データファイルから {processed_count} 件の調教師マッピングを取得しました（未マッチ: {unmatched_count} 件）")
    return index


def build_index() -> Dict:
    """
    インデックス構築
    
    Returns:
        構築されたインデックス辞書
    """
    index = {}
    
    # 1. 調教師CSVファイルから読み込み（優先度: 最高）
    csv_trainers = load_trainer_csv()
    csv_trainer_by_code = {info["jvn_code"]: info for info in csv_trainers.values()}
    
    # 2. 手動マッピングを追加
    for keibabook_id, info in MANUAL_MAPPING.items():
        index[keibabook_id] = {
            "keibabook_id": keibabook_id,
            **info
        }
    
    # 既存のインデックスファイルがあれば読み込んでマージ
    if INDEX_FILE.exists():
        try:
            with open(INDEX_FILE, 'r', encoding='utf-8') as f:
                existing_index = json.load(f)
                # 既存のエントリをマージ（手動マッピングで上書き）
                for keibabook_id, info in existing_index.items():
                    if keibabook_id not in index:
                        # 既存のエントリにコメントデータがない場合、CSVから取得を試みる
                        if 'comment' not in info or not info.get('comment'):
                            jvn_code = info.get('jvn_code', '')
                            if jvn_code and jvn_code in csv_trainer_by_code:
                                csv_info = csv_trainer_by_code[jvn_code]
                                info['comment'] = csv_info.get('comment', '')
                        index[keibabook_id] = info
        except Exception as e:
            print(f"警告: 既存インデックスの読み込みエラー: {e}")
    
    # 実際のデータファイルから自動マッピングを構築
    auto_index = build_index_from_data_files()
    for keibabook_id, info in auto_index.items():
        if keibabook_id not in index:
            index[keibabook_id] = info
        else:
            # 既存のエントリにコメントデータがない場合、自動マッピングから取得
            if 'comment' not in index[keibabook_id] or not index[keibabook_id].get('comment'):
                if 'comment' in info and info.get('comment'):
                    index[keibabook_id]['comment'] = info['comment']
            # CSVからコメントデータを取得（あれば）
            jvn_code = index[keibabook_id].get('jvn_code', '')
            if jvn_code and jvn_code in csv_trainer_by_code:
                csv_info = csv_trainer_by_code[jvn_code]
                csv_comment = csv_info.get('comment', '')
                if csv_comment and (not index[keibabook_id].get('comment') or len(csv_comment) > len(index[keibabook_id].get('comment', ''))):
                    index[keibabook_id]['comment'] = csv_comment
    
    return index


def save_index(index: Dict):
    """インデックスを保存"""
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    with open(INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    
    print(f"調教師インデックス構築完了: {len(index)} 件")
    print(f"保存先: {INDEX_FILE}")


def show_index_info():
    """インデックス情報を表示"""
    if not INDEX_FILE.exists():
        print(f"インデックスファイルが見つかりません: {INDEX_FILE}")
        print("先に --build-index を実行してください。")
        return
    
    with open(INDEX_FILE, 'r', encoding='utf-8') as f:
        index = json.load(f)
    
    print(f"調教師インデックス情報")
    print(f"ファイル: {INDEX_FILE}")
    print(f"登録数: {len(index)} 件")
    print()
    
    if index:
        print("登録済み調教師:")
        for keibabook_id, info in sorted(index.items()):
            jvn_code = info.get("jvn_code", "N/A")
            name = info.get("name", "N/A")
            tozai = info.get("tozai", "N/A")
            print(f"  {keibabook_id} → {jvn_code} ({name}, {tozai})")
    else:
        print("登録されている調教師はありません。")


def main():
    parser = argparse.ArgumentParser(description="調教師IDインデックス構築スクリプト")
    parser.add_argument(
        '--build-index',
        action='store_true',
        help='インデックスを構築'
    )
    parser.add_argument(
        '--info',
        action='store_true',
        help='インデックス情報を表示'
    )
    parser.add_argument(
        '--list-trainers',
        action='store_true',
        help='UM_DATAから調教師一覧を表示（調教師名 → JRA-VANコード）'
    )
    
    args = parser.parse_args()
    
    if args.build_index:
        index = build_index()
        save_index(index)
        if len(index) == 0:
            print()
            print("⚠️  インデックスが空です。")
            print("   競馬ブックのスクレイピングデータから trainer_id を取得後、")
            print("   手動で MANUAL_MAPPING に追加するか、--list-trainers で")
            print("   調教師一覧を確認してマッピングを作成してください。")
    elif args.info:
        show_index_info()
    elif args.list_trainers:
        trainers = get_trainers_from_um_data()
        if trainers:
            print(f"\nUM_DATAから取得した調教師一覧 ({len(trainers)} 名):")
            print("=" * 80)
            for name, info in sorted(trainers.items()):
                print(f"  {info['name']:12} → JRA-VAN: {info['jvn_code']:5} ({info['tozai']})")
            print("=" * 80)
            print("\nこれらの情報を元に、競馬ブックの厩舎IDとマッピングしてください。")
        else:
            print("調教師情報を取得できませんでした。")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
