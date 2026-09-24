/**
 * Deterministic test fixtures for PDP feature tests
 * These fixtures ensure consistent, repeatable test data
 */

export interface ProductVariant {
  sku: string;
  size: string;
  stock: {
    available: boolean;
    quantity?: number;
  };
}

export interface Product {
  productId: string;
  name: string;
  description?: string;
  price?: number;
  currency?: string;
  variants: ProductVariant[];
  isOutOfStock: boolean;
  isOneSize: boolean;
}

/**
 * Standard test fixtures for PDP testing
 * Use these in tests via mockPdpApi(page, 'inStock')
 */
export const PDP_FIXTURES: Record<string, Product> = {
  /**
   * Standard in-stock product with multiple sizes
   * Use for: Happy path tests, size selection flows
   */
  inStock: {
    productId: 'TEST-PROD-001',
    name: 'Classic Sneaker',
    description: 'Comfortable everyday sneaker',
    price: 79.99,
    currency: 'GBP',
    variants: [
      { sku: 'SKU-UK8', size: 'UK 8', stock: { available: true, quantity: 10 } },
      { sku: 'SKU-UK9', size: 'UK 9', stock: { available: true, quantity: 5 } },
      { sku: 'SKU-UK10', size: 'UK 10', stock: { available: true, quantity: 20 } },
    ],
    isOutOfStock: false,
    isOneSize: false,
  },
  
  /**
   * Completely out-of-stock product
   * Use for: Out-of-stock display tests, disabled add-to-bag tests
   */
  outOfStock: {
    productId: 'TEST-PROD-002',
    name: 'Limited Edition Trainer',
    description: 'Sold out everywhere',
    price: 149.99,
    currency: 'GBP',
    variants: [],
    isOutOfStock: true,
    isOneSize: false,
  },
  
  /**
   * One-size product (no size selection needed)
   * Use for: One-size flow tests, direct add-to-bag tests
   */
  oneSize: {
    productId: 'TEST-PROD-003',
    name: 'Universal Baseball Cap',
    description: 'Adjustable fit',
    price: 24.99,
    currency: 'GBP',
    variants: [
      { sku: 'SKU-OS', size: 'One Size', stock: { available: true, quantity: 100 } },
    ],
    isOutOfStock: false,
    isOneSize: true,
  },
  
  /**
   * Partial stock (some sizes out, some in)
   * Use for: Testing dynamic size availability
   */
  partialStock: {
    productId: 'TEST-PROD-004',
    name: 'Popular Running Shoe',
    description: 'Limited sizes remaining',
    price: 99.99,
    currency: 'GBP',
    variants: [
      { sku: 'SKU-UK7', size: 'UK 7', stock: { available: false } }, // Out
      { sku: 'SKU-UK8', size: 'UK 8', stock: { available: false } }, // Out
      { sku: 'SKU-UK9', size: 'UK 9', stock: { available: true, quantity: 2 } }, // Low stock
      { sku: 'SKU-UK10', size: 'UK 10', stock: { available: true, quantity: 1 } }, // Low stock
    ],
    isOutOfStock: false,
    isOneSize: false,
  },
  
  /**
   * Product with many size options
   * Use for: Testing UI with large size selection
   */
  manySizes: {
    productId: 'TEST-PROD-005',
    name: 'Versatile Trainer',
    description: 'Available in all sizes',
    price: 89.99,
    currency: 'GBP',
    variants: [
      { sku: 'SKU-UK6', size: 'UK 6', stock: { available: true, quantity: 5 } },
      { sku: 'SKU-UK7', size: 'UK 7', stock: { available: true, quantity: 8 } },
      { sku: 'SKU-UK8', size: 'UK 8', stock: { available: true, quantity: 12 } },
      { sku: 'SKU-UK9', size: 'UK 9', stock: { available: true, quantity: 15 } },
      { sku: 'SKU-UK10', size: 'UK 10', stock: { available: true, quantity: 10 } },
      { sku: 'SKU-UK11', size: 'UK 11', stock: { available: true, quantity: 6 } },
      { sku: 'SKU-UK12', size: 'UK 12', stock: { available: true, quantity: 3 } },
    ],
    isOutOfStock: false,
    isOneSize: false,
  },
};
