import os
from pathlib import Path
import pandas as pd

def load_df(input_path: str) -> pd.DataFrame:
    p = Path(input_path)
    if not p.exists():
        raise FileNotFoundError(f"找不到輸入檔案: {p}")
    if p.suffix.lower() in [".xlsx", ".xls"]:
        return pd.read_excel(p, engine="openpyxl")
    else:
        return pd.read_csv(p, encoding="utf-8-sig")

def filter_recent_n(input_path: str, horse_list: list[str], n: int = 8, output_path: str = "outputs/horse_recent_8.csv"):
    df = load_df(input_path)

    if "賽事日期" not in df.columns:
        raise KeyError("輸入檔缺少欄位：賽事日期")
    if "馬名" not in df.columns:
        raise KeyError("輸入檔缺少欄位：馬名")

    df["賽事日期"] = pd.to_datetime(df["賽事日期"], errors="coerce")

    matched = []
    for h in horse_list:
        mask = df["馬名"].astype(str).str.contains(h, na=False)
        df_h = df.loc[mask].copy()
        if df_h.empty:
            print(f"⚠ 沒找到相關紀錄: {h}")
            continue
        df_h.sort_values(by="賽事日期", ascending=False, inplace=True)
        matched.append(df_h.head(n))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    if matched:
        res = pd.concat(matched, axis=0)
        res.to_csv(output_path, index=False, encoding="utf-8-sig")
        print(f"✅ 已輸出 {output_path}, 共 {len(res)} 筆資料")
    else:
        print("⚠ 沒找到任何匹配馬名資料")

if __name__ == "__main__":
    input_file = os.getenv("INPUT_FILE", "data/TOTAL_RACE.xlsx")
    horse_list_env = os.getenv("HORSE_LIST", "")
    n = int(os.getenv("N", "8"))
    output_file = os.getenv("OUTPUT_FILE", f"outputs/horse_recent_{n}.csv")

    if horse_list_env.strip():
        horses = [h.strip() for h in horse_list_env.split(",") if h.strip()]
    else:
        horses = [
            "加州動員","遨遊武士","電訊巴打","安遇","當年情",
            "太陽勇士","遙遙領先","銀進","瑪瑙","平凡騎士",
            "愛心神駒","木火兄弟",
        ]

    filter_recent_n(input_file, horses, n, output_file)
