# Feature-Level Testing Guide

## Overview

This project enforces **strict feature-level testing** for React/Next.js components. The testing agent has been updated to generate only feature tests, not unit or component tests.

## What is Feature-Level Testing?

Feature-level testing validates **USER-OBSERVABLE PRODUCT BEHAVIOR** through realistic user interactions and workflows. It focuses on what users see and do, not implementation details.

## Feature vs Unit Testing

### ❌ Unit/Component Testing (NOT ALLOWED)
- Tests implementation details (translation keys, CSS classes, hooks)
- Mocks context providers directly
- Tests internal component state
- Asserts on component internals (scrollIntoView, useEffect)
- Tests components in isolation

### ✅ Feature Testing (REQUIRED)
- Tests user-visible behavior
- Uses real application wrappers
- Uses factory functions for test data
- Tests user interactions with userEvent
- Tests business rules and outcomes
- Tests multiple components together

## Validation System

### Automatic Classification

All generated tests are automatically validated using a scoring system:

**Feature Signals** (+1 each):
- `userEvent` usage
- `userEvent.setup()` in beforeEach
- Real wrappers (`pdpWrapper`, `renderWeb`, `appWrapper`)
- Factory functions (`mockPdpProduct`, `createMockProduct`)
- User action helpers (`pdpUserActions`)
- Async user interactions (`await user.click()`)
- Accessibility queries (`getByRole`)
- Proper cleanup (`cleanupApolloClient`)
- GIVEN/WHEN/THEN test names

**Unit Test Signals** (-2 each):
- `jest.mock()` for application code
- Mocked context providers (`ProductDetailsPageContext.Provider`)
- Mocked hooks (`useTranslations`, `useContext`)
- Translation key assertions (`expect(...).toBe('Translated pdp.labelSelectSize')`)
- Implementation tests (`scrollIntoView`, `toHaveBeenCalled`)
- ClassName tests (unless user-visible state)
- Direct context providers
- `fireEvent` usage

### Scoring
- **Score ≥ +4**: FEATURE TEST ✅ (ACCEPTED)
- **Score 1-3**: HYBRID ❌ (REJECTED)
- **Score ≤ 0**: UNIT TEST ❌ (REJECTED)

## Running the Validator

Validate any test file:

```bash
python validate_test.py <test-file-path>
```

Example:
```bash
python validate_test.py index.test.tsx
python validate_test.py select-size.feature.test.tsx
```

## Example: Bad Test (Unit) vs Good Test (Feature)

### ❌ BAD: Unit Test (index.test.tsx)

```typescript
// WRONG - This is a unit test
import { render, screen } from '@testing-library/react';
import { SelectSize } from './index';
import { ProductDetailsPageContext } from '@components/product-details-page/_context/ProductDetailsPageContext';
import { useTranslations } from 'next-intl';

jest.mock('next-intl', () => ({
  useTranslations: jest.fn(),
}));

describe('SelectSize Feature', () => {
  it('renders select size title WHEN no errors', () => {
    const mockProduct = { isOutOfStock: false };
    const mockState = { showSelectVariantError: false };
    
    render(
      <ProductDetailsPageContext.Provider value={{ state: mockState, product: mockProduct }}>
        <SelectSize />
      </ProductDetailsPageContext.Provider>
    );
    
    expect(screen.getByText('Translated pdp.labelSelectSize')).toBeInTheDocument();
  });
});
```

**Issues:**
- ❌ Mocks `useTranslations` with `jest.mock()`
- ❌ Uses direct context provider
- ❌ Tests translation keys
- ❌ No real wrappers or factories
- ❌ Tests implementation, not user behavior

**Validation Score:** -10 (UNIT TEST - REJECTED)

### ✅ GOOD: Feature Test (select-size.feature.test.tsx)

```typescript
// CORRECT - This is a feature test
import { screen } from '@testing-library/react'
import { userEvent } from '@testing-library/user-event'
import { SelectSize } from '../select-size/index'
import { createMockProduct, mockPdpProduct } from '@mocks/factories'
import { pdpUserActions } from '@test-utils/user-actions'
import { pdpWrapper, renderWeb } from '@test-utils/render'
import { cleanupApolloClient } from '@test-utils/apollo'

describe('PDP SelectSize Feature', () => {
  let pdpActions: ReturnType<typeof pdpUserActions>
  let mockProduct: ReturnType<typeof createMockProduct>

  const renderSelectSizePdp = (product = mockProduct) => 
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
    renderSelectSizePdp()

    expect(screen.getByRole('button', { name: 'UK 8' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'UK 9' })).toBeInTheDocument()
  })

  it('updates the selected size WHEN another size is clicked', async () => {
    renderSelectSizePdp()

    await pdpActions.selectSize('UK 8')
    expect(screen.getByRole('button', { name: 'UK 8' })).toHaveClass('bg-grey-1000')

    await pdpActions.selectSize('UK 9')
    expect(screen.getByRole('button', { name: 'UK 9' })).toHaveClass('bg-grey-1000')
  })
})
```

**Why it's good:**
- ✅ Uses real wrappers (`pdpWrapper`, `renderWeb`)
- ✅ Uses factories (`mockPdpProduct`)
- ✅ Uses user actions (`pdpUserActions`)
- ✅ Tests user-visible behavior (button text, selection state)
- ✅ Uses `getByRole` (accessibility-focused)
- ✅ Tests complete user workflows
- ✅ WHEN clauses in test names

**Validation Score:** +7 (FEATURE TEST - ACCEPTED)

## Mandatory Requirements for Feature Tests

### 1. Import Structure

```typescript
import { screen } from '@testing-library/react'
import { userEvent } from '@testing-library/user-event'
import { ComponentName } from './index'
import { mockPdpProduct, createMockProduct } from '@mocks/factories'
import { pdpUserActions } from '@test-utils/user-actions'
import { pdpWrapper, renderWeb } from '@test-utils/render'
import { cleanupApolloClient } from '@test-utils/apollo'
```

### 2. Setup and Cleanup

```typescript
describe('Feature Name', () => {
  let pdpActions: ReturnType<typeof pdpUserActions>
  let mockProduct: ReturnType<typeof createMockProduct>

  beforeEach(() => {
    pdpActions = pdpUserActions(userEvent.setup())
    mockProduct = mockPdpProduct()
  })

  afterEach(async () => {
    await cleanupApolloClient()
    jest.clearAllMocks()
  })
})
```

### 3. Render Helper

```typescript
const renderComponent = (product = mockProduct) => 
  renderWeb(<ComponentName />, { wrapper: pdpWrapper(product) })
```

### 4. Test Structure

```typescript
it('describes outcome WHEN condition occurs', async () => {
  // GIVEN
  renderComponent()

  // WHEN
  await pdpActions.doSomething()

  // THEN
  expect(screen.getByRole('button', { name: 'Expected' })).toBeInTheDocument()
})
```

## What NOT to Test

❌ **Translation Keys**
```typescript
// WRONG
expect(screen.getByText('Translated pdp.labelSelectSize'))
```

❌ **Internal Hooks**
```typescript
// WRONG
jest.mock('next-intl')
const mockUseTranslations = useTranslations as jest.Mock
```

❌ **Context Providers**
```typescript
// WRONG
<ProductDetailsPageContext.Provider value={mockState}>
  <SelectSize />
</ProductDetailsPageContext.Provider>
```

❌ **Implementation Details**
```typescript
// WRONG
expect(scrollIntoView).toHaveBeenCalled()
expect(container).toHaveClass('some-internal-class')
```

❌ **fireEvent**
```typescript
// WRONG
fireEvent.click(button)

// RIGHT
await user.click(button)
```

## Test Naming Convention

Use GIVEN/WHEN/THEN format:

✅ **Good Names:**
- `renders all sizes WHEN they are in stock`
- `does not render a size WHEN it is out of stock`
- `updates selected size WHEN user clicks another size`
- `shows error message WHEN no size is selected`

❌ **Bad Names:**
- `should render sizes` (vague)
- `test size selection` (not descriptive)
- `renders SelectVariantMenu WHEN not one size` (implementation detail)

## File Naming

Feature tests must use the `.feature.test.tsx` suffix:

✅ `select-size.feature.test.tsx`
✅ `add-to-cart.feature.test.tsx`
❌ `select-size.test.tsx` (ambiguous)
❌ `select-size.unit.test.tsx` (wrong level)

## Integration with Test Generation

The test generator agent automatically:

1. **Generates feature-level tests** when `test_level='feature'`
2. **Validates tests** using the automatic classifier
3. **Rejects non-feature tests** with detailed feedback
4. **Provides recommendations** for fixing issues

## Troubleshooting

### Test Rejected as UNIT or HYBRID

Run the validator to see issues:
```bash
python validate_test.py your-test.test.tsx
```

Common fixes:
1. Remove all `jest.mock()` calls
2. Replace direct providers with wrappers
3. Use factory functions for test data
4. Change assertions from translation keys to visible text
5. Remove implementation detail tests
6. Add `await user.*` interactions

### Test Still Fails After Changes

Check the scoring:
- Need at least **4 feature signals**
- Each unit signal is **-2 points**
- Common missing signals: wrappers, factories, user actions

## Reference Files

- **Good Example:** `select-size.feature.test.tsx`
- **Bad Example:** `index.test.tsx`
- **Validator:** `tools/test_validator.py`
- **Validation Script:** `validate_test.py`
- **Generator Agent:** `agents/test_generator_agent.py`

## Summary

✅ **DO:**
- Use real application wrappers
- Use factory functions
- Test user-visible behavior
- Use userEvent for interactions
- Use getByRole queries
- Write GIVEN/WHEN/THEN tests

❌ **DON'T:**
- Mock hooks or context
- Test translation keys
- Test implementation details
- Use fireEvent
- Test internal APIs
- Write unit tests

**Remember:** Feature tests validate what users see and do, not how the code works internally.
