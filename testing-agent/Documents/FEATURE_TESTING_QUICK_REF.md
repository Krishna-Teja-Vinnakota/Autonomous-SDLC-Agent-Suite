# Feature Testing Quick Reference

## 🎯 Golden Rule
**Test what users see and do, not how the code works internally.**

---

## ✅ Required Imports

```typescript
import { screen } from '@testing-library/react'
import { userEvent } from '@testing-library/user-event'
import { ComponentName } from './index'
import { mockPdpProduct } from '@mocks/factories'
import { pdpUserActions } from '@test-utils/user-actions'
import { pdpWrapper, renderWeb } from '@test-utils/render'
import { cleanupApolloClient } from '@test-utils/apollo'
```

---

## ✅ Required Setup

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

  const renderComponent = (product = mockProduct) => 
    renderWeb(<SelectSize />, { wrapper: pdpWrapper(product) })
})
```

---

## ✅ Test Structure

```typescript
it('outcome WHEN condition', async () => {
  // GIVEN
  renderComponent()

  // WHEN
  await pdpActions.selectSize('UK 8')

  // THEN
  expect(screen.getByRole('button', { name: 'UK 8' }))
    .toHaveClass('bg-grey-1000')
})
```

---

## ✅ DO

| Action | Example |
|--------|---------|
| Use real wrappers | `renderWeb(<Component />, { wrapper: pdpWrapper() })` |
| Use factories | `mockProduct = mockPdpProduct()` |
| Use userEvent | `await user.click(button)` |
| Test visible behavior | `expect(screen.getByRole('button', { name: 'UK 8' }))` |
| Use WHEN clauses | `'renders sizes WHEN in stock'` |
| Use getByRole | `screen.getByRole('button', { name: 'Add to Cart' })` |

---

## ❌ DON'T

| Anti-Pattern | Why It's Wrong |
|--------------|----------------|
| `jest.mock('next-intl')` | Mocks application code |
| `<Context.Provider value={mock}>` | Direct provider mocking |
| `expect(...'Translated pdp.label...')` | Tests translation keys |
| `expect(scrollIntoView).toHaveBeenCalled()` | Tests implementation |
| `fireEvent.click(button)` | Use `userEvent` instead |
| `expect(element).toHaveClass('util-class')` | Tests implementation |

---

## 🔍 Validation

```bash
# Check if your test is a feature test
python validate_test.py my-component.test.tsx

# Score >= 4 → ACCEPTED ✅
# Score < 4  → REJECTED ❌
```

---

## 📊 Scoring System

**Feature Signals (+1):** userEvent, wrappers, factories, getByRole, WHEN clauses

**Unit Signals (-2):** jest.mock, mocked providers, translation keys, implementation tests

**Target:** Score ≥ 4 for ACCEPTANCE

---

## 🎯 Test Names

✅ **GOOD:**
- `renders all sizes WHEN they are in stock`
- `updates selected size WHEN user clicks another size`
- `shows error WHEN no size is selected`

❌ **BAD:**
- `should render sizes` (vague)
- `test size selection` (not descriptive)
- `renders SelectVariantMenu WHEN not one size` (implementation)

---

## 🔧 Common Fixes

| Issue | Fix |
|-------|-----|
| `jest.mock()` detected | Remove mock, use real wrapper |
| Mocked context | Replace with `pdpWrapper()` |
| Translation key assertion | Test actual visible text |
| `fireEvent` used | Change to `await user.click()` |
| Missing `userEvent.setup()` | Add to `beforeEach` |
| Missing cleanup | Add `cleanupApolloClient()` to `afterEach` |

---

## 📁 File Naming

✅ `select-size.feature.test.tsx`  
✅ `add-to-cart.feature.test.tsx`  
❌ `select-size.test.tsx` (ambiguous)  
❌ `select-size.unit.test.tsx` (wrong level)

---

## 🚀 Quick Start

1. Copy the required imports
2. Copy the setup structure
3. Write tests using GIVEN/WHEN/THEN
4. Validate: `python validate_test.py your-test.tsx`
5. Fix issues until score ≥ 4

---

## 📚 Full Documentation

See `FEATURE_TESTING_GUIDE.md` for complete guide.
