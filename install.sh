#!/bin/bash

# 定义颜色
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${GREEN}正在安装 Terminal IME...${NC}"

# 1. 检查依赖
if ! command -v xclip &> /dev/null; then
    echo "检测到未安装 xclip，正在安装..."
    sudo apt update && sudo apt install -y xclip
fi

# 2. 修改脚本名为快捷命令名
if [ -f "terminal_ime.py" ]; then
    mv terminal_ime.py ime
fi

# 3. 赋予执行权限
chmod +x ime

# 4. 创建软链接到系统路径
# 使用绝对路径，确保在任何地方输入 ime 都能找到词库
INSTALL_PATH=$(pwd)/ime
sudo ln -sf "$INSTALL_PATH" /usr/local/bin/ime

echo -e "${GREEN}安装完成！${NC}"
echo -e "现在你可以在任何地方输入 ${GREEN}ime${NC} 来使用它了。"
echo -e "输入完成后按 ${GREEN}Ctrl+D${NC} 自动复制并退出。"
