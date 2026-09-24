# Test Generation Guide

Complete guide to using the autonomous test generation feature.

---

## 🎯 Overview

AutoSDLC Test Agent can now **automatically generate high-quality tests** for your projects using Vertex AI Gemini. The system:

1. **Analyzes** your project structure
2. **Strategizes** which files need testing
3. **Generates** Jest or Pytest tests automatically
4. **Saves** tests in your project folder
5. **Allows downloads** from the UI

---

## 🚀 Quick Start

### Prerequisites

- ✅ Vertex AI configured (see `VERTEX_AI_SETUP.md`)
- ✅ Project uploaded/analyzed
- ✅ AI analysis completed

### Steps

1. **Upload your project** (any method: GitHub, ZIP, Folder, File)
2. **Wait for AI analysis** to complete
3. **Click "Generate Tests"** button
4. **View generated tests** in the UI
5. **Download** individual test files or review code

---

## 🧠 How It Works

### **Phase 1: Strategy Determination**

The `StrategyAgent` analyzes your project and decides:

- **Which files to test** (source files only, not configs/docs)
- **Test priority** (high/medium/low based on complexity)
- **Test framework** (Jest for JS/TS, Pytest for Python)
- **Test type** (unit, integration, component)
- **Complexity level** (simple, moderate, complex)

**Example Strategy:**
```
Source: src/components/Button.tsx
Test: src/components/Button.test.tsx
Priority: Medium
Framework: Jest
Type: Component test
```

### **Phase 2: Test Generation**

The `TestGeneratorAgent` generates actual test code:

- **Reads source file** (limited to 3000 chars for efficiency)
- **Builds intelligent prompt** with framework-specific requirements
- **Uses Gemini AI** to generate contextual tests
- **Extracts code** from response
- **Saves to project** folder (never overwrites existing)

---

## 📝 Test Generation Rules

### **General Rules**

1. ✅ **One test file per source file**
2. ✅ **Never overwrite existing tests**
3. ✅ **Never overwrite source files**
4. ✅ **Save tests adjacent to source** (same directory)
5. ✅ **Limit to 10 files** per generation (for demo/speed)

### **Jest Tests (JavaScript/TypeScript)**

**Conventions:**
- Test file: `filename.test.js` or `filename.test.ts`
- React components: `Component.test.tsx`
- Framework: Jest + React Testing Library (for React)

**Requirements:**
- ✅ Use modern ES6+ syntax
- ✅ Descriptive test names with "should"
- ✅ Arrange-Act-Assert pattern
- ✅ Mock external dependencies
- ✅ Test edge cases and errors
- ❌ **NO snapshot tests** (avoid `toMatchSnapshot`)

**React-Specific:**
- ✅ Use `@testing-library/react`
- ✅ Use `screen` queries (`screen.getByRole`, etc.)
- ✅ Test user interactions
- ✅ Test rendering and behavior
- ❌ Avoid shallow rendering

### **Pytest Tests (Python)**

**Conventions:**
- Test file: `test_filename.py`
- Framework: Pytest

**Requirements:**
- ✅ Python 3.9+ features
- ✅ Descriptive names: `test_should_...`
- ✅ Use fixtures where appropriate
- ✅ Mock with `pytest-mock` or `unittest.mock`
- ✅ Clear assertion messages
- ✅ Test edge cases with `pytest.raises`

**Django/Flask-Specific:**
- ✅ Use framework test utilities
- ✅ Use `pytest-django` fixtures (Django)
- ✅ Test route handlers (Flask)

---

## 🎨 Generated Test Examples

### **Jest Example (React Component)**

```typescript
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Button from './Button';

describe('Button Component', () => {
  test('should render with correct text', () => {
    // Arrange
    const buttonText = 'Click me';
    
    // Act
    render(<Button>{buttonText}</Button>);
    
    // Assert
    expect(screen.getByRole('button')).toHaveTextContent(buttonText);
  });

  test('should call onClick handler when clicked', async () => {
    // Arrange
    const handleClick = jest.fn();
    const user = userEvent.setup();
    
    // Act
    render(<Button onClick={handleClick}>Click</Button>);
    await user.click(screen.getByRole('button'));
    
    // Assert
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  test('should be disabled when disabled prop is true', () => {
    // Arrange & Act
    render(<Button disabled>Disabled</Button>);
    
    // Assert
    expect(screen.getByRole('button')).toBeDisabled();
  });
});
```

### **Pytest Example (Python Function)**

```python
import pytest
from calculator import add, divide

def test_should_add_two_positive_numbers():
    # Arrange
    a, b = 5, 3
    
    # Act
    result = add(a, b)
    
    # Assert
    assert result == 8, "Sum of 5 and 3 should be 8"

def test_should_add_negative_numbers():
    # Arrange
    a, b = -5, -3
    
    # Act
    result = add(a, b)
    
    # Assert
    assert result == -8, "Sum of negatives should be negative"

def test_should_divide_numbers():
    # Arrange
    a, b = 10, 2
    
    # Act
    result = divide(a, b)
    
    # Assert
    assert result == 5.0, "10 divided by 2 should be 5"

def test_should_raise_error_on_division_by_zero():
    # Arrange
    a, b = 10, 0
    
    # Act & Assert
    with pytest.raises(ZeroDivisionError):
        divide(a, b)
```

---

## 💡 Features

### **Smart File Selection**

The system automatically:
- ✅ Identifies testable source files
- ✅ Skips test files (no recursive testing)
- ✅ Skips config files
- ✅ Skips documentation
- ✅ Skips very small files (< 10 lines)
- ✅ Prioritizes by complexity

### **Framework Detection**

Automatically detects and uses:
- **React** → Jest + React Testing Library
- **Django** → Pytest + django test utilities
- **Flask** → Pytest + Flask test client
- **Plain JS/TS** → Jest with best practices
- **Plain Python** → Pytest with fixtures

### **Download Options**

Each generated test file has:
- ✅ **Code preview** in UI
- ✅ **Download button** for individual files
- ✅ **Syntax highlighting**
- ✅ **Test count display**

---

## 🛡️ Safety Features

### **File Protection**

1. **Never Overwrites Source Files**
   - Test files are created separately
   - Source files are read-only

2. **Never Overwrites Existing Tests**
   - If test file exists, shows warning
   - Original tests are preserved
   - User must manually merge if desired

3. **Sandboxed Execution**
   - All files saved in workspace folder
   - Isolated from user's main system

### **Content Safety**

- ✅ Only source code sent to AI (not secrets/env files)
- ✅ Limited to 3000 chars per file (token efficiency)
- ✅ No binary files processed
- ✅ Safe error handling

---

## 📊 Test Strategy

### **Priority Levels**

| Priority | Lines of Code | Complexity | Estimated Tests |
|----------|---------------|------------|-----------------|
| **High** | 200+ | Complex | ~8 tests |
| **Medium** | 100-200 | Moderate | ~5 tests |
| **Low** | < 100 | Simple | ~3 tests |

### **Test Types**

| Type | Use Case | Example |
|------|----------|---------|
| **Unit** | Pure functions, utilities | `add()`, `format()` |
| **Component** | React/Vue components | `<Button>`, `<Form>` |
| **Integration** | API calls, database | `fetchUser()`, `saveOrder()` |

---

## 💰 Cost Implications

### **Token Usage**

Per file test generation:
- **Input:** ~1,000-1,500 tokens (source code + prompt)
- **Output:** ~500-1,000 tokens (generated test)

### **Estimated Costs**

| Files | Approx. Cost (gemini-1.5-flash) |
|-------|----------------------------------|
| 10 | $0.02-0.05 |
| 50 | $0.10-0.25 |
| 100 | $0.20-0.50 |

**Note:** Currently limited to 10 files per generation for cost control.

---

## 🔧 Configuration

### **Adjust Generation Limits**

Edit `app.py`:

```python
# Current: Limited to 10 files
strategies_to_generate = test_strategy.strategies[:10]

# Change to generate more:
strategies_to_generate = test_strategy.strategies[:50]  # 50 files
```

### **Customize Prompts**

Edit `agents/test_generator_agent.py`:
- Modify `_build_jest_prompt()` for Jest customization
- Modify `_build_pytest_prompt()` for Pytest customization

### **Change Test Naming**

Edit `agents/strategy_agent.py` → `_generate_basic_strategies()`:

```python
# Jest: Change from filename.test.ts to filename.spec.ts
test_file = str(source_path.parent / f"{source_path.stem}.spec{source_path.suffix}")

# Pytest: Change from test_filename.py to filename_test.py
test_file = str(source_path.parent / f"{source_path.stem}_test{source_path.suffix}")
```

---

## 🐛 Troubleshooting

### "No testable files found"

**Cause:** No source files detected, or all filtered out

**Solution:**
- Ensure project has `.js`, `.ts`, `.py` files
- Check that files are > 10 lines
- Verify files aren't in ignored directories

### "Test file already exists"

**Cause:** Test file already present in project

**Solution:**
- Review existing test
- Manually delete if you want regeneration
- Or merge manually with generated test

### "Failed to generate test content"

**Cause:** Gemini API error or invalid response

**Solution:**
- Check Vertex AI configuration
- Verify API quotas not exceeded
- Check logs for detailed error

### Empty/Invalid Generated Tests

**Cause:** Source file too complex or unusual structure

**Solution:**
- Review generated code in UI
- Manually adjust if needed
- Report edge cases for improvement

---

## ✅ Best Practices

### **Before Generation**

1. ✅ Ensure Vertex AI is configured
2. ✅ Verify project analysis completed
3. ✅ Review which files will be tested
4. ✅ Backup existing tests (if any)

### **After Generation**

1. ✅ Review generated tests in UI
2. ✅ Download tests to your project
3. ✅ Run tests to ensure they work
4. ✅ Adjust as needed for your use case
5. ✅ Add to version control

### **Quality Assurance**

1. ✅ Run `npm test` or `pytest` to verify
2. ✅ Check test coverage
3. ✅ Fix any linting issues
4. ✅ Add missing edge cases
5. ✅ Update tests as code evolves

---

## 📈 Workflow

### **Complete Generation Workflow**

```
1. Upload Project
   ↓
2. File Indexing (automatic)
   ↓
3. AI Analysis (automatic if configured)
   ↓
4. Click "Generate Tests"
   ↓
5. Strategy Determination (automatic)
   ↓
6. Test Generation (automatic)
   ↓
7. Review Tests in UI
   ↓
8. Download Tests
   ↓
9. Add to Your Project
   ↓
10. Run & Verify
```

---

## 🎓 Examples by Framework

### **React + TypeScript**

**Input:** `Button.tsx` (React component)
**Output:** `Button.test.tsx` with:
- Rendering tests
- User interaction tests
- Props validation
- Edge cases

### **Node.js + JavaScript**

**Input:** `api.js` (Express routes)
**Output:** `api.test.js` with:
- Route handler tests
- Request/response tests
- Error handling
- Middleware tests

### **Python + Django**

**Input:** `views.py` (Django views)
**Output:** `test_views.py` with:
- View tests
- Template rendering
- Database operations
- Authentication tests

---

## 🔮 Future Enhancements

- [ ] Batch download (all tests as ZIP)
- [ ] Test execution in sandbox
- [ ] Coverage reporting
- [ ] Test quality scoring
- [ ] Iterative test improvement
- [ ] Custom test templates

---

## 📚 Related Documentation

- **Setup:** `VERTEX_AI_SETUP.md`
- **Quick Reference:** `QUICK_REFERENCE.md`
- **Main Docs:** `README.md`

---

**Ready to generate tests!** 🧪

Upload a project, wait for analysis, and click "Generate Tests"!

