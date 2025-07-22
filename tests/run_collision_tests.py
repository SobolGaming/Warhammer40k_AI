#!/usr/bin/env python3
"""
Test runner for collision detection tests.

Usage:
    python tests/run_collision_tests.py
    
Or from project root:
    python -m pytest tests/test_collision_detection.py -v
"""

import sys
import os
import subprocess

def run_collision_tests():
    """Run the collision detection test suite."""
    # Get the project root directory
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Change to project root
    os.chdir(project_root)
    
    # Run pytest on the collision detection tests
    cmd = [
        sys.executable, "-m", "pytest", 
        "tests/test_collision_detection.py",
        "-v",  # Verbose output
        "--tb=short",  # Short traceback format
        "--color=yes"  # Colored output
    ]
    
    print("Running collision detection tests...")
    print("=" * 60)
    
    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except Exception as e:
        print(f"Error running tests: {e}")
        return 1

if __name__ == "__main__":
    exit_code = run_collision_tests()
    sys.exit(exit_code)
