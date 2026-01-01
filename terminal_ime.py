#!/usr/bin/env python3
import json
import os
import random
import re
import shutil
import subprocess
import sys
import termios
import tty
import webbrowser

# ================= 配置与路径 =================
BASE_PATH = os.path.dirname(os.path.realpath(__file__))
USER_DICTS_DIR = os.path.join(BASE_PATH, "user_dicts")

# 确保用户词典目录存在
if not os.path.exists(USER_DICTS_DIR):
    os.makedirs(USER_DICTS_DIR)

# ================= 核心工具函数 =================


def load_all_dicts():
    """加载核心词库并合并 user_dicts 目录下所有的自定义词典"""
    dict_path = os.path.join(BASE_PATH, "dict.json")
    data = {}

    # 1. 加载核心词库
    try:
        with open(dict_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"\n[错误] 找不到核心词库: {dict_path}")
        sys.exit(1)

    # 2. 遍历并合并 user_dicts 下的所有 .json 文件
    custom_loaded = []
    for filename in os.listdir(USER_DICTS_DIR):
        if filename.endswith(".json"):
            try:
                with open(
                    os.path.join(USER_DICTS_DIR, filename), "r", encoding="utf-8"
                ) as f:
                    user_data = json.load(f)
                    for py, words in user_data.items():
                        if py in data:
                            # 合并并去重，用户词条排在前面
                            new_list = []
                            for w in words:
                                if w not in new_list:
                                    new_list.append(w)
                            for w in data[py]:
                                if w not in new_list:
                                    new_list.append(w)
                            data[py] = new_list
                        else:
                            data[py] = words
                    custom_loaded.append(filename)
            except Exception as e:
                print(f"[警告] 无法加载词典 {filename}: {e}")

    # 如果是交互模式且有加载自定义词典，给予提示
    if custom_loaded and len(sys.argv) == 1:
        print(f"\033[32m[已加载自定义词典: {', '.join(custom_loaded)}]\033[0m")

    return data


def copy_to_clipboard(text):
    """写入剪贴板"""
    if not text:
        return False
    try:
        if sys.platform == "darwin":
            process = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
        else:
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


# ================= 词典管理逻辑 =================


def manage_dicts(args):
    """处理 --mv, --list, --rm 命令"""
    if "--mv" in args:
        try:
            idx = args.index("--mv")
            src = args[idx + 1]
            if not os.path.exists(src):
                print(f"错误: 找不到源文件 '{src}'")
                return
            target_name = (
                args[idx + 2] if len(args) > idx + 2 else os.path.basename(src)
            )
            if not target_name.endswith(".json"):
                target_name += ".json"

            shutil.copy(src, os.path.join(USER_DICTS_DIR, target_name))
            print(f"成功: 已导入词典 '{target_name}'")
        except (IndexError, shutil.SameFileError):
            print("用法: ime --mv [源JSON文件路径] [可选:重命名]")

    elif "--list" in args:
        dicts = [f for f in os.listdir(USER_DICTS_DIR) if f.endswith(".json")]
        print("\033[1;34m--- 已安装的自定义词典 ---\033[0m")
        if not dicts:
            print("  (暂无自定义词典)")
        for d in dicts:
            print(f"  • {d}")

    elif "--rm" in args:
        try:
            name = args[args.index("--rm") + 1]
            if not name.endswith(".json"):
                name += ".json"
            path = os.path.join(USER_DICTS_DIR, name)
            if os.path.exists(path):
                os.remove(path)
                print(f"成功: 已删除词典 '{name}'")
            else:
                print(f"错误: 找不到词典 '{name}'")
        except IndexError:
            print("用法: ime --rm [词典文件名]")


# ================= 拼音切分与转换 =================


def split_pinyin(dict_data, text):
    if not text:
        return []
    if "'" in text:
        res = []
        for part in text.split("'"):
            res.extend(split_pinyin(dict_data, part))
        return res
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


def quick_convert(dict_data, args):
    should_open = "-o" in args
    a_match = next(
        (re.match(r"^-a(\d*)$", a) for a in args if a.startswith("-a")), None
    )
    list_all = a_match is not None
    list_limit = int(a_match.group(1)) if (a_match and a_match.group(1)) else None

    r_match = next(
        (re.match(r"^-r(\d*)$", a) for a in args if a.startswith("-r")), None
    )
    is_random = r_match is not None
    random_count = (
        int(r_match.group(1))
        if (r_match and r_match.group(1))
        else (1 if is_random else 0)
    )

    clean_args = [a for a in args if not a.startswith("-")]
    query = "".join(clean_args).lower()

    if not query:
        return "用法: ime [拼音] [参数]\n管理: --mv (导入), --list (列表), --rm (删除)\n参数: -aN (列表), -rN (随机), -o (搜索)"

    if list_all:
        cands = dict_data.get(query, [])
        if not cands:
            return f"未找到拼音: '{query}'"
        display_cands = cands[:list_limit] if list_limit else cands
        output = [f"候选词 ({len(display_cands)}个):"]
        for i in range(0, len(display_cands), 5):
            output.append(
                "  ".join(
                    [
                        f"{j + 1}.{display_cands[j]}"
                        for j in range(i, min(i + 5, len(display_cands)))
                    ]
                )
            )
        return "\n".join(output)

    final_output_list = []
    for _ in range(max(1, random_count)):
        tokens = re.findall(r"([a-z']+)([0-9]*)", query)
        current_res = ""
        for py_part, num_str in tokens:
            if py_part in dict_data:
                cands = dict_data[py_part]
                if is_random:
                    current_res += random.choice(cands)
                else:
                    idx = int(num_str) - 1 if num_str else 0
                    current_res += cands[idx] if 0 <= idx < len(cands) else cands[0]
            else:
                for sp in split_pinyin(dict_data, py_part):
                    if sp in dict_data:
                        current_res += (
                            random.choice(dict_data[sp])
                            if is_random
                            else dict_data[sp][0]
                        )
                    else:
                        current_res += sp
        final_output_list.append(current_res)

    result_text = " ".join(final_output_list)
    copy_to_clipboard(result_text)
    if should_open:
        webbrowser.open(f"https://www.google.com/search?q={result_text}")
    return result_text


# ================= 交互模式 =================


def interactive_mode(dict_data):
    buffer, committed, full_history = "", "", ""
    page_index, PAGE_SIZE = 0, 9
    print("\033[1;34m--- Terminal IME v5.0 (Dict Manager) ---\033[0m")
    try:
        while True:
            sys.stdout.write(
                f"\r\033[K\033[32m已输入:\033[0m {full_history}{committed}\033[33m{buffer}\033[0m"
            )
            candidates = []
            if buffer:
                all_cands = dict_data.get(buffer, [])
                if not all_cands:
                    segments = split_pinyin(dict_data, buffer)
                    prediction = "".join(
                        [dict_data[s][0] if s in dict_data else s for s in segments]
                    )
                    if prediction != buffer:
                        all_cands = [prediction]

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
            if key in ("\x04", "\x03"):
                break
            elif key in ("\x7f", "\x08"):
                if buffer:
                    buffer = buffer[:-1]
                elif committed:
                    committed = committed[:-1]
            elif key in ("=", "."):
                page_index += 1
            elif key in ("-", ","):
                page_index = max(0, page_index - 1)
            elif key.isdigit() and buffer:
                idx = int(key) - 1
                if 0 <= idx < len(candidates):
                    committed += candidates[idx]
                    buffer, page_index = "", 0
            elif (key.isalpha() or key == "'") and len(key) == 1:
                buffer += key.lower()
            elif key == " ":
                if buffer and candidates:
                    committed += candidates[0]
                    buffer, page_index = "", 0
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
    except Exception as e:
        print(f"\n运行错误: {e}")
    finally:
        res = full_history + committed
        copy_to_clipboard(res)
        print(f"\n\n[OK] 内容已复制到剪贴板。")


# ================= 程序入口 =================

if __name__ == "__main__":
    # 1. 优先处理管理命令
    if any(arg in sys.argv for arg in ["--mv", "--list", "--rm"]):
        manage_dicts(sys.argv)
        sys.exit(0)

    # 2. 正常运行模式：加载所有词典
    data = load_all_dicts()

    if len(sys.argv) > 1:
        print(quick_convert(data, sys.argv[1:]))
    else:
        interactive_mode(data)
