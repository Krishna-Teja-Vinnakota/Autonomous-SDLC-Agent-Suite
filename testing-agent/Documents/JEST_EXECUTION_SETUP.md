# Jest Execution Setup - Complete Guide

## ✅ What Was Fixed

The test executor agent has been updated to automatically detect and execute Jest tests with coverage reporting.

### Changes Made:

1. **Updated `can_execute_jest()` method**
   - Now checks for `npm` and `package.json` (preferred for local installations)
   - Falls back to `npx` check if npm not available
   - Properly detects Jest installations

2. **Updated `_execute_jest()` method**
   - Uses `npm test -- --coverage --json --verbose` when `package.json` exists
   - Falls back to `npx jest` with coverage flags
   - Automatically includes coverage collection

3. **Updated Command Executor**
   - Added support for `--` separator in npm commands
   - Allows coverage flags (`--coverage`, `--json`, `--verbose`)
   - Updated allowlist to include coverage-related arguments

4. **Coverage Parsing**
   - Already supported via `CoverageParser.parse_jest_coverage()`
   - Reads from `coverage/coverage-final.json`
   - Includes in unified reports automatically

## 🚀 How It Works Now

### Automatic Detection

When the workflow runs:

1. **Test Generation Stage**: Creates Jest test files (e.g., `sample_react_app_for_aitesting.test.jsx`)

2. **Test Execution Stage**: 
   - Detects Jest framework from generated tests
   - Checks if `npm` and `package.json` exist
   - Executes: `npm test -- --coverage --json --verbose`
   - Parses JSON output for test results
   - Collects coverage data from `coverage/coverage-final.json`

3. **Reporting Stage**:
   - Parses coverage data
   - Includes in unified report
   - Shows coverage metrics in UI
   - Generates coverage charts

## 📋 Requirements

For Jest execution to work automatically:

1. ✅ **Node.js installed** (npm comes with it)
2. ✅ **package.json exists** (created during Jest setup)
3. ✅ **Jest installed** (via `npm install` - already done)
4. ✅ **Test files generated** (by test generator agent)

## 🧪 Test Execution Flow

```
Upload File
    ↓
Index Files
    ↓
AI Analysis (optional)
    ↓
Test Strategy
    ↓
Generate Tests → Creates: sample_react_app_for_aitesting.test.jsx
    ↓
Execute Tests → Runs: npm test -- --coverage --json --verbose
    ↓
Parse Results → Extracts: test counts, pass/fail, coverage
    ↓
Generate Report → Shows: test results + coverage metrics
```

## 📊 Coverage Output

After execution, you'll see:

1. **Test Results**:
   - Total tests
   - Passed/Failed/Skipped counts
   - Individual test case results
   - Execution duration

2. **Coverage Metrics**:
   - Total coverage percentage
   - Lines covered/total
   - Branches covered/total
   - Functions covered/total
   - Per-file coverage breakdown

3. **Visual Reports**:
   - Pass/Fail pie chart
   - Coverage bar chart
   - Downloadable JSON/HTML reports

## 🔧 Troubleshooting

### Issue: "jest not available, skipping"

**Solution**: 
- Ensure `package.json` exists in project directory
- Run `npm install` to install Jest dependencies
- Verify `npm` command is available: `npm --version`

### Issue: "No execution results, skipping reporting"

**Solution**:
- Check that test files were generated successfully
- Verify Jest tests can run manually: `npm test`
- Check execution logs for errors

### Issue: Coverage not showing

**Solution**:
- Ensure `--coverage` flag is included (now automatic)
- Check that `coverage/coverage-final.json` exists after test run
- Verify Jest config allows coverage collection

## 📝 Example Workflow

1. **Upload** `sample_react_app_for_aitesting.jsx`
2. **Index** - File is indexed
3. **Run Full Workflow** - Click button in UI
4. **Generate Tests** - Creates `sample_react_app_for_aitesting.test.jsx`
5. **Execute Tests** - Automatically runs Jest with coverage
6. **View Results** - See test results + coverage in UI

## ✅ Verification

To verify Jest execution works:

```bash
# In project directory
npm test -- --coverage --json --verbose
```

Expected output:
- Test results (pass/fail)
- Coverage summary
- `coverage/coverage-final.json` file created

## 🎯 Next Steps

The system now automatically:
1. ✅ Detects Jest installations
2. ✅ Executes Jest tests with coverage
3. ✅ Parses test results
4. ✅ Collects coverage data
5. ✅ Includes in reports

No manual intervention needed - just upload your file and run the workflow!

