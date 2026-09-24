# Feature-Level Testing System

## 🎯 Overview

The SDLC Testing Agent now enforces **strict feature-level testing** for all React/Next.js components. This ensures tests validate user-observable behavior, not implementation details.

## 🚀 Quick Start

### Validate an Existing Test

```bash
python validate_test.py index.test.tsx
```

### Generate Feature Tests

The system automatically generates feature-level tests for React components:

```bash
python app.py
# Upload your React component (e.g., index.tsx)
# System generates: component-name.feature.test.tsx
```

## 📊 How It Works

### 1. Automatic Classification

Every test is scored using this system:

**Feature Signals (+1 point each):**
- `userEvent` usage
- Real wrappers (`pdpWrapper`, `renderWeb`)
- Factory functions (`mockPdpProduct`)
- User actions (`pdpUserActions`)
- `getByRole` queries
- WHEN clause test names

**Unit Test Signals (-2 points each):**
- `jest.mock()` for application code
- Mocked context providers
- Translation key assertions
- Implementation detail tests
- `fireEvent` usage

### 2. Score Interpretation

| Score | Classification | Verdict |
|-------|----------------|---------|
| ≥ 4 | FEATURE TEST | ✅ ACCEPTED |
| 1-3 | HYBRID | ❌ REJECTED |
| ≤ 0 | UNIT TEST | ❌ REJECTED |

### 3. Example Results

**Bad Test (index.test.tsx):**
```
Feature Score: 4
Unit Score: 14
Total Score: -10
Classification: UNIT
Verdict: REJECTED ❌
```

**Good Test (select-size.feature.test.tsx):**
```
Feature Score: 9
Unit Score: 2
Total Score: 7
Classification: FEATURE
Verdict: ACCEPTED ✅
```

## 📁 Key Files

### Documentation
- **`FEATURE_TESTING_GUIDE.md`** - Complete testing guide with examples
- **`FEATURE_TESTING_QUICK_REF.md`** - Quick reference card
- **`FEATURE_TESTING_IMPLEMENTATION.md`** - Technical implementation details

### Code
- **`tools/test_validator.py`** - Core validator module
- **`validate_test.py`** - CLI validation script
- **`agents/test_generator_agent.py`** - Test generator with feature enforcement
- **`agents/strategy_agent.py`** - Strategy agent (defaults React to feature)

### Examples
- **`select-size.feature.test.tsx`** - ✅ GOOD example (feature test)
- **`index.test.tsx`** - ❌ BAD example (unit test)

## ✅ What Changed

### Before
- Generated unit/component tests
- Allowed mocking context and hooks
- Tested implementation details
- No automatic validation

### After
- ✅ Generates only feature-level tests for React components
- ✅ Automatically validates all generated tests
- ✅ Rejects non-feature tests with specific recommendations
- ✅ Enforces real wrappers and factories
- ✅ Prohibits implementation detail testing

## 🎯 Feature Test Requirements

### Must Have (Required)
1. Real application wrappers (`pdpWrapper`, `renderWeb`)
2. Factory functions for test data (`mockPdpProduct`)
3. `userEvent` for interactions (not `fireEvent`)
4. User-visible assertions (`getByRole`, visible text)
5. GIVEN/WHEN/THEN test structure
6. Proper cleanup (`cleanupApolloClient`)

### Must NOT Have (Prohibited)
1. `jest.mock()` for application code
2. Mocked context providers
3. Translation key assertions
4. Implementation detail tests (scrollIntoView, useEffect)
5. `fireEvent` usage
6. className tests (except user-visible state)

## 📝 Test Template

```typescript
import { screen } from '@testing-library/react'
import { userEvent } from '@testing-library/user-event'
import { ComponentName } from './index'
import { mockPdpProduct } from '@mocks/factories'
import { pdpUserActions } from '@test-utils/user-actions'
import { pdpWrapper, renderWeb } from '@test-utils/render'
import { cleanupApolloClient } from '@test-utils/apollo'

describe('Feature Name', () => {
  let pdpActions: ReturnType<typeof pdpUserActions>
  let mockProduct: ReturnType<typeof createMockProduct>

  const renderComponent = (product = mockProduct) => 
    renderWeb(<ComponentName />, { wrapper: pdpWrapper(product) })

  beforeEach(() => {
    pdpActions = pdpUserActions(userEvent.setup())
    mockProduct = mockPdpProduct()
  })

  afterEach(async () => {
    await cleanupApolloClient()
    jest.clearAllMocks()
  })

  it('renders expected UI WHEN condition is met', () => {
    renderComponent()
    expect(screen.getByRole('button', { name: 'Expected' }))
      .toBeInTheDocument()
  })

  it('updates state WHEN user interacts', async () => {
    renderComponent()
    await pdpActions.doAction()
    expect(screen.getByText('Updated')).toBeInTheDocument()
  })
})
```

## 🔍 Validation Commands

### Validate Single Test
```bash
python validate_test.py my-component.test.tsx
```

### Compare Good vs Bad
```bash
# This will FAIL (unit test)
python validate_test.py index.test.tsx

# This will PASS (feature test)
python validate_test.py select-size.feature.test.tsx
```

## 🛠️ Troubleshooting

### Test Rejected as UNIT

**Problem:** Test scored below 4 points

**Solution:**
1. Remove all `jest.mock()` calls
2. Replace `<Context.Provider>` with real wrappers
3. Change assertions from translation keys to visible text
4. Add factory functions
5. Add user actions
6. Re-validate until accepted

### Test Rejected as HYBRID

**Problem:** Test has mix of feature and unit signals

**Solution:**
1. Check validator output for specific issues
2. Remove unit test signals (mocks, implementation tests)
3. Add more feature signals (wrappers, factories, getByRole)
4. Ensure score reaches ≥ 4

### Missing Dependencies

**Problem:** Test can't find wrappers/factories

**Solution:**
Ensure your project has:
- `@test-utils/render` with `pdpWrapper`, `renderWeb`
- `@mocks/factories` with `mockPdpProduct`
- `@test-utils/user-actions` with `pdpUserActions`
- `@test-utils/apollo` with `cleanupApolloClient`

## 📊 Statistics

Run validator on your test suite:

```bash
# Check all tests in a directory
for file in *.test.tsx; do
  python validate_test.py "$file"
done
```

## 🎓 Learning Resources

### Read These First
1. **`FEATURE_TESTING_QUICK_REF.md`** - Quick reference (5 min read)
2. **`FEATURE_TESTING_GUIDE.md`** - Complete guide (20 min read)

### Examples
- **Good:** `select-size.feature.test.tsx`
- **Bad:** `index.test.tsx`

### Compare Side-by-Side
Open both example files and compare:
- Import statements
- Setup/cleanup
- Test assertions
- Test names

## 🚦 CI/CD Integration

Add validation to your pipeline:

```yaml
# .github/workflows/test.yml
- name: Validate Feature Tests
  run: |
    for file in **/*.feature.test.tsx; do
      python validate_test.py "$file" || exit 1
    done
```

## 📈 Benefits

✅ **Refactor-Safe** - Tests don't break when implementation changes  
✅ **User-Focused** - Tests validate actual user experience  
✅ **Maintainable** - Clear, readable tests with consistent structure  
✅ **Comprehensive** - Tests real workflows, not isolated units  
✅ **Automatic** - Validation happens automatically  
✅ **Feedback** - Specific recommendations for fixing issues  

## 🎯 Success Metrics

Your test suite is healthy when:
- All React component tests score ≥ 4
- No `jest.mock()` for application code
- No translation key assertions
- All tests use real wrappers
- All tests use `userEvent`
- Test names follow GIVEN/WHEN/THEN

## 📞 Support

**Issues?** Run the validator and check recommendations:
```bash
python validate_test.py your-test.tsx
```

**Questions?** Refer to:
- `FEATURE_TESTING_GUIDE.md` - Detailed guide
- `FEATURE_TESTING_QUICK_REF.md` - Quick reference
- `select-size.feature.test.tsx` - Working example

---

## 🎉 Summary

The SDLC Testing Agent now enforces feature-level testing for React components. All tests are automatically validated, and non-feature tests are rejected with specific recommendations. This ensures your tests validate real user behavior, not implementation details.

**Remember:** Test what users see and do, not how the code works internally.
