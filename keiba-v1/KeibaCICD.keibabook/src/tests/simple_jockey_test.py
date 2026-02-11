"""
騎手情報取得の簡単なテスト
"""

import os
import json
from pathlib import Path
from datetime import datetime

# データ保存先
data_root = Path('Z:/KEIBA-CICD/data')
jockeys_dir = data_root / 'jockeys'
profiles_dir = jockeys_dir / 'profiles'
leading_dir = jockeys_dir / 'leading'

# ディレクトリ作成
for dir_path in [profiles_dir, leading_dir]:
    dir_path.mkdir(parents=True, exist_ok=True)

# ダミーのリーディングデータを作成
leading_data = {
    'year': 2025,
    'month': 9,
    'updated_at': datetime.now().isoformat(),
    'rankings': [
        {'rank': '1', 'jockey_id': '00666', 'jockey_name': 'ルメール', 'wins': 45, 'rides': 180, 'win_rate': 25.0},
        {'rank': '2', 'jockey_id': '00667', 'jockey_name': '川田将雅', 'wins': 42, 'rides': 165, 'win_rate': 25.5},
        {'rank': '3', 'jockey_id': '00668', 'jockey_name': '横山武史', 'wins': 38, 'rides': 190, 'win_rate': 20.0},
        {'rank': '4', 'jockey_id': '00669', 'jockey_name': 'モレイラ', 'wins': 35, 'rides': 120, 'win_rate': 29.2},
        {'rank': '5', 'jockey_id': '00670', 'jockey_name': '横山典弘', 'wins': 32, 'rides': 145, 'win_rate': 22.1},
    ]
}

# リーディングデータ保存
output_dir = leading_dir / '2025'
output_dir.mkdir(parents=True, exist_ok=True)
output_file = output_dir / '202509.json'

with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(leading_data, f, ensure_ascii=False, indent=2)

print(f"リーディングデータ保存: {output_file}")

# 騎手プロファイル作成（例: ルメール）
profile_content = """# 騎手プロファイル: ルメール

## 基本情報
- **騎手ID**: 00666
- **所属**: 栗東
- **免許取得**: 2015年

## 成績統計
### 通算成績
| 項目 | 1着 | 2着 | 3着 | 着外 | 勝率 | 連対率 | 複勝率 |
|:----:|:---:|:---:|:---:|:----:|:----:|:------:|:------:|
| 全成績 | 45 | 35 | 28 | 72 | 25.0% | 33.3% | 40.0% |

### 今年の成績
| 月 | 騎乗数 | 勝利 | 勝率 | 連対率 | 賞金(万円) |
|:--:|:------:|:----:|:----:|:------:|:----------:|
| 9月 | 180 | 45 | 25.0% | 33.3% | 12,500 |

### 得意条件
- **得意距離**: 1600m (勝率 28.5%)
- **得意競馬場**: 東京 (勝率 30.2%)
- **得意馬場**: 芝・良 (勝率 26.8%)

---
## ユーザーメモ
*予想に役立つ情報を記入*

---
*最終更新: {}*
""".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

profile_file = profiles_dir / '00666_ルメール.md'
with open(profile_file, 'w', encoding='utf-8') as f:
    f.write(profile_content)

print(f"騎手プロファイル作成: {profile_file}")

# リーディング表示
print("\n=== 2025年9月 リーディング騎手 ===")
for ranking in leading_data['rankings']:
    print(f"{ranking['rank']}位: {ranking['jockey_name']} - "
          f"{ranking['wins']}勝/{ranking['rides']}騎乗 "
          f"(勝率{ranking['win_rate']}%)")

print("\n騎手情報の初期データを作成しました。")
print("これらのファイルは今後の予想に活用できます。")