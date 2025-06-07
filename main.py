#!/usr/bin/env python3
"""
競馬ブックスクレイピングシステム メインファイル

使用方法:
    python main.py --race-id 202502041211 --mode scrape_and_parse
    python main.py --race-id 202502041211 --mode parse_only --html-file data/debug/seiseki.html
    python main.py --test
"""

import argparse
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.scrapers.keibabook_scraper import KeibabookScraper
from src.parsers.seiseki_parser import SeisekiParser
from src.utils.config import Config
from src.utils.logger import setup_logger


def scrape_and_parse(race_id: str, save_html: bool = True) -> bool:
    """
    スクレイピングとパースを実行する
    
    Args:
        race_id: レースID
        save_html: HTMLファイルを保存するかどうか
        
    Returns:
        bool: 成功した場合True
    """
    logger = setup_logger("main", level="INFO")
    
    try:
        # 必要なディレクトリを作成
        Config.ensure_directories()
        
        logger.info(f"レースID {race_id} のデータ取得を開始します")
        
        # ステップ1: スクレイピング
        logger.info("=== データのスクレイピング ===")
        scraper = KeibabookScraper(
            headless=Config.get_headless_mode(),
            debug=Config.get_debug_mode()
        )
        
        html_file_path = None
        if save_html:
            html_file_path = Config.DEBUG_DIR / f"seiseki_{race_id}_scraped.html"
        
        html_content = scraper.scrape_seiseki_page(race_id, str(html_file_path) if html_file_path else None)
        
        # コンテンツ検証
        if not scraper.validate_page_content(html_content):
            logger.error("取得したHTMLコンテンツに問題があります")
            return False
        
        # ステップ2: パース
        logger.info("=== データのパース ===")
        parser = SeisekiParser(debug=Config.get_debug_mode())
        
        if html_file_path and html_file_path.exists():
            data = parser.parse(str(html_file_path))
        else:
            # HTMLファイルが保存されていない場合は一時的に保存
            temp_html_path = Config.DEBUG_DIR / f"temp_seiseki_{race_id}.html"
            with open(temp_html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            data = parser.parse(str(temp_html_path))
            temp_html_path.unlink()  # 一時ファイルを削除
        
        # データ検証
        if not parser.validate_data(data):
            logger.error("抽出されたデータが不正です")
            return False
        
        # ステップ3: 結果の保存
        logger.info("=== 結果の保存 ===")
        output_path = Config.SEISEKI_DIR / f"seiseki_{race_id}.json"
        parser.save_json(data, str(output_path))
        
        # 統計情報を表示
        results = data.get("results", [])
        interview_count = sum(1 for result in results if result.get("interview", "").strip())
        memo_count = sum(1 for result in results if result.get("memo", "").strip())
        
        logger.info(f"✅ 処理が完了しました")
        logger.info(f"出走頭数: {len(results)}頭")
        logger.info(f"インタビュー有り: {interview_count}頭")
        logger.info(f"メモ有り: {memo_count}頭")
        logger.info(f"保存先: {output_path}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ エラーが発生しました: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def parse_only(html_file_path: str, race_id: str = None) -> bool:
    """
    HTMLファイルのパースのみを実行する
    
    Args:
        html_file_path: HTMLファイルのパス
        race_id: レースID（出力ファイル名の生成に使用）
        
    Returns:
        bool: 成功した場合True
    """
    logger = setup_logger("main", level="INFO")
    
    try:
        # 必要なディレクトリを作成
        Config.ensure_directories()
        
        # HTMLファイルの存在確認
        html_path = Path(html_file_path)
        if not html_path.exists():
            logger.error(f"HTMLファイルが見つかりません: {html_file_path}")
            return False
        
        logger.info(f"HTMLファイルのパースを開始します: {html_file_path}")
        
        # パース実行
        parser = SeisekiParser(debug=Config.get_debug_mode())
        data = parser.parse(str(html_path))
        
        # データ検証
        if not parser.validate_data(data):
            logger.error("抽出されたデータが不正です")
            return False
        
        # 結果の保存
        if race_id:
            output_filename = f"seiseki_{race_id}.json"
        else:
            output_filename = f"seiseki_{html_path.stem}.json"
        
        output_path = Config.SEISEKI_DIR / output_filename
        parser.save_json(data, str(output_path))
        
        # 統計情報を表示
        results = data.get("results", [])
        interview_count = sum(1 for result in results if result.get("interview", "").strip())
        memo_count = sum(1 for result in results if result.get("memo", "").strip())
        
        logger.info(f"✅ パースが完了しました")
        logger.info(f"出走頭数: {len(results)}頭")
        logger.info(f"インタビュー有り: {interview_count}頭")
        logger.info(f"メモ有り: {memo_count}頭")
        logger.info(f"保存先: {output_path}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ エラーが発生しました: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def run_tests() -> bool:
    """
    テストを実行する
    
    Returns:
        bool: 成功した場合True
    """
    logger = setup_logger("main", level="INFO")
    
    try:
        logger.info("統合テストを実行します")
        
        # テストモジュールをインポート
        from tests.test_new_seiseki_parser import test_seiseki_parser, test_parser_validation
        from tests.test_integration import test_full_workflow, test_error_handling
        
        # 各テストを実行
        tests = [
            ("成績パーサーテスト", test_seiseki_parser),
            ("パーサーバリデーションテスト", test_parser_validation),
            ("統合テスト", test_full_workflow),
            ("エラーハンドリングテスト", test_error_handling)
        ]
        
        results = []
        for test_name, test_func in tests:
            logger.info(f"実行中: {test_name}")
            try:
                if callable(test_func):
                    result = test_func()
                    results.append((test_name, result))
                    if result:
                        logger.info(f"✅ {test_name}: 成功")
                    else:
                        logger.error(f"❌ {test_name}: 失敗")
                else:
                    logger.warning(f"⚠️ {test_name}: テスト関数が呼び出し可能ではありません")
            except Exception as e:
                logger.error(f"❌ {test_name}: エラー - {e}")
                results.append((test_name, False))
        
        # 結果のサマリー
        success_count = sum(1 for _, result in results if result)
        total_count = len(results)
        
        logger.info(f"テスト結果: {success_count}/{total_count} 成功")
        
        return success_count == total_count
        
    except Exception as e:
        logger.error(f"❌ テスト実行中にエラーが発生しました: {e}")
        return False


def main():
    """
    メイン関数
    """
    parser = argparse.ArgumentParser(description="競馬ブックスクレイピングシステム")
    parser.add_argument("--race-id", type=str, help="レースID")
    parser.add_argument("--mode", type=str, choices=["scrape_and_parse", "parse_only"], 
                       default="scrape_and_parse", help="実行モード")
    parser.add_argument("--html-file", type=str, help="HTMLファイルのパス（parse_onlyモード用）")
    parser.add_argument("--test", action="store_true", help="テストを実行")
    parser.add_argument("--no-save-html", action="store_true", help="HTMLファイルを保存しない")
    
    args = parser.parse_args()
    
    if args.test:
        success = run_tests()
        sys.exit(0 if success else 1)
    
    if not args.race_id:
        parser.error("--race-id が必要です（--test モード以外）")
    
    if args.mode == "scrape_and_parse":
        success = scrape_and_parse(args.race_id, save_html=not args.no_save_html)
    elif args.mode == "parse_only":
        if not args.html_file:
            parser.error("--html-file が必要です（parse_only モード）")
        success = parse_only(args.html_file, args.race_id)
    else:
        parser.error("無効なモードです")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()