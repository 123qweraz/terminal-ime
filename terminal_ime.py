#!/usr/bin/env python3
import json
import os
import random
import re
import subprocess
import sys
import webbrowser

# ================= 配置與路徑 =================
BASE_PATH = os.path.dirname(os.path.realpath(__file__))
USER_DICTS_DIR = os.path.join(BASE_PATH, "user_dicts")
HISTORY_FILE = os.path.join(USER_DICTS_DIR, "user_history.json")

if not os.path.exists(USER_DICTS_DIR):
    os.makedirs(USER_DICTS_DIR)


# ================= 核心工具函數 =================
def load_all_dicts():
    hanzi_path = os.path.join(BASE_PATH, "dict_hanzi.json")
    cizu_path = os.path.join(BASE_PATH, "dict_cizu.json")
    data = {}

    history = {}
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except:
            pass

    def merge_dict(path):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    new_data = json.load(f)
                    for py, words in new_data.items():
                        sorted_words = sorted(
                            words, key=lambda w: history.get(w, 0), reverse=True
                        )
                        if py in data:
                            data[py] = list(dict.fromkeys(sorted_words + data[py]))
                        else:
                            data[py] = sorted_words
            except:
                pass

    merge_dict(hanzi_path)
    merge_dict(cizu_path)

    if os.path.exists(USER_DICTS_DIR):
        for filename in os.listdir(USER_DICTS_DIR):
            if filename.endswith(".json") and filename != "user_history.json":
                merge_dict(os.path.join(USER_DICTS_DIR, filename))

    return data, history


def save_history(history):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except:
        pass


def learn_from_text(text, history):
    blocks = re.findall(r"[\u4e00-\u9fff]+", text)
    for b in blocks:
        if 1 < len(b) <= 6:
            history[b] = history.get(b, 0) + 1
    save_history(history)


def copy_to_clipboard(text):
    if not text:
        return False
    try:
        cmd = (
            ["pbcopy"]
            if sys.platform == "darwin"
            else ["xclip", "-selection", "clipboard"]
        )
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        process.communicate(input=text.encode("utf-8"))
        return True
    except:
        return False


def split_pinyin(dict_data, text):
    if not text:
        return []
    res, idx = [], 0
    while idx < len(text):
        matched = False
        for length in range(6, 0, -1):
            part = text[idx : idx + length]
            if part in dict_data:
                res.append(part)
                idx += length
                matched = True
                break
        if not matched:
            res.append(text[idx])
            idx += 1
    return res


# ================= 新增：拆分输入为「拼音段」和「标点/非拼音段」 =================
def split_input_segments(input_str):
    """
    拆分输入字符串，返回片段列表，每个片段是(类型, 内容)，类型为"pinyin"或"punct"
    拼音段：包含a-z、'、0-9（拼音和序号）
    标点段：中英文标点、其他非拼音字符（原样保留）
    """
    # 匹配拼音段（字母、单引号、数字）和非拼音段（其他所有字符）
    pattern = r"([a-z0-9']+)|([^a-z0-9']+)"
    matches = re.findall(pattern, input_str.lower())
    segments = []
    for pinyin_part, punct_part in matches:
        if pinyin_part:
            segments.append(("pinyin", pinyin_part))
        elif punct_part:
            segments.append(("punct", punct_part))
    return segments


# ================= 顏色定義 =================
BLUE = "\033[94m"  # 數字：亮藍
GREEN = "\033[92m"  # 漢字：亮綠
GRAY = "\033[90m"  # 點號
RESET = "\033[0m"


# ================= 快捷模式（美化版，已修改标点处理逻辑） =================
def quick_convert(dict_data, args, history):
    should_open = "-o" in args

    l_match = next(
        (re.match(r"^-l(\d*)$", a) for a in args if a.startswith("-l")), None
    )
    a_match = next(
        (re.match(r"^-a(\d*)$", a) for a in args if a.startswith("-a")), None
    )
    r_match = next(
        (re.match(r"^-r(\d*)$", a) for a in args if a.startswith("-r")), None
    )

    clean_args = [
        a
        for a in args
        if not (
            a.startswith("-l") or a.startswith("-a") or a.startswith("-r") or a == "-o"
        )
    ]
    query = "".join(clean_args)  # 不再直接转小写，拆分片段时统一处理

    if not query:
        return (
            "用法: ime [拼音+标点] [-l[N]] [-a[N]] [-r[N]] [-o]\n"
            "例子:\n"
            "  ime nihao,wohao         → 輸出「你好,我好」\n"
            "  ime nihao5!             → 輸出第5個+！\n"
            "  ime -l nihao,           → 垂直列表（彩色）\n"
            "  ime -a yi.              → 橫向每行10個（數字藍、漢字綠）\n"
            "  ime -a30 yi?            → 前30個橫向排列"
        )

    # 橫向排列模式：-a（主要用于纯拼音查询，兼容标点输入）
    if a_match:
        # 提取纯拼音部分进行查询（-a模式不保留标点的查询匹配）
        pure_pinyin = re.sub(r"[^a-z0-9']", "", query.lower())
        cands = dict_data.get(pure_pinyin, [])
        if not cands:
            return f"未找到對應詞條: {pure_pinyin}"
        limit = int(a_match.group(1)) if a_match.group(1) else 60
        listed = cands[:limit]

        lines = []
        for i in range(0, len(listed), 10):
            chunk = listed[i : i + 10]
            line_parts = []
            for j, word in enumerate(chunk):
                num = i + j + 1
                num_str = f"{num:02d}"
                colored = f"  {BLUE}{num_str}{GRAY}.{RESET} {GREEN}{word}{RESET}"
                line_parts.append(colored)
            lines.append("  ".join(line_parts))
        result = "\n".join(lines)
        print(result)
        return result

    # 垂直列表模式：-l（主要用于纯拼音查询，兼容标点输入）
    if l_match:
        # 提取纯拼音部分进行查询
        pure_pinyin = re.sub(r"[^a-z0-9']", "", query.lower())
        cands = dict_data.get(pure_pinyin, [])
        if not cands:
            return f"未找到對應詞條: {pure_pinyin}"
        limit = int(l_match.group(1)) if l_match.group(1) else 10
        listed = cands[:limit]

        lines = []
        for i, word in enumerate(listed):
            num_str = f"{i + 1:02d}"
            colored = f"  {BLUE}{num_str}{GRAY}.{RESET} {GREEN}{word}{RESET}"
            lines.append(colored)
        result = "\n".join(lines)
        print(result)
        return result

    # 正常轉換或隨機模式（核心修改：支持保留标点）
    count = int(r_match.group(1)) if (r_match and r_match.group(1)) else 1
    results = []

    for _ in range(count):
        # 拆分输入为「拼音段」和「标点段」
        segments = split_input_segments(query)
        current_res = ""

        for seg_type, seg_content in segments:
            # 标点段：直接原样追加
            if seg_type == "punct":
                current_res += seg_content
                continue

            # 拼音段：按原有逻辑处理转换
            tokens = re.findall(r"([a-z']+)([0-9]*)", seg_content)
            for py_part, num_str in tokens if tokens else [(seg_content, "")]:
                if py_part in dict_data:
                    cands = dict_data[py_part]
                    if r_match:
                        chosen = random.choice(cands)
                    else:
                        idx = int(num_str) - 1 if num_str else 0
                        chosen = cands[idx] if 0 <= idx < len(cands) else cands[0]
                    current_res += chosen
                else:
                    for sp in split_pinyin(dict_data, py_part):
                        if sp in dict_data:
                            sub_cands = dict_data[sp]
                            chosen = (
                                random.choice(sub_cands) if r_match else sub_cands[0]
                            )
                            current_res += chosen
                        else:
                            current_res += sp

        results.append(current_res)

    final_text = " ".join(results)
    copy_to_clipboard(final_text)
    learn_from_text(final_text, history)

    if should_open:
        webbrowser.open(f"https://www.google.com/search?q={final_text}")

    print(final_text)
    return final_text


# ================= 入口 =================
if __name__ == "__main__":
    data, history = load_all_dicts()
    if len(sys.argv) > 1:
        quick_convert(data, sys.argv[1:], history)
    else:
        print(quick_convert(data, [], history))
