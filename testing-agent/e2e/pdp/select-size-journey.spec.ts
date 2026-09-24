import { test, expect } from '@playwright/test';
import { mockPdpApi } from '../fixtures/mock-api';
import { resetAppState, waitForAppReady } from '../helpers/test-isolation';

/**
 * E2E Feature Tests: PDP Size Selection Journey
 * 
 * These tests validate the COMPLETE user journey for selecting a size
 * on the Product Detail Page (PDP), NOT just the SelectSize component.
 * 
 * Test Strategy:
 * - Navigate to real PDP URLs
 * - Use accessible selectors (getByRole, getByLabel, etc.)
 * - Assert user-visible outcomes (error messages, success states)
 * - Avoid implementation details (CSS classes, data-test-id, props)
 */
test.describe('PDP - Size Selection Feature Journey', () => {
  /**
   * Reset state before each test to ensure isolation
   */
  test.beforeEach(async ({ page }) => {
    await resetAppState(page);
  });
  
  /**
   * Happy Path: Complete journey from validation error to successful add-to-bag
   */
  test('should complete full journey: validation error → size selection → add to bag', async ({ page }) => {
    // ARRANGE: Mock product API with in-stock product
    await mockPdpApi(page, 'inStock');
    
    // ACT: Navigate to PDP
    await page.goto('/product/TEST-PROD-001');
    await waitForAppReady(page);
    
    // ASSERT: Product loaded successfully
    await expect(page.getByRole('heading', { name: /Classic Sneaker/i })).toBeVisible();
    await expect(page.getByText(/£79.99/)).toBeVisible();
    
    // ASSERT: Size selection UI is present
    await expect(page.getByText(/Select Size/i)).toBeVisible();
    await expect(page.getByRole('button', { name: 'UK 8' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'UK 9' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'UK 10' })).toBeVisible();
    
    // ACT: Try to add to bag WITHOUT selecting a size
    const addToBagButton = page.getByRole('button', { name: /Add to Bag/i });
    await addToBagButton.click();
    
    // ASSERT: Validation error appears
    const errorAlert = page.getByRole('alert');
    await expect(errorAlert).toBeVisible();
    await expect(errorAlert).toContainText(/please select.*size/i);
    
    // ASSERT: Size selector scrolls into view (user is guided to the error)
    const sizeSection = page.locator('[aria-label*="size" i], [role="group"][aria-labelledby*="size"]').first();
    await expect(sizeSection).toBeInViewport();
    
    // ACT: Select UK 9
    const uk9Button = page.getByRole('button', { name: 'UK 9' });
    await uk9Button.click();
    
    // ASSERT: UK 9 is marked as selected (via ARIA attribute, NOT CSS class)
    await expect(uk9Button).toHaveAttribute('aria-pressed', 'true');
    
    // ASSERT: Other sizes are not selected
    await expect(page.getByRole('button', { name: 'UK 8' })).toHaveAttribute('aria-pressed', 'false');
    await expect(page.getByRole('button', { name: 'UK 10' })).toHaveAttribute('aria-pressed', 'false');
    
    // ASSERT: Validation error disappears after selection
    await expect(errorAlert).not.toBeVisible();
    
    // ACT: Add to bag
    await addToBagButton.click();
    
    // ASSERT: Success message appears
    const successStatus = page.getByRole('status').or(page.getByText(/added to bag/i));
    await expect(successStatus).toBeVisible({ timeout: 5000 });
    
    // ASSERT: Cart count is updated
    const cartBadge = page.getByRole('link', { name: /cart/i }).or(page.locator('[aria-label*="cart" i]'));
    await expect(cartBadge).toContainText('1');
  });
  
  /**
   * Size Selection: User can change selected size
   */
  test('should allow user to change size selection', async ({ page }) => {
    await mockPdpApi(page, 'inStock');
    await page.goto('/product/TEST-PROD-001');
    await waitForAppReady(page);
    
    const uk8Button = page.getByRole('button', { name: 'UK 8' });
    const uk9Button = page.getByRole('button', { name: 'UK 9' });
    
    // ACT: Select UK 8
    await uk8Button.click();
    
    // ASSERT: UK 8 is selected
    await expect(uk8Button).toHaveAttribute('aria-pressed', 'true');
    await expect(uk9Button).toHaveAttribute('aria-pressed', 'false');
    
    // ACT: Change selection to UK 9
    await uk9Button.click();
    
    // ASSERT: UK 9 is now selected, UK 8 is deselected
    await expect(uk9Button).toHaveAttribute('aria-pressed', 'true');
    await expect(uk8Button).toHaveAttribute('aria-pressed', 'false');
  });
  
  /**
   * Out of Stock: Display and behavior
   */
  test('should display out-of-stock badge and disable add-to-bag', async ({ page }) => {
    await mockPdpApi(page, 'outOfStock');
    await page.goto('/product/TEST-PROD-002');
    await waitForAppReady(page);
    
    // ASSERT: Out-of-stock badge is visible
    await expect(page.getByText(/out of stock/i)).toBeVisible();
    
    // ASSERT: Add-to-bag button is disabled
    const addToBagButton = page.getByRole('button', { name: /Add to Bag/i });
    await expect(addToBagButton).toBeDisabled();
    
    // ASSERT: No size selection buttons (product is fully out of stock)
    await expect(page.getByRole('button', { name: /UK \d+/ })).toHaveCount(0);
  });
  
  /**
   * Partial Stock: Only show available sizes
   */
  test('should hide unavailable sizes from selection', async ({ page }) => {
    await mockPdpApi(page, 'partialStock');
    await page.goto('/product/TEST-PROD-004');
    await waitForAppReady(page);
    
    // ASSERT: Out-of-stock sizes are NOT shown
    await expect(page.getByRole('button', { name: 'UK 7' })).not.toBeVisible();
    await expect(page.getByRole('button', { name: 'UK 8' })).not.toBeVisible();
    
    // ASSERT: In-stock sizes ARE shown
    await expect(page.getByRole('button', { name: 'UK 9' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'UK 10' })).toBeVisible();
    
    // ACT: Select available size and add to bag
    await page.getByRole('button', { name: 'UK 9' }).click();
    await page.getByRole('button', { name: /Add to Bag/i }).click();
    
    // ASSERT: Add to bag succeeds
    await expect(page.getByText(/added to bag/i)).toBeVisible({ timeout: 5000 });
  });
  
  /**
   * One-Size Product: No size selection needed
   */
  test('should allow direct add-to-bag for one-size products', async ({ page }) => {
    await mockPdpApi(page, 'oneSize');
    await page.goto('/product/TEST-PROD-003');
    await waitForAppReady(page);
    
    // ASSERT: Size is displayed as static text, not a button
    await expect(page.getByText(/size.*one size/i)).toBeVisible();
    
    // ASSERT: No size selection buttons
    await expect(page.getByRole('button', { name: /UK \d+/ })).toHaveCount(0);
    
    // ACT: Add to bag directly (no size selection required)
    await page.getByRole('button', { name: /Add to Bag/i }).click();
    
    // ASSERT: Add to bag succeeds without size selection
    await expect(page.getByText(/added to bag/i)).toBeVisible({ timeout: 5000 });
  });
  
  /**
   * Accessibility: Keyboard navigation
   */
  test('should support keyboard navigation for size selection', async ({ page }) => {
    await mockPdpApi(page, 'inStock');
    await page.goto('/product/TEST-PROD-001');
    await waitForAppReady(page);
    
    // ACT: Focus first size button via Tab
    await page.keyboard.press('Tab');
    
    // Find first size button and ensure it's focused
    const uk8Button = page.getByRole('button', { name: 'UK 8' });
    await expect(uk8Button).toBeFocused();
    
    // ACT: Select via Space/Enter
    await page.keyboard.press('Space');
    
    // ASSERT: Size is selected
    await expect(uk8Button).toHaveAttribute('aria-pressed', 'true');
    
    // ACT: Navigate to next size button with Tab
    await page.keyboard.press('Tab');
    const uk9Button = page.getByRole('button', { name: 'UK 9' });
    
    // ACT: Select next size with Enter
    await page.keyboard.press('Enter');
    
    // ASSERT: New size is selected
    await expect(uk9Button).toHaveAttribute('aria-pressed', 'true');
    await expect(uk8Button).toHaveAttribute('aria-pressed', 'false');
  });
  
  /**
   * Mobile Viewport: Size selection on mobile
   */
  test('should work correctly on mobile viewport', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    
    await mockPdpApi(page, 'inStock');
    await page.goto('/product/TEST-PROD-001');
    await waitForAppReady(page);
    
    // ASSERT: Size buttons are visible and tappable on mobile
    const uk8Button = page.getByRole('button', { name: 'UK 8' });
    await expect(uk8Button).toBeVisible();
    
    // ACT: Tap size button
    await uk8Button.tap();
    
    // ASSERT: Size is selected
    await expect(uk8Button).toHaveAttribute('aria-pressed', 'true');
    
    // ACT: Tap add to bag
    await page.getByRole('button', { name: /Add to Bag/i }).tap();
    
    // ASSERT: Success
    await expect(page.getByText(/added to bag/i)).toBeVisible();
  });
});
