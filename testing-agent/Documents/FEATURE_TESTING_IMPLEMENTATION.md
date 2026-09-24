# Feature-Level Testing Implementation Summary

## Overview

The SDLC Testing Agent has been updated to enforce **strict feature-level testing** for React/Next.js components. The system now:

1. Generates only feature-level tests for React components (not unit/component tests)
2. Automatically validates generated tests
3. Rejects tests that don't meet feature-level standards
4. Provides detailed feedback for improvement

## Changes Made

### 1. Test Generator Agent (`agents/test_generator_agent.py`)

#### Updated Feature Test Prompt
- Added strict feature-level testing enforcement rules
- Prohibited mocking of React context, hooks, and providers
- Required use of real wrappers (`pdpWrapper`, `renderWeb`)
- Required use of factory functions (`mockPdpProduct`, `createMockProduct`)
- Required use of `userEvent` instead of `fireEvent`
- Prohibited testing of implementation details (translation keys, scrollIntoView, className)
- Added GIVEN/WHEN/THEN test naming requirements

#### Integrated Automatic Validation
- Added `TestValidator` integration
- Tests are automatically validated after generation
- Non-feature tests are rejected with detailed feedback
- Validation report is logged for each test

#### Key Changes in Prompts
```python
# Before: Allowed mocking and implementation details
# After: Strict prohibitions and requirements

🔴 CRITICAL PROHIBITIONS FOR FEATURE TESTS:
1. NEVER use jest.mock() for application logic
2. NEVER mock useContext, useTranslations, or any hooks
3. NEVER use direct context providers
4. NEVER assert on translation keys
5. NEVER test scrollIntoView
6. NEVER use fireEvent
```

### 2. Test Validator (`tools/test_validator.py`)

#### New Validator Module
Created a comprehensive test validator that automatically classifies tests as:
- **FEATURE** (Score ≥ 4): Accepted ✅
- **HYBRID** (Score 1-3): Rejected ❌
- **UNIT** (Score ≤ 0): Rejected ❌

#### Scoring System

**Feature Signals (+1 each):**
- `userEvent` usage
- `userEvent.setup()` in beforeEach
- Real wrappers (`pdpWrapper`, `renderWeb`)
- Factory functions (`mockPdpProduct`)
- User action helpers (`pdpUserActions`)
- Async interactions (`await user.click()`)
- Accessibility queries (`getByRole`)
- Proper cleanup (`cleanupApolloClient`)
- GIVEN/WHEN/THEN test names

**Unit Test Signals (-2 each):**
- `jest.mock()` for application code
- Mocked context providers
- Mocked hooks
- Translation key assertions
- Implementation detail tests
- ClassName tests (except user-visible state)
- `fireEvent` usage

### 3. Standalone Validator Script (`validate_test.py`)

Created a command-line tool to validate test files:

```bash
python validate_test.py index.test.tsx
python validate_test.py select-size.feature.test.tsx
```

Features:
- Reads and validates test files
- Generates detailed classification report
- Shows feature/unit scores
- Provides specific recommendations
- Exit code 0 for ACCEPTED, 1 for REJECTED

### 4. Strategy Agent (`agents/strategy_agent.py`)

#### Updated Test Level Classification
Changed the default behavior for React components:

**Before:**
- React components → unit or integration
- Only feature tests for folders with 3+ files

**After:**
- **All React components → feature (DEFAULT)**
- Utilities/helpers → unit
- Python services → integration
- Ensures SelectSize and similar components get feature tests

```python
# DEFAULT: React/Next.js components → FEATURE testing
if source_path.suffix in ['.tsx', '.jsx']:
    logger.info(f"Defaulting React component to FEATURE level testing")
    return 'feature'
```

### 5. Documentation

Created comprehensive documentation:

#### `FEATURE_TESTING_GUIDE.md`
- Complete guide to feature-level testing
- Examples of good vs bad tests
- Mandatory requirements
- Test naming conventions
- Troubleshooting guide
- Reference to validation system

## Validation Results

### Before (index.test.tsx) - REJECTED ❌

```
Feature Score: 4
Unit Score: 14
Total Score: -10
Classification: UNIT
Verdict: REJECTED

Issues:
- jest.mock() for application code
- Mocked context providers
- Translation key assertions
- scrollIntoView tests
- className tests
```

### After (select-size.feature.test.tsx) - ACCEPTED ✅

```
Feature Score: 9
Unit Score: 2
Total Score: 7
Classification: FEATURE
Verdict: ACCEPTED

Features:
- Real wrappers (pdpWrapper, renderWeb)
- Factory functions (mockPdpProduct)
- User actions (pdpUserActions)
- getByRole queries
- WHEN clauses in test names
```

## Usage Examples

### Generating Feature Tests

```python
# The test generator automatically creates feature tests for React components
from agents.test_generator_agent import TestGeneratorAgent
from agents.strategy_agent import StrategyAgent

# Strategy agent now defaults React components to feature level
strategy_result = strategy_agent.determine_test_strategy(...)

# Test generator enforces feature-level rules
tests = test_generator.generate_tests(
    strategies=strategy_result.strategies,
    project_path=project_path,
    analysis_result=analysis_result
)

# Tests are automatically validated
# Non-feature tests are rejected with detailed feedback
```

### Validating Existing Tests

```bash
# Validate a single test file
python validate_test.py my-component.test.tsx

# Output shows:
# - Feature score
# - Unit score
# - Classification (FEATURE/HYBRID/UNIT)
# - Verdict (ACCEPTED/REJECTED)
# - Specific recommendations
```

### Test Structure Required

```typescript
import { screen } from '@testing-library/react'
import { userEvent } from '@testing-library/user-event'
import { SelectSize } from './index'
import { mockPdpProduct } from '@mocks/factories'
import { pdpUserActions } from '@test-utils/user-actions'
import { pdpWrapper, renderWeb } from '@test-utils/render'
import { cleanupApolloClient } from '@test-utils/apollo'

describe('PDP SelectSize Feature', () => {
  let pdpActions: ReturnType<typeof pdpUserActions>
  let mockProduct: ReturnType<typeof createMockProduct>

  const renderComponent = (product = mockProduct) => 
    renderWeb(<SelectSize />, { wrapper: pdpWrapper(product) })

  beforeEach(() => {
    pdpActions = pdpUserActions(userEvent.setup())
    mockProduct = mockPdpProduct()
  })

  afterEach(async () => {
    await cleanupApolloClient()
    jest.clearAllMocks()
  })

  it('renders all sizes WHEN they are in stock', () => {
    renderComponent()
    expect(screen.getByRole('button', { name: 'UK 8' })).toBeInTheDocument()
  })

  it('updates selected size WHEN user clicks', async () => {
    renderComponent()
    await pdpActions.selectSize('UK 8')
    expect(screen.getByRole('button', { name: 'UK 8' })).toHaveClass('bg-grey-1000')
  })
})
```

## Key Requirements Enforced

### ✅ DO (Required)
1. Use real application wrappers
2. Use factory functions for test data
3. Use `userEvent` for interactions
4. Test user-visible behavior only
5. Use `getByRole` queries
6. Write GIVEN/WHEN/THEN test names
7. Use proper cleanup

### ❌ DON'T (Prohibited)
1. Mock hooks or context (`jest.mock`, `ProductDetailsPageContext.Provider`)
2. Test translation keys (`expect(...'Translated pdp.labelSelectSize'...)`)
3. Test implementation details (`scrollIntoView`, `useEffect`)
4. Use `fireEvent` (use `userEvent` instead)
5. Test internal APIs
6. Write unit tests for components

## Benefits

1. **Consistent Quality**: All tests follow feature-level standards
2. **Automatic Validation**: Invalid tests are caught immediately
3. **Clear Feedback**: Specific recommendations for fixing issues
4. **Refactor-Safe**: Tests focus on user behavior, not implementation
5. **Real Integration**: Tests use actual wrappers and factories
6. **Better Coverage**: Tests actual user workflows

## Migration Path

For existing unit tests (like `index.test.tsx`):

1. Run validator: `python validate_test.py index.test.tsx`
2. Review recommendations
3. Remove mocks and direct providers
4. Add real wrappers and factories
5. Change assertions to test user-visible behavior
6. Re-validate until ACCEPTED

## Tools and Scripts

| File | Purpose |
|------|---------|
| `tools/test_validator.py` | Core validator module |
| `validate_test.py` | CLI validation script |
| `agents/test_generator_agent.py` | Updated test generator |
| `agents/strategy_agent.py` | Updated strategy agent |
| `FEATURE_TESTING_GUIDE.md` | Complete testing guide |

## Next Steps

1. ✅ Test generator enforces feature-level testing
2. ✅ Validator automatically classifies tests
3. ✅ Strategy agent defaults React components to feature
4. ✅ Documentation created
5. 🔄 Migrate existing unit tests to feature tests
6. 🔄 Add pre-commit hooks for validation
7. 🔄 Integrate with CI/CD pipeline

## Conclusion

The SDLC Testing Agent now generates **only feature-level tests** for React components. All tests are automatically validated, and non-feature tests are rejected with specific recommendations. This ensures high-quality, maintainable, and refactor-safe tests that validate real user behavior.
