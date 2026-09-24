# E2E Feature Tests

This directory contains **feature-level end-to-end tests** that validate complete user journeys on the running application.

## 🎯 Purpose

These tests are **NOT component tests**. They test real user flows by:

- ✅ Navigating to actual pages (`/product/123`)
- ✅ Interacting via accessible UI elements (`getByRole('button')`)
- ✅ Asserting user-visible outcomes (error messages, success states)
- ❌ NO direct prop manipulation
- ❌ NO CSS class assertions
- ❌ NO `data-test-id` selectors

## 📁 Structure

```
e2e/
├── fixtures/           # Test data and API mocks
│   ├── pdp-fixtures.ts # Product data fixtures
│   └── mock-api.ts     # API mocking helpers
├── helpers/            # Utility functions
│   └── test-isolation.ts # State reset, auth mocks
├── pdp/                # PDP feature tests
│   └── select-size-journey.spec.ts
└── README.md           # This file
```

## 🚀 Running Tests

### Local Development

```bash
# Run all E2E tests (headless)
npm run test:e2e

# Run with UI mode (interactive)
npm run test:e2e:ui

# Run in headed mode (see browser)
npm run test:e2e:headed

# Debug mode (step through tests)
npm run test:e2e:debug

# Run specific test file
npx playwright test e2e/pdp/select-size-journey.spec.ts

# Run tests in a specific browser
npx playwright test --project=chromium
```

### CI Pipeline

Tests run automatically on every PR via GitHub Actions:

```bash
# Install dependencies
npm ci

# Install Playwright browsers
npx playwright install --with-deps

# Build app
npm run build

# Start app server
npm run start &
npx wait-on http://localhost:3000

# Run tests (parallel, 4 shards)
npx playwright test --shard=1/4
```

## 📝 Writing Tests

### Test Contract

Every E2E test MUST follow these rules:

#### ✅ DO

1. **Navigate via URLs**
   ```typescript
   await page.goto('/product/TEST-PROD-001');
   ```

2. **Use accessible selectors**
   ```typescript
   await page.getByRole('button', { name: 'Add to Bag' }).click();
   await expect(page.getByRole('alert')).toContainText('Please select size');
   ```

3. **Assert ARIA attributes**
   ```typescript
   await expect(button).toHaveAttribute('aria-pressed', 'true');
   ```

4. **Test complete journeys**
   ```typescript
   test('should complete checkout flow', async ({ page }) => {
     // 1. Navigate to PDP
     // 2. Select size
     // 3. Add to bag
     // 4. Navigate to checkout
     // 5. Fill form
     // 6. Submit order
     // 7. Assert confirmation page
   });
   ```

#### ❌ DON'T

1. **NO direct prop manipulation**
   ```typescript
   // ❌ BAD (component test style)
   render(<SelectSize variantError={true} />);
   
   // ✅ GOOD (E2E style)
   await page.goto('/product/123');
   await page.getByRole('button', { name: 'Add to Bag' }).click();
   await expect(page.getByRole('alert')).toBeVisible();
   ```

2. **NO `data-test-id`**
   ```typescript
   // ❌ BAD (implementation detail)
   await page.locator('[data-test-id="select-size-title"]').click();
   
   // ✅ GOOD (accessible selector)
   await page.getByRole('heading', { name: /Select Size/i }).isVisible();
   ```

3. **NO CSS class assertions**
   ```typescript
   // ❌ BAD (implementation detail)
   await expect(button).toHaveClass('bg-grey-1000');
   
   // ✅ GOOD (ARIA state)
   await expect(button).toHaveAttribute('aria-pressed', 'true');
   ```

4. **NO component imports**
   ```typescript
   // ❌ BAD (component test)
   import { SelectSize } from '@/components/SelectSize';
   
   // ✅ GOOD (E2E test)
   await page.goto('/product/123');
   ```

### Selector Priority

Use selectors in this order (most preferred first):

1. **Role-based** (best for accessibility)
   ```typescript
   page.getByRole('button', { name: 'Add to Bag' })
   page.getByRole('heading', { name: /Product Name/i })
   page.getByRole('alert')
   ```

2. **Label-based** (good for forms)
   ```typescript
   page.getByLabel('Email address')
   page.getByPlaceholder('Enter your email')
   ```

3. **Text-based** (use sparingly, i18n considerations)
   ```typescript
   page.getByText(/added to bag/i)
   ```

4. **ARIA attributes**
   ```typescript
   page.locator('[aria-pressed="true"]')
   page.locator('[aria-label="Size selector"]')
   ```

5. **NEVER use** (implementation details)
   ```typescript
   // ❌ data-test-id
   // ❌ CSS classes
   // ❌ Deep CSS selectors (.class > div > span)
   ```

## 🎭 Fixtures & Mocking

### Using Fixtures

```typescript
import { mockPdpApi } from '../fixtures/mock-api';

test('should load product', async ({ page }) => {
  // Use predefined fixture
  await mockPdpApi(page, 'inStock');
  await page.goto('/product/TEST-PROD-001');
});
```

Available fixtures:
- `inStock` - Standard product with multiple sizes
- `outOfStock` - Completely out of stock
- `oneSize` - One-size product
- `partialStock` - Some sizes available, some not
- `manySizes` - Product with many size options

### Custom Mocking

```typescript
await page.route('**/api/cart/add', async (route) => {
  await route.fulfill({
    status: 200,
    body: JSON.stringify({ success: true }),
  });
});
```

## 🔍 Debugging

### View Test Report

```bash
# Generate and open HTML report
npx playwright show-report
```

### View Trace

When tests fail in CI, download trace files from artifacts:

```bash
# Download trace.zip from GitHub Actions artifacts
npx playwright show-trace trace.zip
```

### Debug Mode

```bash
# Run single test with debug mode
npx playwright test --debug e2e/pdp/select-size-journey.spec.ts
```

## 📊 CI Integration

### Artifacts on Failure

When tests fail, CI uploads:
- 📸 Screenshots
- 🎥 Videos
- 🔍 Trace files (for Playwright Trace Viewer)

Download from GitHub Actions → Artifacts section.

### Parallel Execution

Tests run in parallel across 4 shards in CI for speed:

```yaml
strategy:
  matrix:
    shardIndex: [1, 2, 3, 4]
    shardTotal: [4]
```

Adjust shard count in `.github/workflows/e2e-tests.yml` based on test count.

## 🛡️ Quality Gates

### ESLint Rules

- Disallow `data-test-id` in `e2e/**`
- Disallow `toHaveClass()` assertions
- Require descriptive test names

### Pre-Commit Hook

```bash
# Checks staged E2E tests for violations
.husky/pre-commit
```

## 📚 Resources

- [Playwright Documentation](https://playwright.dev)
- [Playwright Best Practices](https://playwright.dev/docs/best-practices)
- [Accessibility Selectors](https://playwright.dev/docs/selectors#role-selector)
- [Trace Viewer](https://playwright.dev/docs/trace-viewer)

## 🆘 Common Issues

### Test is flaky

- Use `await expect().toBeVisible()` instead of `await expect().toBeInTheDocument()`
- Add explicit waits: `await page.waitForLoadState('networkidle')`
- Check for animations/transitions that might delay element visibility

### Selector not found

- Check if element is in viewport: `await expect(el).toBeInViewport()`
- Verify ARIA roles: Inspect element in browser DevTools
- Use Playwright Inspector: `npx playwright test --debug`

### Slow tests

- Reduce retries in local dev: `retries: 0` in `playwright.config.ts`
- Use `page.goto('/', { waitUntil: 'commit' })` for faster navigation
- Mock slow APIs with `mockSlowApi()` helper

### CI failures but local passes

- Check viewport size differences (CI runs headless)
- Verify network mocking is active in CI
- Download trace files from CI artifacts to debug
