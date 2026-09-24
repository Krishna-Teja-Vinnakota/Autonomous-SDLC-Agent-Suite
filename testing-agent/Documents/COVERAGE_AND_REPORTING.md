# Coverage and Reporting Guide

Complete guide to test coverage parsing and comprehensive reporting with visualizations.

---

## 🎯 Overview

AutoSDLC Test Agent now provides **comprehensive test reporting** with:

1. **Coverage Parsing** (Jest & pytest-cov)
2. **Unified Reports** (JSON & HTML)
3. **Interactive Visualizations** (Plotly charts)
4. **Downloadable Reports** (for sharing)
5. **Coverage Metrics** (lines, branches, functions)

---

## 📊 Features

### **1. Coverage Parsing**

**Jest Coverage:**
- Parses `coverage/coverage-final.json`
- Extracts lines, branches, functions coverage
- Per-file coverage details
- Total coverage percentage

**Pytest Coverage:**
- Parses `coverage.json` (from pytest-cov)
- Extracts line coverage
- Per-file coverage details
- Total coverage percentage

### **2. Unified Reports**

**Combines:**
- Test execution results
- Coverage data
- Individual test cases
- Pass/fail metrics
- Timestamps

**Formats:**
- JSON (machine-readable)
- HTML (human-readable)

### **3. Visualizations**

**Pass/Fail Pie Chart:**
- Visual distribution of test results
- Color-coded (green/red/amber)
- Shows percentages and counts
- Interactive (Plotly)

**Coverage Bar Chart:**
- Coverage by framework
- Color gradient (red→amber→green)
- Percentage labels
- Comparison across frameworks

### **4. Downloadable Reports**

**JSON Report:**
- Complete test data
- Machine-readable format
- For CI/CD integration
- Timestamped filename

**HTML Report:**
- Beautiful styled report
- Metrics dashboard
- Coverage details
- Test case listing
- Shareable

---

## 🚀 Usage

### **Enable Coverage**

**For Jest:**
```json
// package.json
{
  "scripts": {
    "test": "jest --coverage"
  },
  "jest": {
    "collectCoverage": true,
    "coverageDirectory": "coverage"
  }
}
```

**For Pytest:**
```bash
# Install pytest-cov
pip install pytest-cov

# Run with coverage
pytest --cov=. --cov-report=json
```

### **Generate Reports**

1. **Run tests** with "Run Tests" button
2. **Wait for completion** (auto-generates report)
3. **View visualizations** in UI
4. **Download reports** (JSON/HTML)

---

## 📈 Report Contents

### **Unified Test Report**

```json
{
  "timestamp": "2024-01-15T10:30:00",
  "total_tests": 25,
  "passed": 23,
  "failed": 2,
  "skipped": 0,
  "pass_rate": 92.0,
  "total_coverage": 85.5,
  "execution_results": {
    "jest": {
      "total": 15,
      "passed": 14,
      "failed": 1,
      "duration": 2.34
    },
    "pytest": {
      "total": 10,
      "passed": 9,
      "failed": 1,
      "duration": 1.52
    }
  },
  "coverage_reports": {
    "jest": {
      "total_coverage": 87.3,
      "lines_covered": 234,
      "lines_total": 268,
      "branches_covered": 45,
      "branches_total": 52
    },
    "pytest": {
      "total_coverage": 83.2,
      "lines_covered": 145,
      "lines_total": 174
    }
  },
  "test_cases": [...]
}
```

### **HTML Report Sections**

1. **Header**
   - Overall status
   - Summary text
   - Timestamp

2. **Metrics Dashboard**
   - Total tests
   - Passed/Failed/Skipped
   - Pass rate
   - Coverage percentage

3. **Coverage Details**
   - Progress bar
   - Per-framework breakdown
   - Lines/Branches/Functions

4. **Test Cases**
   - Individual results
   - Status icons
   - Error messages
   - Durations

---

## 📊 Visualizations

### **Pass/Fail Pie Chart**

**Shows:**
- ✅ Passed (green)
- ❌ Failed (red)
- ⏭️ Skipped (amber)

**Features:**
- Donut chart style
- Percentage labels
- Count values
- Interactive tooltips

### **Coverage Bar Chart**

**Shows:**
- Coverage by framework
- Percentage per framework
- Color gradient based on coverage

**Color Scale:**
- 🔴 Red: 0-40% (low)
- 🟠 Amber: 40-80% (moderate)
- 🟢 Green: 80-100% (good)

---

## 💡 Coverage Levels

### **What is Good Coverage?**

| Coverage | Rating | Color | Recommendation |
|----------|--------|-------|----------------|
| 80-100% | Excellent | 🟢 | Maintain it! |
| 60-80% | Good | 🟡 | Improve key areas |
| 40-60% | Moderate | 🟠 | Add more tests |
| 0-40% | Low | 🔴 | Urgent: Add tests |

### **Coverage Types**

**Line Coverage:**
- Which lines of code are executed
- Most common metric
- Shows untested code paths

**Branch Coverage:**
- Which conditional branches taken
- If/else, switch cases
- More thorough than line coverage

**Function Coverage:**
- Which functions are called
- Shows unused code
- Helps identify dead code

---

## 🎨 UI Features

### **Report Display**

**Summary Banner:**
- ✅ Green for all pass
- ⚠️ Amber for failures
- Summary text

**Metrics Cards:**
- 4 key metrics
- Large numbers
- Color-coded

**Interactive Charts:**
- Hover tooltips
- Responsive sizing
- Export options (PNG, SVG)

**Download Buttons:**
- JSON report
- HTML report
- Timestamped filenames

---

## 🔧 Configuration

### **Jest Coverage Config**

```json
// jest.config.js
module.exports = {
  collectCoverage: true,
  coverageDirectory: "coverage",
  coverageReporters: ["json", "html", "text"],
  collectCoverageFrom: [
    "src/**/*.{js,jsx,ts,tsx}",
    "!src/**/*.test.{js,jsx,ts,tsx}"
  ],
  coverageThreshold: {
    global: {
      branches: 80,
      functions: 80,
      lines: 80,
      statements: 80
    }
  }
};
```

### **Pytest Coverage Config**

```ini
# pytest.ini or setup.cfg
[tool:pytest]
addopts = --cov=. --cov-report=json --cov-report=html

[coverage:run]
omit = 
    */tests/*
    */venv/*
    */migrations/*

[coverage:report]
precision = 2
show_missing = True
```

---

## 📥 Report Files

### **Location**

All reports saved in:
```
project/
└── reports/
    ├── test-report.json
    └── test-report.html
```

### **JSON Report**

**Use for:**
- CI/CD integration
- Automated processing
- Trend analysis
- Data storage

**Example:**
```bash
# Parse with jq
cat test-report.json | jq '.pass_rate'

# Check in CI
if [ $(jq '.failed' test-report.json) -gt 0 ]; then
    exit 1
fi
```

### **HTML Report**

**Use for:**
- Team sharing
- Documentation
- Presentations
- Archive

**Features:**
- Self-contained (no external dependencies)
- Mobile-friendly
- Print-friendly
- Beautiful styling

---

## 🐛 Troubleshooting

### "No coverage data available"

**Cause:** Tests run without coverage

**Solution:**
```bash
# Jest
npm test -- --coverage

# Pytest
pytest --cov=. --cov-report=json
```

### "Coverage file not found"

**Cause:** Coverage not generated

**Solution:**
1. Check test configuration
2. Ensure coverage tools installed
3. Verify coverage output directory
4. Re-run tests with coverage enabled

### "Coverage parsing failed"

**Cause:** Unsupported coverage format

**Solution:**
1. Use standard Jest/pytest coverage formats
2. Check coverage file location
3. Verify JSON format validity

---

## 📈 Best Practices

### **Coverage Goals**

1. **Start with 60%** - Basic coverage
2. **Aim for 80%** - Good coverage
3. **Maintain 80%+** - Excellent

### **What to Test**

**High Priority:**
- Business logic
- User interactions
- API endpoints
- Data transformations

**Medium Priority:**
- Utilities
- Helpers
- Validators
- Formatters

**Lower Priority:**
- UI components (appearance)
- Constants
- Simple getters/setters

### **Coverage ≠ Quality**

**Remember:**
- 100% coverage doesn't mean bug-free
- Quality of tests matters more
- Test edge cases, not just happy paths
- Review tests regularly

---

## 🎓 Example Reports

### **Example 1: Excellent Results**

```
📊 Unified Test Report
✅ All 25 tests passed! | Pass rate: 100.0% | Excellent coverage: 92.3%

Metrics:
- Total Tests: 25
- Pass Rate: 100.0%
- Coverage: 92.3%
- Status: ✅ Pass

Coverage by Framework:
- JEST: 94.5%
- PYTEST: 90.1%
```

### **Example 2: Needs Improvement**

```
📊 Unified Test Report
⚠️ 3 out of 20 tests failed | Pass rate: 85.0% | Moderate coverage: 65.2%

Metrics:
- Total Tests: 20
- Pass Rate: 85.0%
- Coverage: 65.2%
- Status: ❌ Fail

Recommendations:
- Fix failing tests
- Increase coverage to 80%+
- Add tests for uncovered code paths
```

---

## 🔮 Advanced Usage

### **CI/CD Integration**

```yaml
# .github/workflows/test.yml
- name: Run Tests
  run: |
    npm test -- --coverage
    pytest --cov=. --cov-report=json

- name: Upload Report
  uses: actions/upload-artifact@v2
  with:
    name: test-report
    path: reports/test-report.html
```

### **Coverage Trends**

Track coverage over time:
```bash
# Save historical data
echo "$(date),$(jq '.total_coverage' test-report.json)" >> coverage-history.csv

# Plot trends (with matplotlib, etc.)
python plot_coverage_trends.py
```

### **Custom Thresholds**

Set minimum coverage requirements:
```python
import json

with open('test-report.json') as f:
    report = json.load(f)

if report['total_coverage'] < 80:
    print("❌ Coverage below threshold")
    exit(1)
```

---

## 📚 Related Documentation

- **Test Execution:** `TEST_EXECUTION_GUIDE.md`
- **Test Generation:** `TEST_GENERATION_GUIDE.md`
- **Main Docs:** `README.md`

---

**Ready to track your coverage!** 📊

Run tests with coverage enabled and get beautiful reports instantly!

