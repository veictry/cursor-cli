#!/usr/bin/env python
"""Setup script for cursor-cli package."""

from setuptools import setup, find_packages

setup(
    name="cursor-cli",
    version="0.1.0",
    description="A wrapper for cursor-agent with formatted output support",
    author="AITS Team",
    python_requires=">=3.8",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    entry_points={
        "console_scripts": [
            "cursor-cli=cursor_cli.__main__:main",
        ],
    },
)
