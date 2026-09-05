main_rows = [
    {"sn": 12, "top": 325.134},
    {"sn": 13, "top": 365.134},
    {"sn": 14, "top": 412.13399999999996},
]

dates = [
    {"date": "2026-07-29", "top": 358.154},
    {"date": "2026-07-30", "top": 405.154},
]

for d in dates:
    closest = min(main_rows, key=lambda m: abs(m["top"] - d["top"]))
    print(f"Date at {d['top']} assigned to sn {closest['sn']}")
