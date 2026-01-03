#!/usr/bin/env python3
import json

INPUT_FILE = "dict_enlt5.json"  # 原 JSON 文件
OUTPUT_FILE = "dict_enlt5s.json"  # 排序后的输出文件


def main():
    # 读取 JSON
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 对 key 排序
    # 规则：先按长度排，长度相同按字母顺序
    sorted_items = sorted(data.items(), key=lambda x: (len(x[0]), x[0]))

    # 构建新的字典
    sorted_dict = dict(sorted_items)

    # 写入输出 JSON
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted_dict, f, ensure_ascii=False, indent=2)

    print(f"✔ 已生成 {OUTPUT_FILE}，共 {len(sorted_dict)} 个词条")


if __name__ == "__main__":
    main()
