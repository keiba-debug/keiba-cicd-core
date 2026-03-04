#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
JRDBデータ自動ダウンロード

年度パック (SED_YYYY.zip 等) と単体ファイル (SEDYYMMDD.zip 等) を
自動でダウンロード・解凍する。

Usage:
    # SEDの年度パック全部ダウンロード (2020-2025)
    python -m jrdb.downloader --type SED --years 2020-2025

    # SEDの単体データ（最新分）をダウンロード
    python -m jrdb.downloader --type SED --latest

    # KYIの年度パック全部ダウンロード
    python -m jrdb.downloader --type KYI --years 2020-2025

    # 全データタイプの年度パックを一括ダウンロード
    python -m jrdb.downloader --all --years 2020-2025

認証情報: C:/KEIBA-CICD/data3/jrdb/.env (JRDB_USER, JRDB_PASS)
"""

import argparse
import os
import re
import sys
import zipfile
from pathlib import Path
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

try:
    import lhafile
except ImportError:
    lhafile = None

# === 設定 ===
JRDB_BASE = 'https://jrdb.com'
DATA_DIR = Path('C:/KEIBA-CICD/data3/jrdb')
ZIP_DIR = DATA_DIR / 'zip'
RAW_DIR = DATA_DIR / 'raw'
ENV_PATH = DATA_DIR / '.env'

# データタイプ → ダウンロードページURL (datazip=ZIP形式, data=LZH形式)
DATA_TYPES = {
    'SED': '/member/datazip/Sed/index.html',    # 成績データ (事後IDM)
    'SKB': '/member/datazip/Skb/index.html',    # 成績拡張データ
    'KYI': '/member/datazip/Kyi/index.html',    # 競走馬データ (事前IDM)
    'TYB': '/member/datazip/Tyb/index.html',    # 直前情報データ
    'HJC': '/member/datazip/Hjc/index.html',    # 払戻情報データ
    'KAA': '/member/data/Kaa/index.html',       # 開催データ (馬場・天候) ※LZH形式
}


def load_credentials() -> tuple:
    """認証情報をロード"""
    if ENV_PATH.exists():
        env = {}
        for line in ENV_PATH.read_text().strip().split('\n'):
            if '=' in line:
                k, v = line.split('=', 1)
                env[k.strip()] = v.strip()
        return env.get('JRDB_USER', ''), env.get('JRDB_PASS', '')

    # 環境変数フォールバック
    return os.environ.get('JRDB_USER', ''), os.environ.get('JRDB_PASS', '')


def get_session() -> requests.Session:
    """認証付きセッションを作成"""
    user, passwd = load_credentials()
    if not user or not passwd:
        print("ERROR: JRDB credentials not found. Set JRDB_USER/JRDB_PASS in .env")
        sys.exit(1)

    session = requests.Session()
    session.auth = (user, passwd)
    session.headers.update({'User-Agent': 'Mozilla/5.0 KeibaCICD/1.0'})
    return session


def list_archive_links(session: requests.Session, data_type: str) -> List[dict]:
    """ダウンロードページからZIP/LZHリンクを収集

    Returns:
        [{'url': str, 'filename': str, 'is_yearly': bool, 'year': int|None}]
    """
    page_path = DATA_TYPES.get(data_type)
    if not page_path:
        print(f"ERROR: Unknown data type: {data_type}")
        return []

    url = JRDB_BASE + page_path
    r = session.get(url)
    if r.status_code != 200:
        print(f"ERROR: HTTP {r.status_code} for {url}")
        return []

    # ベースURL（相対リンク解決用）
    base_dir = page_path.rsplit('/', 1)[0]

    soup = BeautifulSoup(r.content, 'html.parser')
    links = []

    for a in soup.find_all('a', href=True):
        href = a['href']
        if not (href.endswith('.zip') or href.endswith('.lzh')):
            continue

        filename = href.split('/')[-1]
        ext = filename.rsplit('.', 1)[-1]  # zip or lzh

        # 年度パック: SED_2024.zip / KAA_2024.lzh
        yearly_match = re.match(rf'{data_type}_(\d{{4}})\.(?:zip|lzh)', filename, re.IGNORECASE)
        # 単体: SED260301.zip / KAA260301.lzh
        single_match = re.match(rf'{data_type}_?(\d{{6}})\.(?:zip|lzh)', filename, re.IGNORECASE)

        if yearly_match:
            year = int(yearly_match.group(1))
            full_url = href if href.startswith('http') else JRDB_BASE + base_dir + '/' + href
            links.append({
                'url': full_url,
                'filename': filename,
                'is_yearly': True,
                'year': year,
                'format': ext,
            })
        elif single_match:
            full_url = href if href.startswith('http') else JRDB_BASE + base_dir + '/' + href
            links.append({
                'url': full_url,
                'filename': filename,
                'is_yearly': False,
                'year': None,
                'format': ext,
            })

    return links


def download_file(session: requests.Session, url: str, dest: Path) -> bool:
    """ファイルをダウンロード"""
    if dest.exists():
        print(f"  SKIP (exists): {dest.name}")
        return True

    try:
        r = session.get(url, stream=True)
        if r.status_code != 200:
            print(f"  ERROR: HTTP {r.status_code} for {url}")
            return False

        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

        size_kb = dest.stat().st_size / 1024
        print(f"  OK: {dest.name} ({size_kb:.0f} KB)")
        return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def extract_zip(zip_path: Path, dest_dir: Path) -> int:
    """ZIPを解凍してテキストファイルを配置

    Returns: 解凍したファイル数
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for info in zf.infolist():
                name = info.filename
                # ShiftJISファイル名の場合
                try:
                    name = info.filename.encode('cp437').decode('shift_jis')
                except (UnicodeDecodeError, UnicodeEncodeError):
                    pass

                if name.endswith('.txt') or name.endswith('.csv'):
                    # フラット展開（ディレクトリ構造は無視）
                    out_path = dest_dir / Path(name).name
                    if not out_path.exists():
                        data = zf.read(info.filename)
                        out_path.write_bytes(data)
                        count += 1

    except zipfile.BadZipFile:
        print(f"  ERROR: Bad ZIP file: {zip_path.name}")
        return 0

    return count


def extract_lzh(lzh_path: Path, dest_dir: Path) -> int:
    """LZHを解凍してテキストファイルを配置"""
    if lhafile is None:
        print("  ERROR: lhafile not installed. Run: pip install lhafile")
        return 0

    dest_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    try:
        lf = lhafile.Lhafile(str(lzh_path))
        for name in lf.namelist():
            if name.endswith('.txt') or name.endswith('.csv'):
                out_path = dest_dir / Path(name).name
                if not out_path.exists():
                    data = lf.read(name)
                    out_path.write_bytes(data)
                    count += 1
    except Exception as e:
        print(f"  ERROR: Bad LZH file: {lzh_path.name} ({e})")
        return 0

    return count


def extract_archive(archive_path: Path, dest_dir: Path) -> int:
    """ZIP/LZHを自動判定して解凍"""
    if archive_path.suffix.lower() == '.lzh':
        return extract_lzh(archive_path, dest_dir)
    else:
        return extract_zip(archive_path, dest_dir)


def download_yearly(session: requests.Session, data_type: str, years: List[int]):
    """年度パックをダウンロード・解凍"""
    print(f"\n[{data_type}] Downloading yearly packs: {years[0]}-{years[-1]}")

    links = list_archive_links(session, data_type)
    yearly = [l for l in links if l['is_yearly'] and l['year'] in years]

    if not yearly:
        print(f"  No yearly packs found for {data_type} in {years}")
        # リンク一覧を表示
        all_yearly = [l for l in links if l['is_yearly']]
        if all_yearly:
            print(f"  Available: {[l['year'] for l in all_yearly]}")
        return

    type_zip_dir = ZIP_DIR / data_type
    type_raw_dir = RAW_DIR / data_type

    for link in sorted(yearly, key=lambda x: x['year']):
        dest = type_zip_dir / link['filename']
        if download_file(session, link['url'], dest):
            n = extract_archive(dest, type_raw_dir)
            if n > 0:
                print(f"  Extracted: {n} files")


def download_latest(session: requests.Session, data_type: str, count: int = 5):
    """最新の単体ファイルをダウンロード"""
    print(f"\n[{data_type}] Downloading latest {count} files")

    links = list_archive_links(session, data_type)
    singles = [l for l in links if not l['is_yearly']]

    def _sort_key(link):
        """2桁年ファイル名を正しくソート (YY>=80→19XX, else 20XX)"""
        m = re.search(r'(\d{6})', link['filename'])
        if m:
            yy = int(m.group(1)[:2])
            full_year = 1900 + yy if yy >= 80 else 2000 + yy
            return f"{full_year}{m.group(1)[2:]}"
        return link['filename']

    singles.sort(key=_sort_key, reverse=True)

    type_zip_dir = ZIP_DIR / data_type
    type_raw_dir = RAW_DIR / data_type

    for link in singles[:count]:
        dest = type_zip_dir / link['filename']
        if download_file(session, link['url'], dest):
            n = extract_archive(dest, type_raw_dir)
            if n > 0:
                print(f"  Extracted: {n} files")


def main():
    parser = argparse.ArgumentParser(description='JRDB Data Downloader')
    parser.add_argument('--type', choices=list(DATA_TYPES.keys()),
                        help='データタイプ (SED/KYI/TYB/KAA/HJC/SKB)')
    parser.add_argument('--all', action='store_true',
                        help='全データタイプを一括ダウンロード')
    parser.add_argument('--years', default='2020-2025',
                        help='年度範囲 (例: 2020-2025)')
    parser.add_argument('--latest', action='store_true',
                        help='最新の単体ファイルをダウンロード')
    parser.add_argument('--latest-count', type=int, default=10,
                        help='最新ファイルの取得数 (default: 10)')
    parser.add_argument('--list', action='store_true',
                        help='ダウンロード可能なファイル一覧を表示')
    args = parser.parse_args()

    session = get_session()

    # テスト接続
    r = session.get(JRDB_BASE + '/member/dataindex.html')
    if r.status_code != 200:
        print(f"ERROR: Cannot access JRDB member area (HTTP {r.status_code})")
        sys.exit(1)
    print("JRDB login OK")

    # 年度範囲パース
    if '-' in args.years:
        start, end = args.years.split('-')
        years = list(range(int(start), int(end) + 1))
    else:
        years = [int(args.years)]

    types = list(DATA_TYPES.keys()) if args.all else ([args.type] if args.type else ['SED'])

    if args.list:
        for dt in types:
            links = list_zip_links(session, dt)
            print(f"\n[{dt}] {len(links)} files available:")
            for l in links[:10]:
                tag = f"({l['year']})" if l['is_yearly'] else "(single)"
                print(f"  {l['filename']} {tag}")
            if len(links) > 10:
                print(f"  ... and {len(links) - 10} more")
        return

    for dt in types:
        if args.latest:
            download_latest(session, dt, args.latest_count)
        else:
            download_yearly(session, dt, years)

    print("\nDone.")


if __name__ == '__main__':
    main()
