"""
騎手情報管理CLI
騎手成績の取得・更新を行うコマンドラインインターフェース
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import sys
import os
# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from scrapers.jockey_scraper import JockeyScraper
except ImportError:
    # 直接ファイルを読み込む
    exec(open(os.path.join(os.path.dirname(__file__), 'scrapers', 'jockey_scraper.py')).read())

try:
    from utils.logger import get_logger
except ImportError:
    # 簡易ロガー
    class SimpleLogger:
        def info(self, msg): print(f"[INFO] {msg}")
        def warning(self, msg): print(f"[WARN] {msg}")
        def error(self, msg): print(f"[ERROR] {msg}")

    def get_logger(name):
        return SimpleLogger()


def main():
    """メイン処理"""
    print("[DEBUG] jockey_cli started")
    parser = argparse.ArgumentParser(description='騎手情報管理CLI')
    subparsers = parser.add_subparsers(dest='command', help='コマンド')

    # リーディング取得コマンド
    leading_parser = subparsers.add_parser('leading', help='リーディング騎手情報を取得')
    leading_parser.add_argument('--year', type=int, help='年（省略時は現在年）')
    leading_parser.add_argument('--month', type=int, help='月（省略時は現在月）')

    # 騎手プロファイル取得コマンド
    profile_parser = subparsers.add_parser('profile', help='騎手プロファイルを取得')
    profile_parser.add_argument('jockey_id', help='騎手ID')
    profile_parser.add_argument('--name', help='騎手名')

    # 一括更新コマンド
    update_parser = subparsers.add_parser('update', help='騎手情報を一括更新')
    update_parser.add_argument('--date', help='対象日付 (YYYY/MM/DD)')
    update_parser.add_argument('--top', type=int, default=20, help='上位N名の騎手を更新（デフォルト: 20）')

    args = parser.parse_args()
    print(f"[DEBUG] command={args.command}")

    # ロガー初期化
    logger = get_logger('jockey_cli')
    logger.info(f"騎手情報管理CLI開始: command={args.command}")

    if not args.command:
        print("[ERROR] コマンドが指定されていません")
        parser.print_help()
        return

    try:
        scraper = JockeyScraper()

        if args.command == 'leading':
            # リーディング情報取得
            year = args.year or datetime.now().year
            month = args.month or datetime.now().month
            logger.info(f"リーディング情報取得: {year}年{month}月")

            result = scraper.scrape_leading_jockeys(year, month)

            if result:
                logger.info(f"リーディング騎手数: {len(result.get('rankings', []))}")
                # 上位5名を表示
                for ranking in result.get('rankings', [])[:5]:
                    print(f"{ranking['rank']}位: {ranking['jockey_name']} - "
                          f"{ranking['wins']}勝/{ranking['rides']}騎乗 "
                          f"(勝率{ranking['win_rate']}%)")
            else:
                logger.warning("リーディング情報が取得できませんでした")

        elif args.command == 'profile':
            # 騎手プロファイル取得
            logger.info(f"騎手プロファイル取得: ID={args.jockey_id}")

            result = scraper.scrape_jockey_profile(args.jockey_id, args.name)

            if result:
                print(f"騎手名: {result.get('name', '-')}")
                print(f"所属: {result.get('affiliation', '-')}")
                if result.get('stats', {}).get('total'):
                    total = result['stats']['total']
                    print(f"通算成績: {total.get('wins', 0)}勝/{total.get('rides', 0)}騎乗")
            else:
                logger.warning("騎手情報が取得できませんでした")

        elif args.command == 'update':
            # 一括更新
            if args.date:
                # 特定日のレースに騎乗した騎手を更新
                logger.info(f"騎手情報一括更新: {args.date}")

                # まずリーディング情報を取得
                date_parts = args.date.split('/')
                if len(date_parts) >= 2:
                    year = int(date_parts[0])
                    month = int(date_parts[1])
                    leading = scraper.scrape_leading_jockeys(year, month)

                    # 上位N名の騎手プロファイルを更新
                    updated_count = 0
                    for ranking in leading.get('rankings', [])[:args.top]:
                        jockey_id = ranking.get('jockey_id')
                        jockey_name = ranking.get('jockey_name')
                        if jockey_id:
                            logger.info(f"更新中: {jockey_name} (ID={jockey_id})")
                            scraper.scrape_jockey_profile(jockey_id, jockey_name)
                            updated_count += 1

                    logger.info(f"更新完了: {updated_count}名")
            else:
                # 現在月のリーディング上位を更新
                logger.info(f"現在月のリーディング上位{args.top}名を更新")

                leading = scraper.scrape_leading_jockeys()
                updated_count = 0
                for ranking in leading.get('rankings', [])[:args.top]:
                    jockey_id = ranking.get('jockey_id')
                    jockey_name = ranking.get('jockey_name')
                    if jockey_id:
                        logger.info(f"更新中: {jockey_name} (ID={jockey_id})")
                        scraper.scrape_jockey_profile(jockey_id, jockey_name)
                        updated_count += 1

                logger.info(f"更新完了: {updated_count}名")

        else:
            parser.print_help()

    except Exception as e:
        logger.error(f"エラーが発生しました: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()