"""
馬場データ（クッション値・含水率）の予測力分析 v2
- データカバレッジ
- 馬場「性格」分類（硬い/柔らかい、乾燥/湿潤）
- 分類別の好走パターン
- track_conditionとの追加情報量
"""
import csv
import json
import glob
import os
from collections import defaultdict
from pathlib import Path

DATA_ROOT = Path("C:/KEIBA-CICD/data3")
BABA_DIR = DATA_ROOT / "analysis" / "baba"

# track prefix → description
TRACK_PREFIX = {
    '00': 'turf',
    '04': 'turf',  # 京都等の別芝
    '0B': 'turf_inner',
    '0D': 'dirt',
    '03': 'turf_outer',
}


def read_baba_csv(path, target_enc=None):
    """エンコーディング自動判定でCSV読み込み"""
    for enc in (target_enc, 'cp932', 'utf-8-sig', 'utf-8'):
        if enc is None:
            continue
        try:
            with open(path, encoding=enc) as f:
                return list(csv.reader(f))
        except:
            continue
    return []


def parse_csv_id(csv_id):
    """RX{JJ}{YY}{K}{N}{RR} → dict"""
    if len(csv_id) < 10:
        return None
    return {
        'place': csv_id[2:4],
        'year': f"20{csv_id[4:6]}",
        'kai': csv_id[6],
        'nichi': csv_id[7],
        'race_num': csv_id[8:10],
    }


def load_baba_data(years=range(2021, 2027)):
    """全馬場データ読み込み → {key: {cushion, moisture_turf, moisture_dirt, ...}}"""
    data = {}

    for year in years:
        # Cushion
        path = BABA_DIR / f"cushion{year}.csv"
        if path.exists():
            rows = read_baba_csv(path)
            for row in rows:
                if len(row) < 3:
                    continue
                parsed = parse_csv_id(row[1])
                if not parsed:
                    continue
                prefix = row[2][:2]
                val_str = row[2][2:].strip()
                try:
                    val = float(val_str)
                except:
                    continue
                key = f"{parsed['year']}_{parsed['place']}_{parsed['kai']}_{parsed['nichi']}_{parsed['race_num']}"
                if key not in data:
                    data[key] = {}
                data[key]['cushion'] = val
                data[key]['cushion_track'] = TRACK_PREFIX.get(prefix, prefix)

        # Moisture (4corner + goal)
        for ftype in ['moisture4', 'moistureG']:
            path = BABA_DIR / f"{ftype}{year}.csv"
            if not path.exists():
                continue
            rows = read_baba_csv(path)
            for row in rows:
                if len(row) < 3:
                    continue
                parsed = parse_csv_id(row[1])
                if not parsed:
                    continue
                prefix = row[2][:2]
                val_str = row[2][2:].strip()
                try:
                    val = float(val_str)
                except:
                    continue
                key = f"{parsed['year']}_{parsed['place']}_{parsed['kai']}_{parsed['nichi']}_{parsed['race_num']}"
                if key not in data:
                    data[key] = {}

                track = TRACK_PREFIX.get(prefix, prefix)
                label = f"{ftype}_{track}"
                data[key][label] = val

    return data


def load_race_results(years=range(2021, 2027)):
    """race JSONから結果情報を収集"""
    races = []
    for year in years:
        pattern = str(DATA_ROOT / "races" / str(year) / "**" / "race_[0-9]*.json")
        for race_path in glob.glob(pattern, recursive=True):
            try:
                with open(race_path, encoding='utf-8') as f:
                    race = json.load(f)
            except:
                continue

            race_id = race.get('race_id', '')
            if len(race_id) < 16:
                continue

            place = race_id[8:10]
            kai = str(int(race_id[10:12]))
            nichi = str(int(race_id[12:14]))
            race_num = race_id[14:16]
            year_str = race_id[:4]
            key = f"{year_str}_{place}_{kai}_{nichi}_{race_num}"

            track_type = race.get('track_type', '')
            track_cond = race.get('track_condition', '')

            for e in race.get('entries', []):
                fp = e.get('finish_position', 0)
                if fp == 0:
                    continue
                # horse_idはNoneの場合がある。ketto_numを使う
                horse_id = e.get('horse_id') or e.get('ketto_num', '')
                races.append({
                    'key': key,
                    'race_id': race_id,
                    'track_type': track_type,
                    'track_condition': track_cond,
                    'horse_id': str(horse_id),
                    'horse_name': e.get('horse_name', ''),
                    'finish_position': fp,
                    'odds': e.get('odds', 0) or 0,
                    'popularity': e.get('popularity', 0) or 0,
                    'num_runners': race.get('num_runners', 0),
                    'horse_weight': e.get('horse_weight', 0) or 0,
                    'is_win': 1 if fp == 1 else 0,
                    'is_top3': 1 if fp <= 3 else 0,
                })
    return races


def classify_turf_baba(cushion, moisture_turf=None):
    """芝馬場の性格分類"""
    if cushion is None:
        return 'unknown'
    if cushion >= 9.5:
        return 'hard'       # 硬い（高速馬場）
    elif cushion >= 8.5:
        return 'standard'   # 標準
    elif cushion >= 7.5:
        return 'yielding'   # やや軟（パワー要求）
    else:
        return 'soft'       # 軟（重馬場級）


def classify_dirt_baba(moisture_dirt=None, track_condition=None):
    """ダート馬場の性格分類"""
    if moisture_dirt is not None:
        if moisture_dirt >= 12:
            return 'wet'        # 湿潤（時計速い）
        elif moisture_dirt >= 8:
            return 'standard'   # 標準
        else:
            return 'dry'        # 乾燥（重い）
    # 含水率がない場合はtrack_conditionから推定
    if track_condition:
        cond_map = {'良': 'dry', '稍重': 'standard', '重': 'wet', '不良': 'wet'}
        return cond_map.get(track_condition, 'unknown')
    return 'unknown'


def analyze():
    print("=" * 70)
    print("  馬場データ予測力分析 v2")
    print("=" * 70)

    print("\n[1] データ読み込み...")
    baba = load_baba_data()
    print(f"  馬場データ: {len(baba)} レース")

    # サンプル確認
    for key in list(baba.keys())[:3]:
        print(f"  sample {key}: {baba[key]}")

    print("\n  レースJSON読み込み中...")
    entries = load_race_results()
    print(f"  エントリ: {len(entries)}")

    # マッチング
    race_keys = set(e['key'] for e in entries)
    matched = race_keys & set(baba.keys())
    print(f"\n  マッチ率: {len(matched)}/{len(race_keys)} ({len(matched)/len(race_keys)*100:.1f}%)")

    # 年別
    year_stats = defaultdict(lambda: {'total': 0, 'matched': 0})
    for key in race_keys:
        year = key[:4]
        year_stats[year]['total'] += 1
        if key in baba:
            year_stats[year]['matched'] += 1
    for year in sorted(year_stats.keys()):
        s = year_stats[year]
        print(f"  {year}: {s['matched']}/{s['total']} ({s['matched']/s['total']*100:.0f}%)")

    # Enrich
    enriched = []
    for e in entries:
        b = baba.get(e['key'])
        if not b:
            continue
        ec = dict(e)
        ec['cushion'] = b.get('cushion')
        ec['moisture_dirt'] = b.get('moistureG_dirt') or b.get('moisture4_dirt')
        ec['moisture_turf'] = b.get('moistureG_turf') or b.get('moisture4_turf') or b.get('moistureG_turf_inner') or b.get('moisture4_turf_inner')

        if ec['track_type'] == 'turf':
            ec['baba_class'] = classify_turf_baba(ec['cushion'], ec['moisture_turf'])
        elif ec['track_type'] == 'dirt':
            ec['baba_class'] = classify_dirt_baba(ec['moisture_dirt'], ec['track_condition'])
        else:
            ec['baba_class'] = 'unknown'
        enriched.append(ec)

    print(f"\n  enrichedエントリ: {len(enriched)}")

    # ============================================================
    # [2] 芝の馬場性格別分析
    # ============================================================
    print(f"\n{'='*70}")
    print("  [2] 芝の馬場性格別分析")
    print(f"{'='*70}")

    turf = [e for e in enriched if e['track_type'] == 'turf']
    print(f"\n  芝エントリ: {len(turf)}")

    baba_classes = ['hard', 'standard', 'yielding', 'soft']
    print(f"\n  {'馬場性格':<12} {'n':>6} {'top3%':>7} {'1人気勝率':>10} {'1人気ROI':>10} {'穴馬top3%':>10} {'穴馬ROI':>9}")
    for bc in baba_classes:
        grp = [e for e in turf if e['baba_class'] == bc]
        if not grp:
            continue
        n = len(grp)
        top3 = sum(e['is_top3'] for e in grp) / n * 100

        favs = [e for e in grp if e['popularity'] == 1]
        fav_wr = sum(e['is_win'] for e in favs) / len(favs) * 100 if favs else 0
        fav_roi = sum(e['odds'] for e in favs if e['is_win']) / len(favs) * 100 if favs else 0

        long = [e for e in grp if e['popularity'] >= 6]
        long_top3 = sum(e['is_top3'] for e in long) / len(long) * 100 if long else 0
        long_roi = sum(e['odds'] for e in long if e['is_win']) / len(long) * 100 if long else 0

        print(f"  {bc:<12} {n:>6} {top3:>6.1f}% {fav_wr:>9.1f}% {fav_roi:>9.1f}% {long_top3:>9.1f}% {long_roi:>8.1f}%")

    # track_condition × 馬場性格のクロス集計
    print(f"\n  track_condition × 馬場性格 (芝):")
    print(f"  {'':8} {'hard':>8} {'standard':>10} {'yielding':>10} {'soft':>8}")
    for cond in ['良', '稍重', '重', '不良']:
        counts = {}
        for bc in baba_classes:
            counts[bc] = len([e for e in turf if e['track_condition'] == cond and e['baba_class'] == bc])
        total = sum(counts.values())
        if total == 0:
            continue
        parts = [f"{counts[bc]:>6}({counts[bc]/total*100:3.0f}%)" for bc in baba_classes]
        print(f"  {cond:<8} {'  '.join(parts)}")

    # ============================================================
    # [3] ダートの馬場性格別分析
    # ============================================================
    print(f"\n{'='*70}")
    print("  [3] ダートの馬場性格別分析")
    print(f"{'='*70}")

    dirt = [e for e in enriched if e['track_type'] == 'dirt']
    print(f"\n  ダートエントリ: {len(dirt)}")
    print(f"  含水率あり: {len([e for e in dirt if e['moisture_dirt'] is not None])}")

    dirt_classes = ['dry', 'standard', 'wet']
    print(f"\n  {'馬場性格':<12} {'n':>6} {'top3%':>7} {'1人気勝率':>10} {'1人気ROI':>10} {'穴馬top3%':>10} {'穴馬ROI':>9}")
    for bc in dirt_classes:
        grp = [e for e in dirt if e['baba_class'] == bc]
        if not grp:
            continue
        n = len(grp)
        top3 = sum(e['is_top3'] for e in grp) / n * 100

        favs = [e for e in grp if e['popularity'] == 1]
        fav_wr = sum(e['is_win'] for e in favs) / len(favs) * 100 if favs else 0
        fav_roi = sum(e['odds'] for e in favs if e['is_win']) / len(favs) * 100 if favs else 0

        long = [e for e in grp if e['popularity'] >= 6]
        long_top3 = sum(e['is_top3'] for e in long) / len(long) * 100 if long else 0
        long_roi = sum(e['odds'] for e in long if e['is_win']) / len(long) * 100 if long else 0

        print(f"  {bc:<12} {n:>6} {top3:>6.1f}% {fav_wr:>9.1f}% {fav_roi:>9.1f}% {long_top3:>9.1f}% {long_roi:>8.1f}%")

    # track_condition × ダート馬場性格
    print(f"\n  track_condition × ダート馬場性格:")
    print(f"  {'':8} {'dry':>8} {'standard':>10} {'wet':>8}")
    for cond in ['良', '稍重', '重', '不良']:
        counts = {bc: len([e for e in dirt if e['track_condition'] == cond and e['baba_class'] == bc]) for bc in dirt_classes}
        total = sum(counts.values())
        if total == 0:
            continue
        parts = [f"{counts[bc]:>6}({counts[bc]/total*100:3.0f}%)" for bc in dirt_classes]
        print(f"  {cond:<8} {'  '.join(parts)}")

    # ============================================================
    # [4] 馬別「馬場適性」分析（芝）
    # ============================================================
    print(f"\n{'='*70}")
    print("  [4] 馬別「馬場適性」分析")
    print(f"{'='*70}")

    horse_turf = defaultdict(list)
    for e in turf:
        if e['horse_id'] and e['baba_class'] != 'unknown':
            horse_turf[e['horse_id']].append(e)

    multi = {hid: runs for hid, runs in horse_turf.items() if len(runs) >= 5}
    print(f"  芝5走以上の馬: {len(multi)}")

    # 各馬の hard vs soft 成績比較
    type_diff_horses = []
    for hid, runs in multi.items():
        hard_runs = [r for r in runs if r['baba_class'] == 'hard']
        soft_runs = [r for r in runs if r['baba_class'] in ('yielding', 'soft')]

        if len(hard_runs) >= 2 and len(soft_runs) >= 1:
            hard_top3 = sum(r['is_top3'] for r in hard_runs) / len(hard_runs)
            soft_top3 = sum(r['is_top3'] for r in soft_runs) / len(soft_runs)
            diff = hard_top3 - soft_top3
            type_diff_horses.append({
                'horse_id': hid,
                'name': runs[0]['horse_name'],
                'hard_top3': hard_top3,
                'soft_top3': soft_top3,
                'hard_n': len(hard_runs),
                'soft_n': len(soft_runs),
                'diff': diff,
            })

    if type_diff_horses:
        diffs = [h['diff'] for h in type_diff_horses]
        avg_diff = sum(diffs) / len(diffs)
        abs_diffs = [abs(d) for d in diffs]
        avg_abs_diff = sum(abs_diffs) / len(abs_diffs)

        print(f"  hard vs soft/yielding 比較可能馬: {len(type_diff_horses)}")
        print(f"  平均差分 (hard-soft): {avg_diff*100:+.1f}pt")
        print(f"  平均絶対差分: {avg_abs_diff*100:.1f}pt")
        print(f"  → {'硬い馬場の方が好走しやすい' if avg_diff > 0 else '柔らかい馬場の方が好走しやすい'}")

        # 馬場適性の分散が大きい = 馬場で成績が変わる馬が多い
        big_diff = [h for h in type_diff_horses if abs(h['diff']) >= 0.3]
        print(f"  馬場適性差30pt以上の馬: {len(big_diff)}/{len(type_diff_horses)} ({len(big_diff)/len(type_diff_horses)*100:.1f}%)")

        # 硬い馬場巧者 TOP5
        type_diff_horses.sort(key=lambda x: -x['diff'])
        print(f"\n  硬い馬場巧者 TOP5:")
        for h in type_diff_horses[:5]:
            print(f"    {h['name']}: hard={h['hard_top3']*100:.0f}%(n={h['hard_n']}) vs soft={h['soft_top3']*100:.0f}%(n={h['soft_n']})")

        # 柔らかい馬場巧者 TOP5
        type_diff_horses.sort(key=lambda x: x['diff'])
        print(f"\n  柔らかい馬場巧者 TOP5:")
        for h in type_diff_horses[:5]:
            print(f"    {h['name']}: hard={h['hard_top3']*100:.0f}%(n={h['hard_n']}) vs soft={h['soft_top3']*100:.0f}%(n={h['soft_n']})")

    # ============================================================
    # [5] 馬別「馬場適性」分析（ダート）
    # ============================================================
    print(f"\n{'='*70}")
    print("  [5] ダート 馬別「馬場適性」分析")
    print(f"{'='*70}")

    horse_dirt = defaultdict(list)
    for e in dirt:
        if e['horse_id'] and e['baba_class'] != 'unknown':
            horse_dirt[e['horse_id']].append(e)

    multi_d = {hid: runs for hid, runs in horse_dirt.items() if len(runs) >= 5}
    print(f"  ダート5走以上の馬: {len(multi_d)}")

    type_diff_dirt = []
    for hid, runs in multi_d.items():
        dry_runs = [r for r in runs if r['baba_class'] == 'dry']
        wet_runs = [r for r in runs if r['baba_class'] == 'wet']

        if len(dry_runs) >= 2 and len(wet_runs) >= 1:
            dry_top3 = sum(r['is_top3'] for r in dry_runs) / len(dry_runs)
            wet_top3 = sum(r['is_top3'] for r in wet_runs) / len(wet_runs)
            type_diff_dirt.append({
                'horse_id': hid,
                'name': runs[0]['horse_name'],
                'dry_top3': dry_top3,
                'wet_top3': wet_top3,
                'dry_n': len(dry_runs),
                'wet_n': len(wet_runs),
                'diff': dry_top3 - wet_top3,
            })

    if type_diff_dirt:
        diffs = [h['diff'] for h in type_diff_dirt]
        avg_diff = sum(diffs) / len(diffs)
        abs_diffs = [abs(d) for d in diffs]
        avg_abs_diff = sum(abs_diffs) / len(abs_diffs)

        print(f"  dry vs wet 比較可能馬: {len(type_diff_dirt)}")
        print(f"  平均差分 (dry-wet): {avg_diff*100:+.1f}pt")
        print(f"  平均絶対差分: {avg_abs_diff*100:.1f}pt")

        big_diff = [h for h in type_diff_dirt if abs(h['diff']) >= 0.3]
        print(f"  馬場適性差30pt以上の馬: {len(big_diff)}/{len(type_diff_dirt)} ({len(big_diff)/len(type_diff_dirt)*100:.1f}%)")

    # ============================================================
    # [6] 結論
    # ============================================================
    print(f"\n{'='*70}")
    print("  [6] 結論: モデルへの組み込み価値")
    print(f"{'='*70}")

    # track_condition「良」の中でクッション値で分割して差があるか
    good_turf = [e for e in turf if e['track_condition'] == '良']
    if good_turf:
        hard_good = [e for e in good_turf if e['baba_class'] == 'hard']
        std_good = [e for e in good_turf if e['baba_class'] == 'standard']

        if hard_good and std_good:
            h_top3 = sum(e['is_top3'] for e in hard_good) / len(hard_good) * 100
            s_top3 = sum(e['is_top3'] for e in std_good) / len(std_good) * 100

            h_fav = [e for e in hard_good if e['popularity'] == 1]
            s_fav = [e for e in std_good if e['popularity'] == 1]
            h_fav_wr = sum(e['is_win'] for e in h_fav) / len(h_fav) * 100 if h_fav else 0
            s_fav_wr = sum(e['is_win'] for e in s_fav) / len(s_fav) * 100 if s_fav else 0

            print(f"\n  良馬場内の分類差:")
            print(f"    hard(cushion>=9.5): top3={h_top3:.1f}%, 1人気勝率={h_fav_wr:.1f}% (n={len(hard_good)})")
            print(f"    standard(8.5-9.5): top3={s_top3:.1f}%, 1人気勝率={s_fav_wr:.1f}% (n={len(std_good)})")
            print(f"    差分: top3={h_top3-s_top3:+.1f}pt, 1人気勝率={h_fav_wr-s_fav_wr:+.1f}pt")

    print(f"\n  判断基準:")
    print(f"  1. 馬場性格別で好走率に有意差があるか → 上記結果参照")
    print(f"  2. 馬別適性差の大きさ → 絶対差分の大きさで判断")
    print(f"  3. track_condition以上の追加情報があるか → 良馬場内の分類差で判断")


if __name__ == '__main__':
    analyze()
