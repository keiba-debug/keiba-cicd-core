# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

base_date = datetime(2025, 12, 28)
print(f"基準日: {base_date.strftime('%Y-%m-%d')} (weekday={base_date.weekday()})")

# 最終追い切り期間を計算
print("\n直近7日間:")
for i in range(7):
    d = base_date - timedelta(days=i)
    weekday = d.weekday()
    weekday_names = ["月", "火", "水", "木", "金", "土", "日"]
    is_wed_thu = "★水木" if weekday in [2, 3] else ""
    print(f"  {d.strftime('%Y-%m-%d')} ({weekday_names[weekday]}) {is_wed_thu}")

# 12/24と12/17がどの期間に属するか
print("\n12/24と12/17の確認:")
d1224 = datetime(2025, 12, 24)
d1217 = datetime(2025, 12, 17)
print(f"  12/24: weekday={d1224.weekday()} (水曜=2)")
print(f"  12/17: weekday={d1217.weekday()} (水曜=2)")
