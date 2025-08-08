#!/bin/bash

echo "Building inotify-indexer executable..."

# Method 1: Using PyInstaller (creates standalone executable)
if command -v pyinstaller &> /dev/null; then
    echo "Building with PyInstaller..."
    pyinstaller --onefile --name inotify-indexer main.py
    echo "Executable created at: dist/inotify-indexer"
fi

# Method 2: Using setuptools (creates installable package)
echo "Building with setuptools..."
python -m build

# Method 3: Create a simple launcher script
echo "Creating launcher script..."
cat > inotify-indexer << 'EOF'
#!/usr/bin/env python3
import os
import sys

# Add the script directory to Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

# Import and run main
from main import main
if __name__ == "__main__":
    main()
EOF

chmod +x inotify-indexer
echo "Launcher script created: ./inotify-indexer"

echo "Build complete!"
