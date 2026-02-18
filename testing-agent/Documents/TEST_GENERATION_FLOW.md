# Test Generation Flow - Visual Guide

## 🔄 Complete Integration Test Generation Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    USER INPUT                                │
│  - Selects "Integration Testing" in UI                      │
│  - Provides React component: index.tsx                      │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│               STRATEGY AGENT                                 │
│  Step 1: Analyze file characteristics                       │
│    - Has React JSX? ✓                                       │
│    - Uses hooks? ✓                                          │
│    - Has context/API calls? ✓                               │
│                                                              │
│  Step 2: Classify test level                                │
│    → RESULT: "integration"                                  │
│                                                              │
│  Step 3: Determine file name                                │
│    → RESULT: "index.integration.test.tsx"                   │
│                                                              │
│  Step 4: Find related files                                 │
│    → Context files, hooks, APIs                             │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│            ENVIRONMENT SETUP AGENT                           │
│  (Only for Integration/Feature tests)                       │
│                                                              │
│  Setup:                                                      │
│  - Ensure @testing-library/react installed                  │
│  - Ensure @testing-library/user-event installed             │
│  - Check jest.config.js                                     │
│  - Verify setupTests.ts exists                              │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│            TEST GENERATOR AGENT                              │
│                                                              │
│  Input:                                                      │
│  - Source: index.tsx                                        │
│  - Test Level: "integration"                                │
│  - Related files: [context, hooks]                          │
│                                                              │
│  AI Prompt Includes:                                         │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ REQUIRED IMPORTS:                                     │  │
│  │ import { render, screen } from '@testing-library/...'│  │
│  │ import { userEvent } from '@testing-library/user-...'│  │
│  │                                                       │  │
│  │ REQUIRED SETUP:                                       │  │
│  │ let user: ReturnType<typeof userEvent.setup>;        │  │
│  │ beforeEach(() => { user = userEvent.setup(); });     │  │
│  │                                                       │  │
│  │ REQUIRED TEST STRUCTURE:                              │  │
│  │ it('action WHEN condition', async () => {            │  │
│  │   render(<Component />);                             │  │
│  │   await user.click(...);                             │  │
│  │   expect(...).toBeInTheDocument();                   │  │
│  │ });                                                   │  │
│  │                                                       │  │
│  │ QUERY PRIORITY:                                       │  │
│  │ 1. getByRole (MOST PREFERRED)                        │  │
│  │ 2. getByLabelText                                    │  │
│  │ 3. getByPlaceholderText                              │  │
│  │ 4. getByText                                         │  │
│  │ 5. getByTestId (LAST RESORT)                         │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  AI Generates:                                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ import { render, screen } from '@testing-library/... │  │
│  │ import { userEvent } from '@testing-library/user-... │  │
│  │ import { SelectSize } from './index';                │  │
│  │                                                       │  │
│  │ describe('SelectSize Feature', () => {               │  │
│  │   let user: ReturnType<typeof userEvent.setup>;      │  │
│  │                                                       │  │
│  │   beforeEach(() => {                                 │  │
│  │     user = userEvent.setup();                        │  │
│  │   });                                                │  │
│  │                                                       │  │
│  │   afterEach(() => {                                  │  │
│  │     jest.clearAllMocks();                            │  │
│  │   });                                                │  │
│  │                                                       │  │
│  │   it('renders sizes WHEN available', () => {        │  │
│  │     render(<SelectSize />);                          │  │
│  │     expect(screen.getByRole('button', {             │  │
│  │       name: 'UK 8'                                   │  │
│  │     })).toBeInTheDocument();                         │  │
│  │   });                                                │  │
│  │                                                       │  │
│  │   it('updates WHEN clicked', async () => {          │  │
│  │     render(<SelectSize />);                          │  │
│  │     const btn = screen.getByRole('button', {        │  │
│  │       name: 'UK 8'                                   │  │
│  │     });                                              │  │
│  │     await user.click(btn);                           │  │
│  │     expect(btn).toHaveClass('selected');             │  │
│  │   });                                                │  │
│  │ });                                                  │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  Output File: index.integration.test.tsx                    │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│            TEST EXECUTOR AGENT                               │
│                                                              │
│  Execution Rules for "integration":                         │
│  - Mode: Sequential (--runInBand)                           │
│  - Timeout: 60 seconds                                      │
│  - Retry Limit: 2 attempts                                  │
│                                                              │
│  Command:                                                    │
│  jest index.integration.test.tsx --runInBand --coverage     │
│                                                              │
│  Monitors:                                                   │
│  - Test pass/fail status                                    │
│  - Coverage percentage                                      │
│  - Execution time                                           │
│  - Error messages                                           │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│            FAILURE ANALYZER AGENT                            │
│  (Only runs if tests fail)                                  │
│                                                              │
│  Analyzes:                                                   │
│  - Missing imports?                                         │
│  - userEvent not setup?                                     │
│  - Query selector issues?                                   │
│  - Async/await problems?                                    │
│  - Environment setup missing?                               │
│                                                              │
│  Decides:                                                    │
│  - Retry test? (if flaky)                                   │
│  - Fix environment? (if setup issue)                        │
│  - Report failure? (if real bug)                            │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│                 REPORT AGENT                                 │
│                                                              │
│  Generates:                                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ TEST RESULTS SUMMARY                                  │  │
│  │                                                       │  │
│  │ Integration Tests:                                    │  │
│  │   File: index.integration.test.tsx                    │  │
│  │   Tests: 2 passed, 0 failed                           │  │
│  │   Coverage: 87%                                       │  │
│  │   Time: 2.3s                                          │  │
│  │                                                       │  │
│  │ Details:                                              │  │
│  │   ✓ renders sizes WHEN available                     │  │
│  │   ✓ updates WHEN clicked                             │  │
│  │                                                       │  │
│  │ Coverage Breakdown:                                   │  │
│  │   Statements: 87%                                     │  │
│  │   Branches: 82%                                       │  │
│  │   Functions: 90%                                      │  │
│  │   Lines: 87%                                          │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│              STREAMLIT UI DISPLAY                            │
│                                                              │
│  Shows:                                                      │
│  - Test level tabs (Unit | Integration | Feature)          │
│  - Per-level results                                        │
│  - Coverage charts by level                                 │
│  - Test execution logs                                      │
│  - Download test files button                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 Key Decision Points

### Decision Point 1: Test Level Classification

```
File: index.tsx
Has React? YES
Has hooks? YES (useContext, useEffect)
Has API calls? NO
In feature folder? NO
Multiple components? NO

DECISION: INTEGRATION TEST
Reasoning: React component with hooks and context
```

### Decision Point 2: File Naming

```
Test Level: integration
Source File: index.tsx
Extension: .tsx

DECISION: index.integration.test.tsx
Pattern: {filename}.integration.test.{extension}
```

### Decision Point 3: Test Structure

```
Test Level: integration
Framework: Jest + RTL

REQUIREMENTS APPLIED:
✓ userEvent.setup() in beforeEach
✓ Helper render function
✓ WHEN clauses in test names
✓ getByRole queries
✓ await user.* interactions
✓ Proper cleanup in afterEach
```

### Decision Point 4: Execution Strategy

```
Test Level: integration
File Count: 1 file

EXECUTION CONFIG:
- Mode: Sequential (--runInBand)
- Timeout: 60s
- Retries: 2
- Reason: Integration tests may have timing dependencies
```

---

## 📊 Quality Checks at Each Stage

### Strategy Agent Quality Checks
- ✓ Test level correctly classified
- ✓ File naming follows convention
- ✓ Related files identified
- ✓ Test type (component/unit) determined

### Generator Agent Quality Checks
- ✓ Correct imports present
- ✓ userEvent setup in beforeEach
- ✓ Test names include WHEN clauses
- ✓ Queries use getByRole primarily
- ✓ User interactions use await
- ✓ Cleanup in afterEach

### Executor Agent Quality Checks
- ✓ Correct execution mode (sequential)
- ✓ Proper timeout applied
- ✓ Coverage tracking enabled
- ✓ Error capturing configured

### Report Agent Quality Checks
- ✓ Test results grouped by level
- ✓ Coverage calculated correctly
- ✓ Pass/fail status accurate
- ✓ Execution time recorded

---

## 🔍 Example Trace

Let's trace a real example:

**Input:** `SelectSize` component from `index.tsx`

```typescript
// index.tsx
export function SelectSize({ className, variantError }: SelectSizeProps) {
  const { state, product } = useContext(ProductDetailsPageContext);
  const { showSelectVariantError } = state;
  // ... more code
}
```

**Step-by-Step:**

1. **Strategy Agent analyzes:**
   - File type: TypeScript React (.tsx)
   - Has JSX: YES
   - Uses hooks: YES (useContext, useEffect)
   - Complexity: Medium (73 lines)
   - **Classification: INTEGRATION**
   - **Test file: index.integration.test.tsx**

2. **Environment Setup:**
   - Checks @testing-library/react: ✓ Installed
   - Checks @testing-library/user-event: ✓ Installed
   - Checks jest.config.js: ✓ Configured

3. **Generator creates test:**
   - Loads integration-specific prompt
   - AI generates with required structure:
     - userEvent setup ✓
     - Helper render function ✓
     - WHEN clauses ✓
     - getByRole queries ✓

4. **Executor runs:**
   - Command: `jest index.integration.test.tsx --runInBand`
   - Timeout: 60s
   - Result: 2 tests pass, 87% coverage

5. **Report displays:**
   - Integration Tests tab shows results
   - Coverage chart updated
   - Test logs available

**Output:** Production-grade integration test matching your example pattern!

---

## 🎨 Visual Pattern Comparison

### Input Pattern (Your Component)
```typescript
// index.tsx
'use client'
import { useContext, useEffect } from 'react'

export function SelectSize({ className, variantError }: SelectSizeProps) {
  const { state, product } = useContext(ProductDetailsPageContext);
  // ... component logic
}
```

### Output Pattern (Generated Test)
```typescript
// index.integration.test.tsx
import { render, screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { SelectSize } from './index';

describe('SelectSize Feature', () => {
  let user: ReturnType<typeof userEvent.setup>;
  
  beforeEach(() => {
    user = userEvent.setup();
  });
  
  it('renders sizes WHEN available', () => {
    render(<SelectSize />);
    expect(screen.getByRole('button', { name: 'UK 8' })).toBeInTheDocument();
  });
  
  it('updates WHEN clicked', async () => {
    render(<SelectSize />);
    await user.click(screen.getByRole('button', { name: 'UK 8' }));
    expect(screen.getByRole('button', { name: 'UK 8' })).toHaveClass('selected');
  });
});
```

**Perfect Match! ✅**

---

**This flow ensures every integration/feature test generated matches your production-grade example structure!**
