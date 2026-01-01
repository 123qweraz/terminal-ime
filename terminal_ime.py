#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
import termios
import tty
import webbrowser

# ================= 核心工具函数 =================


def load_dict():
    """仅加载核心 dict.json"""
    base_path = os.path.dirname(os.path.realpath(__file__))
    dict_path = os.path.join(base_path, "dict.json")
    try:
        with open(dict_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"\n[错误] 找不到核心词库: {dict_path}")
        sys.exit(1)


def copy_to_clipboard(text):
    """写入剪贴板"""
    if not text:
        return False
    try:
        process = subprocess.Popen(
            ["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE
        )
        process.communicate(input=text.encode("utf-8"))
        return True
    except Exception:
        return False


def get_key():
    """监听键盘"""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            ch += sys.stdin.read(2)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch


# ================= 拼音切分逻辑 =================


def split_pinyin(dict_data, text):
    """将 nihao 拆为 ni, hao"""
    res = []
    idx = 0
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


# ================= 命令行模式 (矩阵展示 & 精准选词) =================


def quick_convert(dict_data, args):
    PAGE_SIZE = 9
    should_open = "-o" in args
    list_all = "-a" in args
    page_arg = next((a for a in args if re.match(r"^-[1-9]\d*$", a)), None)

    clean_args = [a for a in args if a not in ("-o", "-a") and a != page_arg]
    query = "".join(clean_args).lower()

    # 1. 列表模式 (-a 或 -页码)
    if list_all or page_arg:
        cands = dict_data.get(query, [])
        if not cands:
            return f"未找到拼音 '{query}'"

        if list_all:
            display_cands = cands
            title = f"全部候选 ({query})"
        else:
            page_num = int(page_arg[1:]) - 1
            start = page_num * PAGE_SIZE
            display_cands = cands[start : start + PAGE_SIZE]
            title = f"第 {page_num + 1} 页 ({query})"

        # 矩阵对齐输出
        col_width = 10
        formatted = ""
        for i, word in enumerate(display_cands):
            # 计算在整个词库中的索引
            base_idx = 0 if list_all else (int(page_arg[1:]) - 1) * PAGE_SIZE
            idx_label = f"{i + base_idx + 1}.{word}"

            # 计算字符显示宽度以实现完美对齐
            display_len = sum(2 if ord(c) > 127 else 1 for c in idx_label)
            formatted += idx_label + " " * (col_width - display_len)

            if (i + 1) % 10 == 0:
                formatted += "\n"

        return f"\033[36m{title}:\033[0m\n{formatted}"

    # 2. 精准选词模式 (例如: yi66)
    tokens = re.findall(r"([a-z]+)([0-9]*)", query)
    final_res = ""

    for py_part, num_str in tokens:
        if py_part in dict_data:
            cands = dict_data[py_part]
            idx = int(num_str) - 1 if num_str else 0
            final_res += cands[idx] if 0 <= idx < len(cands) else cands[0]
        else:
            sub_pys = split_pinyin(dict_data, py_part)
            for sp in sub_pys:
                final_res += dict_data[sp][0] if sp in dict_data else sp

    copy_to_clipboard(final_res)

    if should_open:
        webbrowser.open(f"https://www.google.com/search?q={final_res}")
        return f"已搜索: {final_res}"

    return final_res


# ================= 交互式模式 =================


def interactive_mode(dict_data):
    buffer, committed, full_history = "", "", ""
    page_index, PAGE_SIZE = 0, 9
    print("\033[1;34m--- Terminal IME v3.2 (Core 3500) ---\033[0m")
    try:
        while True:
            sys.stdout.write(
                f"\r\033[K\033[32m已输入:\033[0m {full_history}{committed}\033[33m{buffer}\033[0m"
            )
            candidates = []
            if buffer:
                all_cands = dict_data.get(buffer, [])
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
                        f"\n\033[K\033[36m候选({page_index + 1}/{total_pages}):\033[0m {cand_str}\033[F"
                    )
            else:
                sys.stdout.write(f"\n\033[K\033[F")
            sys.stdout.flush()

            key = get_key()
            if key in ("\x04", "\x03"):  # Ctrl+D / Ctrl+C
                res = full_history + committed
                copy_to_clipboard(res)
                print(f"\n\n[OK] 已复制。")
                break
            elif key in ("\x7f", "\x08"):  # Backspace
                if buffer:
                    buffer = buffer[:-1]
                elif committed:
                    committed = committed[:-1]
                elif full_history:
                    full_history = full_history[:-1]
            elif key == "=" and buffer:
                page_index += 1
            elif key == "-" and buffer:
                if page_index > 0:
                    page_index -= 1
            elif key.isdigit() and buffer:
                idx = int(key) - 1
                if 0 <= idx < len(candidates):
                    committed += candidates[idx]
                    buffer = ""
                    page_index = 0
            elif key.isalpha() and len(key) == 1:
                if key.islower():
                    buffer += key
                else:
                    if buffer:
                        committed += buffer
                        buffer = ""
                    committed += key
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
                else:
                    full_history += committed + "\n"
                    committed = ""
                    sys.stdout.write("\n")
            else:
                if len(key) == 1:
                    if buffer:
                        committed += buffer
                        buffer = ""
                    committed += key
    except Exception:
        pass


if __name__ == "__main__":
    data = load_dict()
    if len(sys.argv) > 1:
        print(quick_convert(data, sys.argv[1:]))
    else:
        interactive_mode(data)
