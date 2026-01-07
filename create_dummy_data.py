import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

# Setup directories
stock_dir = Path("data/raw/japan_all_stock")
index_dir = Path("data/raw/tosho_index")
stock_dir.mkdir(parents=True, exist_ok=True)
index_dir.mkdir(parents=True, exist_ok=True)

# Parameters
days = 25
industries = ["水産・農林業", "食料品", "建設業", "鉄鋼", "電気機器"]
market_caps = [5000, 50000, 500000, 2000000] # Small, Mid, Large, Super

start_date = datetime.now() - timedelta(days=days)

for i in range(days):
    curr_date = start_date + timedelta(days=i)
    date_str = curr_date.strftime("%Y%m%d")
    date_slash = curr_date.strftime("%Y/%m/%d")

    # Generate Stock Data
    stock_data = []
    for ind in industries:
        for cap in market_caps:
            # Create a few stocks per industry/cap
            for s in range(3):
                stock_data.append({
                    "日付": date_slash,
                    "コード": f"{1000+s}",
                    "銘柄名": f"Stock-{ind}-{cap}-{s}",
                    "業種": ind,
                    "時価総額（百万円）": cap * (1 + np.random.uniform(-0.1, 0.1)),
                    "前日比": np.random.uniform(-100, 100),
                    "前日比（％）": np.random.uniform(-5, 5),
                    "売買代金（千円）": np.random.uniform(100000, 10000000),
                    "市場": "Prime",
                    "終値": 1000,
                    "始値": 1000,
                    "高値": 1010,
                    "安値": 990,
                    "出来高": 10000
                })
    # Add Index dummy (should be filtered out)
    stock_data.append({
        "日付": date_slash, "コード": "0000", "銘柄名": "TOPIX", "業種": "株価指数",
        "時価総額（百万円）": 0, "前日比": 0, "前日比（％）": 0, "売買代金（千円）": 0
    })

    df_stock = pd.DataFrame(stock_data)
    df_stock.to_csv(stock_dir / f"japan-all-stock-prices_{date_str}.csv", index=False, encoding="cp932")

    # Generate Index Data
    index_data = []
    for ind in industries:
        index_data.append({
            "日付": date_slash,
            "指数名": ind,
            "前日比（％）": np.random.uniform(-2, 2)
        })
    df_index = pd.DataFrame(index_data)
    df_index.to_csv(index_dir / f"tosho-index-data_{date_str}.csv", index=False, encoding="cp932")

print(f"Generated {days} days of dummy data.")
