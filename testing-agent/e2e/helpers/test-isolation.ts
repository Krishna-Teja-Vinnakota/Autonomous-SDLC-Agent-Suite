import { Page } from '@playwright/test';

/**
 * Reset application state to ensure test isolation
 * Call this in beforeEach to prevent test pollution
 * 
 * @example
 * ```typescript
 * test.beforeEach(async ({ page }) => {
 *   await resetAppState(page);
 * });
 * ```
 */
export async function resetAppState(page: Page): Promise<void> {
  // Clear all cookies
  await page.context().clearCookies();
  
  // Clear localStorage and sessionStorage
  await page.evaluate(() => {
    localStorage.clear();
    sessionStorage.clear();
  });
  
  // Clear any IndexedDB databases (if your app uses them)
  await page.evaluate(() => {
    return new Promise<void>((resolve) => {
      const dbs = indexedDB.databases?.() || Promise.resolve([]);
      dbs.then((databases) => {
        databases.forEach((db) => {
          if (db.name) {
            indexedDB.deleteDatabase(db.name);
          }
        });
        resolve();
      });
    });
  });
}

/**
 * Wait for application to be fully loaded and hydrated
 * Useful for Next.js/React apps that have client-side hydration
 */
export async function waitForAppReady(page: Page): Promise<void> {
  // Wait for React to hydrate (adjust selector based on your app)
  await page.waitForSelector('[data-reactroot], #__next', {
    state: 'attached',
    timeout: 10000,
  });
  
  // Wait for any loading spinners to disappear
  await page.waitForSelector('[data-loading="true"], .loading-spinner', {
    state: 'hidden',
    timeout: 5000,
  }).catch(() => {
    // Spinner might not exist, that's fine
  });
  
  // Wait for network to be idle
  await page.waitForLoadState('networkidle', { timeout: 10000 });
}

/**
 * Set viewport size (useful for responsive testing)
 */
export async function setViewport(
  page: Page,
  device: 'mobile' | 'tablet' | 'desktop'
): Promise<void> {
  const viewports = {
    mobile: { width: 375, height: 667 },
    tablet: { width: 768, height: 1024 },
    desktop: { width: 1920, height: 1080 },
  };
  
  await page.setViewportSize(viewports[device]);
}

/**
 * Mock locale/language for i18n testing
 */
export async function setLocale(page: Page, locale: string): Promise<void> {
  await page.addInitScript((loc) => {
    Object.defineProperty(navigator, 'language', {
      get() {
        return loc;
      },
    });
  }, locale);
}

/**
 * Login helper (adjust based on your auth mechanism)
 * Example for cookie-based auth
 */
export async function mockAuthentication(
  page: Page,
  user: { id: string; email: string; token?: string }
): Promise<void> {
  // Add auth cookie
  await page.context().addCookies([
    {
      name: 'auth_token',
      value: user.token || 'mock-jwt-token',
      domain: new URL(page.url()).hostname,
      path: '/',
      httpOnly: true,
      secure: false,
      sameSite: 'Lax',
    },
  ]);
  
  // Set user data in localStorage (if your app uses it)
  await page.evaluate((userData) => {
    localStorage.setItem('user', JSON.stringify(userData));
  }, user);
}

/**
 * Wait for a network request to complete
 * Useful for asserting API calls were made
 */
export async function waitForApiCall(
  page: Page,
  urlPattern: string | RegExp
): Promise<void> {
  await page.waitForResponse((response) => {
    const url = response.url();
    return typeof urlPattern === 'string'
      ? url.includes(urlPattern)
      : urlPattern.test(url);
  });
}
