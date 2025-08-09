#!/usr/bin/env python3
"""
競馬ブックスクレイピングシステム メインファイル

使用方法:
    python src/keibabook/main.py --race-id 202502041211 --mode scrape_and_parse
    python src/keibabook/main.py --race-id 202502041211 --mode parse_only --html-file data/debug/seiseki.html
    python src/keibabook/main.py --test
"""

import argparse
import sys
from pathlib import Path
from typing import List

# プロジェクトルートとソースディレクトリのパスを追加
project_root = Path(__file__).parent.parent.parent  # keiba-cicd-coreプロジェクトルート
src_dir = Path(__file__).parent  # KeibaCICD.keibabook/src
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(src_dir))

# .envファイルの読み込み
try:
    from dotenv import load_dotenv
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"[INFO] .envファイルを読み込みました: {env_path}")
except ImportError:
    print("[WARNING] python-dotenvがインストールされていません。")

from .scrapers.keibabook_scraper import KeibabookScraper
from .scrapers.requests_scraper import RequestsScraper
from .parsers.seiseki_parser import SeisekiParser
from .parsers.syutuba_parser import SyutubaParser
from .parsers.cyokyo_parser import CyokyoParser
from .parsers.danwa_parser import DanwaParser
from .utils.config import Config
from .utils.logger import setup_logger
from .batch.core.common import get_json_file_path, ensure_batch_directories
# from batch_processor import BatchProcessor  # 存在しないファイル
# from simple_batch import SimpleBatchProcessor  # 存在しないファイル


def scrape_and_parse(race_id: str, save_html: bool = True, use_requests: bool = False) -> bool:
    """
    スクレイピングとパースを実行する
    
    Args:
        race_id: レースID
        save_html: HTMLファイルを保存するかどうか
        use_requests: requestsライブラリを使用するかどうか（Chromeなし）
        
    Returns:
        bool: 成功した場合True
    """
    logger = setup_logger("main", level="INFO")
    
    try:
        # 必要なディレクトリを作成（従来 + 新保存先）
        Config.ensure_directories()
        ensure_batch_directories()
        
        logger.info(f"レースID {race_id} のデータ取得を開始します")
        
        # ステップ1: スクレイピング
        logger.info("=== データのスクレイピング ===")
        
        if use_requests:
            logger.info("requestsベーススクレイパーを使用します")
            scraper = RequestsScraper(debug=Config.get_debug_mode())
        else:
            logger.info("Seleniumベーススクレイパーを使用します")
            scraper = KeibabookScraper(
                headless=Config.get_headless_mode(),
                debug=Config.get_debug_mode()
            )
        
        html_file_path = None
        if save_html:
            html_file_path = Config.get_debug_dir() / f"seiseki_{race_id}_scraped.html"
        
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
            temp_html_path = Config.get_debug_dir() / f"temp_seiseki_{race_id}.html"
            with open(temp_html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            data = parser.parse(str(temp_html_path))
            temp_html_path.unlink()  # 一時ファイルを削除
        
        # データ検証
        if not parser.validate_data(data):
            logger.error("抽出されたデータが不正です")
            return False
        
        # ステップ3: 結果の保存（保存先を KEIBA_DATA_ROOT_DIR に統一）
        logger.info("=== 結果の保存 ===")
        output_path = Path(get_json_file_path('seiseki', race_id))
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
        # 必要なディレクトリを作成（従来 + 新保存先）
        Config.ensure_directories()
        ensure_batch_directories()
        
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
        identifier = race_id if race_id else html_path.stem
        output_path = Path(get_json_file_path('seiseki', identifier))
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


def batch_process_date_range(from_date_str: str, to_date_str: str, 
                           use_requests: bool = True, save_html: bool = True) -> bool:
    """
    開催日範囲での全レース処理
    
    Args:
        from_date_str: 開始日 (YYYY-MM-DD形式)
        to_date_str: 終了日 (YYYY-MM-DD形式)
        use_requests: requestsスクレイパーを使用するか
        save_html: HTMLファイルを保存するか
        
    Returns:
        bool: 成功した場合True
    """
    logger = setup_logger("batch_main", level="INFO")
    
    try:
        # 日付のパース
        from datetime import datetime
        from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
        to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
        
        if from_date > to_date:
            logger.error("開始日が終了日より後になっています")
            return False
        
        logger.info(f"🏇 開催日範囲バッチ処理開始")
        logger.info(f"📅 期間: {from_date} ～ {to_date}")
        logger.info(f"🔧 スクレイパー: {'requests' if use_requests else 'Selenium'}")
        
        # バッチプロセッサー初期化
        processor = BatchProcessor(use_requests=use_requests, debug=Config.get_debug_mode())
        
        # ステップ1: レースID取得
        logger.info("=" * 50)
        logger.info("🔍 ステップ1: レースID取得")
        logger.info("=" * 50)
        
        race_ids = processor.get_race_ids_for_date_range(from_date, to_date)
        
        if not race_ids:
            logger.warning("指定期間にレースが見つかりませんでした")
            return True
        
        logger.info(f"📊 取得したレース数: {len(race_ids)}")
        
        # ステップ2: 全レース処理
        logger.info("=" * 50)
        logger.info("⚙️ ステップ2: 全レース処理")
        logger.info("=" * 50)
        
        results = processor.process_all_races(race_ids, save_html=save_html)
        
        # 結果表示
        stats = results['stats']
        logger.info("🎉 バッチ処理完了！")
        logger.info(f"✅ 成功: {stats['success_count']}/{stats['total_races']} レース")
        
        if stats['error_count'] > 0:
            logger.warning(f"⚠️ エラー: {stats['error_count']} レース")
        
        if stats['skipped_count'] > 0:
            logger.info(f"⏭️ スキップ: {stats['skipped_count']} レース (既処理済み)")
        
        return stats['error_count'] == 0
        
    except ValueError as e:
        logger.error(f"日付フォーマットエラー: {e}")
        logger.error("日付は YYYY-MM-DD 形式で指定してください (例: 2025-02-01)")
        return False
    except Exception as e:
        logger.error(f"❌ バッチ処理エラー: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def scrape_and_parse_multi_type(race_id: str, data_types: List[str], 
                               save_html: bool = True, use_requests: bool = False) -> bool:
    """
    複数のデータタイプを一括で取得・パース
    
    Args:
        race_id: レースID
        data_types: データタイプのリスト (['seiseki', 'syutuba', 'cyokyo', 'danwa'])
        save_html: HTMLファイルを保存するかどうか
        use_requests: requestsライブラリを使用するかどうか
        
    Returns:
        bool: 成功した場合True
    """
    logger = setup_logger("multi_main", level="INFO")
    
    try:
        # 必要なディレクトリを作成（従来 + 新保存先）
        Config.ensure_directories()
        ensure_batch_directories()
        
        logger.info(f"🏇 複数データタイプ処理開始: レースID {race_id}")
        logger.info(f"📊 対象データタイプ: {', '.join(data_types)}")
        
        # スクレイパー初期化
        if use_requests:
            logger.info("requestsベーススクレイパーを使用します")
            scraper = RequestsScraper(debug=Config.get_debug_mode())
        else:
            logger.info("Seleniumベーススクレイパーを使用します")
            scraper = KeibabookScraper(
                headless=Config.get_headless_mode(),
                debug=Config.get_debug_mode()
            )
        
        # パーサー辞書
        parsers = {
            'seiseki': SeisekiParser(debug=Config.get_debug_mode()),
            'syutuba': SyutubaParser(debug=Config.get_debug_mode()),
            'cyokyo': CyokyoParser(debug=Config.get_debug_mode()),
            'danwa': DanwaParser(debug=Config.get_debug_mode())
        }
        
        results = {}
        
        for data_type in data_types:
            logger.info(f"=" * 50)
            logger.info(f"📋 データタイプ: {data_type}")
            logger.info(f"=" * 50)
            
            try:
                # HTMLファイルパス
                html_file_path = None
                if save_html:
                    html_file_path = Config.get_debug_dir() / f"{data_type}_{race_id}_scraped.html"
                
                # スクレイピング
                html_content = scraper.scrape_page(data_type, race_id, str(html_file_path) if html_file_path else None)
                
                # コンテンツ検証
                if not scraper.validate_page_content(html_content):
                    logger.warning(f"{data_type}: HTMLコンテンツに問題があります")
                    results[data_type] = False
                    continue
                
                # パース
                parser = parsers[data_type]
                if html_file_path and html_file_path.exists():
                    data = parser.parse(str(html_file_path))
                else:
                    # 一時ファイル作成してパース
                    temp_html_path = Config.get_debug_dir() / f"temp_{data_type}_{race_id}.html"
                    with open(temp_html_path, 'w', encoding='utf-8') as f:
                        f.write(html_content)
                    data = parser.parse(str(temp_html_path))
                    temp_html_path.unlink()
                
                # データ検証
                if not parser.validate_data(data):
                    logger.warning(f"{data_type}: 抽出されたデータが不正です")
                    results[data_type] = False
                    continue
                
                # 保存（保存先を KEIBA_DATA_ROOT_DIR に統一）
                output_path = Path(get_json_file_path(data_type, race_id))
                parser.save_json(data, str(output_path))
                
                logger.info(f"✅ {data_type}: 保存完了 - {output_path}")
                results[data_type] = True
                
            except Exception as e:
                logger.error(f"❌ {data_type}: エラー - {e}")
                results[data_type] = False
        
        # 結果サマリー
        logger.info("=" * 50)
        logger.info("📊 処理結果サマリー")
        logger.info("=" * 50)
        
        success_count = sum(1 for success in results.values() if success)
        total_count = len(data_types)
        
        for data_type, success in results.items():
            status = "✅ 成功" if success else "❌ 失敗"
            logger.info(f"  - {data_type}: {status}")
        
        logger.info(f"🎯 成功率: {success_count}/{total_count} ({(success_count/total_count)*100:.1f}%)")
        
        return success_count == total_count
        
    except Exception as e:
        logger.error(f"❌ 複数データタイプ処理エラー: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def simple_batch_process_date_range(from_date_str: str, to_date_str: str, 
                                   use_requests: bool = True, save_html: bool = True) -> bool:
    """
    シンプルバッチ処理での日付範囲処理
    
    Args:
        from_date_str: 開始日 (YYYY-MM-DD形式)
        to_date_str: 終了日 (YYYY-MM-DD形式)
        use_requests: requestsスクレイパーを使用するか
        save_html: HTMLファイルを保存するか
        
    Returns:
        bool: 成功した場合True
    """
    logger = setup_logger("simple_batch_main", level="INFO")
    
    try:
        logger.info(f"🏇 シンプルバッチ処理開始")
        logger.info(f"📅 期間: {from_date_str} ～ {to_date_str}")
        logger.info(f"🔧 スクレイパー: {'requests' if use_requests else 'Selenium'}")
        
        # シンプルバッチプロセッサー初期化
        processor = SimpleBatchProcessor(use_requests=use_requests, debug=Config.get_debug_mode())
        
        # ステップ1: レースID生成
        logger.info("=" * 50)
        logger.info("🔢 ステップ1: レースID生成")
        logger.info("=" * 50)
        
        race_ids = processor.generate_race_ids_for_date_range(from_date_str, to_date_str)
        
        if not race_ids:
            logger.warning("レースIDが生成されませんでした")
            return True
        
        logger.info(f"📊 生成されたレース数: {len(race_ids)}")
        
        # ステップ2: 最初の数件でテスト
        test_race_ids = race_ids[:5]  # 最初の5件でテスト
        logger.info(f"🧪 テスト実行: 最初の {len(test_race_ids)} 件")
        for test_id in test_race_ids:
            logger.info(f"  - {test_id}")
        
        # ステップ3: 実際の処理
        logger.info("=" * 50)
        logger.info("⚙️ ステップ3: レース処理")
        logger.info("=" * 50)
        
        results = processor.process_race_ids(test_race_ids, save_html=save_html, max_errors=3)
        
        # 結果表示
        stats = results['stats']
        logger.info("🎉 シンプルバッチ処理完了！")
        logger.info(f"✅ 成功: {stats['success_count']}/{stats['total_races']} レース")
        
        if stats['error_count'] > 0:
            logger.warning(f"⚠️ エラー: {stats['error_count']} レース")
        
        if stats['skipped_count'] > 0:
            logger.info(f"⏭️ スキップ: {stats['skipped_count']} レース (既処理済み)")
        
        return stats['error_count'] == 0
        
    except Exception as e:
        logger.error(f"❌ シンプルバッチ処理エラー: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def run_tests() -> bool:
    """
    簡単な動作テストを実行する
    
    Returns:
        bool: 成功した場合True
    """
    logger = setup_logger("main", level="INFO")
    
    try:
        logger.info("システム動作テストを実行します")
        
        # 基本的なシステムテスト
        tests = [
            ("設定ファイル読み込み", test_config_loading),
            ("パーサー初期化", test_parsers_initialization),
            ("ディレクトリ作成", test_directory_creation),
            ("基本機能チェック", test_basic_functionality)
        ]
        
        results = []
        for test_name, test_func in tests:
            logger.info(f"実行中: {test_name}")
            try:
                result = test_func()
                results.append((test_name, result))
                if result:
                    logger.info(f"✅ {test_name}: 成功")
                else:
                    logger.error(f"❌ {test_name}: 失敗")
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


def test_config_loading() -> bool:
    """設定ファイル読み込みテスト"""
    try:
        Config.ensure_directories()
        return True
    except Exception as e:
        print(f"設定エラー: {e}")
        return False


def test_parsers_initialization() -> bool:
    """パーサー初期化テスト"""
    try:
        from .parsers.seiseki_parser import SeisekiParser
        from .parsers.syutuba_parser import SyutubaParser
        
        seiseki_parser = SeisekiParser(debug=True)
        syutuba_parser = SyutubaParser(debug=True)
        
        return True
    except Exception as e:
        print(f"パーサー初期化エラー: {e}")
        return False


def test_directory_creation() -> bool:
    """ディレクトリ作成テスト"""
    try:
        data_dir = Config.get_data_dir()
        debug_dir = Config.get_debug_dir()
        seiseki_dir = Config.get_seiseki_dir()
        
        return data_dir.exists() and debug_dir.exists() and seiseki_dir.exists()
    except Exception as e:
        print(f"ディレクトリエラー: {e}")
        return False


def test_basic_functionality() -> bool:
    """基本機能チェック"""
    try:
        from .utils.logger import setup_logger
        test_logger = setup_logger("test", level="INFO")
        test_logger.info("基本機能テスト")
        return True
    except Exception as e:
        print(f"基本機能エラー: {e}")
        return False


def main():
    """
    メイン関数
    """
    parser = argparse.ArgumentParser(description="競馬ブックスクレイピングシステム")
    parser.add_argument("--race-id", type=str, help="レースID")
    parser.add_argument("--mode", type=str, choices=["scrape_and_parse", "parse_only", "multi_type", "batch", "simple_batch"], 
                       default="scrape_and_parse", help="実行モード")
    parser.add_argument("--html-file", type=str, help="HTMLファイルのパス（parse_onlyモード用）")
    parser.add_argument("--from-date", type=str, help="開始日 (YYYY-MM-DD形式、batchモード用)")
    parser.add_argument("--to-date", type=str, help="終了日 (YYYY-MM-DD形式、batchモード用)")
    parser.add_argument("--test", action="store_true", help="テストを実行")
    parser.add_argument("--no-save-html", action="store_true", help="HTMLファイルを保存しない")
    parser.add_argument("--use-requests", action="store_true", help="requestsライブラリを使用（Chromeなし）")
    parser.add_argument("--data-types", type=str, nargs='+', 
                       choices=['seiseki', 'syutuba', 'cyokyo', 'danwa'],
                       default=['seiseki'],
                       help="取得するデータタイプ (複数指定可能、multi_typeモード用)")
    
    args = parser.parse_args()
    
    if args.test:
        success = run_tests()
        sys.exit(0 if success else 1)
    
    if args.mode == "batch":
        # バッチモードの場合
        if not args.from_date or not args.to_date:
            parser.error("--from-date と --to-date が必要です（batch モード）")
        success = batch_process_date_range(
            args.from_date, 
            args.to_date, 
            use_requests=args.use_requests, 
            save_html=not args.no_save_html
        )
    elif args.mode == "simple_batch":
        # シンプルバッチモードの場合
        if not args.from_date or not args.to_date:
            parser.error("--from-date と --to-date が必要です（simple_batch モード）")
        success = simple_batch_process_date_range(
            args.from_date, 
            args.to_date, 
            use_requests=args.use_requests, 
            save_html=not args.no_save_html
        )
    elif args.mode == "scrape_and_parse":
        # 単一レース処理
        if not args.race_id:
            parser.error("--race-id が必要です（scrape_and_parse モード）")
        success = scrape_and_parse(args.race_id, save_html=not args.no_save_html, use_requests=args.use_requests)
    elif args.mode == "parse_only":
        # パースのみ
        if not args.html_file:
            parser.error("--html-file が必要です（parse_only モード）")
        if not args.race_id:
            parser.error("--race-id が必要です（parse_only モード）")
        success = parse_only(args.html_file, args.race_id)
    elif args.mode == "multi_type":
        # 複数データタイプ処理
        if not args.race_id:
            parser.error("--race-id が必要です（multi_type モード）")
        success = scrape_and_parse_multi_type(
            args.race_id, 
            args.data_types, 
            save_html=not args.no_save_html, 
            use_requests=args.use_requests
        )
    else:
        parser.error("無効なモードです")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()