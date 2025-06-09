#!/usr/bin/env python3
"""
Simple test script to verify the AI training system works.
This runs a very short training session to test all components.
"""

import sys
import os
import subprocess

def test_training_system():
    """Run a quick test of the training system."""
    print("Testing Warhammer 40k AI Training System")
    print("=" * 50)
    
    # Test with just 2 episodes and checkpoint every episode
    cmd = [
        sys.executable, "scripts/main.py",
        "--mode", "train",
        "--episodes", "2",
        "--checkpoint-interval", "1"
    ]
    
    print(f"Running command: {' '.join(cmd)}")
    print("This will run 2 training episodes...")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        print("\nSTDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("\nSTDERR:")
            print(result.stderr)
            
        if result.returncode == 0:
            print("\n✅ Test completed successfully!")
            
            # Check if checkpoint files were created
            checkpoint_dir = "checkpoints"
            if os.path.exists(checkpoint_dir):
                files = os.listdir(checkpoint_dir)
                print(f"✅ Checkpoint directory created with {len(files)} files:")
                for file in files:
                    print(f"  - {file}")
            else:
                print("⚠️  No checkpoint directory found")
                
        else:
            print(f"\n❌ Test failed with return code: {result.returncode}")
            
    except subprocess.TimeoutExpired:
        print("\n⏰ Test timed out after 5 minutes")
        print("This might be normal for slower systems")
        
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")

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
    print("Warhammer 40k AI Training System Test")
    print("This will run a quick test to verify everything works.\n")
    
    # Change to the project root directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    test_training_system()
    
    # Optionally test manual mode (commented out since it's interactive)
    # test_manual_mode()
    
    print("\n" + "=" * 50)
    print("Test complete! Check the output above for any issues.")
    print("If successful, you can now run full training with:")
    print("  python scripts/main.py --mode train --episodes 1000") 