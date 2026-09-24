# Test Execution Guide

Complete guide to autonomous test execution with retry logic and failure analysis.

---

## 🎯 Overview

AutoSDLC Test Agent can now **automatically execute tests** with:

1. **Safe subprocess execution** (no `shell=True`)
2. **Command allowlist** (only approved commands)
3. **Automatic retry** (up to 3 attempts)
4. **Result parsing** (pass/fail/skip counts)
5. **Failure analysis** (AI-powered insights)
6. **Execution logs** (stdout, stderr, exit codes)

---

## 🚀 Quick Start

### Prerequisites

**For Jest (JavaScript/TypeScript):**
- ✅ Node.js installed
- ✅ npm or npx available
- ✅ Jest configured (usually automatic)

**For Pytest (Python):**
- ✅ Python installed
- ✅ pytest package installed (`pip install pytest`)

### Steps

1. **Generate tests** (see `TEST_GENERATION_GUIDE.md`)
2. **Click "Run Tests"** button
3. **Wait for execution** (with status updates)
4. **Review results** in UI
5. **Check failure analysis** (if any failures)

---

## 🔒 Security Features

### **Command Allowlist**

Only these commands are allowed:

| Command | Purpose | Allowed Args |
|---------|---------|--------------|
| `npx jest` | Run Jest tests | `--json`, `--verbose`, `--no-cache`, `--ci` |
| `npm test` | Run npm test script | `run`, `test:unit` |
| `pytest` | Run Pytest tests | `-v`, `--json-report`, `-x`, `--tb=short` |
| `python -m pytest` | Alternative pytest | Same as pytest |

### **Security Measures**

1. ✅ **No `shell=True`** - Prevents shell injection
2. ✅ **Command validation** - Only allowlisted commands
3. ✅ **Argument validation** - Only safe arguments
4. ✅ **Sandboxed execution** - Runs in project folder only
5. ✅ **Timeout enforcement** - 5 minutes default
6. ✅ **No arbitrary code** - Cannot execute user-defined scripts

---

## 🔄 Retry Logic

### **Automatic Retries**

Tests are retried up to **3 times** on failure:

**Attempt 1:** Initial execution
- If successful → Done ✓
- If failed → Retry

**Attempt 2:** First retry
- If successful → Done ✓
- If failed → Retry

**Attempt 3:** Final attempt
- Always completes (success or failure)
- Result displayed regardless

### **When to Retry**

Retries are useful for:
- ❌ **Flaky tests** (timing issues)
- ❌ **Network failures** (transient)
- ❌ **Resource contention** (temporary)

Retries won't help:
- ✅ **Logic errors** (code bugs)
- ✅ **Syntax errors** (test errors)
- ✅ **Missing dependencies** (setup issues)

---

## 📊 Result Parsing

### **Jest Results**

**JSON Output Parsing:**
```json
{
  "numTotalTests": 10,
  "numPassedTests": 8,
  "numFailedTests": 2,
  "numPendingTests": 0,
  "testResults": [...]
}
```

**Captured Information:**
- ✅ Total tests
- ✅ Passed/Failed/Skipped counts
- ✅ Individual test cases
- ✅ Error messages
- ✅ Test durations
- ✅ File locations

### **Pytest Results**

**Verbose Output Parsing:**
```
test_file.py::test_name PASSED
test_file.py::test_other FAILED
=== 1 failed, 1 passed in 0.50s ===
```

**Captured Information:**
- ✅ Total tests
- ✅ Passed/Failed/Skipped counts
- ✅ Individual test names
- ✅ Test locations
- ✅ Execution duration

---

## 🔍 Failure Analysis

### **Automatic Analysis**

When tests fail, the system automatically:

1. **Identifies patterns** in error messages
2. **Categorizes failures** (timeout, dependency, assertion, etc.)
3. **Provides recommendations** (actionable fixes)
4. **Assigns severity** (critical/high/medium/low)

### **Analysis Types**

**Basic Analysis (No AI):**
- Pattern matching on error messages
- Common issue detection
- Standard recommendations

**AI-Powered Analysis (With Gemini):**
- Contextual understanding
- Smart recommendations
- Root cause analysis
- Custom insights

### **Severity Levels**

| Severity | Failure Rate | Color | Urgency |
|----------|--------------|-------|---------|
| **Critical** | ≥50% | 🔴 | Immediate |
| **High** | 30-50% | 🟠 | Soon |
| **Medium** | 10-30% | 🟡 | Normal |
| **Low** | <10% | 🟢 | Minor |

---

## 🎨 UI Features

### **Execution Results Display**

**Metrics:**
- Total tests
- ✅ Passed count
- ❌ Failed count
- ⏭️ Skipped count
- ⏱️ Duration

**Test Cases:**
- Individual test status
- Test names
- Execution times
- Error messages (expandable)

**Execution Logs:**
- Standard output (stdout)
- Standard error (stderr)
- Full command output

**Failure Analysis:**
- Severity badge
- Summary
- Likely causes (list)
- Recommendations (actionable)
- Affected tests

---

## 💡 Common Scenarios

### **Scenario 1: All Tests Pass** ✅

```
Jest Results
Total: 10
✅ Passed: 10
❌ Failed: 0

Status: All tests passed! ✓
```

**Next Steps:**
- ✅ Code is working correctly
- ✅ Ready for deployment
- ✅ Update documentation

### **Scenario 2: Some Tests Fail** ⚠️

```
Jest Results
Total: 10
✅ Passed: 7
❌ Failed: 3

Failure Analysis
Severity: MEDIUM
Likely Causes:
- Assertion failures
Recommendations:
- Review test expectations
```

**Next Steps:**
1. Review failure analysis
2. Check error messages
3. Fix failing tests or code
4. Re-run tests

### **Scenario 3: All Tests Fail** 🔴

```
Pytest Results
Total: 8
✅ Passed: 0
❌ Failed: 8

Failure Analysis
Severity: CRITICAL
Likely Causes:
- Missing dependencies
Recommendations:
- Install missing packages
```

**Next Steps:**
1. Check stderr output
2. Install dependencies
3. Fix setup issues
4. Re-run tests

### **Scenario 4: Timeout** ⏰

```
Jest Results
Status: Timed out after 300s

Failure Analysis
Likely Causes:
- Tests timing out
Recommendations:
- Increase timeout
- Optimize slow tests
```

**Next Steps:**
1. Review slow tests
2. Optimize operations
3. Increase timeout if needed
4. Re-run tests

---

## 🛠️ Configuration

### **Timeout Settings**

Default: **300 seconds** (5 minutes)

**To adjust** (edit `agents/test_executor_agent.py`):
```python
result = executor.execute_tests(
    framework,
    timeout=600  # 10 minutes
)
```

### **Retry Count**

Default: **3 attempts**

**To adjust** (edit `agents/test_executor_agent.py`):
```python
MAX_RETRIES = 5  # Change to 5 attempts
```

### **Command Options**

**Jest Options:**
```python
CommandExecutor.build_jest_command({
    'json': True,        # JSON output
    'verbose': True,     # Detailed logs
    'no_cache': True,    # Clear cache
    'ci': True           # CI mode
})
```

**Pytest Options:**
```python
CommandExecutor.build_pytest_command({
    'verbose': True,     # Detailed output
    'traceback': True,   # Short tracebacks
    'no_color': True     # No ANSI colors
})
```

---

## 🐛 Troubleshooting

### "npx command not available"

**Cause:** Node.js/npm not installed

**Solution:**
1. Install Node.js from https://nodejs.org
2. Verify: `npx --version`
3. Re-run tests

### "pytest command not available"

**Cause:** pytest not installed

**Solution:**
```bash
pip install pytest
pytest --version
```

### "Command timed out"

**Cause:** Tests taking too long

**Solutions:**
1. Increase timeout setting
2. Optimize slow tests
3. Check for infinite loops
4. Mock external services

### "Permission denied"

**Cause:** File system permissions

**Solution:**
1. Check file permissions
2. Ensure project folder is accessible
3. Run as appropriate user

### "No tests found"

**Cause:** Tests not in expected location

**Solution:**
1. Verify test files exist
2. Check test naming conventions
3. Ensure proper structure

---

## 📈 Best Practices

### **Before Execution**

1. ✅ Ensure dependencies installed
2. ✅ Verify test files generated
3. ✅ Check project structure
4. ✅ Review test code

### **During Execution**

1. ✅ Monitor status updates
2. ✅ Check for warnings
3. ✅ Note execution times
4. ✅ Watch for timeouts

### **After Execution**

1. ✅ Review all results
2. ✅ Check failure analysis
3. ✅ Read error messages
4. ✅ Fix issues found
5. ✅ Re-run after fixes

### **For CI/CD**

1. ✅ Use `--ci` flag for Jest
2. ✅ Set appropriate timeouts
3. ✅ Capture all logs
4. ✅ Fail on any test failure
5. ✅ Report results

---

## 🔮 Advanced Usage

### **Custom Test Commands**

While the system uses standard commands, you can prepare your project:

**Jest Setup (`package.json`):**
```json
{
  "scripts": {
    "test": "jest --coverage"
  }
}
```

**Pytest Setup (`pytest.ini`):**
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*
```

### **Environment Variables**

Tests run with project directory as working directory:
- `process.cwd()` = project folder
- Environment inherited from parent
- No custom env vars by default

---

## 📊 Workflow

### **Complete Execution Workflow**

```
1. Generate Tests
   ↓
2. Click "Run Tests"
   ↓
3. System checks available commands
   ↓
4. Executes Jest (if applicable)
   ├─ Attempt 1
   ├─ Attempt 2 (if failed)
   └─ Attempt 3 (if failed)
   ↓
5. Executes Pytest (if applicable)
   ├─ Attempt 1
   ├─ Attempt 2 (if failed)
   └─ Attempt 3 (if failed)
   ↓
6. Parses results
   ↓
7. Analyzes failures (if any)
   ↓
8. Displays in UI
```

---

## 🎓 Example Outputs

### **Successful Jest Execution**

```
Jest Results
Total: 15
✅ Passed: 15
❌ Failed: 0
⏱️ Duration: 2.34s

Status: All tests passed! ✓
```

### **Failed Pytest Execution with Analysis**

```
Pytest Results
Total: 10
✅ Passed: 7
❌ Failed: 3
⏱️ Duration: 1.52s

Failure Analysis
Severity: 🟡 MEDIUM

Likely Causes:
1. Assertion failures in business logic
2. Incorrect test expectations

Recommendations:
1. Review test expectations
2. Check implementation details
3. Update assertions as needed

Affected Tests:
- test_calculate_total
- test_apply_discount
- test_validate_input
```

---

## 📚 Related Documentation

- **Test Generation:** `TEST_GENERATION_GUIDE.md`
- **Setup:** `VERTEX_AI_SETUP.md`
- **Quick Reference:** `QUICK_REFERENCE.md`
- **Main Docs:** `README.md`

---

**Ready to execute!** 🏃

Generate tests, click "Run Tests", and see your code in action!

