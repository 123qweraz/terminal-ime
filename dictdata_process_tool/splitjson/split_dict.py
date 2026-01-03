#!/usr/bin/env python3
import json

INPUT_FILE = "dict_sorted.json"

OUT_LT5 = "dict_lt5.json"
OUT_5_10 = "dict_5_10.json"
OUT_GT10 = "dict_gt10.json"


def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    lt5 = {}
    mid = {}
    gt10 = {}

    for word, meanings in data.items():
        if not isinstance(word, str):
            continue
        if not word.isalpha():
            continue

        l = len(word)

        if l < 5:
            lt5[word] = meanings
        elif l <= 10:
            mid[word] = meanings
        else:
            gt10[word] = meanings

    # 按字母顺序排序
    lt5 = dict(sorted(lt5.items()))
    mid = dict(sorted(mid.items()))
    gt10 = dict(sorted(gt10.items()))

    with open(OUT_LT5, "w", encoding="utf-8") as f:
        json.dump(lt5, f, ensure_ascii=False, indent=2)

    with open(OUT_5_10, "w", encoding="utf-8") as f:
        json.dump(mid, f, ensure_ascii=False, indent=2)

    with open(OUT_GT10, "w", encoding="utf-8") as f:
        json.dump(gt10, f, ensure_ascii=False, indent=2)

    print("✔ 已生成：")
    print(f"  - {OUT_LT5}  (<5)")
    print(f"  - {OUT_5_10} (5-10)")
    print(f"  - {OUT_GT10} (>10)")


if __name__ == "__main__":
    main()
