# Checkpoint Migration Guide

After major updates to the AI architecture, existing checkpoint files may be incompatible with the updated neural network systems. This guide helps you handle the transition and manage AI training progress effectively.

## Quick Solutions

### 🚀 Start Fresh (Recommended for Most Users)
If you encounter checkpoint loading errors, the fastest solution is to start fresh:

```bash
python scripts/main.py --mode train --clear-checkpoints --episodes 100
```

This will clear all existing checkpoints and start training with the current AI architecture including deployment learning.

### 🔍 Check Compatibility First
For users with significant training investment, check compatibility before clearing:

```bash
python migrate_checkpoints.py --check-only
```

## Migration Options

### Option 1: Clear and Start Fresh (Recommended)
```bash
# Clear old checkpoints and start new training
python scripts/main.py --mode train --clear-checkpoints --episodes 1000

# Start with manual observation to see new features
python scripts/main.py --mode train --clear-checkpoints --episodes 10 --manual-phases
```

### Option 2: Check Checkpoint Compatibility
```bash
# Check which checkpoints are compatible with current architecture
python migrate_checkpoints.py --check-only

# Get detailed compatibility report
python migrate_checkpoints.py --check-only --verbose
```

### Option 3: Migrate Compatible Checkpoints
```bash
# Attempt to migrate old checkpoints to new format
python migrate_checkpoints.py --migrate

# Remove incompatible ones after migration
python migrate_checkpoints.py --clear-incompatible
```

### Option 4: Backup and Selective Migration
```bash
# Backup existing checkpoints first
cp -r checkpoints/ checkpoints_backup/

# Try migration with fallback
python migrate_checkpoints.py --migrate --backup
```

## What Changed in the Current Architecture

### Enhanced AI Capabilities
The current system includes significantly enhanced AI capabilities:

#### High-Level Agent Enhancements
- **Deployment Zone Selection**: Strategic neural network for zone choice decisions
- **Reserves Management**: Intelligent reserves vs battlefield deployment decisions  
- **Unit Positioning**: Tactical positioning within deployment zones
- **Strategic Planning**: Improved objective-based decision making

#### Game System Integration
- **Seven Setup Phases**: Complete official Warhammer 40k setup sequence
- **Manual Phases Support**: Step-by-step control for learning and debugging
- **Deployment Action Tracking**: Real-time deployment decision monitoring
- **Enhanced Rewards**: More sophisticated reward calculations for all decision types

#### UI and Training Features
- **Interactive Training**: Manual phases mode for training observation
- **Better Logging**: Detailed deployment and tactical decision tracking
- **Improved Visualization**: Enhanced deployment zone and unit status display

### Neural Network Architecture Changes
Old checkpoints may be missing:
- **Deployment Networks**: Zone selection, reserves, and positioning networks
- **Enhanced Feature Processing**: Updated input/output dimensions
- **Reward Integration**: New reward calculation and tracking systems

## Benefits of the Updated System

### 🎯 Official Rule Implementation
- Complete Warhammer 40k 10th Edition deployment rules
- Proper attacker/defender mechanics with strategic implications
- Official alternating deployment with reserves handling

### 🧠 Enhanced AI Learning
- Strategic deployment becomes part of AI learning process
- Better tactical decision making through multi-phase training
- More sophisticated reward structures for complex strategic thinking

### 🔧 Improved Training Experience
- **Manual Phases**: Step through AI learning for educational purposes
- **Better Monitoring**: Real-time deployment action tracking
- **Debugging Tools**: Enhanced logging and visualization for understanding AI behavior

### 🎮 Better Gameplay
- More challenging AI opponents with strategic deployment
- Realistic game progression following official rules
- Enhanced user interface with deployment action tracking

## Migration Script Usage

The `migrate_checkpoints.py` script provides comprehensive checkpoint management:

### Basic Commands
```bash
# Check compatibility only (safe, no changes)
python migrate_checkpoints.py --check-only

# Migrate compatible checkpoints (attempts to preserve training)
python migrate_checkpoints.py --migrate

# Remove broken/incompatible checkpoints
python migrate_checkpoints.py --clear-incompatible

# Custom checkpoint directory
python migrate_checkpoints.py --checkpoint-dir my_checkpoints --check-only
```

### Advanced Options
```bash
# Verbose output for detailed analysis
python migrate_checkpoints.py --check-only --verbose

# Backup checkpoints before migration
python migrate_checkpoints.py --migrate --backup

# Force migration even with warnings
python migrate_checkpoints.py --migrate --force
```

## Example Migration Output

```
🔄 Warhammer 40k AI Checkpoint Migration Tool
==================================================
🔍 Found 8 checkpoint files

📄 Checking hla1_checkpoint.pth...
   ⚠️  Compatible but missing deployment networks (Enhanced AI features unavailable)

📄 Checking hla2_checkpoint.pth...
   ✅ Compatible with current deployment system

📄 Checking ta1_checkpoint.pth...
   ✅ Compatible with current system

📄 Checking lla1_checkpoint.pth...
   ❌ Incompatible - network architecture mismatch

==================================================
📊 SUMMARY:
   Total checkpoints: 8
   Fully compatible: 3
   Partially compatible: 3
   Incompatible: 2
   Deployment ready: 3

💡 RECOMMENDATIONS:
   • Run with --clear-incompatible to remove 2 broken checkpoints
   • Run with --migrate to upgrade 3 partially compatible checkpoints
   • Consider --clear-checkpoints for full enhanced AI capabilities
```

## Training with Updated System

Once your checkpoints are migrated or cleared, training automatically uses the enhanced system:

```bash
# Start training with full enhanced AI capabilities
python scripts/main.py --mode train --episodes 1000

# The AI will now:
# ✓ Follow official Warhammer 40k deployment rules
# ✓ Learn strategic deployment zone selection
# ✓ Make intelligent reserves decisions
# ✓ Develop tactical positioning strategies
# ✓ Integrate deployment learning with combat tactics

# Training with manual observation (great for seeing improvements)
python scripts/main.py --mode train --episodes 50 --manual-phases
```

## Training Progression with Enhanced System

### Phase 1: Basic Learning (Episodes 1-100)
- AI learns basic deployment concepts
- Random-like zone selection and reserves decisions
- Simple unit positioning

### Phase 2: Strategic Development (Episodes 100-500)
- Improved deployment zone selection based on army composition
- Better reserves vs battlefield decisions
- Tactical positioning within zones

### Phase 3: Advanced Integration (Episodes 500+)
- Sophisticated coordination between deployment and battle tactics
- Strategic reserves usage for tactical advantage
- Complex multi-unit positioning strategies

## Troubleshooting

### Common Issues and Solutions

**Error: Missing key(s) in state_dict**
```bash
# Solution: Use fresh training for full capabilities
python scripts/main.py --mode train --clear-checkpoints --episodes 100
```

**Training Performance Changes**
- **Expected**: Initial episodes may show different behavior as AI learns enhanced capabilities
- **Normal**: Training may take slightly longer due to additional learning complexity
- **Benefit**: Resulting AI will be significantly more strategic and challenging

**Deployment Learning Issues**
- **Check**: Ensure army lists are valid and deployment zones load correctly
- **Fallback**: System automatically falls back to basic deployment if needed
- **Logs**: Check training logs for deployment-specific error messages

**Manual Phases Not Working**
- **Requirement**: Must use `--mode play` for interactive manual phases
- **Training**: `--manual-phases` works in training mode for observation only
- **UI**: Ensure UI system is properly initialized

## Performance Optimization

### For Faster Training
```bash
# Reduce checkpoint frequency for faster training
python scripts/main.py --mode train --episodes 1000 --checkpoint-interval 20

# Use smaller episode batches for testing
python scripts/main.py --mode train --episodes 100 --checkpoint-interval 5
```

### For Better AI Quality
```bash
# Longer training for more sophisticated AI
python scripts/main.py --mode train --episodes 2000

# Observe training progress periodically
python scripts/main.py --mode train --episodes 100 --manual-phases
```

## Backup and Recovery

### Creating Backups
```bash
# Backup before major changes
cp -r checkpoints/ checkpoints_backup_$(date +%Y%m%d)/

# Verify backup
ls -la checkpoints_backup_*/
```

### Restoring from Backup
```bash
# Restore previous checkpoints if needed
rm -rf checkpoints/
cp -r checkpoints_backup_20231201/ checkpoints/
```

## Integration with Current Features

The enhanced checkpoint system works seamlessly with:

- **Manual Phases**: Use `--manual-phases` to observe AI learning progression
- **Player Configuration**: All player type combinations (AI vs AI, Human vs AI, etc.)
- **UI Features**: Enhanced deployment visualization and action tracking
- **Training Monitoring**: Improved statistics and reward tracking

This updated system provides a much more sophisticated and educationally valuable AI training experience while maintaining compatibility with existing workflows. 