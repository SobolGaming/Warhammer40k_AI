#!/usr/bin/env python3
"""
Simple test runner for Fight Phase tests

Usage:
    uv run python run_fight_tests.py          # Run all fight phase tests
    uv run python run_fight_tests.py -v       # Run with verbose output
    uv run python run_fight_tests.py --help   # Show help
"""

import sys
import subprocess
import os
import logging
logger = logging.getLogger(__name__)


def main():
    """Run the fight phase tests."""
    # Change to the tests directory
    test_dir = "tests"
    if not os.path.exists(test_dir):
        logger.error(f"❌ Tests directory '{test_dir}' not found!")
        return 1

    # Build the pytest command
    cmd = [sys.executable, "-m", "pytest", "test_unit_fighting.py"]

    # Add any command line arguments
    if len(sys.argv) > 1:
        cmd.extend(sys.argv[1:])
    else:
        cmd.append("-v")  # Default to verbose output

    logger.info(f"🧪 Running Fight Phase Tests...")
    logger.info(f"Command: {' '.join(cmd)}")
    logger.info("=" * 60)

    # Run the tests
    try:
        result = subprocess.run(cmd, cwd=test_dir, check=False)

        if result.returncode == 0:
            logger.info("=" * 60)
            logger.info("✅ All Fight Phase Tests Passed!")
        else:
            logger.info("=" * 60)
            logger.error("❌ Some Fight Phase Tests Failed!")

        return result.returncode

    except FileNotFoundError:
        logger.exception("❌ pytest not found! Please sync test dependencies:")
        logger.info("   uv sync --extra test")
        return 1
    except Exception as e:
        logger.exception(f"❌ Error running tests: {e}")
        return 1

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sys.exit(main())
