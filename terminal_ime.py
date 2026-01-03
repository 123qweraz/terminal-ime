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
            # 優先匹配原始大小寫，失敗則匹配小寫
            if part in dict_data or part.lower() in dict_data:
                res.append(part)
                idx += length
                matched = True
                break
        if not matched:
            res.append(text[idx])
            idx += 1
    return res


def split_input_segments(input_str):
    # 修改正則以包含大寫字母 A-Z
    pattern = r"(/[a-zA-Z0-9]+)|([a-zA-Z0-9']+)|([^a-zA-Z0-9'/]+)"
    matches = re.findall(pattern, input_str)
    segments = []
    for raw_part, pinyin_part, punct_part in matches:
        if raw_part:
            segments.append(("raw", raw_part))
        elif pinyin_part:
            segments.append(("pinyin", pinyin_part))
        elif punct_part:
            segments.append(("punct", punct_part))
    return segments


# ================= 顏色定義 =================
BLUE = "\033[94m"
GREEN = "\033[92m"
GRAY = "\033[90m"
RESET = "\033[0m"


# ================= 轉換邏輯 =================
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
    query_raw = " ".join(clean_args)

    if not query_raw:
        return "用法: ime [拼音] [/英文] [-l] [-a] [-r] [-o]"

    # 列表模式
    if a_match or l_match:
        # 這裡過濾保留大小寫以便搜尋詞庫
        pure_pinyin = re.sub(r"[^a-zA-Z0-9']", "", query_raw)
        cands = dict_data.get(pure_pinyin)

        # 找不到則嘗試小寫搜尋
        if not cands:
            cands = dict_data.get(pure_pinyin.lower(), [])

        if not cands:
            print(f"未找到對應詞條: {pure_pinyin}")
            return f"未找到對應詞條: {pure_pinyin}"

        if a_match:
            limit = int(a_match.group(1)) if a_match.group(1) else 60
            listed = cands[:limit]
            lines = []
            for i in range(0, len(listed), 10):
                chunk = listed[i : i + 10]
                line_parts = [
                    f"  {BLUE}{i + j + 1:02d}{GRAY}.{RESET} {GREEN}{word}{RESET}"
                    for j, word in enumerate(chunk)
                ]
                lines.append("  ".join(line_parts))
            result = "\n".join(lines)
        else:
            limit = int(l_match.group(1)) if l_match.group(1) else 10
            listed = cands[:limit]
            result = "\n".join(
                [
                    f"  {BLUE}{i + 1:02d}{GRAY}.{RESET} {GREEN}{word}{RESET}"
                    for i, word in enumerate(listed)
                ]
            )

        print(result)
        return result

    # 正常轉換模式
    count = int(r_match.group(1)) if (r_match and r_match.group(1)) else 1
    total_variants = []

    for _ in range(count):
        space_blocks = query_raw.split(" ")
        converted_blocks = []

        for block in space_blocks:
            if not block:
                continue

            segments = split_input_segments(block)
            block_res = ""

            for seg_type, seg_content in segments:
                if seg_type == "raw":
                    block_res += seg_content[1:]
                    continue

                if seg_type == "punct":
                    block_res += seg_content
                    continue

                # 修改正則以包含大寫
                tokens = re.findall(r"([a-zA-Z']+)([0-9]*)", seg_content)
                if not tokens:
                    block_res += seg_content
                    continue

                for py_part, num_str in tokens:
                    # 搜尋邏輯：優先原始，次之小寫
                    cands = dict_data.get(py_part)
                    if not cands:
                        cands = dict_data.get(py_part.lower())

                    if cands:
                        if r_match:
                            chosen = random.choice(cands)
                        else:
                            idx = int(num_str) - 1 if num_str else 0
                            chosen = cands[idx] if 0 <= idx < len(cands) else cands[0]
                        block_res += chosen
                    else:
                        # 分詞搜尋也支持大小寫
                        for sp in split_pinyin(dict_data, py_part):
                            sub_cands = dict_data.get(sp)
                            if not sub_cands:
                                sub_cands = dict_data.get(sp.lower())

                            if sub_cands:
                                chosen = (
                                    random.choice(sub_cands)
                                    if r_match
                                    else sub_cands[0]
                                )
                                block_res += chosen
                            else:
                                block_res += sp
            converted_blocks.append(block_res)

        total_variants.append("".join(converted_blocks))

    final_text = "\n".join(total_variants)
    copy_to_clipboard(final_text)
    learn_from_text(final_text, history)

    if should_open:
        webbrowser.open(f"https://www.google.com/search?q={final_text}")

    print(final_text)
    return final_text


if __name__ == "__main__":
    data, history = load_all_dicts()
    if len(sys.argv) > 1:
        quick_convert(data, sys.argv[1:], history)
    else:
        print(quick_convert(data, [], history))
