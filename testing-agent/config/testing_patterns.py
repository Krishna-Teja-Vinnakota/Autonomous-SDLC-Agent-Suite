"""
Testing Patterns Configuration
==============================
Generalized testing best practices and patterns for test generation.
Abstracted from real-world testing implementations to avoid project-specific assumptions.

This file provides:
1. Framework-specific testing patterns (Jest/RTL, pytest)
2. Infrastructure detection for uploaded projects
3. Pattern injection utilities for LLM prompts

Usage:
    from config.testing_patterns import get_testing_patterns, detect_test_infrastructure
    
    patterns = get_testing_patterns('jest')
    infrastructure = detect_test_infrastructure(project_root)
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ============================================================================
# JEST + REACT TESTING LIBRARY PATTERNS
# ============================================================================

JEST_RTL_PATTERNS = """
═══════════════════════════════════════════════════════════════════════
TESTING PATTERNS GUIDE - Jest + React Testing Library
═══════════════════════════════════════════════════════════════════════

## 1. REQUIRED INFRASTRUCTURE FILES

### jest.config.js
- Define test environment: testEnvironment: 'jsdom' for React
- Setup files: setupFilesAfterEnv: ['<rootDir>/jest.setup.js']
- Coverage collection from src/**/*.{ts,tsx}, exclude test files
- Transform patterns for node_modules if needed

### jest.setup.js
- Import @testing-library/jest-dom
- Configure MSW server lifecycle (if API mocking needed):
  * beforeAll(() => server.listen())
  * afterEach(() => server.resetHandlers())
  * afterAll(() => server.close())
- Mock browser APIs: Router, localStorage, matchMedia
- Mock external services: Analytics, Auth, Feature Flags

### jest.polyfills.js (if needed)
- TextEncoder/TextDecoder polyfills
- matchMedia mock
- IntersectionObserver mock
- ResizeObserver mock

### setupTests.ts
- Additional test-specific setup
- Import testing utilities

───────────────────────────────────────────────────────────────────────

## 2. MSW (MOCK SERVICE WORKER) PATTERN

### When to Use
- Integration/feature tests that make API calls
- Testing with realistic API responses
- Testing error states

### Directory Structure
mocks/
├── server.ts          # MSW server setup
├── handlers/          # API handlers
│   ├── index.ts      # Export all handlers
│   └── *.handlers.ts # Domain-specific handlers
└── factories/         # Mock data factories
    ├── index.ts
    └── *.factory.ts

### Server Setup (mocks/server.ts)
import { setupServer } from 'msw/node'
import { handlers } from './handlers'

export const server = setupServer(...handlers)

### Handler Pattern (mocks/handlers/*.handlers.ts)
import { http, HttpResponse } from 'msw'
// OR for GraphQL:
import { graphql } from 'msw'

export const entityHandlers = [
  // REST example
  http.get('/api/entity/:id', ({ params }) => {
    return HttpResponse.json(createMockEntity({ id: params.id }))
  }),
  
  // GraphQL example
  graphql.query('GetEntity', ({ variables }) => {
    return HttpResponse.json({
      data: { entity: createMockEntity(variables) }
    })
  }),
]

### Override Handlers in Tests
import { server } from '@/mocks/server'
import { http, HttpResponse } from 'msw'

it('handles API error', async () => {
  server.use(
    http.post('/api/action', () => {
      return HttpResponse.json(
        { error: 'Server error' },
        { status: 500 }
      )
    })
  )
  // Test error handling...
})

───────────────────────────────────────────────────────────────────────

## 3. MOCK FACTORIES PATTERN

### Purpose
- Generate realistic test data
- Provide sensible defaults
- Allow targeted overrides
- Maintain type safety

### Factory Pattern
export const createMock[Entity] = (overrides?: Partial<EntityType>): EntityType => {
  return {
    id: 'default-id',
    name: 'Default Name',
    status: 'active',
    // ... all required fields with defaults
    ...overrides,  // Apply overrides last
  }
}

### Composition Pattern
// Compose small factories into larger ones
export const createMockUser = (overrides?: Partial<User>): User => {
  return {
    profile: createMockProfile(),
    settings: createMockSettings(),
    ...overrides,
  }
}

### Stateful Mocks (for carts, wishlists, etc.)
let mockState = initialState

export const getMockState = () => mockState
export const updateMockState = (newState) => { mockState = newState }
export const resetMockState = () => { mockState = initialState }

───────────────────────────────────────────────────────────────────────

## 4. TEST UTILITIES PATTERN

### Custom Render Wrapper (test-utils.tsx)
import { render } from '@testing-library/react'
import { RouterContext } from 'next/dist/shared/lib/router-context'
// Add other providers as needed

export const renderWithProviders = (
  ui: React.ReactElement,
  options?: RenderOptions
) => {
  const Wrapper = ({ children }) => (
    <RouterContext.Provider value={mockRouter}>
      {/* Add other providers: Apollo, Redux, Theme, etc. */}
      {children}
    </RouterContext.Provider>
  )
  
  return render(ui, { wrapper: Wrapper, ...options })
}

### Cleanup Utilities
export const cleanupApolloClient = async () => {
  await client.clearStore()
  await client.cache.reset()
}

───────────────────────────────────────────────────────────────────────

## 5. TEST STRUCTURE TEMPLATE

describe('Component/Feature Name', () => {
  beforeEach(() => {
    // Reset mocks and state before each test
    jest.clearAllMocks()
    resetMockState()  // If using stateful mocks
  })
  
  afterEach(async () => {
    // Cleanup after each test
    await cleanupApolloClient()  // If using Apollo
  })
  
  it('should perform expected user-visible behavior', async () => {
    // ──────────────────────────────────────────────────
    // 1. ARRANGE - Set up test data and state
    // ──────────────────────────────────────────────────
    const mockData = createMockEntity({
      id: 'test-123',
      status: 'active'
    })
    
    // ──────────────────────────────────────────────────
    // 2. ACT - Render component
    // ──────────────────────────────────────────────────
    renderWithProviders(<YourComponent data={mockData} />)
    
    // ──────────────────────────────────────────────────
    // 3. ACT - Simulate user interactions
    // ──────────────────────────────────────────────────
    const user = userEvent.setup()
    const button = screen.getByRole('button', { name: /submit/i })
    await user.click(button)
    
    // ──────────────────────────────────────────────────
    // 4. ASSERT - Verify user-visible outcomes
    // ──────────────────────────────────────────────────
    await waitFor(() => {
      expect(screen.getByText(/success/i)).toBeInTheDocument()
    })
  })
})

───────────────────────────────────────────────────────────────────────

## 6. SEMANTIC QUERY PRIORITY

### Query Priority (Best to Last Resort)
1. **getByRole** - Accessible to assistive technology
   screen.getByRole('button', { name: /add to cart/i })
   screen.getByRole('textbox', { name: /email/i })
   
2. **getByLabelText** - Form elements with labels
   screen.getByLabelText(/password/i)
   
3. **getByPlaceholderText** - Input placeholders
   screen.getByPlaceholderText(/search/i)
   
4. **getByText** - Non-interactive content
   screen.getByText(/welcome/i)
   
5. **getByDisplayValue** - Current form values
   screen.getByDisplayValue('current-value')
   
6. **getByAltText** - Images with alt text
   screen.getByAltText(/product image/i)
   
7. **getByTestId** - LAST RESORT when nothing else works
   screen.getByTestId('custom-component')

### Use Regex for Text Matching
// ✅ GOOD - Case insensitive, flexible
screen.getByRole('button', { name: /add to cart/i })
screen.getByText(/price.*£\d+\.\d+/i)

// ❌ BAD - Exact match, brittle
screen.getByRole('button', { name: 'Add to Cart' })

───────────────────────────────────────────────────────────────────────

## 7. ASYNC OPERATIONS & USER INTERACTIONS

### Always Use userEvent (NOT fireEvent)
import { userEvent } from '@testing-library/user-event'

const user = userEvent.setup()
await user.click(element)
await user.type(input, 'text')
await user.selectOptions(select, 'option')

### Wrap Assertions in waitFor
// ✅ GOOD - Waits for async operations
await user.click(button)
await waitFor(() => {
  expect(button).toBeDisabled()
})

// ❌ BAD - May fail due to timing
await user.click(button)
expect(button).toBeDisabled()  // Race condition!

### Custom Timeout for Slow Operations
await waitFor(
  () => {
    expect(element).toBeInTheDocument()
  },
  { timeout: 5000 }
)

───────────────────────────────────────────────────────────────────────

## 8. WHAT TO TEST (User Behavior)

### ✅ TEST THESE
- User-visible behavior
- Form validation messages
- Loading/error states
- Successful operations
- Disabled/enabled states
- Accessible attributes (aria-*)
- Text content changes
- Navigation/routing
- API error handling

### ❌ DON'T TEST THESE
- Component internal state
- CSS classes (use aria attributes instead)
- Implementation details
- Function calls/prop drilling
- Translation keys (test visible text)
- Library internals

───────────────────────────────────────────────────────────────────────

## 9. TESTING ERROR STATES

### Pattern
it('displays error when operation fails', async () => {
  // Override handler to return error
  server.use(
    http.post('/api/action', () => {
      return HttpResponse.json(
        { message: 'Operation failed' },
        { status: 400 }
      )
    })
  )
  
  renderWithProviders(<YourComponent />)
  
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: /submit/i }))
  
  await waitFor(() => {
    expect(screen.getByText(/operation failed/i)).toBeInTheDocument()
  })
})

───────────────────────────────────────────────────────────────────────

## 10. TEST ISOLATION & CLEANUP

### Each Test Should
1. Set up its own data
2. Not depend on other tests
3. Clean up after itself
4. Reset mocks and state

### Cleanup Pattern
afterEach(async () => {
  // Clear all mocks
  jest.clearAllMocks()
  
  // Reset stateful mocks
  resetMockCart()
  resetMockAuth()
  
  // Clean up client state
  await cleanupApolloClient()
  
  // Reset MSW handlers
  // (handled automatically by jest.setup.js)
})

───────────────────────────────────────────────────────────────────────

## 11. BEST PRACTICES CHECKLIST

✓ Use descriptive test names that describe user behavior
✓ One assertion per test (or closely related assertions)
✓ Use semantic queries (prefer getByRole)
✓ Use regex for text matching
✓ Always await userEvent interactions
✓ Wrap async assertions in waitFor
✓ Clean up after each test
✓ Test error states
✓ Keep tests isolated
✓ Use factories for complex data
✓ Mock external dependencies
✓ Test accessibility (screen reader compatible)

───────────────────────────────────────────────────────────────────────

## 12. COMMON PATTERNS

### Testing Forms
const user = userEvent.setup()
const emailInput = screen.getByLabelText(/email/i)
const submitButton = screen.getByRole('button', { name: /submit/i })

await user.type(emailInput, 'test@example.com')
await user.click(submitButton)

await waitFor(() => {
  expect(screen.getByText(/success/i)).toBeInTheDocument()
})

### Testing Conditional Rendering
// Element should appear
expect(screen.getByText(/visible/i)).toBeInTheDocument()

// Element should not appear
expect(screen.queryByText(/hidden/i)).not.toBeInTheDocument()

### Testing Loading States
expect(screen.getByText(/loading/i)).toBeInTheDocument()

await waitFor(() => {
  expect(screen.queryByText(/loading/i)).not.toBeInTheDocument()
})

### Testing Disabled States
const button = screen.getByRole('button', { name: /submit/i })
expect(button).toBeDisabled()

// After some action
await waitFor(() => {
  expect(button).not.toBeDisabled()
})

───────────────────────────────────────────────────────────────────────

## 13. COMPONENT-LEVEL TESTING PATTERN (React Components)

### When to Use
- Testing React components in isolation
- Unit-level component testing
- Testing component logic without child component dependencies
- Fast, isolated component tests

### Key Principles
1. **Mock ALL dependencies**: Hooks, child components, analytics
2. **jest.mock() at top**: All mocks must be declared before imports
3. **Control mocks per test**: Use mockReturnValue to vary behavior
4. **Test component behavior**: Not child component internals

### Mock Structure (At Top of File)

```typescript
// ✅ CORRECT - All mocks at top, before imports
jest.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}))

jest.mock('@lib/analytics/gtm-triggers', () => ({
  sendGTMEvent: jest.fn(),
}))

// Mock hooks with controllable return values
const mockUseWishlist = jest.fn()
jest.mock('@components/wishlist/useWishlist', () => ({
  useWishlist: () => mockUseWishlist(),
}))

// Mock child components with minimal, predictable JSX
jest.mock('./wishlist-product-card', () => ({
  WishlistProductCard: jest.fn(({ item, onRemove, isOwnWishlist }) => (
    <div data-testid="mock-wishlist-product-card">
      <span>{item.name}</span>
      {isOwnWishlist && (
        <button onClick={() => onRemove(item.sku)} data-testid="remove-button">
          Remove
        </button>
      )}
    </div>
  )),
}))

jest.mock('./clear-wishlist', () => ({
  ClearWishlist: jest.fn(() => (
    <button data-testid="clear-wishlist-button">Clear</button>
  )),
}))

jest.mock('./wishlist-empty', () => ({
  WishlistEmpty: jest.fn(() => (
    <div data-testid="wishlist-empty">
      <h1>Empty List</h1>
      <a href="/" data-testid="start-shopping-link">Start Shopping</a>
    </div>
  )),
}))

jest.mock('@components/ui/loading-spinner', () => ({
  LoadingSpinner: jest.fn(() => (
    <div data-testid="loading-spinner" aria-label="Loading">Loading...</div>
  )),
}))

// Now import after mocks
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Wishlist from './wishlist'
```

### Test Structure

```typescript
describe('Wishlist Component', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    // Reset default mock return values
    mockUseWishlist.mockReturnValue({
      updating: [],
      handleRemoveFromWishlist: jest.fn(),
    })
  })

  afterEach(() => {
    jest.clearAllMocks()
  })

  it('should render items when lineItems exist', () => {
    const shoppingList = {
      id: '1',
      name: 'wishlist',
      lineItems: [{ id: '1', sku: 'SKU1', name: 'Product 1' }],
    }

    render(<Wishlist shoppingList={shoppingList} />)

    expect(screen.getByText(/wishlist/i)).toBeInTheDocument()
    expect(screen.getByTestId('mock-wishlist-product-card')).toBeInTheDocument()
  })

  it('should call handleRemoveFromWishlist when remove clicked', async () => {
    const handleRemove = jest.fn()
    mockUseWishlist.mockReturnValue({
      updating: [],
      handleRemoveFromWishlist: handleRemove,
    })

    const shoppingList = {
      id: '1',
      name: 'wishlist',
      lineItems: [{ id: '1', sku: 'SKU1', name: 'Product 1' }],
    }

    render(<Wishlist shoppingList={shoppingList} isOwnWishlist={true} />)

    const user = userEvent.setup()
    const removeButton = screen.getByTestId('remove-button')
    await user.click(removeButton)

    expect(handleRemove).toHaveBeenCalledWith('SKU1')
  })
})
```

### 🛑 HARD RULES (AUTOMATIC REJECTION IF VIOLATED)

**RULE #1: Component Mocking Requirement**
- If a component is imported, it MUST be mocked
- NO EXCEPTIONS: All child components, hooks, UI components must be mocked
- Violation = CRITICAL = REJECTION

**RULE #2: jest.mock() Placement**
- ALL jest.mock() calls MUST be at the very top, BEFORE any imports
- Violation = CRITICAL = REJECTION

**RULE #3: Hook Mocking Pattern**
- MUST use: `const mockHook = jest.fn()` pattern
- FORBIDDEN: `jest.mocked(require(...))` pattern
- Violation = CRITICAL = REJECTION

**RULE #4: Translation Assertions**
- FORBIDDEN: `getByText('(wishlist.itemsCount)')`
- FORBIDDEN: `getByText('wishlist.itemsCount')`
- REQUIRED: Use regex like `getByText(/items/i)`
- Violation = CRITICAL = REJECTION

**RULE #5: Cleanup Blocks**
- REQUIRED: `afterEach(() => { jest.clearAllMocks() })`
- REQUIRED: `beforeEach(() => { ... })` for mock reset
- Violation = CRITICAL = REJECTION

### Detailed Rules

❌ **FORBIDDEN**:
- jest.mock() inside test cases or after imports
- Asserting translation string internals: `getByText('(wishlist.itemsCount)')`
- Using `jest.mocked(require(...))` for hooks
- Assuming ARIA roles on mocked components: `getByRole('progressbar')` on mocked LoadingSpinner
- Testing child component internals
- Real analytics calls
- Missing cleanup blocks

✅ **REQUIRED**:
- All jest.mock() at top of file (before imports)
- Mock all hooks, child components, analytics
- Use controllable pattern: `const mockHook = jest.fn()`
- Use mockReturnValue to control behavior per test
- Use data-testid for mocked components
- Include afterEach and beforeEach cleanup
- Use semantic/partial text assertions with regex

═══════════════════════════════════════════════════════════════════════
END OF JEST/RTL PATTERNS GUIDE
═══════════════════════════════════════════════════════════════════════
"""


# ============================================================================
# PYTEST PATTERNS
# ============================================================================

PYTEST_PATTERNS = """
═══════════════════════════════════════════════════════════════════════
TESTING PATTERNS GUIDE - Pytest
═══════════════════════════════════════════════════════════════════════

## 1. REQUIRED INFRASTRUCTURE

### pytest.ini or pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --tb=short --strict-markers"
markers = [
    "unit: Unit tests",
    "integration: Integration tests",
    "slow: Slow running tests"
]

### conftest.py (Root Level)
- Define fixtures
- Configure test environment
- Add custom markers
- Setup/teardown logic

───────────────────────────────────────────────────────────────────────

## 2. FIXTURES PATTERN

### Function Scope (Default)
@pytest.fixture
def sample_data():
    \"\"\"Fixture that runs before each test\"\"\"
    data = {"key": "value"}
    yield data
    # Cleanup code here (optional)

### Module Scope (Shared Across Test Module)
@pytest.fixture(scope="module")
def database_connection():
    \"\"\"Setup expensive resource once per module\"\"\"
    conn = create_connection()
    yield conn
    conn.close()

### Session Scope (Once Per Test Session)
@pytest.fixture(scope="session")
def app_config():
    \"\"\"Load config once for entire test session\"\"\"
    config = load_config()
    return config

### Fixture Composition
@pytest.fixture
def authenticated_user(user, auth_token):
    \"\"\"Compose fixtures - depends on other fixtures\"\"\"
    user.token = auth_token
    return user

───────────────────────────────────────────────────────────────────────

## 3. TEST STRUCTURE

def test_descriptive_function_name(fixture1, fixture2):
    \"\"\"Docstring describing what is being tested\"\"\"
    # ──────────────────────────────────────────────────
    # GIVEN - Setup state and preconditions
    # ──────────────────────────────────────────────────
    input_data = {"user_id": 123}
    
    # ──────────────────────────────────────────────────
    # WHEN - Execute the operation being tested
    # ──────────────────────────────────────────────────
    result = function_under_test(input_data)
    
    # ──────────────────────────────────────────────────
    # THEN - Assert expected outcomes
    # ──────────────────────────────────────────────────
    assert result.status == "success"
    assert result.user_id == 123

───────────────────────────────────────────────────────────────────────

## 4. MOCKING PATTERNS

### Using unittest.mock
from unittest.mock import Mock, patch, MagicMock

def test_with_mock():
    mock_service = Mock()
    mock_service.get_data.return_value = {"key": "value"}
    
    result = function_using_service(mock_service)
    
    assert result == {"key": "value"}
    mock_service.get_data.assert_called_once()

### Using pytest-mock (monkeypatch)
def test_with_monkeypatch(monkeypatch):
    # Patch at the import site
    monkeypatch.setattr("module.function", lambda: "mocked")
    
    result = call_function()
    assert result == "mocked"

### Environment Variables
def test_with_env_var(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-key")
    # Test code that reads API_KEY

───────────────────────────────────────────────────────────────────────

## 5. ASYNC TESTING

### Mark Async Tests
import pytest

@pytest.mark.asyncio
async def test_async_operation():
    result = await async_function()
    assert result.status == "complete"

### Async Fixtures
@pytest.fixture
async def async_client():
    client = await create_async_client()
    yield client
    await client.close()

───────────────────────────────────────────────────────────────────────

## 6. PARAMETRIZED TESTS

### Basic Parametrization
@pytest.mark.parametrize("input,expected", [
    (1, 2),
    (2, 4),
    (3, 6),
])
def test_double(input, expected):
    assert double(input) == expected

### Multiple Parameters
@pytest.mark.parametrize("user_type,permissions", [
    ("admin", ["read", "write", "delete"]),
    ("user", ["read"]),
    ("guest", []),
])
def test_permissions(user_type, permissions):
    user = create_user(user_type)
    assert user.permissions == permissions

───────────────────────────────────────────────────────────────────────

## 7. EXCEPTION TESTING

### Assert Raises
import pytest

def test_raises_exception():
    with pytest.raises(ValueError, match="Invalid input"):
        function_that_raises("invalid")

### Assert Warns
def test_warns():
    with pytest.warns(UserWarning):
        function_that_warns()

───────────────────────────────────────────────────────────────────────

## 8. MARKERS

### Custom Markers
@pytest.mark.slow
def test_slow_operation():
    # Long running test
    pass

@pytest.mark.integration
def test_database_integration():
    # Integration test
    pass

### Skip/XFail
@pytest.mark.skip(reason="Not implemented yet")
def test_future_feature():
    pass

@pytest.mark.xfail(reason="Known bug")
def test_known_issue():
    pass

───────────────────────────────────────────────────────────────────────

## 9. BEST PRACTICES

✓ Use descriptive test names
✓ One logical assertion per test
✓ Use fixtures for setup/teardown
✓ Parametrize similar tests
✓ Test edge cases and errors
✓ Keep tests independent
✓ Use appropriate fixture scopes
✓ Mock external dependencies
✓ Use markers for test organization
✓ Write test docstrings

═══════════════════════════════════════════════════════════════════════
END OF PYTEST PATTERNS GUIDE
═══════════════════════════════════════════════════════════════════════
"""


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class TestInfrastructure:
    """Detected test infrastructure in a project"""
    jest_config: bool = False
    jest_setup: bool = False
    jest_polyfills: bool = False
    setup_tests: bool = False
    msw_server: bool = False
    msw_handlers: List[str] = None
    factories: List[str] = None
    test_utils: bool = False
    pytest_ini: bool = False
    conftest: bool = False
    
    def __post_init__(self):
        if self.msw_handlers is None:
            self.msw_handlers = []
        if self.factories is None:
            self.factories = []
    
    def has_msw(self) -> bool:
        """Check if MSW is configured"""
        return self.msw_server and len(self.msw_handlers) > 0
    
    def has_factories(self) -> bool:
        """Check if mock factories exist"""
        return len(self.factories) > 0
    
    def get_summary(self) -> str:
        """Get human-readable summary"""
        findings = []
        
        # Jest infrastructure
        if self.jest_config:
            findings.append("✓ jest.config.js detected")
        if self.jest_setup:
            findings.append("✓ jest.setup.js detected")
        if self.setup_tests:
            findings.append("✓ setupTests.ts detected")
        
        # MSW infrastructure
        if self.has_msw():
            findings.append(f"✓ MSW configured with {len(self.msw_handlers)} handler file(s)")
        elif self.msw_server:
            findings.append("⚠ MSW server detected but no handlers found")
        
        # Factories
        if self.has_factories():
            findings.append(f"✓ {len(self.factories)} mock factory file(s) detected")
        
        # Test utilities
        if self.test_utils:
            findings.append("✓ test-utils file detected (use renderWithProviders or similar)")
        
        # Pytest infrastructure
        if self.pytest_ini:
            findings.append("✓ pytest.ini or pyproject.toml detected")
        if self.conftest:
            findings.append("✓ conftest.py detected")
        
        return "\n".join(findings) if findings else "⚠ No testing infrastructure detected"


# ============================================================================
# INFRASTRUCTURE DETECTION
# ============================================================================

def detect_test_infrastructure(project_root: Path) -> TestInfrastructure:
    """
    Detect testing infrastructure in the uploaded project
    
    Args:
        project_root: Root directory of the project
        
    Returns:
        TestInfrastructure: Detected infrastructure details
    """
    logger.info(f"Detecting test infrastructure in: {project_root}")
    
    infra = TestInfrastructure()
    
    try:
        # Jest configuration files
        infra.jest_config = (project_root / 'jest.config.js').exists() or \
                           (project_root / 'jest.config.ts').exists()
        
        infra.jest_setup = (project_root / 'jest.setup.js').exists() or \
                          (project_root / 'jest.setup.ts').exists()
        
        infra.jest_polyfills = (project_root / 'jest.polyfills.js').exists() or \
                              (project_root / 'jest.polyfills.ts').exists()
        
        infra.setup_tests = (project_root / 'setupTests.ts').exists() or \
                           (project_root / 'setupTests.js').exists() or \
                           (project_root / 'src' / 'setupTests.ts').exists()
        
        # MSW infrastructure - check common locations
        msw_locations = [
            project_root / 'src' / 'mocks' / 'server.ts',
            project_root / 'src' / 'mocks' / 'server.js',
            project_root / 'mocks' / 'server.ts',
            project_root / 'mocks' / 'server.js',
        ]
        
        for location in msw_locations:
            if location.exists():
                infra.msw_server = True
                logger.info(f"Found MSW server at: {location}")
                break
        
        # Find MSW handlers
        handler_dirs = [
            project_root / 'src' / 'mocks' / 'handlers',
            project_root / 'mocks' / 'handlers',
        ]
        
        for handler_dir in handler_dirs:
            if handler_dir.exists() and handler_dir.is_dir():
                handlers = list(handler_dir.glob('*.ts')) + list(handler_dir.glob('*.js'))
                infra.msw_handlers = [h.name for h in handlers]
                logger.info(f"Found {len(handlers)} MSW handler file(s)")
                break
        
        # Find mock factories
        factory_dirs = [
            project_root / 'src' / 'mocks' / 'factories',
            project_root / 'mocks' / 'factories',
        ]
        
        for factory_dir in factory_dirs:
            if factory_dir.exists() and factory_dir.is_dir():
                factories = list(factory_dir.glob('*.ts')) + list(factory_dir.glob('*.js'))
                infra.factories = [f.name for f in factories]
                logger.info(f"Found {len(factories)} mock factory file(s)")
                break
        
        # Test utilities
        test_utils_locations = [
            project_root / 'src' / 'test-utils.tsx',
            project_root / 'src' / 'test-utils.ts',
            project_root / 'test-utils.tsx',
            project_root / 'test-utils.ts',
        ]
        
        for location in test_utils_locations:
            if location.exists():
                infra.test_utils = True
                logger.info(f"Found test utilities at: {location}")
                break
        
        # Pytest infrastructure
        pytest_config_locations = [
            project_root / 'pytest.ini',
            project_root / 'pyproject.toml',
            project_root / 'setup.cfg',
        ]
        
        for location in pytest_config_locations:
            if location.exists():
                infra.pytest_ini = True
                logger.info(f"Found pytest config at: {location}")
                break
        
        infra.conftest = (project_root / 'conftest.py').exists() or \
                        (project_root / 'tests' / 'conftest.py').exists()
        
        if infra.conftest:
            logger.info("Found conftest.py")
        
        # Log summary
        summary = infra.get_summary()
        logger.info(f"Infrastructure detection complete:\n{summary}")
        
        return infra
        
    except Exception as e:
        logger.error(f"Error detecting test infrastructure: {e}")
        return infra


# ============================================================================
# PATTERN RETRIEVAL
# ============================================================================

def get_testing_patterns(framework: str) -> str:
    """
    Get testing patterns for the specified framework
    
    Args:
        framework: 'jest' or 'pytest'
        
    Returns:
        str: Testing patterns guide
    """
    framework_lower = framework.lower()
    
    if framework_lower in ['jest', 'react', 'rtl']:
        return JEST_RTL_PATTERNS
    elif framework_lower in ['pytest', 'python']:
        return PYTEST_PATTERNS
    else:
        logger.warning(f"Unknown framework: {framework}, returning empty patterns")
        return ""


def build_infrastructure_context(
    project_root: Path,
    framework: str = 'jest'
) -> str:
    """
    Build complete testing context including patterns and detected infrastructure
    
    Args:
        project_root: Root directory of project
        framework: Testing framework ('jest' or 'pytest')
        
    Returns:
        str: Complete testing context for LLM prompt
    """
    # Get generalized patterns
    patterns = get_testing_patterns(framework)
    
    # Detect project-specific infrastructure
    infrastructure = detect_test_infrastructure(project_root)
    infra_summary = infrastructure.get_summary()
    
    # Build combined context
    context = f"""{patterns}

═══════════════════════════════════════════════════════════════════════
PROJECT-SPECIFIC INFRASTRUCTURE DETECTED
═══════════════════════════════════════════════════════════════════════

{infra_summary}

INSTRUCTIONS FOR TEST GENERATION:
• Follow the patterns above as general guidelines
• Use the detected infrastructure where available
• If MSW server detected: Use server for API mocking
• If factories detected: Use them for mock data (check factory files for available functions)
• If test-utils detected: Use renderWithProviders() or similar custom render
• Adapt import paths to match the project structure
• DO NOT invent APIs or utilities that don't exist in the project
• DO refer to related files for correct import paths and function signatures

═══════════════════════════════════════════════════════════════════════
"""
    
    return context


# ============================================================================
# HELPER UTILITIES
# ============================================================================

def get_mock_factory_names(project_root: Path) -> List[str]:
    """
    Extract mock factory function names from factory files
    
    Args:
        project_root: Root directory of project
        
    Returns:
        List[str]: List of factory function names (e.g., ['createMockProduct', 'createMockUser'])
    """
    factory_names = []
    
    factory_dirs = [
        project_root / 'src' / 'mocks' / 'factories',
        project_root / 'mocks' / 'factories',
    ]
    
    import re
    factory_pattern = re.compile(r'export\s+(?:const|function)\s+(create\w+)\s*[=(]')
    
    for factory_dir in factory_dirs:
        if factory_dir.exists() and factory_dir.is_dir():
            for factory_file in factory_dir.glob('*.ts'):
                try:
                    content = factory_file.read_text(encoding='utf-8')
                    matches = factory_pattern.findall(content)
                    factory_names.extend(matches)
                except Exception as e:
                    logger.debug(f"Could not parse factory file {factory_file}: {e}")
    
    return list(set(factory_names))  # Remove duplicates


def get_test_utils_exports(project_root: Path) -> List[str]:
    """
    Extract exported utility function names from test-utils file
    
    Args:
        project_root: Root directory of project
        
    Returns:
        List[str]: List of exported function names
    """
    export_names = []
    
    test_utils_locations = [
        project_root / 'src' / 'test-utils.tsx',
        project_root / 'src' / 'test-utils.ts',
        project_root / 'test-utils.tsx',
        project_root / 'test-utils.ts',
    ]
    
    import re
    export_pattern = re.compile(r'export\s+(?:const|function)\s+(\w+)')
    
    for location in test_utils_locations:
        if location.exists():
            try:
                content = location.read_text(encoding='utf-8')
                matches = export_pattern.findall(content)
                export_names.extend(matches)
                break
            except Exception as e:
                logger.debug(f"Could not parse test-utils file {location}: {e}")
    
    return export_names


# ============================================================================
# FEATURE TEST QUALITY RULES (MACHINE-READABLE)
# ============================================================================

# These rules are used by test_rules_validator.py for post-generation validation
FEATURE_TEST_QUALITY_RULES = {
    # Semantic Queries
    "semantic_queries_required": True,
    "semantic_query_priority": ["getByRole", "getByText", "getByLabelText", "getByPlaceholderText", "getByTestId"],
    "forbid_testid_for_interactive": True,  # buttons, links, inputs must use getByRole
    "interactive_elements": ["button", "link", "input", "checkbox", "radio", "select", "textarea"],
    
    # Root Container Assertion
    "root_container_assertion_required": True,
    "root_container_patterns": ["container", "root", "wrapper", "app", "feature"],
    
    # AAA Structure
    "aaa_structure_required": True,
    "aaa_phases": {
        "arrange": ["setup", "mock", "render", "const", "let"],
        "act": ["user.", "await user", "click", "type", "submit", "fireEvent"],
        "assert": ["expect(", "toBeInTheDocument", "toHaveText", "toBeVisible"]
    },
    
    # Factory Cleanliness
    "factory_cleanliness_required": True,
    "forbid_setup_fields": ["__typename"],  # GraphQL internal fields
    "max_factory_fields": 10,  # More than this likely includes noise
    
    # User Event
    "user_event_required": True,
    "forbid_fire_event": True,  # Use userEvent instead
    
    # Test Naming
    "test_naming_pattern": r"should .+ when .+",
    "forbid_generic_names": ["test1", "test 1", "works", "it works"]
}

# Unit Test Rules (more flexible)
UNIT_TEST_QUALITY_RULES = {
    "semantic_queries_required": False,  # Unit tests can be more flexible
    "aaa_structure_required": True,
    "factory_cleanliness_required": False,  # Can mock inline
}

# Integration Test Rules (middle ground)
INTEGRATION_TEST_QUALITY_RULES = {
    "semantic_queries_required": True,
    "aaa_structure_required": True,
    "factory_cleanliness_required": True,
    "msw_usage_recommended": True,
}


# ============================================================================
# EXPORT PUBLIC API
# ============================================================================

__all__ = [
    'JEST_RTL_PATTERNS',
    'PYTEST_PATTERNS',
    'TestInfrastructure',
    'detect_test_infrastructure',
    'get_testing_patterns',
    'build_infrastructure_context',
    'get_mock_factory_names',
    'get_test_utils_exports',
    'FEATURE_TEST_QUALITY_RULES',
    'UNIT_TEST_QUALITY_RULES',
    'INTEGRATION_TEST_QUALITY_RULES',
]
