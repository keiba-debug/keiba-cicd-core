"""
馬名インデックス作成スクリプト
過去レースデータから馬名のインデックスを作成し、高速検索を可能にする
"""

import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def create_horse_index():
    """馬名インデックスを作成"""

    # データディレクトリ
    temp_dir = Path("Z:/KEIBA-CICD/data/temp")
    index_file = Path("Z:/KEIBA-CICD/data/horses/horse_race_index.json")
    index_file.parent.mkdir(parents=True, exist_ok=True)

    # インデックス構造: {馬名: [レースファイル情報]}
    horse_index = defaultdict(list)

    # seisekiファイルを検索
    seiseki_files = list(temp_dir.glob("seiseki_*.json"))
    logger.info(f"インデックス作成開始: {len(seiseki_files)}ファイル")

    processed = 0
    for json_file in seiseki_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            race_info = data.get('race_info', {})
            race_name = race_info.get('race_name', '')

            # race_nameから日付を抽出
            import re
            date_match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', race_name)
            race_date = ''
            if date_match:
                race_date = f"{date_match.group(1)}/{date_match.group(2).zfill(2)}/{date_match.group(3).zfill(2)}"

            # 各馬の情報を記録
            if 'results' in data:
                for result in data['results']:
                    horse_name = result.get('馬名')
                    if horse_name:
                        race_entry = {
                            'file': str(json_file.name),
                            'date': race_date,
                            'race_name': race_name,
                            '着順': result.get('着順', ''),
                            '騎手': result.get('騎手_2', '') or result.get('騎手', ''),
                            'タイム': result.get('タイム', ''),
                            '上がり': result.get('上り3F', '') or result.get('上がり', ''),
                            '寸評': result.get('寸評', ''),
                            'memo': result.get('memo', ''),
                            'interview': result.get('interview', '')
                        }
                        horse_index[horse_name].append(race_entry)

            processed += 1
            if processed % 100 == 0:
                logger.info(f"  処理済み: {processed}/{len(seiseki_files)}")

        except Exception as e:
            logger.debug(f"スキップ: {json_file.name} - {e}")

    # インデックスを保存
    logger.info(f"インデックス保存中: {len(horse_index)}頭")

    # 各馬のレースを日付でソート
    for horse_name in horse_index:
        horse_index[horse_name] = sorted(
            horse_index[horse_name],
            key=lambda x: x.get('date', ''),
            reverse=True
        )

    with open(index_file, 'w', encoding='utf-8') as f:
        json.dump(dict(horse_index), f, ensure_ascii=False, indent=2)

    logger.info(f"インデックス作成完了: {index_file}")
    logger.info(f"登録馬数: {len(horse_index)}")

    # サンプル表示
    sample_horses = list(horse_index.keys())[:5]
    for horse in sample_horses:
        races = horse_index[horse]
        logger.info(f"  {horse}: {len(races)}レース")

    return index_file

if __name__ == "__main__":
    create_horse_index()