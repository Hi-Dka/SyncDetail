#!/bin/bash

set -e  # 遇到错误时退出

echo "Building inotify-indexer executable..."

# 检查是否存在虚拟环境
if [ ! -d ".venv" ]; then
    echo "Error: Virtual environment not found. Please run setup_venv.sh first."
    exit 1
fi

# 激活虚拟环境
echo "Activating virtual environment..."
source .venv/bin/activate

# 安装 PyInstaller（如果未安装）
if ! pip list | grep -q "pyinstaller"; then
    echo "Installing PyInstaller..."
    pip install pyinstaller
fi

# 清理之前的构建
echo "Cleaning previous builds..."
rm -rf build/ dist/ *.spec

# 使用 PyInstaller 创建单独的可执行文件
echo "Building with PyInstaller..."
pyinstaller \
    --onefile \
    --name inotify-indexer \
    --add-data "app:app" \
    --paths app \
    --hidden-import=watchdog \
    --hidden-import=watchdog.observers \
    --hidden-import=watchdog.events \
    --hidden-import=sqlite3 \
    --hidden-import=argparse \
    --hidden-import=signal \
    --hidden-import=time \
    --hidden-import=os \
    --hidden-import=sys \
    --hidden-import=typing \
    --console \
    app/main.py

# 检查构建结果
if [ -f "dist/inotify-indexer" ]; then
    echo "✅ Successfully built executable: dist/inotify-indexer"
    echo "File size: $(du -h dist/inotify-indexer | cut -f1)"
    
    # 测试可执行文件
    echo "Testing executable..."
    ./dist/inotify-indexer --help
    
    echo ""
    echo "🎉 Build complete! You can now run: ./dist/inotify-indexer"
    echo "Or copy the executable to any location and run it standalone."
else
    echo "❌ Build failed! Executable not found in dist/"
    exit 1
fi

# 停用虚拟环境
deactivate
