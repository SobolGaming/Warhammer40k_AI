# Checkpoint Migration Guide

After integrating the new deployment system, existing checkpoint files may be incompatible with the updated neural network architecture. This guide helps you handle the transition.

## 🚨 Quick Fix

If you encounter checkpoint loading errors, the fastest solution is to start fresh:

```bash
python scripts/main.py --mode train --clear-checkpoints --episodes 100
```

This will clear all existing checkpoints and start training with the new deployment-enabled agents.

## 🔧 Migration Options

### Option 1: Clear and Start Fresh (Recommended)
```bash
# Clear old checkpoints and start new training
python scripts/main.py --mode train --clear-checkpoints --episodes 1000
```

### Option 2: Check Checkpoint Compatibility
```bash
# Check which checkpoints are compatible
python migrate_checkpoints.py --check-only
```

### Option 3: Migrate Compatible Checkpoints
```bash
# Migrate old checkpoints to new format
python migrate_checkpoints.py --migrate

# Remove incompatible ones
python migrate_checkpoints.py --clear-incompatible
```

## 🧠 What Changed

The new deployment system adds three neural networks to the HighLevelAgent:
- **Deployment Zone Network**: Chooses which deployment zone to use (if defender)
- **Reserves Selection Network**: Decides which units go into reserves
- **Unit Deployment Network**: Positions units within the deployment zone

Old checkpoints don't have these networks, causing loading errors.

## 🎯 Benefits of the New System

- **Official Rules**: Follows Warhammer 40k 10th Edition deployment rules
- **Strategic Learning**: AI learns proper deployment strategies
- **Better Gameplay**: More realistic and challenging AI opponents
- **Extensible**: Easy to add new deployment strategies

## 🛠️ Migration Script Usage

The `migrate_checkpoints.py` script provides several options:

```bash
# Check compatibility only
python migrate_checkpoints.py --check-only

# Migrate old checkpoints
python migrate_checkpoints.py --migrate

# Remove broken checkpoints
python migrate_checkpoints.py --clear-incompatible

# Custom checkpoint directory
python migrate_checkpoints.py --checkpoint-dir my_checkpoints --check-only
```

## 📊 Example Output

```
🔄 Warhammer 40k AI Checkpoint Migration Tool
==================================================
🔍 Found 6 checkpoint files

📄 Checking hla1_checkpoint.pth...
   ⚠️  Compatible but missing deployment networks

📄 Checking ta1_checkpoint.pth...
   ✅ Compatible with deployment system

==================================================
📊 SUMMARY:
   Total checkpoints: 6
   Compatible: 5
   Incompatible: 1
   Deployment ready: 3

💡 RECOMMENDATIONS:
   • Run with --clear-incompatible to remove 1 broken checkpoints
   • Run with --migrate to upgrade 2 old checkpoints
```

## 🚀 Training with New System

Once your checkpoints are migrated or cleared, training will automatically use the new deployment system:

```bash
# Start training with deployment integration
python scripts/main.py --mode train --episodes 1000

# The AI will now:
# ✓ Follow official deployment rules
# ✓ Learn deployment strategies
# ✓ Make strategic reserve decisions
# ✓ Position units tactically
```

## ❓ Troubleshooting

**Error: Missing key(s) in state_dict**
- Solution: Use `--clear-checkpoints` or run the migration script

**Training seems slower**
- This is normal - the AI is now learning deployment strategies too
- The additional learning will improve overall gameplay quality

**Deployment fails during training**
- The system will automatically fall back to legacy deployment
- Check logs for specific error messages

## 📈 Performance Notes

- Initial episodes may show different behavior as AI learns deployment
- Deployment rewards are now included in agent learning
- Overall training time may increase slightly but with better results
- AI will become more strategic over time with proper deployment decisions 