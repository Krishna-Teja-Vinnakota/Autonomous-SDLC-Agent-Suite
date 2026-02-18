# Workflow Orchestration Guide

Complete guide to LangGraph-style workflow orchestration in AutoSDLC Test Agent.

---

## 🎯 Overview

The system uses **LangGraph-style orchestration** to manage the complete testing workflow:

1. **Shared State Management** - Tracks workflow progress
2. **Stage-Based Execution** - Sequential stage processing
3. **Retry Guards** - Automatic retry on failure
4. **Cleanup Logic** - Resource cleanup guarantees
5. **Security Hardening** - No arbitrary code execution

---

## 🔄 Workflow Stages

### **Stage 1: Indexing** 📁
**Purpose:** Analyze project structure

**Actions:**
- Scan project directory
- Categorize files
- Count lines of code
- Build file tree

**Required:** ✅ Yes (critical)

**Retries:** Up to 3

**Timeout:** None (fast operation)

### **Stage 2: Analyzing** 🤖
**Purpose:** AI-powered project analysis

**Actions:**
- Detect languages
- Identify frameworks
- Analyze test setup
- Generate summary

**Required:** ❌ No (optional)

**Retries:** Up to 3

**Timeout:** None (AI call timeout handled)

### **Stage 3: Strategizing** 🎯
**Purpose:** Determine test strategy

**Actions:**
- Identify testable files
- Assign priorities
- Determine frameworks
- Estimate test count

**Required:** ❌ No (optional)

**Retries:** Up to 3

**Timeout:** None

### **Stage 4: Generating** ✍️
**Purpose:** Generate test files

**Actions:**
- Generate Jest tests
- Generate Pytest tests
- Save test files
- Validate generation

**Required:** ❌ No (optional)

**Retries:** Up to 3

**Timeout:** None

### **Stage 5: Executing** 🏃
**Purpose:** Execute generated tests

**Actions:**
- Run Jest tests
- Run Pytest tests
- Capture results
- Parse output

**Required:** ❌ No (optional)

**Retries:** Up to 3 per framework

**Timeout:** 5 minutes per test run

### **Stage 6: Reporting** 📊
**Purpose:** Generate comprehensive reports

**Actions:**
- Parse coverage
- Generate unified report
- Create visualizations
- Save JSON/HTML

**Required:** ❌ No (optional)

**Retries:** Up to 3

**Timeout:** None

---

## 🔐 Security Architecture

### **UI Never Executes Code Directly**

**Architecture:**
```
UI (app.py)
  ↓
WorkflowOrchestrator
  ↓
Stage Functions
  ↓
Agents/Tools
  ↓
Command Executor (with allowlist)
  ↓
Subprocess (no shell=True)
```

**Protection:**
- ✅ UI only triggers workflow
- ✅ All execution through orchestrator
- ✅ Commands validated before execution
- ✅ No direct subprocess calls from UI

### **Shared State Object**

**Purpose:**
- Track workflow progress
- Store intermediate results
- Manage retries
- Handle errors
- Ensure cleanup

**Security:**
- ✅ Immutable state updates
- ✅ Error isolation
- ✅ Audit trail
- ✅ Resource tracking

---

## 🔄 Retry Logic

### **Per-Stage Retries**

Each stage can retry up to **3 times**:

```python
for attempt in range(3):
    try:
        result = stage_function()
        if result:
            return True
        # Retry if failed
    except Exception as e:
        # Retry on exception
```

### **Overall Retries**

Workflow can retry up to **3 times** overall:

```python
if state.can_retry():
    state.increment_retry()
    # Retry workflow
```

### **Retry Guards**

**Prevents:**
- Infinite loops
- Resource exhaustion
- Timeout cascades

**Enforces:**
- Maximum retry count
- Delay between retries
- Cleanup on failure

---

## 🧹 Cleanup Logic

### **Automatic Cleanup**

**Always Executed:**
- ✅ On workflow completion
- ✅ On workflow failure
- ✅ On timeout
- ✅ On exception

**Cleanup Actions:**
- Close file handles
- Release resources
- Clean temporary files
- Reset state flags

### **Cleanup Guarantees**

**Ensured:**
- Cleanup always runs
- Resources released
- State marked complete
- No resource leaks

---

## ⏱️ Timeout Protection

### **Per-Test Timeout**

**Default:** 5 minutes (300 seconds)

**Enforced:**
- Per test execution
- Per framework run
- Prevents hangs

**Configurable:**
```python
MAX_EXECUTION_TIME = 300.0  # seconds
```

### **Overall Timeout**

**Default:** 30 minutes (1800 seconds)

**Enforced:**
- Entire workflow
- Prevents infinite runs
- Resource protection

**Configurable:**
```python
WORKFLOW_TIMEOUT = 1800.0  # seconds
```

---

## 📊 State Management

### **WorkflowState Object**

**Tracks:**
- Current stage
- Completed stages
- Failed stages
- Retry counts
- Execution data
- Errors/warnings
- Cleanup status

**Methods:**
- `can_retry()` - Check retry eligibility
- `increment_retry()` - Increment retry count
- `get_elapsed_time()` - Get execution time
- `is_timeout()` - Check timeout
- `add_error()` - Log error
- `add_warning()` - Log warning

### **State Transitions**

```
INITIALIZED
  ↓
INDEXING → ANALYZING → STRATEGIZING → GENERATING → EXECUTING → REPORTING
  ↓
COMPLETED or FAILED
  ↓
CLEANUP
```

---

## 🎯 Usage

### **Basic Usage**

```python
from workflows.langgraph_flow import WorkflowOrchestrator

# Create orchestrator
orchestrator = WorkflowOrchestrator(project_path)

# Execute workflow
result = orchestrator.execute()

# Check result
if result.success:
    print("Workflow completed!")
    print(f"Duration: {result.duration:.2f}s")
    print(f"Stages: {len(result.state.completed_stages)}")
else:
    print(f"Workflow failed: {result.message}")
    print(f"Errors: {result.state.errors}")
```

### **Access State**

```python
# Get current state
state = orchestrator.get_state()

# Check stage
print(f"Current stage: {state.current_stage.value}")

# Get results
if state.index_result:
    print(f"Files indexed: {state.index_result.total_files}")

if state.execution_results:
    for framework, result in state.execution_results.items():
        print(f"{framework}: {result.passed}/{result.total_tests} passed")
```

---

## 🔧 Configuration

### **Timeout Settings**

```python
# In workflows/langgraph_flow.py
MAX_EXECUTION_TIME = 300.0  # 5 minutes per test
WORKFLOW_TIMEOUT = 1800.0    # 30 minutes overall
```

### **Retry Settings**

```python
# Per-stage retries
MAX_STAGE_RETRIES = 3

# Overall retries
MAX_RETRIES = 3
```

### **Stage Configuration**

```python
# Make stages optional
def _stage_analyzing(self) -> bool:
    # Returns True even on failure (non-critical)
    return True
```

---

## 🐛 Error Handling

### **Error Isolation**

**Each stage:**
- Isolated execution
- Independent error handling
- Doesn't affect other stages
- Can continue on failure

### **Error Types**

**Critical Errors:**
- Indexing failures
- State corruption
- Timeout exceeded

**Non-Critical Errors:**
- AI analysis failures
- Test generation failures
- Reporting failures

### **Error Recovery**

**Automatic:**
- Retry on failure
- Continue on non-critical errors
- Cleanup on all errors

**Manual:**
- Review error messages
- Fix underlying issues
- Re-run workflow

---

## 📈 Monitoring

### **Workflow Metrics**

**Tracked:**
- Stage completion times
- Retry counts
- Error rates
- Success rates
- Resource usage

### **Logging**

**Logged:**
- Stage starts/completions
- Retry attempts
- Errors/warnings
- Timeout events
- Cleanup operations

---

## ✅ Best Practices

### **Workflow Design**

1. **Isolate Stages:**
   - Independent execution
   - No shared state mutations
   - Clear inputs/outputs

2. **Handle Failures:**
   - Retry on transient errors
   - Continue on non-critical failures
   - Cleanup always

3. **Set Timeouts:**
   - Per-stage timeouts
   - Overall timeout
   - Prevent hangs

4. **Track State:**
   - Update state consistently
   - Log all operations
   - Maintain audit trail

### **Security**

1. **Validate Inputs:**
   - Check all inputs
   - Sanitize paths
   - Verify commands

2. **Isolate Execution:**
   - Sandboxed workspaces
   - No direct code execution
   - All through workflow

3. **Limit Resources:**
   - Timeout enforcement
   - Retry limits
   - Resource cleanup

---

## 🔮 Advanced Usage

### **Custom Stages**

```python
def _stage_custom(self) -> bool:
    """Custom stage"""
    try:
        # Your logic here
        return True
    except Exception as e:
        self.state.add_error(str(e))
        return False

# Add to workflow
self.stages.append(self._stage_custom)
```

### **Conditional Execution**

```python
def _stage_conditional(self) -> bool:
    """Conditional stage"""
    if not self.state.analysis_result:
        self.state.add_warning("Skipping conditional stage")
        return True  # Skip
    
    # Execute if condition met
    return self._execute_conditional_logic()
```

---

## 📚 Related Documentation

- **Setup:** `setup.md`
- **Security:** `SECURITY.md`
- **Main Docs:** `README.md`

---

**Workflow Orchestration Complete!** 🔄

All execution flows through secure, orchestrated workflow with retry guards and cleanup guarantees.

