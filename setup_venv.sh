#!/usr/bin/env bash
set -euo pipefail

# 提示 venv 可能缺失时的解决办法
if ! python3 -m venv --help >/dev/null 2>&1; then
  echo "python3-venv 未安装。请先执行: sudo apt update && sudo apt install -y python3-venv"
  exit 1
fi

# 创建虚拟环境
python3 -m venv .venv

# 激活虚拟环境并安装依赖
# shellcheck source=/dev/null
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

echo
echo "已完成。后续使用请先执行:"
echo "  source .venv/bin/activate"
echo "然后运行你的程序。"
