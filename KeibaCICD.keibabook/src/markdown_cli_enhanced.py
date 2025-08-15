"""
拡張版Markdown生成CLI
外部コメント・馬場情報対応
"""

import argparse
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.integrator.markdown_generator_enhanced import EnhancedMarkdownGenerator
from src.integrator.race_data_integrator import RaceDataIntegrator
from src.batch.core.common import setup_batch_logger


def main():
    parser = argparse.ArgumentParser(description='拡張版レースMarkdown生成')
    
    parser.add_argument('--race-id', required=True, help='レースID (例: 202501080811)')
    parser.add_argument('--organized', action='store_true', help='organizedディレクトリ以下に出力')
    parser.add_argument('--preview', action='store_true', help='プレビューのみ（保存なし）')
    
    args = parser.parse_args()
    
    # ロガー初期化
    logger = setup_batch_logger('markdown_cli_enhanced')
    logger.info("[START] 拡張版Markdown生成")
    logger.info(f"[RACE]: {args.race_id}")
    
    try:
        # ジェネレータ初期化
        generator = EnhancedMarkdownGenerator(use_organized_dir=args.organized)
        integrator = RaceDataIntegrator(use_organized_dir=args.organized)
        
        # データ取得
        race_data = integrator.create_integrated_file(args.race_id, save=False)
        if not race_data:
            logger.error(f"[ERROR] データ取得失敗: {args.race_id}")
            return
        
        # Markdown生成
        if args.preview:
            # プレビューモード
            markdown_text = generator.generate_race_markdown(race_data, save=False)
            print("\n" + "=" * 60)
            print("PREVIEW")
            print("=" * 60)
            # UTF-8エンコーディングで出力
            import sys
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
            print(markdown_text)
        else:
            # 保存モード
            markdown_text = generator.generate_race_markdown(race_data, save=True)
            output_path = generator._get_output_path(race_data)
            logger.info(f"[SUCCESS] Markdown生成完了: {output_path}")
            
            # 外部コメントの有無を確認
            date_str = args.race_id[:8]
            venue = generator._get_venue_name(args.race_id)
            external_comments = generator._load_external_comments(date_str, venue, args.race_id)
            
            if external_comments:
                logger.info("[INFO] 外部コメントを統合しました")
            
            # 馬場情報の有無を確認
            track_condition = generator._load_track_condition(date_str, venue)
            if track_condition:
                logger.info("[INFO] 馬場情報を統合しました")
                
    except Exception as e:
        logger.error(f"[ERROR] 生成エラー: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()