#!/usr/bin/env python3
import json
import os
import random
import re
import subprocess
import sys
import termios
import tty
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
    data, phrases = {}, []

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
                        # 歷史高頻詞排在前面
                        sorted_words = sorted(
                            words, key=lambda w: history.get(w, 0), reverse=True
                        )
                        phrases.extend(words)
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

    return data, list(set(phrases)), history


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


def get_key():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            ch += sys.stdin.read(2)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch


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


# ================= 快捷模式邏輯 =================


def quick_convert(dict_data, args, history):
    should_open = "-o" in args
    a_match = next(
        (re.match(r"^-a(\d*)$", a) for a in args if a.startswith("-a")), None
    )
    r_match = next(
        (re.match(r"^-r(\d*)$", a) for a in args if a.startswith("-r")), None
    )
    clean_args = [a for a in args if not a.startswith("-")]
    query = "".join(clean_args).lower()

    if not query:
        return "用法: ime [拼音] [-aN] [-rN] [-o]"

    # 列表模式
    if a_match:
        cands = dict_data.get(query, [])
        if not cands:
            return f"未找到: {query}"
        limit = int(a_match.group(1)) if a_match.group(1) else None
        return "\n".join(cands[:limit])

    # 正常或隨機模式
    count = int(r_match.group(1)) if (r_match and r_match.group(1)) else 1
    results = []
    for _ in range(count):
        tokens = re.findall(r"([a-z']+)([0-9]*)", query)
        current_res = ""
        for py_part, num_str in tokens if tokens else [(query, "")]:
            if py_part in dict_data:
                cands = dict_data[py_part]
                if r_match:
                    current_res += random.choice(cands)
                else:
                    idx = int(num_str) - 1 if num_str else 0
                    current_res += cands[idx] if 0 <= idx < len(cands) else cands[0]
            else:
                for sp in split_pinyin(dict_data, py_part):
                    if sp in dict_data:
                        current_res += (
                            random.choice(dict_data[sp])
                            if r_match
                            else dict_data[sp][0]
                        )
                    else:
                        current_res += sp
        results.append(current_res)

    final_text = " ".join(results)
    copy_to_clipboard(final_text)
    learn_from_text(final_text, history)  # 快捷模式也進行學習
    if should_open:
        webbrowser.open(f"https://www.google.com/search?q={final_text}")
    return final_text


# ================= 交互模式 =================


def interactive_mode(data, phrases, history):
    buffer, committed, full_history = "", "", ""
    page_index, PAGE_SIZE = 0, 9

    print("\033[1;34m--- Terminal IME v8.1 (全功能修復版) ---\033[0m")

    try:
        while True:
            ghost_text, current_first_cand = "", ""
            if buffer:
                all_cands = data.get(buffer, [])
                if not all_cands:
                    segments = split_pinyin(data, buffer)
                    current_first_cand = "".join(
                        [data[s][0] if s in data else s for s in segments]
                    )
                else:
                    current_first_cand = all_cands[0]

                matches = [
                    p
                    for p in phrases
                    if p.startswith(current_first_cand)
                    and len(p) > len(current_first_cand)
                ]
                if matches:
                    best_match = max(
                        matches, key=lambda x: (history.get(x, 0), -len(x))
                    )
                    ghost_text = best_match[len(current_first_cand) :]

            sys.stdout.write(
                f"\r\033[K\033[32m已輸入:\033[0m {full_history}{committed}"
            )
            if buffer:
                sys.stdout.write(
                    f"\033[33m{current_first_cand}\033[0m\033[90m{ghost_text}\033[0m \033[2m({buffer})\033[0m"
                )

            candidates = []
            if buffer:
                all_cands = data.get(
                    buffer, [current_first_cand] if current_first_cand else []
                )
                total_pages = (len(all_cands) - 1) // PAGE_SIZE + 1
                page_index = max(0, min(page_index, total_pages - 1))
                candidates = all_cands[
                    page_index * PAGE_SIZE : (page_index + 1) * PAGE_SIZE
                ]
                if candidates:
                    cand_str = "  ".join(
                        [f"{i + 1}.{c}" for i, c in enumerate(candidates)]
                    )
                    sys.stdout.write(
                        f"\n\033[K\033[36m候選({page_index + 1}/{total_pages}):\033[0m {cand_str}\033[F"
                    )
            else:
                sys.stdout.write(f"\n\033[K\033[F")
            sys.stdout.flush()

            key = get_key()

            if (key == "\t" or key == "\x1b[C") and (ghost_text or buffer):
                committed += current_first_cand + ghost_text
                buffer = ""
                continue

            if key in ("\x04", "\x03"):
                break

            elif key in ("\x7f", "\x08"):
                if buffer:
                    buffer = buffer[:-1]
                elif committed:
                    committed = committed[:-1]

            elif key in ("=", "."):
                if buffer:
                    page_index += 1
                else:
                    committed += "。" if key == "." else "="
            elif key in ("-", ","):
                if buffer:
                    page_index = max(0, page_index - 1)
                else:
                    committed += "，" if key == "," else "-"

            elif key.isdigit() and buffer:
                idx = int(key) - 1
                if 0 <= idx < len(candidates):
                    committed += candidates[idx]
                    buffer = ""
                    page_index = 0

            elif (key.isalpha() or key == "'") and len(key) == 1:
                buffer += key.lower()
                page_index = 0

            elif key == " ":
                if buffer and candidates:
                    committed += candidates[0]
                    buffer = ""
                    page_index = 0
                else:
                    committed += " "

            elif key in ("\r", "\n"):
                if buffer:
                    committed += buffer
                    buffer = ""
                elif committed:
                    full_history += committed + "\n"
                    committed = ""
                    sys.stdout.write("\n")
    finally:
        final_output = full_history + committed
        learn_from_text(final_output, history)
        copy_to_clipboard(final_output)
        print(f"\n[OK] 內容已複製並學習成功。")


# ================= 入口 =================

if __name__ == "__main__":
    data, phrases, history = load_all_dicts()
    if len(sys.argv) > 1:
        # 修復：重新啟用快速轉換模式入口
        print(quick_convert(data, sys.argv[1:], history))
    else:
        interactive_mode(data, phrases, history)
