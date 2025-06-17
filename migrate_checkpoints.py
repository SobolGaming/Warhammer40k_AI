#!/usr/bin/env python3
"""
Migration script for Warhammer 40k AI checkpoints.

This script helps migrate from old checkpoint format to the new format that includes
deployment neural networks. It can also clear incompatible checkpoints.
"""

import os
import sys
import torch
import argparse
from pathlib import Path

def check_checkpoint_compatibility(checkpoint_path):
    """Check if a checkpoint is compatible with the new deployment system."""
    try:
        checkpoint = torch.load(checkpoint_path, weights_only=False)
        
        # Check for deployment networks
        deployment_keys = [
            'deployment_zone_net_state_dict',
            'reserves_selection_net_state_dict', 
            'unit_deployment_net_state_dict'
        ]
        
        has_deployment = any(key in checkpoint for key in deployment_keys)
        has_main_policy = 'policy_net_state_dict' in checkpoint
        
        return {
            'compatible': has_main_policy,
            'has_deployment': has_deployment,
            'keys': list(checkpoint.keys())
        }
        
    except Exception as e:
        return {
            'compatible': False,
            'error': str(e),
            'keys': []
        }

def migrate_checkpoint(old_path, new_path=None):
    """Migrate an old checkpoint to be compatible with new deployment system."""
    if new_path is None:
        new_path = old_path.replace('.pth', '_migrated.pth')
    
    try:
        checkpoint = torch.load(old_path, weights_only=False)
        
        # Add empty deployment network states if they don't exist
        deployment_networks = {
            'deployment_zone_net_state_dict': {},
            'deployment_zone_optimizer_state_dict': {},
            'reserves_selection_net_state_dict': {},
            'reserves_selection_optimizer_state_dict': {},
            'unit_deployment_net_state_dict': {},
            'unit_deployment_optimizer_state_dict': {},
            'deployment_rewards': [],
            'deployment_log_probs': [],
            'reserves_rewards': [],
            'reserves_log_probs': []
        }
        
        # Add missing keys
        for key, default_value in deployment_networks.items():
            if key not in checkpoint:
                checkpoint[key] = default_value
        
        # Save migrated checkpoint
        torch.save(checkpoint, new_path)
        return True
        
    except Exception as e:
        print(f"❌ Migration failed for {old_path}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Migrate Warhammer 40k AI checkpoints')
    parser.add_argument('--checkpoint-dir', default='checkpoints', 
                        help='Directory containing checkpoint files')
    parser.add_argument('--check-only', action='store_true',
                        help='Only check compatibility, don\'t migrate')
    parser.add_argument('--clear-incompatible', action='store_true',
                        help='Remove incompatible checkpoint files')
    parser.add_argument('--migrate', action='store_true',
                        help='Migrate old checkpoints to new format')
    
    args = parser.parse_args()
    
    print("🔄 Warhammer 40k AI Checkpoint Migration Tool")
    print("=" * 50)
    
    checkpoint_dir = Path(args.checkpoint_dir)
    if not checkpoint_dir.exists():
        print(f"❌ Checkpoint directory '{checkpoint_dir}' not found")
        return 1
    
    # Find all checkpoint files
    checkpoint_files = list(checkpoint_dir.glob('*.pth'))
    if not checkpoint_files:
        print(f"📁 No checkpoint files found in '{checkpoint_dir}'")
        return 0
    
    print(f"🔍 Found {len(checkpoint_files)} checkpoint files")
    
    compatible_count = 0
    incompatible_count = 0
    deployment_ready_count = 0
    
    # Check each checkpoint
    for checkpoint_file in checkpoint_files:
        print(f"\n📄 Checking {checkpoint_file.name}...")
        
        info = check_checkpoint_compatibility(checkpoint_file)
        
        if not info['compatible']:
            print(f"   ❌ Incompatible: {info.get('error', 'Unknown error')}")
            incompatible_count += 1
            
            if args.clear_incompatible:
                try:
                    checkpoint_file.unlink()
                    print(f"   🗑️  Removed incompatible checkpoint")
                except Exception as e:
                    print(f"   ⚠️  Could not remove file: {e}")
                    
        else:
            compatible_count += 1
            if info['has_deployment']:
                print(f"   ✅ Compatible with deployment system")
                deployment_ready_count += 1
            else:
                print(f"   ⚠️  Compatible but missing deployment networks")
                
                if args.migrate:
                    print(f"   🔄 Migrating...")
                    if migrate_checkpoint(str(checkpoint_file)):
                        print(f"   ✅ Migration successful")
                        deployment_ready_count += 1
                    else:
                        print(f"   ❌ Migration failed")
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 SUMMARY:")
    print(f"   Total checkpoints: {len(checkpoint_files)}")
    print(f"   Compatible: {compatible_count}")
    print(f"   Incompatible: {incompatible_count}")
    print(f"   Deployment ready: {deployment_ready_count}")
    
    if args.check_only:
        print("\n💡 RECOMMENDATIONS:")
        if incompatible_count > 0:
            print(f"   • Run with --clear-incompatible to remove {incompatible_count} broken checkpoints")
        if compatible_count > deployment_ready_count:
            missing_deployment = compatible_count - deployment_ready_count
            print(f"   • Run with --migrate to upgrade {missing_deployment} old checkpoints")
        if deployment_ready_count == len(checkpoint_files):
            print("   • All checkpoints are ready for deployment training! 🎉")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 