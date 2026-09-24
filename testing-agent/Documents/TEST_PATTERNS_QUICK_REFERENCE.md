# Test Patterns Quick Reference

## 🎯 Test Structure Template

### Integration/Feature Tests

```typescript
import { render, screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { ComponentName } from './index';

describe('ComponentName Feature', () => {
  let user: ReturnType<typeof userEvent.setup>;
  
  beforeEach(() => {
    user = userEvent.setup();
  });
  
  afterEach(() => {
    jest.clearAllMocks();
  });
  
  it('does something WHEN condition occurs', async () => {
    render(<ComponentName />);
    
    const button = screen.getByRole('button', { name: 'Click' });
    await user.click(button);
    
    expect(screen.getByText('Result')).toBeInTheDocument();
  });
});
```

## 📝 Test Naming Patterns

### ✅ Good Test Names (with WHEN clauses)

```typescript
it('renders all options WHEN data is available', () => {})
it('updates state WHEN user clicks button', async () => {})
it('shows error WHEN validation fails', () => {})
it('disables submit WHEN form is invalid', () => {})
it('navigates to page WHEN link is clicked', async () => {})
```

### ❌ Bad Test Names

```typescript
it('works', () => {})
it('test component', () => {})
it('renders', () => {})
it('button click', () => {})
```

## 🔍 Query Selector Priority

### 1️⃣ Most Preferred: `getByRole`
```typescript
screen.getByRole('button', { name: 'Submit' })
screen.getByRole('textbox', { name: 'Email' })
screen.getByRole('checkbox', { name: 'Accept Terms' })
```

### 2️⃣ Second: `getByLabelText`
```typescript
screen.getByLabelText('Email Address')
screen.getByLabelText(/password/i)
```

### 3️⃣ Third: `getByPlaceholderText`
```typescript
screen.getByPlaceholderText('Enter email...')
```

### 4️⃣ Fourth: `getByText`
```typescript
screen.getByText('Welcome')
screen.getByText(/hello/i)
```

### 5️⃣ Last Resort: `getByTestId`
```typescript
screen.getByTestId('custom-component')
```

## 👆 User Interactions

### ✅ Correct Way (userEvent)

```typescript
const user = userEvent.setup();

// Click
await user.click(element);

// Type
await user.type(input, 'Hello World');

// Hover
await user.hover(element);

// Select
await user.selectOptions(select, 'option1');

// Clear
await user.clear(input);

// Tab
await user.tab();
```

### ❌ Deprecated Way (fireEvent)

```typescript
// DON'T use these
fireEvent.click(element);
fireEvent.change(input, { target: { value: 'text' } });
```

## 🧪 Common Test Patterns

### Pattern 1: Render with Mock Data
```typescript
const renderComponent = (overrides = {}) => {
  const mockData = {
    items: ['Item 1', 'Item 2'],
    ...overrides
  };
  return render(<Component {...mockData} />);
};

it('renders items WHEN provided', () => {
  renderComponent();
  expect(screen.getByText('Item 1')).toBeInTheDocument();
});

it('shows empty state WHEN no items', () => {
  renderComponent({ items: [] });
  expect(screen.getByText('No items')).toBeInTheDocument();
});
```

### Pattern 2: Test User Workflow
```typescript
it('completes checkout WHEN user fills form', async () => {
  render(<CheckoutForm />);
  
  // Step 1: Fill form
  await user.type(screen.getByLabelText('Name'), 'John Doe');
  await user.type(screen.getByLabelText('Email'), 'john@example.com');
  
  // Step 2: Submit
  await user.click(screen.getByRole('button', { name: 'Submit' }));
  
  // Step 3: Verify success
  expect(await screen.findByText('Order confirmed')).toBeInTheDocument();
});
```

### Pattern 3: Test State Changes
```typescript
it('toggles visibility WHEN button is clicked', async () => {
  render(<Accordion />);
  
  // Initial state
  expect(screen.queryByText('Content')).not.toBeInTheDocument();
  
  // Trigger change
  await user.click(screen.getByRole('button', { name: 'Expand' }));
  
  // New state
  expect(screen.getByText('Content')).toBeInTheDocument();
  
  // Toggle back
  await user.click(screen.getByRole('button', { name: 'Collapse' }));
  expect(screen.queryByText('Content')).not.toBeInTheDocument();
});
```

### Pattern 4: Test Multiple Scenarios
```typescript
describe('Button Component', () => {
  it('renders enabled WHEN no disabled prop', () => {
    render(<Button>Click</Button>);
    expect(screen.getByRole('button')).not.toBeDisabled();
  });
  
  it('renders disabled WHEN disabled prop is true', () => {
    render(<Button disabled>Click</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });
  
  it('calls onClick WHEN clicked', async () => {
    const handleClick = jest.fn();
    render(<Button onClick={handleClick}>Click</Button>);
    
    await user.click(screen.getByRole('button'));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });
});
```

### Pattern 5: Test Loading States
```typescript
it('shows loading WHEN data is fetching', () => {
  render(<DataList isLoading={true} />);
  expect(screen.getByText('Loading...')).toBeInTheDocument();
});

it('shows data WHEN loading completes', async () => {
  render(<DataList />);
  
  expect(await screen.findByText('Item 1')).toBeInTheDocument();
  expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
});
```

## 🎭 Common Assertions

```typescript
// Element presence
expect(element).toBeInTheDocument();
expect(element).not.toBeInTheDocument();

// Visibility
expect(element).toBeVisible();
expect(element).not.toBeVisible();

// Disabled state
expect(button).toBeDisabled();
expect(button).not.toBeDisabled();

// Text content
expect(element).toHaveTextContent('Hello');
expect(element).toHaveTextContent(/hello/i);

// CSS classes
expect(element).toHaveClass('active');
expect(element).not.toHaveClass('disabled');

// Attributes
expect(input).toHaveAttribute('type', 'email');
expect(link).toHaveAttribute('href', '/page');

// Form values
expect(input).toHaveValue('text');
expect(checkbox).toBeChecked();

// Count
expect(screen.getAllByRole('listitem')).toHaveLength(3);

// Async assertions
expect(await screen.findByText('Loaded')).toBeInTheDocument();
await waitFor(() => {
  expect(screen.getByText('Updated')).toBeInTheDocument();
});
```

## 📁 File Naming Conventions

| Test Type | File Name | Example |
|-----------|-----------|---------|
| Unit | `Component.test.tsx` | `Button.test.tsx` |
| Integration | `Component.integration.test.tsx` | `Form.integration.test.tsx` |
| Feature | `Component.feature.test.tsx` | `Checkout.feature.test.tsx` |

## ⚙️ Setup/Teardown Patterns

### Basic Setup
```typescript
beforeEach(() => {
  user = userEvent.setup();
});

afterEach(() => {
  jest.clearAllMocks();
});
```

### With Mock Data
```typescript
let mockData: any;

beforeEach(() => {
  user = userEvent.setup();
  mockData = {
    id: 1,
    name: 'Test Item'
  };
});

afterEach(() => {
  jest.clearAllMocks();
});
```

### With Cleanup
```typescript
afterEach(async () => {
  await cleanup(); // React Testing Library cleanup
  jest.clearAllMocks();
  localStorage.clear();
});
```

## 🚀 Quick Start Checklist

- [ ] Import `{ render, screen }` from `@testing-library/react`
- [ ] Import `{ userEvent }` from `@testing-library/user-event`
- [ ] Setup `user = userEvent.setup()` in `beforeEach`
- [ ] Use descriptive test names with WHEN clauses
- [ ] Prefer `getByRole` queries
- [ ] Use `await user.click()` not `fireEvent`
- [ ] Add cleanup in `afterEach`
- [ ] Test user-visible behavior, not implementation
- [ ] Use async/await for user interactions
- [ ] Group related tests in `describe` blocks

---

**Tip:** Keep this reference open while writing tests for quick lookup!
