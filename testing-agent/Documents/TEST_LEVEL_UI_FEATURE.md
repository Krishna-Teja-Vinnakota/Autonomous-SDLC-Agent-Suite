# Test Level Selection UI Feature

## 🎯 Overview

Added comprehensive test-level selection UI to the Streamlit interface, allowing users to choose which test levels (unit, integration, feature) to execute. The backend workflow respects these selections and only generates/executes tests for the selected levels.

---

## ✅ Implementation Details

### 1. UI Components Added (Sidebar)

#### **Test Level Multiselect**
- Location: Sidebar Configuration section
- Options: Unit, Integration, Feature
- Default: All three selected
- Description tooltips for each level

#### **Quick Action Buttons**
- **🔹 Unit Only**: Fast execution, isolated tests
- **🔷 Integration**: Multi-module tests with MSW setup
- **💎 Feature Only**: Complete user workflows (E2E-lite)
- **🎯 All Levels**: Run all test levels

#### **Status Display**
- Shows currently selected test levels in the Status section
- Visual indicators with level-specific icons

### 2. Backend Integration

#### **State Management**
```python
# Session state stores selected test levels
safe_set('test_levels_to_run', ['unit', 'integration', 'feature'])
safe_get('test_levels_to_run', default)
```

#### **Workflow Orchestrator Updates**
- Added `test_levels_filter` to `WorkflowState`
- Modified `execute()` to accept `test_levels` parameter
- Filters test plan during strategy stage
- Only generates/executes tests for selected levels

#### **Execution Flow**
```
User selects test levels in UI
    ↓
Selection stored in session state
    ↓
"Run Workflow" button clicked
    ↓
execute_full_workflow(project_path) reads selection
    ↓
WorkflowOrchestrator.execute(test_levels=selection)
    ↓
Strategy stage applies filter
    ↓
Only selected levels are processed
```

### 3. Code Changes

#### **app.py**
- Added test level multiselect (line ~1505)
- Added quick action buttons (line ~1517)
- Updated status display to show selected levels (line ~1535)
- Modified `execute_full_workflow()` to accept `test_levels` parameter
- Updated auto-run workflow to respect selection (4 locations)
- Updated workflow button to show selected levels

#### **workflows/langgraph_flow.py**
- Added `test_levels_filter: Optional[List[str]]` to `WorkflowState`
- Modified `execute()` to accept `test_levels` parameter
- Added filter application in `_stage_strategizing()`
- Modified `_stage_generating()` to only process filtered levels
- Modified `_stage_executing()` to only process filtered levels

---

## 🎨 UI Layout

### Sidebar Structure

```
⚙️ Configuration
├─ Upload your project to begin analysis
├─ 🚀 Auto-run workflow after indexing [checkbox]
├─ ───────────────
├─ 🎯 Test Levels
│  ├─ Select test levels to execute: [multiselect]
│  │  └─ Options: unit, integration, feature
│  ├─ Quick Actions:
│  │  ├─ [🔹 Unit Only] [🔷 Integration]
│  │  ├─ [💎 Feature Only]
│  │  └─ [🎯 All Levels]
├─ ───────────────
├─ [🔄 Reset Session]
├─ ───────────────
└─ 📋 Status
   ├─ Run ID: xxxxx...
   ├─ Workspace: run_xxxxx...
   └─ Test Levels: 🔹 Unit 🔷 Integration 💎 Feature
```

### Main Content

```
🚀 Run Workflow Button
├─ Shows selected levels: "Running workflow for Unit, Integration tests..."
└─ Info: "Workflow will execute: AI Analysis → Test Strategy → 🔹Unit → 🔷Integration → Reporting"
```

---

## 🔧 Usage Examples

### Scenario 1: Quick Unit Tests Only

1. Click **🔹 Unit Only** button
2. Click **🚀 Run Workflow**
3. Result: Only unit tests generated and executed (~30 seconds)

### Scenario 2: Integration Testing Focus

1. Click **🔷 Integration** button
2. Click **🚀 Run Workflow**
3. Result: Only integration tests with MSW setup (~2-3 minutes)

### Scenario 3: Custom Selection

1. Use multiselect to choose "unit" and "feature"
2. Click **🚀 Run Workflow**
3. Result: Unit and feature tests, skips integration

### Scenario 4: Full Suite

1. Click **🎯 All Levels** button (or leave default)
2. Click **🚀 Run Workflow**
3. Result: All test levels executed in sequence

---

## 📊 Benefits

### Performance
- ⚡ **Faster Iterations**: Run only unit tests for quick feedback
- 🎯 **Targeted Testing**: Focus on specific test levels
- 💰 **Cost Efficiency**: Skip expensive feature tests when not needed

### Developer Experience
- 🎨 **Clear Visual Feedback**: Icons and status indicators
- 🔘 **Quick Actions**: One-click presets
- 📈 **Flexibility**: Custom level combinations

### Workflow Efficiency
- 🔄 **Auto-run Support**: Respects selection in auto-run mode
- 📝 **Clear Logging**: Shows which levels are running
- ⏱️ **Time Savings**: Skip unnecessary test generation

---

## 🔍 Implementation Details

### Filter Logic

```python
# In WorkflowOrchestrator._stage_strategizing()
if self.state.test_levels_filter:
    filtered_plan = {
        level: strategies 
        for level, strategies in self.state.test_plan.items()
        if level in self.state.test_levels_filter
    }
    self.state.test_plan = filtered_plan
```

### Generation Stage

```python
# In WorkflowOrchestrator._stage_generating()
if self.state.test_levels_filter:
    test_levels = [lvl for lvl in ['unit', 'integration', 'feature'] 
                   if lvl in self.state.test_levels_filter]
else:
    test_levels = ['unit', 'integration', 'feature']
```

### Execution Stage

```python
# In WorkflowOrchestrator._stage_executing()
if self.state.test_levels_filter:
    test_levels = [lvl for lvl in ['unit', 'integration', 'feature'] 
                   if lvl in self.state.test_levels_filter]
else:
    test_levels = ['unit', 'integration', 'feature']
```

---

## 🧪 Test Scenarios

### Test 1: Unit Only
```
Input: Select "unit" only
Expected: 
- Only unit test strategies generated
- Only unit tests executed
- Fast execution (<1 min)
- Report shows only unit results
```

### Test 2: Integration Only
```
Input: Select "integration" only
Expected:
- Only integration test strategies generated
- MSW environment setup runs
- Integration tests with --runInBand
- Report shows only integration results
```

### Test 3: Feature Only
```
Input: Select "feature" only
Expected:
- Only feature test strategies generated
- Feature tests with full setup
- Sequential execution
- Report shows only feature results
```

### Test 4: Custom Combination
```
Input: Select "unit" and "feature"
Expected:
- Unit and feature strategies generated
- Integration skipped
- Execution in order: unit → feature
- Report shows both levels
```

---

## 📝 User Instructions

### Getting Started

1. **Upload Your Project**
   - Use GitHub URL, ZIP, or folder upload
   - Wait for indexing to complete

2. **Select Test Levels**
   - Go to sidebar → "🎯 Test Levels"
   - Choose desired levels from dropdown
   - OR use Quick Action buttons

3. **Run Workflow**
   - Click "🚀 Run Workflow"
   - Monitor progress in status messages
   - View results by test level in tabs

### Quick Actions Guide

| Button | Test Levels | Use Case | Typical Time |
|--------|-------------|----------|--------------|
| 🔹 Unit Only | unit | Fast feedback, TDD | 30-60s |
| 🔷 Integration | integration | API/component testing | 2-3 min |
| 💎 Feature Only | feature | E2E validation | 5-10 min |
| 🎯 All Levels | all | Full test suite | 5-15 min |

---

## 🎯 Future Enhancements

### Potential Additions

1. **Test Level Priorities**
   - Set priority order for execution
   - Stop on first failure at level

2. **Smart Defaults**
   - Remember last selection per project
   - Suggest levels based on changes

3. **Parallel Execution**
   - Run different levels in parallel
   - Aggregate results at the end

4. **Level-Specific Settings**
   - Different timeout per level
   - Different retry counts
   - Custom execution parameters

5. **Advanced Filtering**
   - Filter by file patterns
   - Filter by tags/markers
   - Exclude specific tests

---

## ✨ Summary

The test level selection feature provides:

- ✅ **Flexible control** over which test levels to run
- ✅ **Quick actions** for common scenarios
- ✅ **Visual feedback** with icons and status
- ✅ **Backend integration** with workflow filtering
- ✅ **Efficient execution** by skipping unnecessary tests
- ✅ **Better UX** with clear, actionable UI

This enhancement makes the SDLC Testing Agent more practical for day-to-day development workflows by allowing developers to run only the tests they need, when they need them.

---

**Implementation Date**: January 16, 2026  
**Status**: ✅ COMPLETE  
**Files Modified**: 2 (`app.py`, `workflows/langgraph_flow.py`)  
**Lines Added**: ~150  
**Linter Errors**: 0
