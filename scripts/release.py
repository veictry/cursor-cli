#!/usr/bin/env python3
"""
PyPI Release Script for cursor-cli

Usage:
    python scripts/release.py [--test]
    
Options:
    --test    Upload to TestPyPI instead of PyPI
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from getpass import getpass


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.resolve()


def get_version() -> str:
    """Extract version from pyproject.toml."""
    pyproject = get_project_root() / "pyproject.toml"
    with open(pyproject, "r") as f:
        for line in f:
            if line.startswith("version"):
                # version = "0.1.0"
                return line.split("=")[1].strip().strip('"')
    raise ValueError("Version not found in pyproject.toml")


def clean_build_dirs():
    """Clean up build directories."""
    root = get_project_root()
    dirs_to_clean = ["dist", "build", "src/cursor_cli.egg-info"]
    
    for dir_name in dirs_to_clean:
        dir_path = root / dir_name
        if dir_path.exists():
            print(f"  Removing {dir_path}")
            shutil.rmtree(dir_path)


def build_package():
    """Build the package."""
    root = get_project_root()
    print("\n📦 Building package...")
    
    result = subprocess.run(
        [sys.executable, "-m", "build"],
        cwd=root,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"❌ Build failed:\n{result.stderr}")
        sys.exit(1)
    
    print("✓ Build successful")
    
    # List built files
    dist_dir = root / "dist"
    for f in dist_dir.iterdir():
        print(f"  - {f.name}")


def upload_to_pypi(token: str, test: bool = False):
    """Upload package to PyPI."""
    root = get_project_root()
    
    if test:
        repo_url = "https://test.pypi.org/legacy/"
        repo_name = "TestPyPI"
    else:
        repo_url = "https://upload.pypi.org/legacy/"
        repo_name = "PyPI"
    
    print(f"\n🚀 Uploading to {repo_name}...")
    
    result = subprocess.run(
        [
            sys.executable, "-m", "twine", "upload",
            "--repository-url", repo_url,
            "--username", "__token__",
            "--password", token,
            "dist/*"
        ],
        cwd=root,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"❌ Upload failed:\n{result.stderr}")
        sys.exit(1)
    
    print(f"✓ Successfully uploaded to {repo_name}")


def check_dependencies():
    """Check if required tools are installed."""
    missing = []
    
    # Check build
    try:
        subprocess.run(
            [sys.executable, "-m", "build", "--version"],
            capture_output=True, check=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        missing.append("build")
    
    # Check twine
    try:
        subprocess.run(
            [sys.executable, "-m", "twine", "--version"],
            capture_output=True, check=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        missing.append("twine")
    
    if missing:
        print(f"❌ Missing dependencies: {', '.join(missing)}")
        print(f"   Install with: pip install {' '.join(missing)}")
        sys.exit(1)


def show_changelog():
    """Show recent changelog entries."""
    changelog = get_project_root() / "CHANGELOG.md"
    if changelog.exists():
        print("\n📋 Recent changes:")
        with open(changelog, "r") as f:
            lines = f.readlines()
            # Show first 30 lines or until second version header
            count = 0
            for i, line in enumerate(lines):
                if i > 0 and line.startswith("## "):
                    break
                print(f"  {line.rstrip()}")
                count += 1
                if count > 30:
                    print("  ...")
                    break


def main():
    test_mode = "--test" in sys.argv
    
    version = get_version()
    target = "TestPyPI" if test_mode else "PyPI"
    
    print(f"🎯 cursor-cli v{version} -> {target}")
    print("=" * 50)
    
    # Show changelog
    show_changelog()
    
    # Check dependencies
    print("\n🔍 Checking dependencies...")
    check_dependencies()
    print("✓ All dependencies installed")
    
    # Clean previous builds
    print("\n🧹 Cleaning build directories...")
    clean_build_dirs()
    print("✓ Clean complete")
    
    # Build
    build_package()
    
    # Get token
    print("\n" + "=" * 50)
    if test_mode:
        print("Enter your TestPyPI API token:")
    else:
        print("Enter your PyPI API token:")
    print("(Get one at https://pypi.org/manage/account/token/)")
    
    token = getpass("Token: ")
    
    if not token:
        print("❌ No token provided")
        sys.exit(1)
    
    # Upload
    upload_to_pypi(token, test=test_mode)
    
    # Success message
    print("\n" + "=" * 50)
    print(f"🎉 Release v{version} complete!")
    if test_mode:
        print(f"   View at: https://test.pypi.org/project/cursor-cli/")
        print(f"   Install: pip install -i https://test.pypi.org/simple/ cursor-cli")
    else:
        print(f"   View at: https://pypi.org/project/cursor-cli/")
        print(f"   Install: pip install cursor-cli")


if __name__ == "__main__":
    main()

