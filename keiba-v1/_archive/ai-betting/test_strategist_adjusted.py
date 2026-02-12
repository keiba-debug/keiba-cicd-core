"""
シカマル（STRATEGIST）調整テスト

より保守的なパラメータでテスト
"""

import sys
from pathlib import Path

# strategist.py をインポート
sys.path.insert(0, str(Path(__file__).parent))
from strategist import BettingStrategist


def test_adjusted():
    """
    Quarter Kelly + より緩いリスク設定でテスト
    """
    print("=" * 60)
    print("シカマル（STRATEGIST）調整テスト - Quarter Kelly")
    print("=" * 60)
    print()

    # より保守的な設定
    strategist = BettingStrategist(
        bankroll=100000,
        min_ev_threshold=1.10,
        kelly_fraction=0.25,          # Quarter Kelly（より保守的）
        max_loss_per_race_rate=0.05   # 1レース最大5%まで
    )

    print(f"総資金: {strategist.bankroll:,}円")
    print(f"期待値閾値: {strategist.min_ev_threshold:.0%}")
    print(f"Kelly係数: {strategist.kelly_fraction:.0%} (Quarter Kelly)")
    print(f"1レース最大損失: {strategist.risk_manager.max_loss_per_race:,}円")
    print()

    # エバちゃんからの期待値計算結果
    race_evaluations = [
        {
            'race_id': '2026020101010101',
            'horse_name': 'ドウデュース',
            'prob': 0.30,
            'odds': 5.0,
            'expected_value': 50.0,
            'expected_value_rate': 1.50,
            'bet_type': 'win'
        },
        {
            'race_id': '2026020101010102',
            'horse_name': 'イクイノックス',
            'prob': 0.25,
            'odds': 6.0,
            'expected_value': 50.0,
            'expected_value_rate': 1.50,
            'bet_type': 'win'
        },
        {
            'race_id': '2026020101010103',
            'horse_name': 'リバティアイランド',
            'prob': 0.20,
            'odds': 4.5,
            'expected_value': -10.0,
            'expected_value_rate': 0.90,  # 期待値不足
            'bet_type': 'win'
        },
        {
            'race_id': '2026020101010104',
            'horse_name': 'ソングライン',
            'prob': 0.35,
            'odds': 4.0,
            'expected_value': 40.0,
            'expected_value_rate': 1.40,
            'bet_type': 'win'
        },
        {
            'race_id': '2026020101010105',
            'horse_name': 'ジャスティンパレス',
            'prob': 0.28,
            'odds': 4.5,
            'expected_value': 26.0,
            'expected_value_rate': 1.26,
            'bet_type': 'win'
        }
    ]

    # 購入推奨リスト生成
    print("=" * 60)
    print("購入推奨リスト（期待値率順）")
    print("=" * 60)
    print()

    recommendations = strategist.generate_purchase_list(race_evaluations)

    for i, rec in enumerate(recommendations, 1):
        print(f"[{i}] {rec.horse_name}")
        print(f"    推奨: {'YES' if rec.should_bet else 'NO'}")
        print(f"    賭け金: {rec.bet_amount:,}円")
        print(f"    期待値率: {rec.expected_value_rate:.1%}")
        print(f"    Kelly: {rec.kelly_fraction:.2%}")
        print(f"    リスク: {rec.risk_level}")
        print(f"    理由: {rec.reason}")
        print()

    # 推奨リストのみ抽出
    buy_list = [rec for rec in recommendations if rec.should_bet]

    print("=" * 60)
    print(f"購入推奨: {len(buy_list)}件")
    print("=" * 60)
    print()

    if buy_list:
        total_bet = sum(rec.bet_amount for rec in buy_list)
        print(f"合計賭け金: {total_bet:,}円 ({total_bet/strategist.bankroll:.1%})")
        print()

        print("【購入指示書】")
        for rec in buy_list:
            print(f"  - {rec.horse_name}: {rec.bet_type.upper()} {rec.bet_amount:,}円")
        print()
    else:
        print("今回は見送りだ。")
        print()

    # 状態確認
    status = strategist.get_status()
    print("=" * 60)
    print("シカマルの状態")
    print("=" * 60)
    print(f"総資金: {status['bankroll']:,}円")
    print(f"今日の損失: {status['daily_loss']:,}円")
    print(f"連敗数: {status['consecutive_losses']}回")
    print()

    print("シカマル: 「めんどくせぇけど、戦略的にはこうだ」")
    print("シカマル: 「Quarter Kellyで慎重に行く。リスクを抑えつつ期待値を取る」")


if __name__ == '__main__':
    test_adjusted()
