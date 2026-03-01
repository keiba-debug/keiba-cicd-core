"""
馬場分析レポート: 会場×含水率/クッション値×脚質の相関分析
- 東京ダート: 含水率高→差し有利?
- 小倉ダート: 不良→前・内有利?
- 会場別の馬場傾向マップ
"""
import csv
import json
import glob
import os
from collections import defaultdict
from pathlib import Path

DATA_ROOT = Path("C:/KEIBA-CICD/data3")
BABA_DIR = DATA_ROOT / "analysis" / "baba"

PLACE_CODES = {
    '01': '札幌', '02': '函館', '03': '福島', '04': '新潟',
    '05': '東京', '06': '中山', '07': '中京', '08': '京都',
    '09': '阪神', '10': '小倉',
}

# prefix → surface type
TURF_PREFIXES = {'00', '03', '04', '0B'}
DIRT_PREFIXES = {'0D'}


def read_csv(path):
    for enc in ('cp932', 'utf-8-sig', 'utf-8'):
        try:
            with open(path, encoding=enc) as f:
                return list(csv.reader(f))
        except:
            continue
    return []


def parse_csv_id(csv_id):
    if len(csv_id) < 10:
        return None
    return {
        'place': csv_id[2:4],
        'year': f"20{csv_id[4:6]}",
        'kai': csv_id[6],
        'nichi': csv_id[7],
        'race_num': csv_id[8:10],
    }


def load_all_baba(years=range(2021, 2027)):
    """全馬場データ → {key: {cushion, turf_moisture, dirt_moisture}}"""
    data = {}

    for year in years:
        # Cushion
        path = BABA_DIR / f"cushion{year}.csv"
        if path.exists():
            for row in read_csv(path):
                if len(row) < 3:
                    continue
                p = parse_csv_id(row[1])
                if not p:
                    continue
                prefix = row[2][:2]
                try:
                    val = float(row[2][2:].strip())
                except:
                    continue
                key = f"{p['year']}_{p['place']}_{p['kai']}_{p['nichi']}_{p['race_num']}"
                data.setdefault(key, {})
                data[key]['cushion'] = val

        # Moisture (goal前 = moistureG が最重要)
        for ftype in ['moistureG']:
            path = BABA_DIR / f"{ftype}_{year}.csv"
            if not path.exists():
                continue
            for row in read_csv(path):
                if len(row) < 3:
                    continue
                p = parse_csv_id(row[1])
                if not p:
                    continue
                prefix = row[2][:2]
                try:
                    val = float(row[2][2:].strip())
                except:
                    continue
                key = f"{p['year']}_{p['place']}_{p['kai']}_{p['nichi']}_{p['race_num']}"
                data.setdefault(key, {})
                if prefix in TURF_PREFIXES:
                    # 複数芝prefixがある場合は最初の値を採用
                    if 'turf_moisture' not in data[key]:
                        data[key]['turf_moisture'] = val
                elif prefix in DIRT_PREFIXES:
                    data[key]['dirt_moisture'] = val

    return data


def load_race_entries(years=range(2021, 2027)):
    """レースJSON → エントリリスト（脚質情報付き）"""
    entries = []
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
            distance = race.get('distance', 0)
            venue = PLACE_CODES.get(place, place)
            num_runners = race.get('num_runners', 0)

            for e in race.get('entries', []):
                fp = e.get('finish_position', 0)
                if fp == 0:
                    continue

                # 脚質推定: コーナー通過順位から
                corners = e.get('corners', [])
                if corners and len(corners) >= 2:
                    first_corner = corners[0] if corners[0] else 0
                    last_corner = corners[-1] if corners[-1] else 0
                else:
                    first_corner = 0
                    last_corner = 0

                # 脚質分類（簡易版）
                if first_corner > 0 and num_runners > 0:
                    ratio = first_corner / num_runners
                    if ratio <= 0.25:
                        style = '逃げ先行'
                    elif ratio <= 0.5:
                        style = '好位'
                    elif ratio <= 0.75:
                        style = '差し'
                    else:
                        style = '追込'
                else:
                    style = '不明'

                # 位置取り変化
                if first_corner > 0 and last_corner > 0:
                    position_gain = first_corner - fp  # 正=追い込んだ
                else:
                    position_gain = 0

                wakuban = e.get('wakuban', 0) or 0
                umaban = e.get('umaban', 0) or 0
                # 枠分類
                if wakuban >= 1 and wakuban <= 3:
                    waku_class = '内枠(1-3)'
                elif wakuban >= 4 and wakuban <= 5:
                    waku_class = '中枠(4-5)'
                elif wakuban >= 6:
                    waku_class = '外枠(6-8)'
                else:
                    waku_class = '不明'

                nichi_int = int(nichi)
                # 開催日分類
                if nichi_int <= 2:
                    nichi_phase = '序盤(1-2日)'
                elif nichi_int <= 4:
                    nichi_phase = '前半(3-4日)'
                elif nichi_int <= 6:
                    nichi_phase = '中盤(5-6日)'
                else:
                    nichi_phase = '後半(7日~)'

                entries.append({
                    'key': key,
                    'race_id': race_id,
                    'venue': venue,
                    'place_code': place,
                    'track_type': track_type,
                    'track_condition': track_cond,
                    'distance': distance,
                    'horse_id': str(e.get('horse_id') or e.get('ketto_num', '')),
                    'horse_name': e.get('horse_name', ''),
                    'finish_position': fp,
                    'odds': e.get('odds', 0) or 0,
                    'popularity': e.get('popularity', 0) or 0,
                    'num_runners': num_runners,
                    'kai': int(kai),
                    'nichi': nichi_int,
                    'nichi_phase': nichi_phase,
                    'wakuban': wakuban,
                    'umaban': umaban,
                    'waku_class': waku_class,
                    'first_corner': first_corner,
                    'last_corner': last_corner,
                    'style': style,
                    'position_gain': position_gain,
                    'is_win': 1 if fp == 1 else 0,
                    'is_top3': 1 if fp <= 3 else 0,
                })
    return entries


def classify_moisture(moisture, track_type):
    """含水率を分類"""
    if moisture is None:
        return 'unknown'
    if track_type == 'dirt':
        if moisture >= 12:
            return '湿潤(>=12%)'
        elif moisture >= 8:
            return '標準(8-12%)'
        else:
            return '乾燥(<8%)'
    else:  # turf
        if moisture >= 10:
            return '湿潤(>=10%)'
        elif moisture >= 5:
            return '標準(5-10%)'
        else:
            return '乾燥(<5%)'


def analyze():
    print("=" * 70)
    print("  馬場分析レポート: 会場×含水率×脚質")
    print("=" * 70)

    print("\n[1] データ読み込み...")
    baba = load_all_baba()
    print(f"  馬場データ: {len(baba)} レース")

    # 含水率カバレッジ確認
    has_dirt_m = sum(1 for v in baba.values() if 'dirt_moisture' in v)
    has_turf_m = sum(1 for v in baba.values() if 'turf_moisture' in v)
    has_cushion = sum(1 for v in baba.values() if 'cushion' in v)
    print(f"  cushion: {has_cushion}, turf_moisture: {has_turf_m}, dirt_moisture: {has_dirt_m}")

    print("\n  レースJSON読み込み中...")
    entries = load_race_entries()
    print(f"  エントリ: {len(entries)}")

    # Enrich
    enriched = []
    for e in entries:
        b = baba.get(e['key'])
        if not b:
            continue
        ec = dict(e)
        ec['cushion'] = b.get('cushion')
        if ec['track_type'] == 'turf':
            ec['moisture'] = b.get('turf_moisture')
        else:
            ec['moisture'] = b.get('dirt_moisture')
        ec['moisture_class'] = classify_moisture(ec['moisture'], ec['track_type'])
        enriched.append(ec)

    print(f"  enrichedエントリ: {len(enriched)}")

    # ========================================================
    # [2] ダート: 会場別 × 含水率 × 脚質
    # ========================================================
    print(f"\n{'='*70}")
    print("  [2] ダート: 会場別 × 含水率 × 脚質分析")
    print(f"{'='*70}")

    dirt = [e for e in enriched if e['track_type'] == 'dirt' and e['style'] != '不明']
    print(f"\n  ダート（脚質判明）: {len(dirt)}")
    print(f"  含水率あり: {len([e for e in dirt if e['moisture'] is not None])}")

    # 全会場サマリー
    venues_order = ['東京', '中山', '阪神', '京都', '中京', '新潟', '福島', '小倉', '札幌', '函館']
    moisture_classes = ['乾燥(<8%)', '標準(8-12%)', '湿潤(>=12%)']
    styles = ['逃げ先行', '好位', '差し', '追込']

    for venue in venues_order:
        venue_dirt = [e for e in dirt if e['venue'] == venue and e['moisture'] is not None]
        if len(venue_dirt) < 100:
            continue

        print(f"\n  ■ {venue}ダート (n={len(venue_dirt)})")
        print(f"    {'含水率':<14} {'n':>5} {'逃先top3%':>10} {'好位top3%':>10} {'差しtop3%':>10} {'追込top3%':>10} {'差し有利度':>10}")

        for mc in moisture_classes:
            grp = [e for e in venue_dirt if e['moisture_class'] == mc]
            if len(grp) < 30:
                continue

            style_stats = {}
            for s in styles:
                sg = [e for e in grp if e['style'] == s]
                if sg:
                    style_stats[s] = sum(e['is_top3'] for e in sg) / len(sg) * 100
                else:
                    style_stats[s] = 0

            # 差し有利度 = (差し+追込のtop3率) - (逃先+好位のtop3率)
            front = (style_stats.get('逃げ先行', 0) + style_stats.get('好位', 0)) / 2
            back = (style_stats.get('差し', 0) + style_stats.get('追込', 0)) / 2
            advantage = back - front

            print(f"    {mc:<14} {len(grp):>5} {style_stats.get('逃げ先行',0):>9.1f}% {style_stats.get('好位',0):>9.1f}% {style_stats.get('差し',0):>9.1f}% {style_stats.get('追込',0):>9.1f}% {advantage:>+9.1f}pt")

    # ========================================================
    # [3] 芝: 会場別 × クッション値 × 脚質
    # ========================================================
    print(f"\n{'='*70}")
    print("  [3] 芝: 会場別 × クッション値 × 脚質分析")
    print(f"{'='*70}")

    turf = [e for e in enriched if e['track_type'] == 'turf' and e['style'] != '不明']

    cushion_classes_labels = [('硬(>=9.5)', 9.5, 99), ('標準(8.5-9.5)', 8.5, 9.5), ('柔(<8.5)', 0, 8.5)]

    for venue in venues_order:
        venue_turf = [e for e in turf if e['venue'] == venue and e['cushion'] is not None]
        if len(venue_turf) < 100:
            continue

        print(f"\n  ■ {venue}芝 (n={len(venue_turf)})")
        print(f"    {'クッション':<16} {'n':>5} {'逃先top3%':>10} {'好位top3%':>10} {'差しtop3%':>10} {'追込top3%':>10} {'差し有利度':>10}")

        for label, lo, hi in cushion_classes_labels:
            grp = [e for e in venue_turf if lo <= (e['cushion'] or 0) < hi]
            if len(grp) < 30:
                continue

            style_stats = {}
            for s in styles:
                sg = [e for e in grp if e['style'] == s]
                if sg:
                    style_stats[s] = sum(e['is_top3'] for e in sg) / len(sg) * 100
                else:
                    style_stats[s] = 0

            front = (style_stats.get('逃げ先行', 0) + style_stats.get('好位', 0)) / 2
            back = (style_stats.get('差し', 0) + style_stats.get('追込', 0)) / 2
            advantage = back - front

            print(f"    {label:<16} {len(grp):>5} {style_stats.get('逃げ先行',0):>9.1f}% {style_stats.get('好位',0):>9.1f}% {style_stats.get('差し',0):>9.1f}% {style_stats.get('追込',0):>9.1f}% {advantage:>+9.1f}pt")

    # ========================================================
    # [4] 距離別分析（短距離/中距離/長距離での違い）
    # ========================================================
    print(f"\n{'='*70}")
    print("  [4] ダート含水率 × 距離帯 × 脚質")
    print(f"{'='*70}")

    dist_bands = [(1000, 1400, '短距離(~1400)'), (1400, 1800, 'マイル(1400-1800)'), (1800, 2500, '中長距離(1800~)')]

    for d_label_tuple in dist_bands:
        d_lo, d_hi, d_label = d_label_tuple
        band = [e for e in dirt if d_lo <= e['distance'] < d_hi and e['moisture'] is not None]
        if len(band) < 200:
            continue

        print(f"\n  ■ {d_label} (n={len(band)})")
        print(f"    {'含水率':<14} {'n':>5} {'逃先top3%':>10} {'好位top3%':>10} {'差しtop3%':>10} {'追込top3%':>10} {'差し有利度':>10}")

        for mc in moisture_classes:
            grp = [e for e in band if e['moisture_class'] == mc]
            if len(grp) < 50:
                continue

            style_stats = {}
            for s in styles:
                sg = [e for e in grp if e['style'] == s]
                if sg:
                    style_stats[s] = sum(e['is_top3'] for e in sg) / len(sg) * 100
                else:
                    style_stats[s] = 0

            front = (style_stats.get('逃げ先行', 0) + style_stats.get('好位', 0)) / 2
            back = (style_stats.get('差し', 0) + style_stats.get('追込', 0)) / 2
            advantage = back - front

            print(f"    {mc:<14} {len(grp):>5} {style_stats.get('逃げ先行',0):>9.1f}% {style_stats.get('好位',0):>9.1f}% {style_stats.get('差し',0):>9.1f}% {style_stats.get('追込',0):>9.1f}% {advantage:>+9.1f}pt")

    # ========================================================
    # [5] 穴馬ROI分析: 馬場状態別
    # ========================================================
    print(f"\n{'='*70}")
    print("  [5] 穴馬(6番人気↓)の馬場状態別成績")
    print(f"{'='*70}")

    for track_label, track_entries, class_key in [
        ('芝', turf, 'cushion'),
        ('ダート', dirt, 'moisture'),
    ]:
        longshots = [e for e in track_entries if e['popularity'] >= 6]
        if not longshots:
            continue

        print(f"\n  ■ {track_label} 穴馬")

        if track_label == '芝':
            classes = cushion_classes_labels
            for label, lo, hi in classes:
                grp = [e for e in longshots if (e.get('cushion') or 0) >= lo and (e.get('cushion') or 0) < hi]
                if len(grp) < 100:
                    continue
                top3 = sum(e['is_top3'] for e in grp) / len(grp) * 100
                roi_win = sum(e['odds'] for e in grp if e['is_win']) / len(grp) * 100
                # 脚質別
                for s in styles:
                    sg = [e for e in grp if e['style'] == s]
                    if len(sg) >= 30:
                        s_top3 = sum(e['is_top3'] for e in sg) / len(sg) * 100
                        s_roi = sum(e['odds'] for e in sg if e['is_win']) / len(sg) * 100
                        print(f"    {label:<16} {s:<8} n={len(sg):>4} top3={s_top3:5.1f}% ROI={s_roi:5.0f}%")
        else:
            for mc in moisture_classes:
                grp = [e for e in longshots if e.get('moisture_class') == mc]
                if len(grp) < 100:
                    continue
                for s in styles:
                    sg = [e for e in grp if e['style'] == s]
                    if len(sg) >= 30:
                        s_top3 = sum(e['is_top3'] for e in sg) / len(sg) * 100
                        s_roi = sum(e['odds'] for e in sg if e['is_win']) / len(sg) * 100
                        print(f"    {mc:<14} {s:<8} n={len(sg):>4} top3={s_top3:5.1f}% ROI={s_roi:5.0f}%")

    # 追加分析
    analyze_waku(enriched, dirt, turf, venues_order, moisture_classes,
                 cushion_classes_labels, styles)
    analyze_condition_cross(enriched, dirt, turf, venues_order, moisture_classes,
                            cushion_classes_labels, styles)
    analyze_venue_distance_cross(enriched, dirt, venues_order, moisture_classes, styles)
    analyze_position_gain(enriched, dirt, turf, venues_order, moisture_classes,
                          cushion_classes_labels)
    analyze_waku_style_cross(enriched, dirt, venues_order, moisture_classes, styles)
    analyze_kaisai_progression(enriched, turf, venues_order, cushion_classes_labels, styles)
    analyze_first_corner_distance(enriched, venues_order, cushion_classes_labels,
                                  moisture_classes, styles)


def analyze_waku(enriched, dirt, turf, venues_order, moisture_classes,
                  cushion_classes_labels, styles):
    """[6] 枠番×含水率/クッション×会場"""
    print(f"\n{'='*70}")
    print("  [6] ダート: 会場別 × 含水率 × 枠番（内外有利分析）")
    print(f"{'='*70}")

    waku_classes = ['内枠(1-3)', '中枠(4-5)', '外枠(6-8)']

    for venue in venues_order:
        venue_dirt = [e for e in dirt if e['venue'] == venue
                      and e['moisture'] is not None and e['waku_class'] != '不明']
        if len(venue_dirt) < 200:
            continue

        print(f"\n  ■ {venue}ダート (n={len(venue_dirt)})")
        print(f"    {'含水率':<14} {'枠':<10} {'n':>5} {'勝率':>7} {'top3率':>7} {'単ROI':>7}")
        print(f"    {'-'*55}")

        for mc in moisture_classes:
            grp = [e for e in venue_dirt if e['moisture_class'] == mc]
            if len(grp) < 50:
                continue
            for wk in waku_classes:
                sg = [e for e in grp if e['waku_class'] == wk]
                if len(sg) < 20:
                    continue
                wr = sum(e['is_win'] for e in sg) / len(sg) * 100
                tr = sum(e['is_top3'] for e in sg) / len(sg) * 100
                roi = sum(e['odds'] for e in sg if e['is_win']) / len(sg) * 100
                print(f"    {mc:<14} {wk:<10} {len(sg):>5} {wr:>6.1f}% {tr:>6.1f}% {roi:>6.0f}%")

    # 芝も同様
    print(f"\n{'='*70}")
    print("  [7] 芝: 会場別 × クッション値 × 枠番")
    print(f"{'='*70}")

    for venue in venues_order:
        venue_turf = [e for e in turf if e['venue'] == venue
                      and e['cushion'] is not None and e['waku_class'] != '不明']
        if len(venue_turf) < 200:
            continue

        print(f"\n  ■ {venue}芝 (n={len(venue_turf)})")
        print(f"    {'クッション':<16} {'枠':<10} {'n':>5} {'勝率':>7} {'top3率':>7} {'単ROI':>7}")
        print(f"    {'-'*55}")

        for label, lo, hi in cushion_classes_labels:
            grp = [e for e in venue_turf if lo <= (e['cushion'] or 0) < hi]
            if len(grp) < 50:
                continue
            for wk in waku_classes:
                sg = [e for e in grp if e['waku_class'] == wk]
                if len(sg) < 20:
                    continue
                wr = sum(e['is_win'] for e in sg) / len(sg) * 100
                tr = sum(e['is_top3'] for e in sg) / len(sg) * 100
                roi = sum(e['odds'] for e in sg if e['is_win']) / len(sg) * 100
                print(f"    {label:<16} {wk:<10} {len(sg):>5} {wr:>6.1f}% {tr:>6.1f}% {roi:>6.0f}%")


def analyze_condition_cross(enriched, dirt, turf, venues_order, moisture_classes,
                            cushion_classes_labels, styles):
    """[8] 馬場状態×含水率の交差"""
    print(f"\n{'='*70}")
    print("  [8] ダート: 馬場状態(良/稍重/重/不良) × 含水率 × 脚質")
    print(f"{'='*70}")

    conditions = ['良', '稍重', '重', '不良']
    for cond in conditions:
        cond_dirt = [e for e in dirt if e['track_condition'] == cond
                     and e['moisture'] is not None]
        if len(cond_dirt) < 100:
            continue

        print(f"\n  ■ ダート・{cond} (n={len(cond_dirt)})")
        # 含水率の実際の分布
        moistures = [e['moisture'] for e in cond_dirt]
        print(f"    含水率: min={min(moistures):.1f}% max={max(moistures):.1f}% avg={sum(moistures)/len(moistures):.1f}%")
        print(f"    {'含水率':<14} {'n':>5} {'逃先top3%':>10} {'好位top3%':>10} {'差しtop3%':>10} {'追込top3%':>10} {'差し有利度':>10}")

        for mc in moisture_classes:
            grp = [e for e in cond_dirt if e['moisture_class'] == mc]
            if len(grp) < 30:
                continue
            style_stats = {}
            for s in styles:
                sg = [e for e in grp if e['style'] == s]
                if sg:
                    style_stats[s] = sum(e['is_top3'] for e in sg) / len(sg) * 100
                else:
                    style_stats[s] = 0
            front = (style_stats.get('逃げ先行', 0) + style_stats.get('好位', 0)) / 2
            back = (style_stats.get('差し', 0) + style_stats.get('追込', 0)) / 2
            advantage = back - front
            print(f"    {mc:<14} {len(grp):>5} {style_stats.get('逃げ先行',0):>9.1f}% {style_stats.get('好位',0):>9.1f}% {style_stats.get('差し',0):>9.1f}% {style_stats.get('追込',0):>9.1f}% {advantage:>+9.1f}pt")


def analyze_venue_distance_cross(enriched, dirt, venues_order, moisture_classes, styles):
    """[9] 主要会場の距離帯×含水率クロス"""
    print(f"\n{'='*70}")
    print("  [9] 主要会場: 距離帯 × 含水率 × 脚質")
    print(f"{'='*70}")

    dist_bands = [(1000, 1400, '短距離'), (1400, 1800, 'マイル'), (1800, 2600, '中長距離')]
    target_venues = ['東京', '中山', '阪神', '中京', '小倉']

    for venue in target_venues:
        venue_dirt = [e for e in dirt if e['venue'] == venue and e['moisture'] is not None]
        if len(venue_dirt) < 300:
            continue

        print(f"\n  ■ {venue}ダート")
        print(f"    {'距離帯':<10} {'含水率':<14} {'n':>5} {'逃先top3%':>10} {'差しtop3%':>10} {'差し有利度':>10} {'穴馬top3%':>10}")
        print(f"    {'-'*75}")

        for d_lo, d_hi, d_label in dist_bands:
            band = [e for e in venue_dirt if d_lo <= e['distance'] < d_hi]
            if len(band) < 50:
                continue

            for mc in moisture_classes:
                grp = [e for e in band if e['moisture_class'] == mc]
                if len(grp) < 30:
                    continue

                front_grp = [e for e in grp if e['style'] in ('逃げ先行', '好位')]
                back_grp = [e for e in grp if e['style'] in ('差し', '追込')]
                front_t3 = sum(e['is_top3'] for e in front_grp) / len(front_grp) * 100 if front_grp else 0
                back_t3 = sum(e['is_top3'] for e in back_grp) / len(back_grp) * 100 if back_grp else 0
                advantage = back_t3 - front_t3

                longshots = [e for e in grp if e['popularity'] >= 6]
                ls_t3 = sum(e['is_top3'] for e in longshots) / len(longshots) * 100 if longshots else 0

                print(f"    {d_label:<10} {mc:<14} {len(grp):>5} {front_t3:>9.1f}% {back_t3:>9.1f}% {advantage:>+9.1f}pt {ls_t3:>9.1f}%")


def analyze_position_gain(enriched, dirt, turf, venues_order, moisture_classes,
                          cushion_classes_labels):
    """[10] 含水率別の追い込み有効度"""
    print(f"\n{'='*70}")
    print("  [10] 含水率/クッション別 追い込み有効度（position gain分析）")
    print(f"{'='*70}")

    print("\n  ■ ダート: 含水率別の追い込み（4角→着順で何頭抜けるか）")
    print(f"    {'会場':<8} {'含水率':<14} {'n':>5} {'avg_gain':>9} {'top3内gain':>11} {'4角5番手↓で巻返し率':>20}")
    print(f"    {'-'*75}")

    for venue in venues_order:
        venue_dirt = [e for e in dirt if e['venue'] == venue
                      and e['moisture'] is not None and e['last_corner'] > 0]
        if len(venue_dirt) < 200:
            continue

        for mc in moisture_classes:
            grp = [e for e in venue_dirt if e['moisture_class'] == mc]
            if len(grp) < 50:
                continue

            gains = [e['last_corner'] - e['finish_position'] for e in grp]
            avg_gain = sum(gains) / len(gains)

            # top3内の平均gain
            top3_grp = [e for e in grp if e['is_top3']]
            top3_gains = [e['last_corner'] - e['finish_position'] for e in top3_grp] if top3_grp else [0]
            avg_top3_gain = sum(top3_gains) / len(top3_gains)

            # 4角5番手以下から複勝圏に巻き返した率
            behind = [e for e in grp if e['last_corner'] >= 5]
            if behind:
                comeback = sum(e['is_top3'] for e in behind) / len(behind) * 100
            else:
                comeback = 0

            print(f"    {venue:<8} {mc:<14} {len(grp):>5} {avg_gain:>+8.2f} {avg_top3_gain:>+10.2f} {comeback:>19.1f}%")


def analyze_waku_style_cross(enriched, dirt, venues_order, moisture_classes, styles):
    """[11] 小倉・中山フォーカス: 枠×脚質×含水率"""
    print(f"\n{'='*70}")
    print("  [11] 注目会場: 枠番 × 脚質 × 含水率 クロス分析")
    print(f"{'='*70}")

    waku_classes = ['内枠(1-3)', '外枠(6-8)']
    target_venues = ['小倉', '中山', '東京', '札幌']

    for venue in target_venues:
        venue_dirt = [e for e in dirt if e['venue'] == venue
                      and e['moisture'] is not None and e['waku_class'] != '不明']
        if len(venue_dirt) < 200:
            continue

        print(f"\n  ■ {venue}ダート")
        print(f"    {'含水率':<14} {'枠':<10} {'脚質':<8} {'n':>5} {'top3率':>7} {'単ROI':>7}")
        print(f"    {'-'*60}")

        for mc in moisture_classes:
            grp = [e for e in venue_dirt if e['moisture_class'] == mc]
            if len(grp) < 50:
                continue
            for wk in waku_classes:
                for style in ['逃げ先行', '差し']:
                    sg = [e for e in grp if e['waku_class'] == wk and e['style'] == style]
                    if len(sg) < 15:
                        continue
                    tr = sum(e['is_top3'] for e in sg) / len(sg) * 100
                    roi = sum(e['odds'] for e in sg if e['is_win']) / len(sg) * 100
                    print(f"    {mc:<14} {wk:<10} {style:<8} {len(sg):>5} {tr:>6.1f}% {roi:>6.0f}%")


def analyze_kaisai_progression(enriched, turf, venues_order, cushion_classes_labels, styles):
    """[12]-[15] 開催日(nichi)進行による内外・脚質バイアスの変化"""

    # ========================================================
    # [12] 芝: 開催日別 × 脚質バイアス推移
    # ========================================================
    print(f"\n{'='*70}")
    print("  [12] 芝: 開催日(日目)別の脚質バイアス推移")
    print(f"{'='*70}")

    phases = ['序盤(1-2日)', '前半(3-4日)', '中盤(5-6日)', '後半(7日~)']

    for venue in venues_order:
        venue_turf = [e for e in turf if e['venue'] == venue]
        if len(venue_turf) < 500:
            continue

        print(f"\n  ■ {venue}芝 (n={len(venue_turf)})")
        print(f"    {'開催日':<14} {'n':>5} {'逃先top3%':>10} {'好位top3%':>10} {'差しtop3%':>10} {'追込top3%':>10} {'差し有利度':>10}")

        for phase in phases:
            grp = [e for e in venue_turf if e['nichi_phase'] == phase]
            if len(grp) < 100:
                continue
            style_stats = {}
            for s in styles:
                sg = [e for e in grp if e['style'] == s]
                if sg:
                    style_stats[s] = sum(e['is_top3'] for e in sg) / len(sg) * 100
                else:
                    style_stats[s] = 0
            front = (style_stats.get('逃げ先行', 0) + style_stats.get('好位', 0)) / 2
            back = (style_stats.get('差し', 0) + style_stats.get('追込', 0)) / 2
            advantage = back - front
            print(f"    {phase:<14} {len(grp):>5} {style_stats.get('逃げ先行',0):>9.1f}% {style_stats.get('好位',0):>9.1f}% {style_stats.get('差し',0):>9.1f}% {style_stats.get('追込',0):>9.1f}% {advantage:>+9.1f}pt")

    # ========================================================
    # [13] 芝: 開催日別 × 枠番バイアス推移
    # ========================================================
    print(f"\n{'='*70}")
    print("  [13] 芝: 開催日(日目)別の内外バイアス推移")
    print(f"{'='*70}")

    waku_classes = ['内枠(1-3)', '中枠(4-5)', '外枠(6-8)']

    for venue in venues_order:
        venue_turf = [e for e in turf if e['venue'] == venue and e['waku_class'] != '不明']
        if len(venue_turf) < 500:
            continue

        print(f"\n  ■ {venue}芝 (n={len(venue_turf)})")
        print(f"    {'開催日':<14} {'枠':<10} {'n':>5} {'勝率':>7} {'top3率':>7} {'単ROI':>7}")
        print(f"    {'-'*60}")

        for phase in phases:
            grp = [e for e in venue_turf if e['nichi_phase'] == phase]
            if len(grp) < 100:
                continue
            for wk in waku_classes:
                sg = [e for e in grp if e['waku_class'] == wk]
                if len(sg) < 30:
                    continue
                wr = sum(e['is_win'] for e in sg) / len(sg) * 100
                tr = sum(e['is_top3'] for e in sg) / len(sg) * 100
                roi = sum(e['odds'] for e in sg if e['is_win']) / len(sg) * 100
                print(f"    {phase:<14} {wk:<10} {len(sg):>5} {wr:>6.1f}% {tr:>6.1f}% {roi:>6.0f}%")

    # ========================================================
    # [14] 芝: 開催日別 × クッション値の推移
    # ========================================================
    print(f"\n{'='*70}")
    print("  [14] 芝: 開催日(日目)別のクッション値推移")
    print(f"{'='*70}")

    for venue in venues_order:
        venue_turf = [e for e in turf if e['venue'] == venue and e.get('cushion') is not None]
        if len(venue_turf) < 200:
            continue

        print(f"\n  ■ {venue}芝")
        print(f"    {'開催日':<14} {'n':>5} {'avg_cushion':>12} {'硬(>=9.5)%':>10} {'柔(<8.5)%':>10}")

        for phase in phases:
            grp = [e for e in venue_turf if e['nichi_phase'] == phase]
            if len(grp) < 50:
                continue
            cushions = [e['cushion'] for e in grp]
            avg_c = sum(cushions) / len(cushions)
            pct_hard = sum(1 for c in cushions if c >= 9.5) / len(cushions) * 100
            pct_soft = sum(1 for c in cushions if c < 8.5) / len(cushions) * 100
            print(f"    {phase:<14} {len(grp):>5} {avg_c:>11.2f} {pct_hard:>9.1f}% {pct_soft:>9.1f}%")

    # ========================================================
    # [15] 芝: 開催日 × クッション × 枠 × 脚質 クロス（核心分析）
    # ========================================================
    print(f"\n{'='*70}")
    print("  [15] 芝: 開催序盤(硬) vs 後半(柔) の内外・脚質バイアス変化")
    print(f"{'='*70}")

    target_venues = ['東京', '中山', '阪神', '京都', '中京', '新潟', '福島', '小倉']

    for venue in target_venues:
        venue_turf = [e for e in turf if e['venue'] == venue
                      and e.get('cushion') is not None and e['waku_class'] != '不明']
        if len(venue_turf) < 500:
            continue

        # 序盤×硬 vs 後半×柔
        combos = [
            ('序盤+硬', lambda e: e['nichi'] <= 2 and e['cushion'] >= 9.5),
            ('序盤+標準', lambda e: e['nichi'] <= 2 and 8.5 <= e['cushion'] < 9.5),
            ('後半+標準', lambda e: e['nichi'] >= 5 and 8.5 <= e['cushion'] < 9.5),
            ('後半+柔', lambda e: e['nichi'] >= 5 and e['cushion'] < 8.5),
        ]

        has_data = False
        rows = []
        for label, cond in combos:
            grp = [e for e in venue_turf if cond(e)]
            if len(grp) < 50:
                continue
            has_data = True

            # 内外
            inner = [e for e in grp if e['waku_class'] == '内枠(1-3)']
            outer = [e for e in grp if e['waku_class'] == '外枠(6-8)']
            inner_t3 = sum(e['is_top3'] for e in inner) / len(inner) * 100 if inner else 0
            outer_t3 = sum(e['is_top3'] for e in outer) / len(outer) * 100 if outer else 0
            inner_advantage = inner_t3 - outer_t3

            # 脚質
            style_stats = {}
            for s in styles:
                sg = [e for e in grp if e['style'] == s]
                if sg:
                    style_stats[s] = sum(e['is_top3'] for e in sg) / len(sg) * 100
                else:
                    style_stats[s] = 0
            front = (style_stats.get('逃げ先行', 0) + style_stats.get('好位', 0)) / 2
            back = (style_stats.get('差し', 0) + style_stats.get('追込', 0)) / 2
            style_advantage = back - front

            # 内×逃先 vs 外×差し (核心指標)
            inner_front = [e for e in grp if e['waku_class'] == '内枠(1-3)' and e['style'] in ('逃げ先行', '好位')]
            outer_back = [e for e in grp if e['waku_class'] == '外枠(6-8)' and e['style'] in ('差し', '追込')]
            if_t3 = sum(e['is_top3'] for e in inner_front) / len(inner_front) * 100 if inner_front else 0
            ob_t3 = sum(e['is_top3'] for e in outer_back) / len(outer_back) * 100 if outer_back else 0

            rows.append((label, len(grp), inner_t3, outer_t3, inner_advantage,
                         style_advantage, if_t3, ob_t3))

        if has_data:
            print(f"\n  ■ {venue}芝")
            print(f"    {'条件':<12} {'n':>5} {'内top3%':>8} {'外top3%':>8} {'内有利度':>8} {'差有利度':>8} {'内先行':>7} {'外差し':>7}")
            print(f"    {'-'*70}")
            for r in rows:
                label, n, it3, ot3, ia, sa, ift3, obt3 = r
                print(f"    {label:<12} {n:>5} {it3:>7.1f}% {ot3:>7.1f}% {ia:>+7.1f}pt {sa:>+7.1f}pt {ift3:>6.1f}% {obt3:>6.1f}%")


def analyze_first_corner_distance(enriched, venues_order, cushion_classes_labels,
                                  moisture_classes, styles):
    """[16]-[18] スタート→1角距離によるバイアス分析"""

    # コーナー数でコースを分類
    # corners が4つ → 4角コース（1角まで短い傾向）
    # corners が2つ → ワンターンコース（1角まで長い傾向）
    # corners が0-1 → 直線 or 特殊

    # JRA主要コースの1角までの概算距離（メートル）
    # venue + track_type + distance → approx first corner distance
    FIRST_CORNER_DIST = {
        # 東京
        ('東京', 'turf', 1400): 540,   # 2角ワンターン
        ('東京', 'turf', 1600): 540,   # 2角ワンターン
        ('東京', 'turf', 1800): 340,   # 4角
        ('東京', 'turf', 2000): 540,   # 4角だが直線入り
        ('東京', 'turf', 2400): 350,   # 4角
        ('東京', 'dirt', 1300): 150,   # ★超短
        ('東京', 'dirt', 1400): 270,   # 2角ワンターン
        ('東京', 'dirt', 1600): 470,   # 2角ワンターン
        ('東京', 'dirt', 2100): 350,   # 4角
        # 中山
        ('中山', 'turf', 1200): 200,   # ★超短 4角
        ('中山', 'turf', 1600): 250,   # 4角
        ('中山', 'turf', 1800): 460,   # 4角
        ('中山', 'turf', 2000): 260,   # 4角
        ('中山', 'turf', 2200): 460,   # 4角
        ('中山', 'turf', 2500): 260,   # 4角
        ('中山', 'dirt', 1200): 250,   # ★短 4角
        ('中山', 'dirt', 1800): 450,   # 4角
        # 阪神
        ('阪神', 'turf', 1200): 280,   # ★短 4角内回り
        ('阪神', 'turf', 1400): 310,   # 4角内回り
        ('阪神', 'turf', 1600): 450,   # 4角外回り
        ('阪神', 'turf', 1800): 310,   # 4角内回り
        ('阪神', 'turf', 2000): 450,   # 4角外回り
        ('阪神', 'turf', 2200): 280,   # 4角内回り
        ('阪神', 'turf', 2400): 440,   # 4角外回り
        ('阪神', 'dirt', 1200): 270,   # ★短
        ('阪神', 'dirt', 1400): 460,   # 2角ワンターン
        ('阪神', 'dirt', 1800): 260,   # 4角
        ('阪神', 'dirt', 2000): 460,   # 4角
        # 京都
        ('京都', 'turf', 1200): 280,   # ★短 4角内
        ('京都', 'turf', 1400): 400,   # 4角外
        ('京都', 'turf', 1600): 280,   # 4角内
        ('京都', 'turf', 1800): 400,   # 4角外
        ('京都', 'turf', 2000): 280,   # 4角内
        ('京都', 'turf', 2200): 400,   # 4角外
        ('京都', 'turf', 2400): 350,   # 4角
        ('京都', 'dirt', 1200): 280,   # ★短
        ('京都', 'dirt', 1400): 420,   # ワンターン
        ('京都', 'dirt', 1800): 250,   # 4角
        ('京都', 'dirt', 1900): 350,   # 4角
        # 中京
        ('中京', 'turf', 1200): 310,   # 4角
        ('中京', 'turf', 1400): 510,   # ワンターン
        ('中京', 'turf', 1600): 310,   # 4角
        ('中京', 'turf', 2000): 350,   # 4角
        ('中京', 'turf', 2200): 350,   # 4角
        ('中京', 'dirt', 1200): 310,   # ★短
        ('中京', 'dirt', 1400): 510,   # ワンターン
        ('中京', 'dirt', 1800): 310,   # 4角
        ('中京', 'dirt', 1900): 410,   # 4角
        # 新潟
        ('新潟', 'turf', 1000): 999,   # 直線
        ('新潟', 'turf', 1200): 440,   # 2角外
        ('新潟', 'turf', 1400): 450,   # 2角内
        ('新潟', 'turf', 1600): 350,   # 4角外
        ('新潟', 'turf', 1800): 250,   # 4角内
        ('新潟', 'turf', 2000): 450,   # 4角外
        ('新潟', 'dirt', 1200): 380,   # 2角
        ('新潟', 'dirt', 1800): 280,   # 4角
        # 福島
        ('福島', 'turf', 1200): 320,   # 4角
        ('福島', 'turf', 1800): 380,   # 4角
        ('福島', 'turf', 2000): 310,   # 4角
        ('福島', 'turf', 2600): 310,   # 4角
        ('福島', 'dirt', 1150): 300,   # 4角
        ('福島', 'dirt', 1700): 360,   # 4角
        # 小倉
        ('小倉', 'turf', 1200): 310,   # 4角
        ('小倉', 'turf', 1800): 320,   # 4角
        ('小倉', 'turf', 2000): 310,   # 4角
        ('小倉', 'dirt', 1000): 200,   # ★超短
        ('小倉', 'dirt', 1700): 350,   # 4角
        # 札幌
        ('札幌', 'turf', 1200): 310,   # 4角
        ('札幌', 'turf', 1500): 310,   # 4角
        ('札幌', 'turf', 1800): 310,   # 4角
        ('札幌', 'turf', 2000): 310,   # 4角
        ('札幌', 'dirt', 1000): 200,   # ★超短
        ('札幌', 'dirt', 1700): 360,   # 4角
        # 函館
        ('函館', 'turf', 1200): 280,   # 4角
        ('函館', 'turf', 1800): 330,   # 4角
        ('函館', 'turf', 2000): 250,   # 4角
        ('函館', 'dirt', 1000): 200,   # ★超短
        ('函館', 'dirt', 1700): 350,   # 4角
    }

    # 1角距離の分類
    def classify_fc_dist(d):
        if d is None:
            return None
        if d <= 250:
            return '超短(~250m)'
        elif d <= 350:
            return '短(250-350m)'
        elif d <= 450:
            return '中(350-450m)'
        else:
            return '長(450m~)'

    # enrichedにfirst_corner_distを追加
    for e in enriched:
        key = (e['venue'], e['track_type'], e['distance'])
        e['fc_dist'] = FIRST_CORNER_DIST.get(key)
        e['fc_class'] = classify_fc_dist(e['fc_dist'])

    # ========================================================
    # [16] 1角距離別の内外バイアス
    # ========================================================
    print(f"\n{'='*70}")
    print("  [16] 1角距離別の内外・脚質バイアス（全会場集計）")
    print(f"{'='*70}")

    fc_classes = ['超短(~250m)', '短(250-350m)', '中(350-450m)', '長(450m~)']
    waku_classes = ['内枠(1-3)', '中枠(4-5)', '外枠(6-8)']

    for track_type, track_label in [('turf', '芝'), ('dirt', 'ダート')]:
        track_data = [e for e in enriched if e['track_type'] == track_type
                      and e['fc_class'] is not None and e['waku_class'] != '不明'
                      and e['style'] != '不明']
        if not track_data:
            continue

        print(f"\n  ■ {track_label}")
        print(f"    {'1角距離':<14} {'n':>6} {'内top3%':>8} {'外top3%':>8} {'内有利度':>8} {'逃先top3%':>10} {'差しtop3%':>10} {'差有利度':>8}")
        print(f"    {'-'*80}")

        for fc in fc_classes:
            grp = [e for e in track_data if e['fc_class'] == fc]
            if len(grp) < 200:
                continue

            inner = [e for e in grp if e['waku_class'] == '内枠(1-3)']
            outer = [e for e in grp if e['waku_class'] == '外枠(6-8)']
            inner_t3 = sum(e['is_top3'] for e in inner) / len(inner) * 100 if inner else 0
            outer_t3 = sum(e['is_top3'] for e in outer) / len(outer) * 100 if outer else 0
            inner_adv = inner_t3 - outer_t3

            front = [e for e in grp if e['style'] == '逃げ先行']
            sashi = [e for e in grp if e['style'] == '差し']
            front_t3 = sum(e['is_top3'] for e in front) / len(front) * 100 if front else 0
            sashi_t3 = sum(e['is_top3'] for e in sashi) / len(sashi) * 100 if sashi else 0
            style_adv = sashi_t3 - front_t3

            print(f"    {fc:<14} {len(grp):>6} {inner_t3:>7.1f}% {outer_t3:>7.1f}% {inner_adv:>+7.1f}pt {front_t3:>9.1f}% {sashi_t3:>9.1f}% {style_adv:>+7.1f}pt")

    # ========================================================
    # [17] コース別 内有利ランキング（1角距離付き）
    # ========================================================
    print(f"\n{'='*70}")
    print("  [17] コース別 内有利度ランキング（1角距離付き）")
    print(f"{'='*70}")

    for track_type, track_label in [('turf', '芝'), ('dirt', 'ダート')]:
        print(f"\n  ■ {track_label}")
        print(f"    {'コース':<20} {'1角m':>5} {'n':>6} {'内top3%':>8} {'外top3%':>8} {'内有利度':>8} {'逃先%':>7} {'差し有利度':>8}")
        print(f"    {'-'*80}")

        course_stats = []
        for key, fc_dist in FIRST_CORNER_DIST.items():
            venue, tt, dist = key
            if tt != track_type:
                continue
            grp = [e for e in enriched if e['venue'] == venue
                   and e['track_type'] == tt and e['distance'] == dist
                   and e['waku_class'] != '不明' and e['style'] != '不明']
            if len(grp) < 100:
                continue

            inner = [e for e in grp if e['waku_class'] == '内枠(1-3)']
            outer = [e for e in grp if e['waku_class'] == '外枠(6-8)']
            inner_t3 = sum(e['is_top3'] for e in inner) / len(inner) * 100 if inner else 0
            outer_t3 = sum(e['is_top3'] for e in outer) / len(outer) * 100 if outer else 0
            inner_adv = inner_t3 - outer_t3

            front = [e for e in grp if e['style'] == '逃げ先行']
            sashi = [e for e in grp if e['style'] == '差し']
            oikomi = [e for e in grp if e['style'] == '追込']
            front_t3 = sum(e['is_top3'] for e in front) / len(front) * 100 if front else 0
            sashi_t3 = sum(e['is_top3'] for e in sashi) / len(sashi) * 100 if sashi else 0
            oikomi_t3 = sum(e['is_top3'] for e in oikomi) / len(oikomi) * 100 if oikomi else 0
            style_adv = ((sashi_t3 + oikomi_t3) / 2) - ((front_t3 + sum(e['is_top3'] for e in [e for e in grp if e['style'] == '好位']) / max(1, len([e for e in grp if e['style'] == '好位'])) * 100) / 2)

            course_name = f"{venue}{dist}m"
            course_stats.append((course_name, fc_dist, len(grp), inner_t3, outer_t3,
                                 inner_adv, front_t3, style_adv))

        # 内有利度でソート
        course_stats.sort(key=lambda x: -x[5])
        for cs in course_stats:
            name, fc, n, it3, ot3, ia, ft3, sa = cs
            marker = '★' if ia > 3 else ('▼' if ia < -3 else '')
            print(f"    {name:<20} {fc:>5} {n:>6} {it3:>7.1f}% {ot3:>7.1f}% {ia:>+7.1f}pt {ft3:>6.1f}% {sa:>+7.1f}pt {marker}")

    # ========================================================
    # [18] 1角距離×クッション/含水率 クロス
    # ========================================================
    print(f"\n{'='*70}")
    print("  [18] 1角距離 × クッション/含水率 × 枠番 クロス分析")
    print(f"{'='*70}")

    # 芝: 1角距離 × クッション値 × 枠
    print(f"\n  ■ 芝: 1角距離 × クッション値 × 内外バイアス")
    print(f"    {'1角距離':<14} {'クッション':<14} {'n':>5} {'内top3%':>8} {'外top3%':>8} {'内有利度':>8}")
    print(f"    {'-'*60}")

    cushion_labels = [('硬(>=9.5)', 9.5, 99), ('標準(8.5-9.5)', 8.5, 9.5), ('柔(<8.5)', 0, 8.5)]

    for fc in fc_classes:
        turf_fc = [e for e in enriched if e['track_type'] == 'turf'
                   and e['fc_class'] == fc and e.get('cushion') is not None
                   and e['waku_class'] != '不明']
        if len(turf_fc) < 100:
            continue

        for c_label, c_lo, c_hi in cushion_labels:
            grp = [e for e in turf_fc if c_lo <= (e['cushion'] or 0) < c_hi]
            if len(grp) < 50:
                continue
            inner = [e for e in grp if e['waku_class'] == '内枠(1-3)']
            outer = [e for e in grp if e['waku_class'] == '外枠(6-8)']
            inner_t3 = sum(e['is_top3'] for e in inner) / len(inner) * 100 if inner else 0
            outer_t3 = sum(e['is_top3'] for e in outer) / len(outer) * 100 if outer else 0
            inner_adv = inner_t3 - outer_t3
            print(f"    {fc:<14} {c_label:<14} {len(grp):>5} {inner_t3:>7.1f}% {outer_t3:>7.1f}% {inner_adv:>+7.1f}pt")

    # ダート: 1角距離 × 含水率 × 枠
    print(f"\n  ■ ダート: 1角距離 × 含水率 × 内外バイアス")
    print(f"    {'1角距離':<14} {'含水率':<14} {'n':>5} {'内top3%':>8} {'外top3%':>8} {'内有利度':>8}")
    print(f"    {'-'*60}")

    for fc in fc_classes:
        dirt_fc = [e for e in enriched if e['track_type'] == 'dirt'
                   and e['fc_class'] == fc and e.get('moisture') is not None
                   and e['waku_class'] != '不明']
        if len(dirt_fc) < 100:
            continue

        for mc in moisture_classes:
            grp = [e for e in dirt_fc if e['moisture_class'] == mc]
            if len(grp) < 50:
                continue
            inner = [e for e in grp if e['waku_class'] == '内枠(1-3)']
            outer = [e for e in grp if e['waku_class'] == '外枠(6-8)']
            inner_t3 = sum(e['is_top3'] for e in inner) / len(inner) * 100 if inner else 0
            outer_t3 = sum(e['is_top3'] for e in outer) / len(outer) * 100 if outer else 0
            inner_adv = inner_t3 - outer_t3
            print(f"    {fc:<14} {mc:<14} {len(grp):>5} {inner_t3:>7.1f}% {outer_t3:>7.1f}% {inner_adv:>+7.1f}pt")


if __name__ == '__main__':
    analyze()
