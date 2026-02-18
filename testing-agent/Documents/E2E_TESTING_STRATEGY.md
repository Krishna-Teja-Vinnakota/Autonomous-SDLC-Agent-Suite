# E2E Testing Strategy: Feature-Level Test Architecture

## 1. Tool Selection: **Playwright** ✅

### Why Playwright over Cypress
- ✅ Native multi-browser (Chrome, Firefox, WebKit)
- ✅ Built-in parallel execution (`--shard`)
- ✅ Superior CI artifacts (traces, videos, screenshots)
- ✅ Better network mocking (`page.route()`)
- ✅ Faster headless performance (~30% faster in CI)
- ✅ First-class TypeScript support

## 2. CI Pipeline Architecture

### Pipeline Stages (GitHub Actions)
```
1. Install dependencies (npm ci)
2. Install Playwright browsers (chromium for speed)
3. Build application (npm run build)
4. Start app server on port 3000
5. Health check (wait-on http://localhost:3000)
6. Run E2E tests in parallel (4 shards)
7. Upload artifacts on failure (screenshots/videos/traces)
8. Merge reports from all shards
```

**Key Features:**
- ⚡ Parallel execution across 4 shards
- 🔄 Auto-retry on failure (2 retries in CI)
- 📊 HTML report merging
- 🎯 Trace viewer for debugging
- ⏱️ 20-minute timeout protection

## 3. Deterministic Data Strategy

### Approach: Network Boundary Mocking (Playwright Route)

**Why NOT test database:**
- ❌ Slow DB resets (~2-5s per test)
- ❌ Race conditions in parallel runs
- ❌ Infrastructure complexity

**Why Playwright route mocking:**
- ✅ Fast (~50ms setup)
- ✅ Deterministic responses
- ✅ No test pollution
- ✅ Works in parallel

### Implementation
```typescript
// Predefined fixtures
await mockPdpApi(page, 'inStock');    // Multi-size product
await mockPdpApi(page, 'outOfStock'); // Out of stock
await mockPdpApi(page, 'oneSize');    // One-size product
await mockPdpApi(page, 'partialStock'); // Some sizes unavailable
```

## 4. Feature Test Contract

### ✅ REQUIRED
1. Navigate via URLs: `page.goto('/product/123')`
2. Use accessible selectors: `getByRole('button', { name: 'Add to Bag' })`
3. Assert ARIA attributes: `expect(el).toHaveAttribute('aria-pressed', 'true')`
4. Test complete journeys: PDP → size selection → add-to-bag → cart

### ❌ FORBIDDEN
1. NO direct props: ~~`<SelectSize variantError={true} />`~~
2. NO data-test-id: ~~`getByTestId('size-selector')`~~
3. NO CSS classes: ~~`expect(el).toHaveClass('bg-grey-1000')`~~
4. NO component imports: ~~`import { SelectSize }`~~

### Quality Gates
- **ESLint rules** enforce selector restrictions
- **Pre-commit hooks** block violations
- **Folder structure** separates unit vs E2E (`src/**/*.test.tsx` vs `e2e/**/*.spec.ts`)

## 5. SelectSize Journey Rewrite

### Before (Component Integration) ❌
```typescript
// OLD: index.feature.test.tsx
it('displays error state WHEN validation fails', () => {
  renderSelectSizePdp(mockProduct, true); // Direct prop
  expect(screen.getByText(/sizeError/i)).toBeInTheDocument();
});
```

### After (Feature Journey) ✅
```typescript
// NEW: e2e/pdp/select-size-journey.spec.ts
test('should display validation error when adding to bag without size', async ({ page }) => {
  await mockPdpApi(page, 'inStock');
  await page.goto('/product/TEST-PROD-001');
  
  // Try add-to-bag without size
  await page.getByRole('button', { name: /Add to Bag/i }).click();
  
  // Assert error appears
  await expect(page.getByRole('alert')).toContainText(/please select.*size/i);
  
  // Assert size selector scrolls into view
  await expect(page.locator('[aria-label="Size selector"]')).toBeInViewport();
  
  // Select size
  await page.getByRole('button', { name: 'UK 8' }).click();
  await expect(page.getByRole('button', { name: 'UK 8' })).toHaveAttribute('aria-pressed', 'true');
  
  // Add to bag succeeds
  await page.getByRole('button', { name: /Add to Bag/i }).click();
  await expect(page.getByRole('status')).toContainText(/added to bag/i);
});
```

## 6. File Structure

```
project/
├── src/components/         # Component unit tests (Jest)
│   └── *.unit.test.tsx
├── e2e/                    # Feature E2E tests (Playwright)
│   ├── fixtures/
│   │   ├── pdp-fixtures.ts
│   │   └── mock-api.ts
│   ├── helpers/
│   │   └── test-isolation.ts
│   └── pdp/
│       └── select-size-journey.spec.ts
├── playwright.config.ts
└── .github/workflows/e2e-tests.yml
```

## Quick Start

### 1. Install Playwright
```bash
npm install -D @playwright/test wait-on
npx playwright install --with-deps
```

### 2. Update package.json
```json
{
  "scripts": {
    "test:unit": "jest",
    "test:e2e": "playwright test",
    "test:e2e:ui": "playwright test --ui",
    "test:all": "npm run test:unit && npm run test:e2e"
  }
}
```

### 3. Run Tests
```bash
# Local development
npm run test:e2e:ui

# CI simulation
npm run build
npm run start &
npx wait-on http://localhost:3000
npm run test:e2e
```

### 4. Debug Failures
```bash
# Download trace.zip from CI artifacts
npx playwright show-trace trace.zip
```

## Migration Checklist

- [x] Install Playwright + create config
- [x] Create `e2e/` folder structure
- [x] Create fixtures (pdp-fixtures.ts, mock-api.ts)
- [x] Create helpers (test-isolation.ts)
- [x] Write sample E2E test (select-size-journey.spec.ts)
- [x] Setup CI pipeline (GitHub Actions)
- [x] Add ESLint rules for E2E quality gates
- [ ] Update test generator agent to produce E2E tests
- [ ] Migrate existing *.feature.test.tsx → e2e/*.spec.ts
- [ ] Add pre-commit hooks
- [ ] Document in team wiki

## Key Metrics

| Metric | Target |
|--------|--------|
| Test execution time | < 5 min (parallel) |
| Flakiness rate | < 2% |
| Coverage | 80% critical journeys |
| Debug time (with trace) | < 10 min |

## Resources

- Playwright Docs: https://playwright.dev
- Trace Viewer: https://playwright.dev/docs/trace-viewer
- Best Practices: https://playwright.dev/docs/best-practices
