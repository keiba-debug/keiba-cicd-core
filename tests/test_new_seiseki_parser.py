"""
新しい成績パーサーのテスト

リファクタリング後の成績パーサーの動作を確認します。
"""

import json
import logging
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.parsers.seiseki_parser import SeisekiParser
from src.utils.config import Config
from src.utils.logger import setup_logger


def test_seiseki_parser():
    """
    成績パーサーのテストを実行する
    """
    # ロガーをセットアップ
    logger = setup_logger("test_seiseki_parser", level="DEBUG")
    
    try:
        # 必要なディレクトリを作成
        Config.ensure_directories()
        
        # テスト用HTMLファイルのパス
        html_file_path = "data/debug/seiseki_202502041211_full.html"
        
        if not Path(html_file_path).exists():
            logger.error(f"テスト用HTMLファイルが見つかりません: {html_file_path}")
            return False
        
        # パーサーを初期化
        parser = SeisekiParser(debug=True)
        
        # HTMLをパースしてデータを抽出
        logger.info("成績データの抽出を開始します")
        data = parser.parse(html_file_path)
        
        # 結果を表示
        logger.info("=== レース情報 ===")
        race_info = data.get("race_info", {})
        for key, value in race_info.items():
            logger.info(f"{key}: {value}")
        
        logger.info("=== 成績データ ===")
        results = data.get("results", [])
        logger.info(f"総出走頭数: {len(results)}頭")
        
        # 各馬の詳細情報を表示（最初の3頭のみ）
        for i, result in enumerate(results[:3]):
            logger.info(f"\n--- {i+1}頭目 ---")
            for key, value in result.items():
                if key in ["interview", "memo"]:
                    # インタビューとメモは最初の50文字のみ表示
                    display_value = value[:50] + "..." if len(value) > 50 else value
                    logger.info(f"{key}: {display_value}")
                else:
                    logger.info(f"{key}: {value}")
        
        # インタビューとメモの統計
        interview_count = sum(1 for result in results if result.get("interview", "").strip())
        memo_count = sum(1 for result in results if result.get("memo", "").strip())
        
        logger.info(f"\nインタビュー有り: {interview_count}頭")
        logger.info(f"メモ有り: {memo_count}頭")
        
        # JSONファイルとして保存
        output_path = Config.SEISEKI_DIR / "seiseki_test_result.json"
        parser.save_json(data, str(output_path))
        logger.info(f"結果をJSONファイルに保存しました: {output_path}")
        
        # データ検証
        if parser.validate_data(data):
            logger.info("✅ テストが正常に完了しました")
            return True
        else:
            logger.error("❌ データ検証に失敗しました")
            return False
            
    except Exception as e:
        logger.error(f"❌ テスト中にエラーが発生しました: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_parser_validation():
    """
    パーサーのバリデーション機能をテストする
    """
    logger = logging.getLogger("test_seiseki_parser")
    
    parser = SeisekiParser(debug=True)
    
    # 正常なデータのテスト
    valid_data = {
        "race_info": {
            "race_name": "テストレース"
        },
        "results": [
            {
                "着順": "1",
                "馬名": "テスト馬",
                "騎手": "テスト騎手",
                "interview": "テストインタビュー",
                "memo": "テストメモ"
            }
        ]
    }
    
    if parser.validate_data(valid_data):
        logger.info("✅ 正常データのバリデーションが成功しました")
    else:
        logger.error("❌ 正常データのバリデーションが失敗しました")
    
    # 異常なデータのテスト
    invalid_data = {
        "race_info": {},  # レース名なし
        "results": []     # 空の結果
    }
    
    if not parser.validate_data(invalid_data):
        logger.info("✅ 異常データのバリデーションが正しく失敗しました")
    else:
        logger.error("❌ 異常データのバリデーションが期待通りに失敗しませんでした")


if __name__ == "__main__":
    print("新しい成績パーサーのテストを開始します...")
    
    # メインテストを実行
    success = test_seiseki_parser()
    
    # バリデーションテストを実行
    test_parser_validation()
    
    if success:
        print("\n✅ 全てのテストが正常に完了しました")
    else:
        print("\n❌ テストに失敗しました")
        sys.exit(1)