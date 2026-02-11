#!/usr/bin/env python3
"""
修正した出馬表パーサーをテストするスクリプト
"""

from ..parsers.syutuba_parser import SyutubaParser
import json

def main():
    # 先ほど保存したHTMLファイルを使用
    html_file = 'debug_html/syutuba_202503040101.html'
    
    print(f"🔍 出馬表パーサーテスト開始")
    print(f"📁 HTMLファイル: {html_file}")
    
    # パーサーを初期化
    parser = SyutubaParser(debug=True)
    
    # HTMLファイルをパース
    try:
        result = parser.parse(html_file)
        
        print(f"\n✅ パース成功!")
        print(f"📊 出走馬数: {result.get('horse_count', 0)}")
        
        # レース情報を表示
        race_info = result.get('race_info', {})
        print(f"\n📋 レース情報:")
        for key, value in race_info.items():
            print(f"   {key}: {value}")
        
        # 出走馬情報を表示
        horses = result.get('horses', [])
        print(f"\n🐎 出走馬情報 (最初の5頭):")
        
        for i, horse in enumerate(horses[:5]):
            print(f"\n   [{i+1}] 馬番: {horse.get('馬番', 'N/A')}")
            print(f"       umacd: {horse.get('umacd', 'N/A')}")
            print(f"       馬名: {horse.get('馬名_clean', horse.get('馬名', 'N/A'))}")
            print(f"       性齢: {horse.get('性齢', 'N/A')}")
            print(f"       騎手: {horse.get('騎手', 'N/A')}")
            print(f"       重量: {horse.get('重量', 'N/A')}")
            print(f"       厩舎: {horse.get('厩舎', 'N/A')}")
            print(f"       人気: {horse.get('人気', 'N/A')}")
            print(f"       着順: {horse.get('着順', 'N/A')}")
        
        # umacdの統計
        umacd_count = sum(1 for horse in horses if horse.get('umacd'))
        print(f"\n📊 umacd統計:")
        print(f"   umacd有り: {umacd_count}頭")
        print(f"   umacd無し: {len(horses) - umacd_count}頭")
        
        # 全umacdリスト
        umacds = [horse.get('umacd') for horse in horses if horse.get('umacd')]
        print(f"\n🔢 全umacdリスト:")
        print(f"   {', '.join(umacds)}")
        
        # データ検証
        is_valid = parser.validate_data(result)
        print(f"\n✅ データ検証: {'OK' if is_valid else 'NG'}")
        
        # JSONファイルに保存
        output_file = 'debug_html/syutuba_202503040101_parsed.json'
        parser.save_json(result, output_file)
        print(f"💾 JSONファイル保存: {output_file}")
        
    except Exception as e:
        print(f"❌ パースエラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main() 