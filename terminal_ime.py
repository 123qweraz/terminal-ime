#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import termios
import tty


def load_dict():
    base_path = os.path.dirname(os.path.realpath(__file__))
    dict_path = os.path.join(base_path, "dict.json")
    try:
        with open(dict_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"\n错误: 在 {dict_path} 未找到词库文件。")
        sys.exit(1)


def copy_to_clipboard(text):
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
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
        if ch == "\x1b":  # 处理可能的转义
            ch += sys.stdin.read(2)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch


def main():
    dict_data = load_dict()
    buffer, committed, full_history = "", "", ""
    page_index, PAGE_SIZE = 0, 9

    print("--- 终端打字机 v2.1 ---")
    print("操作: 小写字母拼音, 大写字母/符号直接输入, Ctrl+D 退出并复制")

    try:
        while True:
            # UI 渲染
            sys.stdout.write(
                f"\r\033[K\033[32m已输入:\033[0m {full_history}{committed}\033[33m{buffer}\033[0m"
            )

            candidates = []
            if buffer:
                all_cands = dict_data.get(buffer, [])  # 拼音匹配
                total_pages = (len(all_cands) - 1) // PAGE_SIZE + 1
                page_index = max(0, min(page_index, total_pages - 1))
                candidates = all_cands[
                    page_index * PAGE_SIZE : (page_index + 1) * PAGE_SIZE
                ]

                if candidates:
                    cand_str = " ".join(
                        [f"{i + 1}.{c}" for i, c in enumerate(candidates)]
                    )
                    sys.stdout.write(
                        f"\n\033[K\033[36m候选({page_index + 1}/{total_pages}):\033[0m {cand_str}\033[F"
                    )
            else:
                sys.stdout.write(f"\n\033[K\033[F")

            sys.stdout.flush()
            key = get_key()

            # 1. 退出 (Ctrl+D / Ctrl+C)
            if key in ("\x04", "\x03"):
                res = full_history + committed
                copy_to_clipboard(res)
                print(f"\n\n[OK] 内容已复制。")
                break

            # 2. 退格
            elif key in ("\x7f", "\x08"):
                if buffer:
                    buffer = buffer[:-1]
                    page_index = 0
                elif committed:
                    committed = committed[:-1]
                elif full_history:
                    full_history = full_history[:-1]

            # 3. 翻页 (仅缓冲区有拼音时)
            elif key == "=" and buffer:
                page_index += 1
            elif key == "-" and buffer:
                if page_index > 0:
                    page_index -= 1

            # 4. 数字处理
            elif key.isdigit():
                if buffer and candidates:  # 选词
                    idx = int(key) - 1
                    if 0 <= idx < len(candidates):
                        committed += candidates[idx]
                        buffer = ""
                        page_index = 0
                else:  # 直接输入数字
                    committed += key

            # 5. 字母处理
            elif key.isalpha() and len(key) == 1:
                if key.islower():  # 小写字母进拼音缓冲区
                    buffer += key
                    page_index = 0
                else:  # 大写字母直接上屏
                    if buffer:  # 如果有拼音，先冲刷掉
                        committed += buffer
                        buffer = ""
                    committed += key

            # 6. 空格处理
            elif key == " ":
                if buffer and candidates:
                    committed += candidates[0]
                    buffer = ""
                    page_index = 0
                else:
                    committed += " "

            # 7. 回车处理
            elif key in ("\r", "\n"):
                if buffer:
                    committed += buffer
                    buffer = ""
                else:
                    full_history += committed + "\n"
                    committed = ""
                    sys.stdout.write("\n")

            # 8. 其他所有符号 (., / [ ]等)
            else:
                if len(key) == 1:
                    if buffer:
                        committed += buffer
                        buffer = ""
                    committed += key

    except Exception:
        pass


if __name__ == "__main__":
    main()
