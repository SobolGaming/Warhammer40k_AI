#!/usr/bin/env python3
"""
Simple test script to verify the AI training system works.
This runs a very short training session to test all components.
"""

import sys
import os
import subprocess
import logging

def test_training_system():
    """Run a quick test of the training system."""
    print("🧪 Testing Warhammer 40k AI Training System")
    print("=" * 50)
    
    # Test with just 2 episodes and checkpoint every episode
    cmd = [
        sys.executable, "scripts/main.py",
        "--mode", "train",
        "--episodes", "2",
        "--checkpoint-interval", "1"
    ]
    
    print(f"Running command: {' '.join(cmd)}")
    print("This will run 2 training episodes...\n")
    
    try:
        # Set environment variable to reduce logging noise during test
        env = os.environ.copy()
        env['PYTHONPATH'] = os.getcwd()
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)
        
        if result.returncode == 0:
            print("✅ Test completed successfully!")
            print("\n--- Test Output ---")
            # Only show the important lines from output
            lines = result.stdout.split('\n')
            important_lines = [line for line in lines if any(keyword in line for keyword in 
                              ['Starting training', 'Episode', 'completed', 'Progress Update', 'TRAINING COMPLETED', 'Final Results'])]
            for line in important_lines[-20:]:  # Show last 20 important lines
                print(line)
            
            if result.stderr:
                print("\n--- Warnings/Errors ---")
                print(result.stderr[:1000])  # Show first 1000 chars of stderr
                
        else:
            print("❌ Test failed!")
            print(f"Return code: {result.returncode}")
            print("\n--- Error Output ---")
            print(result.stderr)
            print("\n--- Standard Output ---") 
            print(result.stdout[-1000:])  # Show last 1000 chars
            
    except subprocess.TimeoutExpired:
        print("⏱️ Test timed out after 5 minutes")
        return False
    except Exception as e:
        print(f"❌ Test error: {e}")
        return False
    
    return result.returncode == 0

def test_manual_mode():
    """Test that manual mode starts without errors."""
    print("\n" + "=" * 50)
    print("Testing Manual Play Mode (will exit quickly)")
    
    cmd = [sys.executable, "scripts/main.py", "--mode", "play"]
    
    try:
        # Start the process but kill it quickly since it's interactive
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Give it a moment to initialize
        import time
        time.sleep(3)
        
        # Kill the process
        process.terminate()
        stdout, stderr = process.communicate(timeout=5)
        
        print("✅ Manual mode started successfully (terminated for testing)")
        
    except Exception as e:
        print(f"❌ Manual mode test failed: {e}")

if __name__ == "__main__":
    # Set logging level to reduce noise
    logging.basicConfig(level=logging.ERROR)
    
    success = test_training_system()
    sys.exit(0 if success else 1)
    
    # Optionally test manual mode (commented out since it's interactive)
    # test_manual_mode()
    
    print("\n" + "=" * 50)
    print("Test complete! Check the output above for any issues.")
    print("If successful, you can now run full training with:")
    print("  python scripts/main.py --mode train --episodes 1000") 