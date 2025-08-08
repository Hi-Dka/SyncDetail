from setuptools import setup, find_packages

setup(
    name="inotify-indexer",
    version="1.0.0",
    description="Inotify-based indexer for source/media with SQLite sync",
    author="Your Name",
    packages=find_packages(),
    install_requires=[
        "watchdog>=2.1.0",
    ],
    entry_points={
        "console_scripts": [
            "inotify-indexer=main:main",
        ],
    },
    python_requires=">=3.7",
)
