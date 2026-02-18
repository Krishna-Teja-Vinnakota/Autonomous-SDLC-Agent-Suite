# Jest Setup Guide

This guide will help you install and configure Jest with React Testing Library for testing React components.

## Prerequisites

- Node.js (v14 or higher recommended)
- npm or yarn package manager

## Installation Steps

### 1. Install Dependencies

Open your terminal in the project root directory and run:

```bash
npm install
```

This will install all the required dependencies including:
- Jest (testing framework)
- React Testing Library (for React component testing)
- Babel (for JSX/ES6+ transformation)
- Other testing utilities

### 2. Verify Installation

After installation, verify Jest is working:

```bash
npm test
```

If you see Jest's help menu, the installation was successful!

## Running Tests

### Run all tests:
```bash
npm test
```

### Run tests in watch mode (auto-rerun on file changes):
```bash
npm run test:watch
```

### Run tests with coverage report:
```bash
npm run test:coverage
```

## Project Structure

The Jest configuration expects test files to be:
- Named with `.test.js` or `.test.jsx` extension
- Named with `.spec.js` or `.spec.jsx` extension
- Located in `__tests__` folders

Example:
- `sample_react_app_for_aitesting.test.jsx`
- `__tests__/sample_react_app_for_aitesting.test.jsx`

## Configuration Files

- **package.json** - Contains Jest scripts and dependencies
- **jest.config.js** - Main Jest configuration
- **babel.config.js** - Babel configuration for JSX transformation
- **jest.setup.js** - Setup file that runs before each test

## Testing Your React Component

To test your `sample_react_app_for_aitesting.jsx` component, create a test file:

**sample_react_app_for_aitesting.test.jsx**
```javascript
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import SampleReactApp from './sample_react_app_for_aitesting';

describe('SampleReactApp', () => {
  test('renders User Manager heading', () => {
    render(<SampleReactApp />);
    expect(screen.getByText('User Manager')).toBeInTheDocument();
  });

  test('allows user to add a new user', async () => {
    render(<SampleReactApp />);
    const input = screen.getByPlaceholderText('Enter username');
    const button = screen.getByText('Add User');

    fireEvent.change(input, { target: { value: 'testuser' } });
    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByText('testuser')).toBeInTheDocument();
    });
  });
});
```

## Troubleshooting

### Issue: "Cannot find module '@/components/ui/card'"

**Solution**: Create mock components or install the actual UI library. For testing, you can create simple mocks:

Create `components/ui/card.jsx`:
```javascript
export function Card({ children }) {
  return <div className="card">{children}</div>;
}

export function CardContent({ children }) {
  return <div className="card-content">{children}</div>;
}
```

Create `components/ui/button.jsx`:
```javascript
export function Button({ children, onClick, disabled }) {
  return (
    <button onClick={onClick} disabled={disabled}>
      {children}
    </button>
  );
}
```

### Issue: "SyntaxError: Unexpected token '<'"

**Solution**: Make sure Babel is configured correctly. Check that `babel.config.js` exists and contains the React preset.

### Issue: Tests are not running

**Solution**: 
1. Make sure you're in the project root directory
2. Verify `node_modules` folder exists (run `npm install` if missing)
3. Check that test files match the pattern in `jest.config.js`

## Next Steps

1. Create test files for your components
2. Run `npm test` to execute tests
3. Use `npm run test:coverage` to see code coverage
4. Integrate with your CI/CD pipeline

## Additional Resources

- [Jest Documentation](https://jestjs.io/docs/getting-started)
- [React Testing Library Documentation](https://testing-library.com/docs/react-testing-library/intro/)
- [Jest DOM Matchers](https://github.com/testing-library/jest-dom)

