# Integration Test Configuration Guide

## Overview
The SDLC Testing Agent has been configured to generate production-grade integration and feature tests that follow enterprise testing patterns.

## Test Structure Pattern

### File Naming Convention

| Test Level | Naming Pattern | Example |
|------------|----------------|---------|
| Unit | `*.test.tsx` | `Button.test.tsx` |
| Integration | `*.integration.test.tsx` | `SelectSize.integration.test.tsx` |
| Feature | `*.feature.test.tsx` | `SelectSize.feature.test.tsx` |

### Required Test Structure

All integration and feature tests follow this standardized structure:

```typescript
import { render, screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { ComponentName } from './index';

describe('ComponentName Feature', () => {
  let user: ReturnType<typeof userEvent.setup>;
  let mockData: any;
  
  const renderComponent = (overrides = {}) => {
    return render(<ComponentName {...mockData} {...overrides} />);
  };
  
  beforeEach(() => {
    user = userEvent.setup();
    mockData = {
      // Setup mock data
    };
  });
  
  afterEach(() => {
    jest.clearAllMocks();
  });
  
  it('renders expected elements WHEN component loads', () => {
    renderComponent();
    
    expect(screen.getByRole('button', { name: 'Click' })).toBeInTheDocument();
  });
  
  it('updates state WHEN user interacts', async () => {
    renderComponent();
    
    const button = screen.getByRole('button', { name: 'Click' });
    await user.click(button);
    
    expect(screen.getByText('Updated')).toBeInTheDocument();
  });
});
```

## Key Configuration Changes

### 1. Strategy Agent (`agents/strategy_agent.py`)

**Changes:**
- Classifies test level BEFORE determining test file naming
- Uses level-specific file naming conventions
- For React components: `.integration.test.tsx` or `.feature.test.tsx`
- For Python modules: `test_*_integration.py` or `test_*_feature.py`

**Classification Rules:**
- **Unit**: Utilities, helpers, pure functions
- **Integration**: React components with hooks/APIs, modules with dependencies
- **Feature**: Components in feature folders, complete user workflows

### 2. Test Generator Agent (`agents/test_generator_agent.py`)

**Enhanced Instructions for Integration/Feature Tests:**

#### Required Imports
```typescript
import { render, screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { ComponentName } from './index';
```

#### Required Setup
```typescript
let user: ReturnType<typeof userEvent.setup>;

beforeEach(() => {
  user = userEvent.setup();
});

afterEach(() => {
  jest.clearAllMocks();
});
```

#### User Interactions
- ✅ Use: `await user.click(element)`
- ✅ Use: `await user.type(input, 'text')`
- ✅ Use: `await user.hover(element)`
- ❌ NEVER: `fireEvent.click(element)`

#### Query Priority (Most to Least Preferred)
1. `getByRole` - Most accessible
2. `getByLabelText`
3. `getByPlaceholderText`
4. `getByText`
5. `getByTestId` - Last resort

#### Test Naming Convention
Use descriptive names with **WHEN clauses**:

✅ **Good Examples:**
- `'renders all sizes WHEN they are in stock'`
- `'updates selected size WHEN another size is clicked'`
- `'shows error WHEN no size is selected'`
- `'disables button WHEN item is out of stock'`

❌ **Bad Examples:**
- `'it works'`
- `'test button click'`
- `'renders component'`

### 3. Test Execution (`agents/test_executor_agent.py`)

**Execution Rules by Level:**

| Level | Execution Mode | Timeout | Retry Limit |
|-------|---------------|---------|-------------|
| Unit | Parallel | 30s | 1 |
| Integration | Sequential (`--runInBand`) | 60s | 2 |
| Feature | Sequential | 120s | 2 |

## Example: Input → Output Mapping

### Input Component: `index.tsx`
```typescript
export function SelectSize({ className, variantError }: SelectSizeProps) {
  const { state, product } = useContext(ProductDetailsPageContext);
  // ... component logic
}
```

### Generated Test: `index.feature.test.tsx`
```typescript
import { screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { SelectSize } from './index';

describe('SelectSize Feature', () => {
  let user: ReturnType<typeof userEvent.setup>;
  let mockProduct: any;
  
  const renderSelectSize = (overrides = {}) => {
    return render(<SelectSize {...mockProduct} {...overrides} />);
  };
  
  beforeEach(() => {
    user = userEvent.setup();
    mockProduct = {
      variants: [
        { sku: 'SKU1', size: 'UK 8', stock: { available: true } },
        { sku: 'SKU2', size: 'UK 9', stock: { available: true } }
      ]
    };
  });
  
  afterEach(() => {
    jest.clearAllMocks();
  });
  
  it('renders all sizes WHEN they are in stock', () => {
    renderSelectSize();
    
    expect(screen.getByRole('button', { name: 'UK 8' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'UK 9' })).toBeInTheDocument();
  });
  
  it('updates selected size WHEN another size is clicked', async () => {
    renderSelectSize();
    
    const uk8Button = screen.getByRole('button', { name: 'UK 8' });
    const uk9Button = screen.getByRole('button', { name: 'UK 9' });
    
    await user.click(uk8Button);
    expect(uk8Button).toHaveClass('selected');
    
    await user.click(uk9Button);
    expect(uk9Button).toHaveClass('selected');
    expect(uk8Button).not.toHaveClass('selected');
  });
});
```

## Benefits of This Configuration

### 1. **Production-Ready Tests**
- Tests mirror real-world enterprise testing patterns
- Follows React Testing Library best practices
- Uses modern userEvent API (not deprecated fireEvent)

### 2. **Consistency**
- All integration/feature tests follow the same structure
- Easy to read and maintain
- Clear naming conventions

### 3. **Accessibility First**
- Prioritizes `getByRole` queries
- Tests how users actually interact with the app
- Ensures ARIA compliance

### 4. **Maintainability**
- Helper render functions with overrides
- Centralized setup/teardown
- Clear test organization

### 5. **Reliability**
- Proper async handling with await
- Cleanup after each test
- Sequential execution for stability

## Usage in UI

When you select **Integration Testing** or **Feature Testing** in the Streamlit UI:

1. The system classifies files into appropriate test levels
2. Generates tests with the correct naming convention
3. Creates tests following the standardized structure
4. Executes tests with appropriate timeout and retry settings
5. Reports results grouped by test level

## Next Steps

To generate integration/feature tests:

1. **Select Test Level** in the UI sidebar
2. Choose "Integration" or "Feature Only" quick action
3. Click **"Generate Tests"**
4. System automatically:
   - Classifies files
   - Generates properly structured tests
   - Executes with correct settings
   - Provides detailed reports

## Troubleshooting

### No Integration Tests Generated?

**Check:**
1. Are your files classified as integration-level?
2. View the logs for "test_plan" breakdown
3. The system may have classified all files as "unit"

**Solution:**
- React components with hooks/APIs are auto-classified as integration
- Feature folders are auto-classified as feature level
- You can also check `agents/strategy_agent.py` classification rules

### Tests Failing with Timeout?

**Check:**
1. Test level execution timeout settings
2. Async operations need `await`
3. Sequential execution for integration/feature tests

**Solution:**
- Integration tests: 60s timeout
- Feature tests: 120s timeout
- All set in `test_executor_agent.py`

## Technical Details

### Files Modified
- `agents/strategy_agent.py` - Test level classification and file naming
- `agents/test_generator_agent.py` - Enhanced prompts with structure requirements
- `workflows/langgraph_flow.py` - Test level filtering and execution order

### Configuration Location
All configuration is embedded in the agent prompts and strategy rules. No external configuration files needed.

---

**Last Updated:** 2026-01-16
**Version:** 2.0 (Production-Grade Integration Testing)
