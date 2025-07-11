#!/usr/bin/env python3
"""
Simple test runner for Fight Phase tests

Usage:
    python run_fight_tests.py          # Run all fight phase tests
    python run_fight_tests.py -v       # Run with verbose output
    python run_fight_tests.py --help   # Show help
"""

import sys
import subprocess
import os

def main():
    """Run the fight phase tests."""
    # Change to the tests directory
    test_dir = "tests"
    if not os.path.exists(test_dir):
        print(f"❌ Tests directory '{test_dir}' not found!")
        return 1
    
    # Build the pytest command
    cmd = [sys.executable, "-m", "pytest", "test_unit_fighting.py"]
    
    # Add any command line arguments
    if len(sys.argv) > 1:
        cmd.extend(sys.argv[1:])
    else:
        cmd.append("-v")  # Default to verbose output
    
    print(f"🧪 Running Fight Phase Tests...")
    print(f"Command: {' '.join(cmd)}")
    print("=" * 60)
    
    # Run the tests
    try:
        result = subprocess.run(cmd, cwd=test_dir, check=False)
        
        if result.returncode == 0:
            print("=" * 60)
            print("✅ All Fight Phase Tests Passed!")
        else:
            print("=" * 60)
            print("❌ Some Fight Phase Tests Failed!")
            
        return result.returncode
        
    except FileNotFoundError:
        print("❌ pytest not found! Please install pytest:")
        print("   pip install pytest")
        return 1
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 