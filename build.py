#!/usr/bin/env python3
"""
Build script for SynergyPlus
Packages master and server applications using PyInstaller
"""

import os
import sys
import platform
import subprocess


def check_pyinstaller():
    """Check if PyInstaller is installed"""
    try:
        import PyInstaller
        return True
    except ImportError:
        return False


def install_pyinstaller():
    """Install PyInstaller"""
    print("Installing PyInstaller...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])


def build_app(script_name, app_name):
    """Build application using PyInstaller"""
    print(f"\nBuilding {app_name}...")
    
    # PyInstaller command
    cmd = [
        "pyinstaller",
        "--name", app_name,
        "--onedir",  # Create a directory containing the executable
        "--windowed",  # No console window (GUI app)
        "--clean",
        script_name
    ]
    
    # Add platform-specific options
    if platform.system() == "Darwin":  # macOS
        print("Building for macOS...")
    elif platform.system() == "Linux":
        print("Building for Linux...")
    
    try:
        subprocess.check_call(cmd)
        print(f"✓ {app_name} built successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Error building {app_name}: {e}")
        return False


def main():
    """Main build function"""
    print("=" * 60)
    print("SynergyPlus Build Script")
    print("=" * 60)
    print(f"Platform: {platform.system()}")
    print(f"Python: {sys.version}")
    print()
    
    # Check PyInstaller
    if not check_pyinstaller():
        print("PyInstaller not found.")
        install_pyinstaller()
    
    # Build master
    success_master = build_app("master.py", "SynergyPlus-Master")
    
    # Build server
    success_server = build_app("server.py", "SynergyPlus-Server")
    
    # Summary
    print("\n" + "=" * 60)
    print("Build Summary")
    print("=" * 60)
    print(f"Master: {'✓ Success' if success_master else '✗ Failed'}")
    print(f"Server: {'✓ Success' if success_server else '✗ Failed'}")
    
    if success_master and success_server:
        print("\nBuilt applications can be found in:")
        print("  - dist/SynergyPlus-Master/")
        print("  - dist/SynergyPlus-Server/")
        print("\nTo run the applications:")
        print("  - macOS/Linux: ./dist/SynergyPlus-Master/SynergyPlus-Master")
        print("  - macOS/Linux: ./dist/SynergyPlus-Server/SynergyPlus-Server")
    else:
        print("\n✗ Build failed. Please check the errors above.")
        sys.exit(1)


if __name__ == '__main__':
    main()
