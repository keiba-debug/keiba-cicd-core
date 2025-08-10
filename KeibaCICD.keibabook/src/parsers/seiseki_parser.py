"""
成績パーサー

競馬ブックの成績ページから情報を抽出します。
"""

import re
from typing import Any, Dict, List

from bs4 import BeautifulSoup

from .base_parser import BaseParser
from ..utils.config import Config


class SeisekiParser(BaseParser):
    """
    成績ページのパーサー
    
    競馬ブックの成績ページから以下の情報を抽出します：
    - レース情報
    - 出走馬の成績
    - インタビュー
    - 次走へのメモ
    """
    
    def __init__(self, debug: bool = False):
        """
        初期化
        
        Args:
            debug: デバッグモードの有効化
        """
        super().__init__(debug)
    
    def parse(self, html_file_path: str) -> Dict[str, Any]:
        """
        HTMLファイルをパースして成績データを抽出する
        
        Args:
            html_file_path: HTMLファイルのパス
            
        Returns:
            Dict[str, Any]: 抽出された成績データ
        """
        self.logger.info("成績データの抽出を開始します")
        
        # HTMLを読み込み
        soup = self.load_html(html_file_path)
        
        # レース情報を抽出
        race_info = self._extract_race_info(soup)
        
        # 成績データを抽出
        results = self._extract_results(soup)
        
        # インタビューとメモを抽出
        interviews_and_memos = self._extract_interviews_and_memos(soup)
        
        # 結果をマージ
        results = self._merge_interview_memo_data(results, interviews_and_memos)
        
        # 追加: 配当・レース詳細・ラップ
        payouts = self._extract_payout_info(soup)
        race_details = self._extract_race_details(soup)
        laps = self._extract_laps(soup)
        
        data = {
            "race_info": race_info,
            "results": results,
            "payouts": payouts,
            "race_details": race_details,
            "laps": laps
        }
        
        # データ検証
        if self.validate_data(data):
            self.logger.info(f"成績データの抽出が完了しました。出走頭数: {len(results)}頭")
        else:
            self.logger.warning("抽出されたデータに問題がある可能性があります")
        
        return data
    
    def _extract_race_info(self, soup: BeautifulSoup) -> Dict[str, str]:
        """
        レース情報を抽出する
        
        Args:
            soup: BeautifulSoupオブジェクト
            
        Returns:
            Dict[str, str]: レース情報
        """
        race_info = {}
        
        # レース名を抽出（titleタグから）
        title_element = soup.find('title')
        if title_element:
            title_text = self.extract_text_safely(title_element)
            # "レース結果 | 2025年6月1日東京11R第９２回　東京優駿(ＧＩ) | 競馬ブック" から抽出
            if " | " in title_text:
                parts = title_text.split(" | ")
                if len(parts) >= 2:
                    race_info["race_name"] = parts[1].strip()
                else:
                    race_info["race_name"] = title_text
            else:
                race_info["race_name"] = title_text
        
        # h1タグからも試してみる
        if not race_info.get("race_name"):
            h1_element = soup.find('h1')
            if h1_element:
                race_info["race_name"] = self.extract_text_safely(h1_element)
        
        self.debug_log("レース情報を抽出しました", race_info)
        return race_info
    
    def _extract_results(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """
        成績データを抽出する
        
        Args:
            soup: BeautifulSoupオブジェクト
            
        Returns:
            List[Dict[str, str]]: 成績データのリスト
        """
        results = []
        
        # テーブルを検索
        table = soup.find('table', class_='default seiseki')
        if not table:
            # 'seiseki'クラスのみも試してみる
            table = soup.find('table', {'class': 'seiseki'})
        if not table:
            self.logger.warning("成績テーブルが見つかりません")
            print("成績テーブルが見つかりません")
            return results
        
        # ヘッダー行を取得
        header_row = table.find('tr')
        if not header_row:
            self.logger.warning("ヘッダー行が見つかりません")
            return results
        
        # ヘッダーを抽出（colspanを考慮）
        headers = []
        for th in header_row.find_all(['th', 'td']):
            header_text = self.extract_text_safely(th)
            colspan = int(th.get('colspan', 1))
            
            if colspan > 1:
                # colspanが2以上の場合は、その分だけヘッダーを複製
                for i in range(colspan):
                    if i == 0:
                        headers.append(header_text)
                    else:
                        headers.append(header_text + f"_{i+1}")  # 重複を避けるため番号を追加
            else:
                headers.append(header_text)
        
        self.debug_log("テーブルヘッダー", headers)
        
        # データ行を処理
        for row in table.find_all('tr')[1:]:  # ヘッダー行をスキップ
            cells = row.find_all(['td', 'th'])
            if len(cells) >= len(headers):
                row_data = {}
                for i, cell in enumerate(cells[:len(headers)]):
                    if i < len(headers):
                        row_data[headers[i]] = self.extract_text_safely(cell)
                
                if row_data:
                    results.append(row_data)
        
        self.debug_log(f"成績データを抽出しました", f"{len(results)}頭")
        return results
    
    def _extract_interviews_and_memos(self, soup: BeautifulSoup) -> Dict[str, Dict[str, str]]:
        """
        インタビューとメモを抽出する
        
        Args:
            soup: BeautifulSoupオブジェクト
            
        Returns:
            Dict[str, Dict[str, str]]: 馬名をキーとしたインタビューとメモのデータ
        """
        interviews_and_memos = {}
        
        # bameiboxクラスの要素を検索
        bameibox_elements = soup.find_all('div', class_='bameibox')
        
        for element in bameibox_elements:
            # 馬名を抽出
            horse_name = self._extract_horse_name_from_element(element)
            if not horse_name:
                continue
            
            # テキストを抽出
            text = self.extract_text_safely(element)
            
            # インタビューかメモかを判定
            if self._is_interview_text(text):
                interview_content = self._clean_interview_text(text)
                if horse_name not in interviews_and_memos:
                    interviews_and_memos[horse_name] = {}
                interviews_and_memos[horse_name]["interview"] = interview_content
                self.debug_log(f"interview", f"raw='{text[:50]}...', horse='{horse_name}', body='{interview_content[:50]}...'")
            else:
                memo_content = self._clean_memo_text(text)
                if horse_name not in interviews_and_memos:
                    interviews_and_memos[horse_name] = {}
                interviews_and_memos[horse_name]["memo"] = memo_content
                self.debug_log(f"memo", f"raw='{text[:50]}...', horse='{horse_name}', body='{memo_content[:50]}...'")
        
        return interviews_and_memos
    
    def _extract_horse_name_from_element(self, element) -> str:
        """
        要素から馬名を抽出する
        
        Args:
            element: BeautifulSoupの要素
            
        Returns:
            str: 馬名
        """
        text = self.extract_text_safely(element)
        
        # パターン1: 馬名（着順）の形式
        pattern1 = r'^([^（]+)（[^）]*）'
        match = re.match(pattern1, text)
        if match:
            return match.group(1).strip()
        
        # パターン2: 馬名……の形式
        pattern2 = r'^([^…]+)…'
        match = re.match(pattern2, text)
        if match:
            return match.group(1).strip()
        
        return ""
    
    def _is_interview_text(self, text: str) -> bool:
        """
        テキストがインタビューかどうかを判定する
        
        Args:
            text: 判定対象のテキスト
            
        Returns:
            bool: インタビューの場合True
        """
        # 着順と騎手名が含まれている場合はインタビュー
        interview_pattern = r'[（(][０-９\d]+着[）)].*?騎手'
        return bool(re.search(interview_pattern, text))
    
    def _clean_interview_text(self, text: str) -> str:
        """
        インタビューテキストをクリーニングする
        
        Args:
            text: クリーニング対象のテキスト
            
        Returns:
            str: クリーニング後のテキスト
        """
        # 馬名と着順部分を除去
        pattern = r'^[^（]*（[^）]*）\s*'
        cleaned_text = re.sub(pattern, '', text)
        return self.clean_text(cleaned_text)
    
    def _clean_memo_text(self, text: str) -> str:
        """
        メモテキストをクリーニングする
        
        Args:
            text: クリーニング対象のテキスト
            
        Returns:
            str: クリーニング後のテキスト
        """
        # 馬名と「……」部分を除去
        pattern = r'^[^…]*…+'
        cleaned_text = re.sub(pattern, '', text)
        return self.clean_text(cleaned_text)
    
    def _merge_interview_memo_data(
        self, 
        results: List[Dict[str, str]], 
        interviews_and_memos: Dict[str, Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """
        成績データにインタビューとメモを統合する
        
        Args:
            results: 成績データのリスト
            interviews_and_memos: インタビューとメモのデータ
            
        Returns:
            List[Dict[str, str]]: 統合された成績データ
        """
        for result in results:
            horse_name = result.get("馬名", "")
            if horse_name in interviews_and_memos:
                result["interview"] = interviews_and_memos[horse_name].get("interview", "")
                result["memo"] = interviews_and_memos[horse_name].get("memo", "")
            else:
                result["interview"] = ""
                result["memo"] = ""
        
        return results
    
    def validate_data(self, data: Dict[str, Any]) -> bool:
        """
        抽出されたデータを検証する
        
        Args:
            data: 検証対象のデータ
            
        Returns:
            bool: データが有効な場合True
        """
        # 基本構造の確認
        if not isinstance(data, dict):
            self.logger.error("データがdict型ではありません")
            return False
        
        if "race_info" not in data or "results" not in data:
            self.logger.error("必要なキー（race_info, results）が不足しています")
            return False
        
        # レース情報の確認
        race_info = data["race_info"]
        if not isinstance(race_info, dict) or not race_info.get("race_name"):
            self.logger.error("レース情報が不正です")
            return False
        
        # 成績データの確認
        results = data["results"]
        if not isinstance(results, list) or len(results) == 0:
            self.logger.error("成績データが空または不正です")
            return False
        
        # 各成績データの確認
        required_fields = ["着順", "馬名"]
        for i, result in enumerate(results):
            if not isinstance(result, dict):
                self.logger.error(f"成績データ{i}がdict型ではありません")
                return False
            
            for field in required_fields:
                if field not in result or not result[field]:
                    self.logger.warning(f"成績データ{i}に必要なフィールド'{field}'がありません")
            
            # 騎手フィールドの存在確認（騎手または騎手_2などでもOK）
            has_jockey = any(key for key in result.keys() if key.startswith("騎手"))
            if not has_jockey:
                self.logger.warning(f"成績データ{i}に騎手フィールドがありません")
        
        return True

    def _extract_payout_info(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """配当情報を抽出（寛容に複数パターンへ対応）"""
        payout = {
            "win": None,
            "place": [],
            "quinella": None,
            "exacta": None,
            "wide": [],
            "trio": None,
            "trifecta": None
        }
        try:
            # 配当テーブル候補を総当り
            tables = soup.find_all('table')
            for table in tables:
                text = table.get_text()
                if any(k in text for k in ["単勝", "複勝", "馬連", "馬単", "ワイド", "3連複", "3連単", "三連複", "三連単"]):
                    for row in table.find_all('tr'):
                        cells = [self.extract_text_safely(td) for td in row.find_all(['th', 'td'])]
                        if len(cells) < 2:
                            continue
                        label = cells[0]
                        amount = cells[1]
                        if "単勝" in label and payout["win"] is None:
                            payout["win"] = self._parse_amount(amount)
                        elif "複勝" in label:
                            amt = self._parse_amount(amount)
                            if amt is not None:
                                payout["place"].append(amt)
                        elif "馬連" in label and payout["quinella"] is None:
                            payout["quinella"] = self._parse_amount(amount)
                        elif "馬単" in label and payout["exacta"] is None:
                            payout["exacta"] = self._parse_amount(amount)
                        elif "ワイド" in label:
                            amt = self._parse_amount(amount)
                            if amt is not None:
                                payout["wide"].append(amt)
                        elif ("3連複" in label or "三連複" in label) and payout["trio"] is None:
                            payout["trio"] = self._parse_amount(amount)
                        elif ("3連単" in label or "三連単" in label) and payout["trifecta"] is None:
                            payout["trifecta"] = self._parse_amount(amount)
        except Exception:
            pass
        return payout

    def _parse_amount(self, amount_str: str) -> int:
        """金額文字列を数値に変換（"1,234円" -> 1234）"""
        try:
            s = (amount_str or "").replace(',', '').replace('円', '').strip()
            # 数字抽出
            import re
            m = re.findall(r"\d+", s)
            if not m:
                return None
            return int(m[0])
        except Exception:
            return None

    def _extract_race_details(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """距離/馬場/天候/発走時刻/グレード/賞金などを抽出（見つかった範囲で）"""
        details: Dict[str, Any] = {
            "distance": None,
            "track_type": None,
            "track_condition": None,
            "weather": None,
            "start_time": None,
            "grade": None,
            "prize_money": []
        }
        try:
            # タイトル周辺や見出しを探索
            header_candidates = soup.find_all(['div', 'section', 'p', 'span'])
            import re
            for h in header_candidates:
                t = self.extract_text_safely(h)
                if not t:
                    continue
                if ('芝' in t or 'ダート' in t) and 'm' in t:
                    m = re.search(r'(芝|ダート)\s*(\d+)m', t)
                    if m:
                        details['track_type'] = m.group(1)
                        details['distance'] = int(m.group(2))
                if any(k in t for k in ['良', '稍重', '重', '不良']):
                    # 例: 馬場: 良
                    details['track_condition'] = details.get('track_condition') or next((k for k in ['良','稍重','重','不良'] if k in t), None)
                if '天候' in t or '晴' in t or '雨' in t or '曇' in t:
                    details['weather'] = details.get('weather') or next((k for k in ['晴','雨','曇','小雨','雪'] if k in t), None)
                if '発走' in t or ':' in t:
                    m = re.search(r'(\d{1,2}:\d{2})', t)
                    if m:
                        details['start_time'] = m.group(1)
                if 'G1' in t or 'G2' in t or 'G3' in t or 'GI' in t or 'GII' in t or 'GIII' in t or 'OP' in t:
                    details['grade'] = details.get('grade') or next((k for k in ['G1','G2','G3','OP','GI','GII','GIII'] if k in t), None)
                if '賞金' in t or '本賞金' in t:
                    money = re.findall(r"[\d,]+万?円", t)
                    if money:
                        details['prize_money'] = money
        except Exception:
            pass
        return details

    def _extract_laps(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """ラップタイム/1000m/簡易ペース判定（取得できた範囲のみ）"""
        laps: Dict[str, Any] = {
            "lap_times": [],
            "first_1000m": None,
            "pace": None
        }
        try:
            # ラップらしきテキストを探索
            import re
            text = soup.get_text(" ")
            # 200m刻みなどのラップ配列を抽出（簡易）
            candidates = re.findall(r"(\d{2}\.\d)", text)
            if candidates and len(candidates) >= 4:
                laps['lap_times'] = candidates[:20]
            m1000 = re.search(r"1000m[:：]?\s*(\d{2}\.\d)", text)
            if m1000:
                laps['first_1000m'] = m1000.group(1)
            # 簡易ペース判定（前半と後半の平均比較）
            def to_float(v: str) -> float:
                try:
                    return float(v)
                except Exception:
                    return 0.0
            if laps['lap_times']:
                half = len(laps['lap_times']) // 2 or 1
                first_avg = sum(to_float(x) for x in laps['lap_times'][:half]) / half
                second_avg = sum(to_float(x) for x in laps['lap_times'][half:]) / max(len(laps['lap_times'][half:]), 1)
                # 前半が速ければH、同等ならM、遅ければS（簡易）
                if first_avg + 0.2 < second_avg:
                    laps['pace'] = 'H'
                elif abs(first_avg - second_avg) <= 0.2:
                    laps['pace'] = 'M'
                else:
                    laps['pace'] = 'S'
        except Exception:
            pass
        return laps