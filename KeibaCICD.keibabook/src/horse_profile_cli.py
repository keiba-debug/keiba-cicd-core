#!/usr/bin/env python3
"""
馬プロファイル管理CLI
開催日を指定して馬プロファイルを生成・更新する
"""

import argparse
import logging
from datetime import datetime
from pathlib import Path
import sys

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scrapers.horse_profile_manager import HorseProfileManager

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(
        description='馬プロファイル管理ツール',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 特定日のWIN5対象馬プロファイルを生成
  python -m src.horse_profile_cli --date 2025/09/14 --win5

  # 特定日の全レース出走馬プロファイルを生成
  python -m src.horse_profile_cli --date 2025/09/14 --all

  # 過去成績を含む詳細プロファイルを生成
  python -m src.horse_profile_cli --date 2025/09/14 --win5 --with-history

  # 特定の馬IDのプロファイルを生成
  python -m src.horse_profile_cli --horse-id 0936453 --horse-name カムニャック
        """
    )

    # 引数定義
    parser.add_argument(
        '--date',
        help='対象日付 (YYYY/MM/DD形式)',
        default=datetime.now().strftime('%Y/%m/%d')
    )

    parser.add_argument(
        '--win5',
        action='store_true',
        help='WIN5対象レースの馬のみ処理'
    )

    parser.add_argument(
        '--all',
        action='store_true',
        help='全レースの出走馬を処理'
    )

    parser.add_argument(
        '--with-history',
        action='store_true',
        help='過去成績を含む詳細プロファイルを生成'
    )

    parser.add_argument(
        '--horse-id',
        help='特定の馬IDを指定'
    )

    parser.add_argument(
        '--horse-name',
        help='馬名を指定（--horse-id と併用）'
    )

    parser.add_argument(
        '--race-file',
        help='特定のレースファイルから馬情報を抽出'
    )

    parser.add_argument(
        '--output-dir',
        help='出力ディレクトリ（デフォルト: Z:/KEIBA-CICD/data/horses/profiles）'
    )

    args = parser.parse_args()

    # バリデーション
    if not args.win5 and not args.all and not args.horse_id and not args.race_file:
        logger.error("処理対象を指定してください: --win5, --all, --horse-id, または --race-file")
        parser.print_help()
        return 1

    # マネージャー初期化
    try:
        manager = HorseProfileManager()

        if args.output_dir:
            manager.profiles_dir = Path(args.output_dir)
            manager.profiles_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"馬プロファイル管理開始")
        logger.info(f"出力先: {manager.profiles_dir}")

        total_processed = 0

        # 個別馬の処理
        if args.horse_id:
            if not args.horse_name:
                logger.error("--horse-id を指定する場合は --horse-name も必要です")
                return 1

            logger.info(f"馬プロファイル生成: {args.horse_id} - {args.horse_name}")

            profile_path = manager.create_horse_profile(
                args.horse_id,
                args.horse_name,
                include_history=args.with_history,
                use_web_fetch=args.with_history
            )

            logger.info(f"✓ 生成完了: {profile_path.name}")
            total_processed = 1

        # レースファイルからの処理
        elif args.race_file:
            race_file = Path(args.race_file)
            if not race_file.exists():
                logger.error(f"レースファイルが見つかりません: {race_file}")
                return 1

            logger.info(f"レースファイル解析: {race_file}")
            horses = manager.extract_horses_from_race(race_file)

            for horse_id, horse_name, horse_data in horses:
                profile_path = manager.create_horse_profile(
                    horse_id,
                    horse_name,
                    horse_data,
                    include_history=args.with_history,
                    use_web_fetch=args.with_history
                )
                logger.info(f"✓ {horse_name}: {profile_path.name}")
                total_processed += 1

        # WIN5対象馬の処理
        elif args.win5:
            logger.info(f"WIN5対象馬プロファイル生成: {args.date}")

            results = manager.update_win5_horses(args.date)

            for race_key, horses in results.items():
                if horses:
                    logger.info(f"  {race_key}: {len(horses)}頭処理")
                    total_processed += len(horses)

                    # 詳細プロファイルを生成
                    if args.with_history:
                        for horse in horses:
                            profile_path = manager.create_horse_profile(
                                horse['horse_id'],
                                horse['horse_name'],
                                include_history=True,
                                use_web_fetch=True
                            )
                            logger.debug(f"    詳細プロファイル生成: {profile_path.name}")

        # 全レース処理
        elif args.all:
            logger.info(f"全レース出走馬プロファイル生成: {args.date}")

            # 日付をパス形式に変換
            date_parts = args.date.split('/')
            year = date_parts[0]
            month = date_parts[1].zfill(2)
            day = date_parts[2].zfill(2)

            organized_path = Path(f"Z:/KEIBA-CICD/data/organized/{year}/{month}/{day}")

            if not organized_path.exists():
                logger.error(f"データディレクトリが見つかりません: {organized_path}")
                return 1

            # 全競馬場のMDファイルを処理
            for track_dir in organized_path.iterdir():
                if track_dir.is_dir():
                    logger.info(f"  競馬場: {track_dir.name}")

                    for md_file in track_dir.glob("*.md"):
                        horses = manager.extract_horses_from_race(md_file)

                        for horse_id, horse_name, horse_data in horses:
                            profile_path = manager.create_horse_profile(
                                horse_id,
                                horse_name,
                                horse_data,
                                include_history=args.with_history,
                                use_web_fetch=args.with_history
                            )
                            logger.debug(f"    {horse_name}: {profile_path.name}")
                            total_processed += 1

        # 結果サマリー
        logger.info("=" * 60)
        logger.info(f"処理完了")
        logger.info(f"  処理馬数: {total_processed}頭")
        logger.info(f"  出力先: {manager.profiles_dir}")
        logger.info(f"  詳細モード: {'有効' if args.with_history else '無効'}")
        logger.info("=" * 60)

        return 0

    except Exception as e:
        logger.error(f"エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())