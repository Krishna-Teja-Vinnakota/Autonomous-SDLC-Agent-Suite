import { Page, Route } from '@playwright/test';
import { PDP_FIXTURES, Product } from './pdp-fixtures';

/**
 * Mock PDP API responses for deterministic testing
 * This ensures tests don't depend on real backend data
 * 
 * @param page - Playwright page instance
 * @param fixture - Key from PDP_FIXTURES
 * 
 * @example
 * ```typescript
 * test('should load product', async ({ page }) => {
 *   await mockPdpApi(page, 'inStock');
 *   await page.goto('/product/TEST-PROD-001');
 * });
 * ```
 */
export async function mockPdpApi(
  page: Page,
  fixture: keyof typeof PDP_FIXTURES
): Promise<void> {
  const product = PDP_FIXTURES[fixture];
  
  // Mock product API endpoint
  await page.route('**/api/products/**', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      headers: {
        'Access-Control-Allow-Origin': '*',
      },
      body: JSON.stringify({
        data: product,
        success: true,
      }),
    });
  });
  
  // Mock GraphQL product query (if using GraphQL)
  await page.route('**/graphql', async (route: Route) => {
    const postData = route.request().postDataJSON();
    
    if (postData?.query?.includes('getProduct')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          data: {
            product,
          },
        }),
      });
    } else {
      await route.continue();
    }
  });
  
  // Mock add-to-bag/cart API
  await page.route('**/api/cart/add', async (route: Route) => {
    const postData = route.request().postDataJSON();
    
    // Simulate backend validation
    if (!postData?.sku) {
      await route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({
          error: 'SKU is required',
          message: 'Please select a size',
        }),
      });
      return;
    }
    
    // Check if SKU is available
    const variant = product.variants.find((v) => v.sku === postData.sku);
    if (!variant || !variant.stock.available) {
      await route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({
          error: 'Product unavailable',
          message: 'This size is out of stock',
        }),
      });
      return;
    }
    
    // Success
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        cartItemId: `CART-${Date.now()}`,
        cart: {
          itemCount: 1,
          items: [
            {
              sku: postData.sku,
              quantity: postData.quantity || 1,
              product: product.name,
              size: variant.size,
            },
          ],
        },
      }),
    });
  });
  
  // Mock cart count API
  await page.route('**/api/cart', async (route: Route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          itemCount: 0,
          items: [],
        }),
      });
    } else {
      await route.continue();
    }
  });
}

/**
 * Mock API failure scenarios for error handling tests
 */
export async function mockApiFailure(
  page: Page,
  endpoint: string,
  statusCode: number = 500
): Promise<void> {
  await page.route(`**/${endpoint}`, async (route: Route) => {
    await route.fulfill({
      status: statusCode,
      contentType: 'application/json',
      body: JSON.stringify({
        error: 'Internal Server Error',
        message: 'Something went wrong',
      }),
    });
  });
}

/**
 * Mock slow API response for loading state tests
 */
export async function mockSlowApi(
  page: Page,
  endpoint: string,
  delayMs: number = 3000
): Promise<void> {
  await page.route(`**/${endpoint}`, async (route: Route) => {
    await new Promise((resolve) => setTimeout(resolve, delayMs));
    await route.continue();
  });
}
