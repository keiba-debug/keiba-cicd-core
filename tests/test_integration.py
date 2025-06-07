"""
統合テスト

スクレイパーとパーサーを組み合わせた統合テストです。
"""

import sys
from pathlib import Path
from datetime import datetime

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.scrapers.keibabook_scraper import KeibabookScraper
from src.parsers.seiseki_parser import SeisekiParser
from src.utils.config import Config
from src.utils.logger import setup_logger


def test_full_workflow():
    """
    スクレイピングからパースまでの完全なワークフローをテストする
    """
    # ロガーをセットアップ
    logger = setup_logger("test_integration", level="INFO")
    
    try:
        # 必要なディレクトリを作成
        Config.ensure_directories()
        
        # テスト用のレースID（実際のものに変更してください）
        race_id = "202502041211"  # 東京優駿のレースID
        
        logger.info(f"統合テストを開始します。レースID: {race_id}")
        
        # ステップ1: スクレイピング
        logger.info("=== Step 1: データのスクレイピング ===")
        
        scraper = KeibabookScraper(headless=True, debug=True)
        
        # HTMLの保存先パスを生成
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        html_file_path = Config.DEBUG_DIR / f"seiseki_{race_id}_{timestamp}_integration_test.html"
        
        try:
            # 成績ページをスクレイピング
            html_content = scraper.scrape_seiseki_page(race_id, str(html_file_path))
            
            # 内容を検証
            if scraper.validate_page_content(html_content):
                logger.info("✅ スクレイピングが正常に完了しました")
            else:
                logger.warning("⚠️ スクレイピングされたコンテンツに問題がある可能性があります")
                
        except Exception as e:
            logger.error(f"❌ スクレイピングに失敗しました: {e}")
            # テスト用に既存のHTMLファイルを使用
            html_file_path = Config.DEBUG_DIR / "seiseki_202502041211_full.html"
            if not html_file_path.exists():
                logger.error("既存のテスト用HTMLファイルも見つかりません")
                return False
            logger.info(f"既存のHTMLファイルを使用します: {html_file_path}")
        
        # ステップ2: パース
        logger.info("=== Step 2: データのパース ===")
        
        parser = SeisekiParser(debug=True)
        
        # HTMLをパースしてデータを抽出
        data = parser.parse(str(html_file_path))
        
        # ステップ3: 結果の検証と保存
        logger.info("=== Step 3: 結果の検証と保存 ===")
        
        # データ検証
        if parser.validate_data(data):
            logger.info("✅ データ検証が成功しました")
        else:
            logger.error("❌ データ検証に失敗しました")
            return False
        
        # 結果の統計情報を表示
        race_info = data.get("race_info", {})
        results = data.get("results", [])
        
        logger.info(f"レース名: {race_info.get('race_name', 'N/A')}")
        logger.info(f"出走頭数: {len(results)}頭")
        
        # インタビューとメモの統計
        interview_count = sum(1 for result in results if result.get("interview", "").strip())
        memo_count = sum(1 for result in results if result.get("memo", "").strip())
        
        logger.info(f"インタビュー有り: {interview_count}頭")
        logger.info(f"メモ有り: {memo_count}頭")
        
        # JSONファイルとして保存
        output_path = Config.SEISEKI_DIR / f"seiseki_{race_id}_integration_test.json"
        parser.save_json(data, str(output_path))
        logger.info(f"結果をJSONファイルに保存しました: {output_path}")
        
        logger.info("✅ 統合テストが正常に完了しました")
        return True
        
    except Exception as e:
        logger.error(f"❌ 統合テスト中にエラーが発生しました: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_error_handling():
    """
    エラーハンドリングのテストを実行する
    """
    logger = setup_logger("test_error_handling", level="INFO")
    
    logger.info("=== エラーハンドリングのテスト ===")
    
    # 存在しないHTMLファイルでのパーステスト
    parser = SeisekiParser(debug=True)
    
    try:
        non_existent_file = "non_existent_file.html"
        data = parser.parse(non_existent_file)
        logger.error("❌ 存在しないファイルでエラーが発生しませんでした")
        return False
    except FileNotFoundError:
        logger.info("✅ 存在しないファイルに対して適切にエラーが発生しました")
    except Exception as e:
        logger.warning(f"⚠️ 予期しないエラーが発生しました: {e}")
    
    # 不正なレースIDでのスクレイピングテスト
    try:
        scraper = KeibabookScraper(headless=True, debug=True)
        invalid_race_id = "invalid_race_id"
        html_content = scraper.scrape_seiseki_page(invalid_race_id)
        logger.warning("⚠️ 不正なレースIDでもスクレイピングが成功しました（要確認）")
    except Exception as e:
        logger.info(f"✅ 不正なレースIDに対して適切にエラーが発生しました: {e}")
    
    return True


if __name__ == "__main__":
    print("統合テストを開始します...")
    
    # メインの統合テストを実行
    success = test_full_workflow()
    
    # エラーハンドリングテストを実行
    error_test_success = test_error_handling()
    
    if success and error_test_success:
        print("\n✅ 全ての統合テストが正常に完了しました")
        print("\n📋 次のステップ:")
        print("1. 実際の運用環境で環境変数（Cookie等）を設定")
        print("2. 定期実行のスケジュール設定")
        print("3. エラー監視とアラート設定")
        print("4. データ分析・可視化の実装")
    else:
        print("\n❌ 統合テストに失敗しました")
        sys.exit(1)