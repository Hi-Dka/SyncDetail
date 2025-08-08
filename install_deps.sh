#!/bin/bash

echo "Installing build dependencies..."

# Install PyInstaller for creating standalone executables
pip install pyinstaller

# Install build tools
pip install build

# Install project dependencies
pip install -r requirements.txt

echo "Dependencies installed successfully!"
