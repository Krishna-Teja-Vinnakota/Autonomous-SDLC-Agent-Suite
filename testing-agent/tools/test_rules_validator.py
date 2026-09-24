"""
Test Rules Validator - Post-Generation Violation Detection
Validates generated tests against project-specific rules
"""

import logging
import re
from typing import List, Dict, Optional, Set
from dataclasses import dataclass

from tools.testing_rules import ProjectTestingRules

logger = logging.getLogger(__name__)


@dataclass
class RuleViolation:
    """A single rule violation"""
    rule_id: str
    severity: str  # 'critical', 'high', 'medium', 'low'
    message: str
    line_number: Optional[int] = None
    suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of test validation"""
    is_valid: bool
    violations: List[RuleViolation]
    warnings: List[RuleViolation]
    score: int  # 0-100, higher is better
    
    def has_critical_violations(self) -> bool:
        """Check if there are critical violations"""
        return any(v.severity == 'critical' for v in self.violations)
    
    def get_violation_summary(self) -> str:
        """Get human-readable summary"""
        if self.is_valid:
            return f"✅ VALID (score: {self.score}/100)"
        else:
            critical = sum(1 for v in self.violations if v.severity == 'critical')
            high = sum(1 for v in self.violations if v.severity == 'high')
            return f"❌ INVALID (score: {self.score}/100) - {critical} critical, {high} high severity violations"


class TestRulesValidator:
    """
    Validates generated test code against project rules
    Catches violations before execution
    """
    
    def __init__(self, rules: ProjectTestingRules):
        """
        Initialize validator with project rules
        
        Args:
            rules: Project-specific testing rules
        """
        self.rules = rules
    
    def validate(
        self,
        test_code: str,
        test_level: str,
        test_file_path: str = "",
        source_code: str = ""
    ) -> ValidationResult:
        """
        Validate test code against rules
        
        Args:
            test_code: Generated test code
            test_level: 'unit', 'integration', or 'feature'
            test_file_path: Path to test file (for logging)
            source_code: Source code being tested (for component dependency checking)
            
        Returns:
            ValidationResult: Validation result with violations
        """
        """
        Validate test code against rules
        
        Args:
            test_code: Generated test code
            test_level: 'unit', 'integration', or 'feature'
            test_file_path: Path to test file (for logging)
            source_code: Source code being tested (for i18n detection)
            
        Returns:
            ValidationResult: Validation result with violations
        """
        logger.info(f"Validating {test_level} test: {test_file_path}")
        
        violations = []
        warnings = []
        
        # Universal structure validation
        violations.extend(self._validate_structure(test_code))
        
        # Test level specific validation
        if test_level == 'feature':
            violations.extend(self._validate_feature_test(test_code, source_code))
        elif test_level == 'integration':
            violations.extend(self._validate_integration_test(test_code))
        elif test_level == 'unit':
            violations.extend(self._validate_unit_test(test_code, source_code))
        
        # Infrastructure validation
        violations.extend(self._validate_infrastructure_usage(test_code, test_level))
        
        # Selector validation
        violations.extend(self._validate_selectors(test_code))
        
        # Import validation
        violations.extend(self._validate_imports(test_code))
        
        # NEW: i18n validation
        if source_code:
            violations.extend(self._validate_i18n_mocking(test_code, source_code))
        
        # NEW: Child component boundary validation
        violations.extend(self._validate_child_component_boundaries(test_code))
        
        # NEW: Implementation detail validation
        violations.extend(self._validate_implementation_details(test_code))
        
        # V3: Critical feature test rules (ONLY for feature tests)
        if test_level == 'feature':
            violations.extend(self._validate_no_react_hooks(test_code))
            violations.extend(self._validate_no_custom_context(test_code))
            violations.extend(self._validate_test_name_matches_assertions(test_code))
            violations.extend(self._validate_standard_wrapper_usage(test_code))
            violations.extend(self._validate_no_feature_hook_mocking(test_code, source_code))
            violations.extend(self._validate_no_state_injection(test_code))
            violations.extend(self._validate_real_user_actions(test_code))
            violations.extend(self._validate_user_visible_behavior_only(test_code))
            violations.extend(self._validate_renders_complete_feature(test_code))
            
            # V4: Reference-pattern-based validators (from 15 reference tests)
            violations.extend(self._validate_pdp_feature_template_compliance(test_code))
            violations.extend(self._validate_import_order(test_code))
            violations.extend(self._validate_type_annotations(test_code))
            violations.extend(self._validate_custom_render_function(test_code))
            violations.extend(self._validate_test_naming_convention(test_code))
            violations.extend(self._validate_pdp_actions_usage(test_code))
            violations.extend(self._validate_cleanup_pattern(test_code))
        
        # React import check applies to all test levels (syntax issue)
        violations.extend(self._validate_no_missing_react_import(test_code))
        
        # Calculate score
        score = self._calculate_score(violations)
        
        # Determine if valid
        is_valid = score >= 70 and not any(v.severity == 'critical' for v in violations)
        
        logger.info(f"Validation complete: {'VALID' if is_valid else 'INVALID'} (score: {score}/100)")
        
        return ValidationResult(
            is_valid=is_valid,
            violations=violations,
            warnings=warnings,
            score=score
        )
    
    def _validate_structure(self, test_code: str) -> List[RuleViolation]:
        """Validate universal test structure"""
        violations = []
        
        # Must have describe block
        if self.rules.require_describe and 'describe(' not in test_code:
            violations.append(RuleViolation(
                rule_id='structure.missing_describe',
                severity='critical',
                message='Missing describe() block - all tests must be in a describe block',
                suggestion='Wrap tests in: describe("ComponentName", () => { ... })'
            ))
        
        # Must have test or it blocks
        if self.rules.require_test_or_it:
            if 'test(' not in test_code and 'it(' not in test_code:
                violations.append(RuleViolation(
                    rule_id='structure.missing_tests',
                    severity='critical',
                    message='No test() or it() blocks found',
                    suggestion='Add test cases: test("should do something", async () => { ... })'
                ))
        
        # Check for cleanup (afterEach)
        if 'afterEach' not in test_code and 'cleanup' not in test_code.lower():
            violations.append(RuleViolation(
                rule_id='structure.missing_cleanup',
                severity='medium',
                message='Missing cleanup in afterEach block',
                suggestion='Add: afterEach(async () => { await cleanup(); })'
            ))
        
        return violations
    
    def _validate_feature_test(self, test_code: str, source_code: str = "") -> List[RuleViolation]:
        """Validate feature test specific rules"""
        violations = []
        feature_rules = self.rules.feature_test_rules
        
        # Must use userEvent
        if feature_rules.get('require_user_event'):
            if 'userEvent' not in test_code:
                violations.append(RuleViolation(
                    rule_id='feature.missing_user_event',
                    severity='critical',
                    message='Feature tests MUST use userEvent for interactions',
                    suggestion='Replace fireEvent with: const user = userEvent.setup(); await user.click(...)'
                ))
        
        # Must use real wrappers
        if feature_rules.get('require_wrapper'):
            available_wrappers = feature_rules.get('available_wrappers', [])
            if available_wrappers:
                has_wrapper = any(wrapper in test_code for wrapper in available_wrappers)
                if not has_wrapper:
                    violations.append(RuleViolation(
                        rule_id='feature.missing_wrapper',
                        severity='critical',
                        message=f'Feature tests must use real wrappers: {", ".join(available_wrappers[:3])}',
                        suggestion=f'Use: {available_wrappers[0]}(<Component />)' if available_wrappers else 'Use renderWithProviders()'
                    ))
        
        # Must NOT use jest.mock on app code
        if feature_rules.get('forbid_jest_mock'):
            if re.search(r"jest\.mock\(['\"](?!.*node_modules)", test_code):
                violations.append(RuleViolation(
                    rule_id='feature.forbidden_jest_mock',
                    severity='critical',
                    message='Feature tests MUST NOT use jest.mock() on application code',
                    suggestion='Remove jest.mock() and use real implementations with MSW for APIs'
                ))
        
        # Check for shallow rendering
        if feature_rules.get('forbid_shallow_render'):
            # Look for bare render(<Component />) without wrapper
            if re.search(r'\brender\(\s*<[A-Z]\w+\s*/?\>', test_code):
                violations.append(RuleViolation(
                    rule_id='feature.shallow_render',
                    severity='high',
                    message='Feature tests should not render components in isolation',
                    suggestion='Use app wrappers like renderWithProviders() instead of bare render()'
                ))
        
        # Check for fireEvent (should use userEvent)
        if 'fireEvent' in test_code and 'userEvent' in test_code:
            violations.append(RuleViolation(
                rule_id='feature.using_fire_event',
                severity='high',
                message='Use userEvent instead of fireEvent for realistic interactions',
                suggestion='Replace: fireEvent.click() → await user.click()'
            ))
        
        # NEW: Quality validation checks
        violations.extend(self._validate_semantic_queries(test_code))
        violations.extend(self._validate_root_assertion(test_code))
        violations.extend(self._validate_aaa_structure(test_code))
        violations.extend(self._validate_factory_usage(test_code))
        
        # NEW: Strict feature test rules (from user requirements)
        violations.extend(self._validate_no_feature_hook_mocking(test_code, source_code))
        violations.extend(self._validate_no_state_injection(test_code))
        violations.extend(self._validate_user_visible_behavior_only(test_code))
        violations.extend(self._validate_real_user_actions(test_code))
        
        return violations
    
    def _validate_integration_test(self, test_code: str) -> List[RuleViolation]:
        """Validate integration test specific rules"""
        violations = []
        integration_rules = self.rules.integration_test_rules
        
        # If MSW is available, should use it
        if integration_rules.get('use_msw_if_available'):
            if 'server' not in test_code.lower() and 'msw' not in test_code.lower():
                violations.append(RuleViolation(
                    rule_id='integration.missing_msw',
                    severity='medium',
                    message='Integration tests should use MSW for API mocking',
                    suggestion='Import server from mocks/server and override handlers in tests'
                ))
        
        return violations
    
    def _validate_unit_test(self, test_code: str, source_code: str = "") -> List[RuleViolation]:
        """Validate unit test specific rules"""
        violations = []
        
        # Component-level test validation (for React/TypeScript components)
        # Check if this is a React component test
        is_react_component_test = bool(
            'render' in test_code.lower() and 
            ('@testing-library/react' in test_code or 'react' in test_code.lower())
        )
        
        if is_react_component_test:
            violations.extend(self._validate_component_level_test(test_code, source_code))
        
        # Unit tests are most flexible, fewer restrictions for non-React code
        return violations
    
    def _validate_component_level_test(self, test_code: str, source_code: str = "") -> List[RuleViolation]:
        """Validate component-level test specific rules for React components"""
        violations = []
        lines = test_code.split('\n')
        
        # 🛑 HARD RULE #1: Check jest.mock() placement - MUST be before imports
        import_line_indices = []
        jest_mock_line_indices = []
        
        for i, line in enumerate(lines):
            # Find import statements
            if re.match(r'^\s*import\s+', line):
                import_line_indices.append(i)
            # Find jest.mock() calls
            if 'jest.mock(' in line:
                jest_mock_line_indices.append(i)
        
        # Check if any jest.mock() comes after imports
        if import_line_indices and jest_mock_line_indices:
            first_import = min(import_line_indices)
            for mock_line in jest_mock_line_indices:
                if mock_line > first_import:
                    violations.append(RuleViolation(
                        rule_id='component.jest_mock_after_import',
                        severity='critical',
                        message=f'jest.mock() at line {mock_line+1} comes AFTER imports - MUST be at top before all imports',
                        line_number=mock_line+1,
                        suggestion='Move ALL jest.mock() calls to the very top of the file, before any import statements'
                    ))
                    break  # Report once
        
        # Check for jest.mock() inside test cases
        in_test_block = False
        for i, line in enumerate(lines):
            # Detect test blocks
            if re.search(r'\b(it|test|describe)\s*\(', line):
                in_test_block = True
            if in_test_block and line.strip().startswith('}'):
                in_test_block = False
            
            # Check for jest.mock inside test blocks
            if in_test_block and 'jest.mock(' in line:
                violations.append(RuleViolation(
                    rule_id='component.jest_mock_in_test',
                    severity='critical',
                    message=f'jest.mock() found inside test case at line {i+1} - MUST be at top of file',
                    line_number=i+1,
                    suggestion='Move all jest.mock() calls to the top of the file, before imports'
                ))
                break  # Only report once
        
        # 🛑 HARD RULE #2: Check hook mocking pattern - must use controllable pattern
        hook_mock_pattern = r"jest\.mock\(['\"][^'\"]*use\w+['\"]"
        hook_mocks = re.findall(hook_mock_pattern, test_code)
        
        if hook_mocks:
            # Check for controllable pattern: const mockHook = jest.fn()
            has_controllable_pattern = bool(
                re.search(r'const\s+mock\w+\s*=\s*jest\.fn\(\)', test_code) and
                re.search(r'mock\w+\(\)', test_code)  # mockHook() usage
            )
            
            # Check for forbidden pattern: jest.mocked(require(...))
            has_forbidden_pattern = bool(
                re.search(r'jest\.mocked\(require\(', test_code)
            )
            
            if has_forbidden_pattern:
                violations.append(RuleViolation(
                    rule_id='component.hook_mock_forbidden_pattern',
                    severity='critical',
                    message='Using forbidden jest.mocked(require(...)) pattern - MUST use controllable mock pattern',
                    suggestion='Use: const mockHook = jest.fn(); jest.mock(...); mockHook.mockReturnValue({...})'
                ))
            elif not has_controllable_pattern:
                violations.append(RuleViolation(
                    rule_id='component.hook_mock_no_control',
                    severity='critical',
                    message='Hook is mocked but not using controllable pattern - MUST use jest.fn() with mockReturnValue',
                    suggestion='Use: const mockHook = jest.fn(); jest.mock(...); mockHook.mockReturnValue({...})'
                ))
        
        # 🛑 HARD RULE #3: Check child component mocking - ALL must be mocked
        # Find all relative imports (child components) in TEST file
        relative_imports = re.findall(r"import.*from\s+['\"](\.\/|\.\.\/)([^'\"]+)['\"]", test_code)
        component_imports = []
        for prefix, path in relative_imports:
            # Extract component name from path
            component_name = path.split('/')[-1].replace('.tsx', '').replace('.ts', '')
            component_imports.append((prefix + path, component_name))
        
        # Find all @components imports (UI components) in TEST file
        ui_component_imports = re.findall(r"import.*from\s+['\"]@components/([^'\"]+)['\"]", test_code)
        
        # Check if all are mocked
        all_mocks = '\n'.join(lines[:100])  # Check first 100 lines for mocks
        
        # Check test file imports
        for import_path, component_name in component_imports:
            # Check if this component is mocked (check for path or component name)
            mock_pattern_path = rf"jest\.mock\(['\"].*{re.escape(import_path)}"
            mock_pattern_name = rf"jest\.mock\(['\"].*{re.escape(component_name)}"
            if not (re.search(mock_pattern_path, all_mocks, re.IGNORECASE) or 
                    re.search(mock_pattern_name, all_mocks, re.IGNORECASE)):
                violations.append(RuleViolation(
                    rule_id='component.child_component_not_mocked',
                    severity='critical',
                    message=f'Child component "{component_name}" imported from "{import_path}" is NOT mocked - component-level tests MUST mock all child components',
                    suggestion=f'Add at top: jest.mock("{import_path}", () => ({component_name}: jest.fn(...)))'
                ))
        
        for ui_path in ui_component_imports:
            component_name = ui_path.split('/')[-1]
            mock_pattern = rf"jest\.mock\(['\"].*{re.escape(component_name)}"
            mock_pattern_path = rf"jest\.mock\(['\"].*@components/{re.escape(ui_path)}"
            if not (re.search(mock_pattern, all_mocks, re.IGNORECASE) or 
                    re.search(mock_pattern_path, all_mocks, re.IGNORECASE)):
                violations.append(RuleViolation(
                    rule_id='component.ui_component_not_mocked',
                    severity='critical',
                    message=f'UI component "{component_name}" from "@components/{ui_path}" is NOT mocked - component-level tests MUST mock all UI components',
                    suggestion=f'Add at top: jest.mock("@components/{ui_path}", () => ({component_name}: jest.fn(...)))'
                ))
        
        # 🛑 ALSO check SOURCE file for components that MUST be mocked
        if source_code:
            # Find imports in source file - these components MUST be mocked in test
            source_relative_imports = re.findall(r"import.*from\s+['\"](\.\/|\.\.\/)([^'\"]+)['\"]", source_code)
            source_ui_imports = re.findall(r"import.*from\s+['\"]@components/([^'\"]+)['\"]", source_code)
            
            # Check each source import
            for prefix, path in source_relative_imports:
                import_path = prefix + path
                component_name = path.split('/')[-1].replace('.tsx', '').replace('.ts', '')
                # Check if mocked
                mock_pattern = rf"jest\.mock\(['\"].*{re.escape(component_name)}"
                mock_pattern_path = rf"jest\.mock\(['\"].*{re.escape(import_path)}"
                if not (re.search(mock_pattern, all_mocks, re.IGNORECASE) or 
                        re.search(mock_pattern_path, all_mocks, re.IGNORECASE)):
                    violations.append(RuleViolation(
                        rule_id='component.source_component_not_mocked',
                        severity='critical',
                        message=f'Component "{component_name}" imported in source from "{import_path}" is NOT mocked - component-level tests MUST mock all components used by source',
                        suggestion=f'Add at top: jest.mock("{import_path}", () => ({component_name}: jest.fn(...)))'
                    ))
            
            for ui_path in source_ui_imports:
                component_name = ui_path.split('/')[-1]
                mock_pattern = rf"jest\.mock\(['\"].*{re.escape(component_name)}"
                mock_pattern_path = rf"jest\.mock\(['\"].*@components/{re.escape(ui_path)}"
                if not (re.search(mock_pattern, all_mocks, re.IGNORECASE) or 
                        re.search(mock_pattern_path, all_mocks, re.IGNORECASE)):
                    violations.append(RuleViolation(
                        rule_id='component.source_ui_component_not_mocked',
                        severity='critical',
                        message=f'UI component "{component_name}" imported in source from "@components/{ui_path}" is NOT mocked - component-level tests MUST mock all UI components used by source',
                        suggestion=f'Add at top: jest.mock("@components/{ui_path}", () => ({component_name}: jest.fn(...)))'
                    ))
        
        # Check for analytics mocking
        if 'sendGTMEvent' in test_code or 'analytics' in test_code.lower():
            if 'jest.mock' not in test_code or not re.search(r"jest\.mock\(['\"][^'\"]*analytics|gtm", test_code, re.IGNORECASE):
                violations.append(RuleViolation(
                    rule_id='component.analytics_not_mocked',
                    severity='high',
                    message='Analytics functions used but not mocked - must mock to prevent real calls',
                    suggestion="Add: jest.mock('@lib/analytics/gtm-triggers', () => ({ sendGTMEvent: jest.fn() }))"
                ))
        
        # 🛑 HARD RULE #4: Check translation string internals - ABSOLUTELY FORBIDDEN
        # Pattern 1: Translation keys with parentheses: "(wishlist.itemsCount)"
        translation_internals_pattern1 = r"getByText\(['\"][^'\"]*\([^)]+\)['\"]"
        # Pattern 2: Translation keys without parentheses: "wishlist.itemsCount"
        translation_internals_pattern2 = r"getByText\(['\"][a-z]+\.[a-z]+['\"]"
        
        if re.search(translation_internals_pattern1, test_code):
            violations.append(RuleViolation(
                rule_id='component.translation_internals',
                severity='critical',
                message='Asserting translation string internals with parentheses (e.g., "(wishlist.itemsCount)") - ABSOLUTELY FORBIDDEN',
                suggestion='Use: expect(screen.getByText(/items/i)).toBeInTheDocument() instead of exact translation strings'
            ))
        elif re.search(translation_internals_pattern2, test_code):
            # Check if it's a translation key (has dot notation like "wishlist.itemsCount")
            # But allow if it's a file path or actual text
            matches = re.finditer(translation_internals_pattern2, test_code)
            for match in matches:
                text = match.group(0)
                # If it looks like a translation key (word.word pattern), flag it
                if re.match(r"['\"][a-z]+\.[a-z]+['\"]", text):
                    violations.append(RuleViolation(
                        rule_id='component.translation_key_assertion',
                        severity='critical',
                        message=f'Asserting translation key "{text}" - ABSOLUTELY FORBIDDEN, use semantic/partial text with regex',
                        suggestion='Use: expect(screen.getByText(/partial text/i)).toBeInTheDocument()'
                    ))
                    break
        
        # Check for ARIA role assumptions on mocked components
        if 'getByRole' in test_code and 'progressbar' in test_code:
            # Check if LoadingSpinner is mocked
            if 'LoadingSpinner' in test_code and 'jest.mock' in test_code:
                if not re.search(r"jest\.mock\(['\"][^'\"]*loading-spinner", test_code, re.IGNORECASE):
                    violations.append(RuleViolation(
                        rule_id='component.aria_role_assumption',
                        severity='medium',
                        message='Using getByRole("progressbar") on potentially mocked component - mocked components may not have ARIA roles',
                        suggestion='Use data-testid from mocked component: expect(screen.getByTestId("loading-spinner")).toBeInTheDocument()'
                    ))
        
        # 🛑 HARD RULE #5: Check cleanup blocks - REQUIRED
        if 'afterEach' not in test_code:
            violations.append(RuleViolation(
                rule_id='component.missing_cleanup',
                severity='critical',
                message='Missing afterEach cleanup block - REQUIRED for component-level tests',
                suggestion='Add: afterEach(() => { jest.clearAllMocks() })'
            ))
        
        if 'beforeEach' not in test_code:
            violations.append(RuleViolation(
                rule_id='component.missing_beforeEach',
                severity='high',
                message='Missing beforeEach block - Recommended for resetting mock return values',
                suggestion='Add: beforeEach(() => { jest.clearAllMocks(); mockHook.mockReturnValue({...}) })'
            ))
        
        return violations
    
    def _validate_infrastructure_usage(self, test_code: str, test_level: str) -> List[RuleViolation]:
        """Validate usage of detected infrastructure"""
        violations = []
        
        # Check if using detected factories
        if self.rules.detected_factories:
            # Look for inline mock data instead of factories
            inline_mock_pattern = r'const\s+mock\w+\s*=\s*\{'
            if re.search(inline_mock_pattern, test_code):
                # Check if any factory is used
                uses_factory = any(factory in test_code for factory in self.rules.detected_factories)
                if not uses_factory:
                    violations.append(RuleViolation(
                        rule_id='infrastructure.not_using_factories',
                        severity='medium',
                        message=f'Should use detected factories instead of inline mocks: {", ".join(self.rules.detected_factories[:3])}',
                        suggestion=f'Replace inline mocks with: {self.rules.detected_factories[0]}(...)'
                    ))
        
        return violations
    
    def _validate_selectors(self, test_code: str) -> List[RuleViolation]:
        """Validate selector usage"""
        violations = []
        
        # Forbidden: querySelector
        if 'querySelector' in test_code or 'querySelectorAll' in test_code:
            violations.append(RuleViolation(
                rule_id='selector.using_query_selector',
                severity='high',
                message='Do not use querySelector - use Testing Library queries',
                suggestion='Use: screen.getByRole(), screen.getByTestId(), etc.'
            ))
        
        # Check for hardcoded text without regex
        exact_text_pattern = r"getByText\(['\"][^/].*?['\"]\)"
        if re.search(exact_text_pattern, test_code):
            violations.append(RuleViolation(
                rule_id='selector.hardcoded_text',
                severity='medium',
                message='Avoid exact text matching - use regex for flexibility',
                suggestion='Replace: getByText("Submit") → getByText(/submit/i)'
            ))
        
        return violations
    
    def _validate_imports(self, test_code: str) -> List[RuleViolation]:
        """Validate import statements"""
        violations = []
        
        # Check for common issues
        lines = test_code.split('\n')
        
        # Look for missing @testing-library imports if using screen
        if 'screen.' in test_code:
            if not any('@testing-library/react' in line for line in lines):
                violations.append(RuleViolation(
                    rule_id='imports.missing_testing_library',
                    severity='critical',
                    message='Missing import from @testing-library/react',
                    suggestion='Add: import { render, screen } from "@testing-library/react"'
                ))
        
        # Check for userEvent import if used
        if 'userEvent' in test_code:
            if not any('@testing-library/user-event' in line for line in lines):
                violations.append(RuleViolation(
                    rule_id='imports.missing_user_event',
                    severity='critical',
                    message='Missing import for userEvent',
                    suggestion='Add: import { userEvent } from "@testing-library/user-event"'
                ))
        
        return violations
    
    def _validate_semantic_queries(self, test_code: str) -> List[RuleViolation]:
        """
        Validate semantic query usage (QUALITY CHECK)
        Enforces getByRole/getByText over getByTestId for interactive elements
        """
        violations = []
        
        # Check for getByTestId on interactive elements (CRITICAL VIOLATION)
        interactive_elements = ["button", "link", "input", "checkbox", "radio", "select", "textarea"]
        for element in interactive_elements:
            # Pattern: getByTestId('...-button') or getByTestId('submit-btn') etc
            pattern = rf'getByTestId\([\'"](?!.*container|.*wrapper|.*root).*?{element}'
            if re.search(pattern, test_code, re.IGNORECASE):
                violations.append(RuleViolation(
                    rule_id='quality.semantic_queries.interactive_testid',
                    severity='critical',
                    message=f'Using getByTestId for {element} - MUST use getByRole instead',
                    suggestion=f'Replace: getByTestId("...-{element}") → getByRole("{element}", {{ name: /text/i }})'
                ))
                break  # Only report once
        
        # Check for lack of semantic queries when getByTestId is used
        has_testid = 'getByTestId' in test_code
        has_semantic = 'getByRole' in test_code or re.search(r'getByText\(/.*?/i?\)', test_code)
        
        if has_testid and not has_semantic:
            violations.append(RuleViolation(
                rule_id='quality.semantic_queries.no_semantic',
                severity='high',
                message='Only using getByTestId - MUST prefer getByRole/getByText for better accessibility testing',
                suggestion='Add semantic queries: screen.getByRole("button"), screen.getByText(/visible text/i)'
            ))
        
        return violations
    
    def _validate_root_assertion(self, test_code: str) -> List[RuleViolation]:
        """
        Validate root container assertion (QUALITY CHECK)
        Feature tests must assert the root container exists
        """
        violations = []
        
        # Look for root container assertion patterns
        root_patterns = [
            r'expect\(screen\.getByTestId\([\'"].*?container[\'"].*?\)\)\.toBeInTheDocument\(\)',
            r'expect\(screen\.getByTestId\([\'"].*?root[\'"].*?\)\)\.toBeInTheDocument\(\)',
            r'expect\(screen\.getByTestId\([\'"].*?wrapper[\'"].*?\)\)\.toBeInTheDocument\(\)',
            r'expect\(.*?container.*?\)\.toBeInTheDocument\(\)',
        ]
        
        has_root_assertion = any(re.search(pattern, test_code) for pattern in root_patterns)
        
        if not has_root_assertion:
            violations.append(RuleViolation(
                rule_id='quality.root_assertion.missing',
                severity='critical',
                message='Feature test MUST assert root container exists as first check',
                suggestion='Add at test start: expect(screen.getByTestId("feature-container")).toBeInTheDocument()'
            ))
        
        return violations
    
    def _validate_aaa_structure(self, test_code: str) -> List[RuleViolation]:
        """
        Validate Arrange-Act-Assert structure (QUALITY CHECK)
        Tests should follow clear AAA pattern
        """
        violations = []
        
        # Check for basic AAA components
        has_render = 'render' in test_code.lower()
        has_user_action = 'user.' in test_code or 'await user' in test_code
        has_expect = 'expect(' in test_code
        
        if not (has_render and has_expect):
            violations.append(RuleViolation(
                rule_id='quality.aaa.incomplete',
                severity='high',
                message='Test missing basic AAA structure (Arrange-Act-Assert)',
                suggestion='Ensure test has: 1) Setup/Render (Arrange), 2) User Action (Act), 3) Assertions (Assert)'
            ))
        
        # Feature tests should have user actions
        if has_render and has_expect and not has_user_action:
            violations.append(RuleViolation(
                rule_id='quality.aaa.no_user_action',
                severity='medium',
                message='Feature test should include user interaction in Act phase',
                suggestion='Add: const user = userEvent.setup(); await user.click(...)'
            ))
        
        return violations
    
    def _validate_factory_usage(self, test_code: str) -> List[RuleViolation]:
        """
        Validate factory cleanliness (QUALITY CHECK)
        Factories should only include fields the component uses
        """
        violations = []
        
        # Check for __typename in factory calls (GraphQL setup field)
        if '__typename' in test_code and 'createMock' in test_code:
            violations.append(RuleViolation(
                rule_id='quality.factory.setup_fields',
                severity='medium',
                message='Factory includes __typename (setup field) - remove fields not used by component',
                suggestion='Only include fields the component actually uses, remove __typename'
            ))
        
        # Check for excessive factory fields (likely includes noise)
        factory_pattern = r'(createMock\w+|mock\w+Factory)\(\{([^}]+)\}\)'
        matches = re.finditer(factory_pattern, test_code, re.DOTALL)
        
        for match in matches:
            fields_block = match.group(2)
            # Count number of fields (approximate by counting commas)
            field_count = fields_block.count(',') + 1
            
            if field_count > 10:
                violations.append(RuleViolation(
                    rule_id='quality.factory.excessive_fields',
                    severity='medium',
                    message=f'Factory call has {field_count} fields - likely includes unnecessary setup fields',
                    suggestion='Remove fields not used by component - keep only essential fields the component reads'
                ))
                break  # Only report once
        
        return violations
    
    def _validate_i18n_mocking(self, test_code: str, source_code: str = "") -> List[RuleViolation]:
        """
        Validate i18n mocking (CRITICAL CHECK)
        If component uses translations, test must mock them
        """
        violations = []
        
        # Check if source uses translations
        uses_translations = bool(
            source_code and (
                'useTranslations' in source_code or
                'useTranslate' in source_code or
                'useT(' in source_code or
                "import { t }" in source_code or
                "from 'next-intl'" in source_code or
                "from 'react-i18next'" in source_code
            )
        )
        
        if not uses_translations:
            return violations  # No i18n in source, no problem
        
        # Source uses i18n - check if test mocks it
        has_i18n_mock = bool(
            'jest.mock' in test_code and (
                'next-intl' in test_code or
                'react-i18next' in test_code or
                'i18next' in test_code
            )
        )
        
        if not has_i18n_mock:
            violations.append(RuleViolation(
                rule_id='quality.i18n.missing_mock',
                severity='critical',
                message='Component uses i18n (useTranslations) but test does not mock translation library',
                suggestion='Add at top of test: jest.mock("next-intl", () => ({ useTranslations: () => (key: string) => key }))'
            ))
        
        # Check for English text assertions instead of translation keys
        # Pattern: getByText with English words (not translation keys like 'pdp.')
        english_text_pattern = r'getByText\([\'"]?/[A-Z][a-z]+.*?/i?\)'
        has_english_assertions = re.search(english_text_pattern, test_code)
        
        # Also check for common English words in getByText
        common_english = ['Select', 'Please', 'Size', 'Error', 'Out of stock', 'Add to cart']
        for word in common_english:
            if f'getByText(/{word}' in test_code or f"getByText('/{word}" in test_code:
                has_english_assertions = True
                break
        
        if uses_translations and has_english_assertions:
            violations.append(RuleViolation(
                rule_id='quality.i18n.english_text_assertions',
                severity='high',
                message='Test asserts English text instead of translation keys - will fail in i18n environments',
                suggestion='Use translation keys: expect(screen.getByText("pdp.labelSelectSize")) not expect(screen.getByText(/Select Size/i))'
            ))
        
        return violations
    
    def _validate_child_component_boundaries(self, test_code: str) -> List[RuleViolation]:
        """
        Validate child component boundaries (NEW CRITICAL CHECK)
        Feature tests must not assert child component internals
        """
        violations = []
        
        # Look for test-ids that suggest child component internals
        # Pattern: getByTestId with names like 'product-variants-menu', 'child-component-id'
        child_component_patterns = [
            r'getByTestId\([\'"](?!select-size)[a-z-]+-(?:menu|modal|dialog|dropdown|list|grid)[\'"]',
            r'getByTestId\([\'"][a-z-]+-(?:component|widget|element)[\'"]',
        ]
        
        for pattern in child_component_patterns:
            if re.search(pattern, test_code):
                violations.append(RuleViolation(
                    rule_id='quality.child_boundaries.asserting_internals',
                    severity='critical',
                    message='Feature test asserts child component internal test-ids - creates tight coupling',
                    suggestion='Assert user-visible behavior instead: use getByRole, getByText for child outputs, not child test-ids'
                ))
                break
        
        return violations
    
    def _validate_implementation_details(self, test_code: str) -> List[RuleViolation]:
        """
        Validate against testing implementation details (NEW CHECK)
        """
        violations = []
        
        # Check for exact function call parameter matching
        exact_param_pattern = r'toHaveBeenCalledWith\s*\(\s*\{[^}]+behavior:\s*[\'"]smooth[\'"][^}]+\}'
        if re.search(exact_param_pattern, test_code):
            violations.append(RuleViolation(
                rule_id='quality.implementation.exact_params',
                severity='medium',
                message='Testing exact function call parameters - tests implementation, not behavior',
                suggestion='Use toHaveBeenCalled() instead of toHaveBeenCalledWith({exact params})'
            ))
        
        # Check for DOM method replacement with exact assertions
        if 'scrollIntoView = jest.fn()' in test_code and 'toHaveBeenCalledWith' in test_code:
            violations.append(RuleViolation(
                rule_id='quality.implementation.dom_method_params',
                severity='medium',
                message='Testing exact DOM method parameters - brittle implementation detail',
                suggestion='Assert that scrollIntoView was called, not how it was called'
            ))
        
        return violations
    
    def _validate_no_react_hooks(self, test_code: str) -> List[RuleViolation]:
        """
        Validate no React hooks in test code (NEW CRITICAL CHECK - V3)
        Feature tests are NOT components - they test components from outside
        """
        violations = []
        
        # React hooks that should NEVER appear in feature tests
        react_hooks = [
            'useState', 'useContext', 'useEffect', 'useReducer', 
            'useMemo', 'useCallback', 'useRef', 'useLayoutEffect'
        ]
        
        for hook in react_hooks:
            # Check for React.useState or useState(
            patterns = [
                rf'React\.{hook}',
                rf'\b{hook}\s*\(',
            ]
            
            for pattern in patterns:
                if re.search(pattern, test_code):
                    violations.append(RuleViolation(
                        rule_id='critical.react_hooks',
                        severity='critical',
                        message=f'Test uses {hook} - feature tests MUST NOT use React hooks',
                        suggestion='Feature tests test components from outside. Use real wrappers, not custom state/context.'
                    ))
                    return violations  # Only report once
        
        return violations
    
    def _validate_no_custom_context(self, test_code: str) -> List[RuleViolation]:
        """
        Validate no custom context creation (NEW CRITICAL CHECK - V3)
        Feature tests must use real wrappers, not recreate context
        """
        violations = []
        
        # Patterns indicating custom context creation
        context_patterns = [
            (r'<\w+Context\.Provider', 'Context.Provider JSX'),
            (r'createContext\s*\(', 'createContext() call'),
            (r'const\s+\w+Provider\s*=', 'custom Provider component'),
            (r'ProductDetailsPageContext\.Provider', 'ProductDetailsPageContext.Provider'),
        ]
        
        for pattern, description in context_patterns:
            if re.search(pattern, test_code):
                violations.append(RuleViolation(
                    rule_id='critical.custom_context',
                    severity='critical',
                    message=f'Test creates custom context ({description}) - MUST use real wrappers (pdpWrapper)',
                    suggestion='Remove custom context. Use: const wrapper = pdpWrapper(mockProduct); renderWeb(<Component />, { wrapper })'
                ))
                break  # Only report once
        
        # Check for manual context value creation (more specific patterns)
        context_value_patterns = [
            (r'contextValue\s*=\s*\{[^}]*state\s*:', 'contextValue with state'),
            (r'createMockContext', 'createMockContext function'),
            (r'const\s+\w+Context\s*=\s*\{[^}]*state\s*:', 'manual context object with state'),
        ]
        
        for pattern, description in context_value_patterns:
            if re.search(pattern, test_code, re.IGNORECASE):
                violations.append(RuleViolation(
                    rule_id='critical.manual_context_value',
                    severity='critical',
                    message=f'Test manually creates context values ({description}) - this is unit test behavior, not feature test',
                    suggestion='Use real wrappers (pdpWrapper) that provide real context. Never manually inject state or context values'
                ))
                break  # Only report once
        
        return violations
    
    def _validate_test_name_matches_assertions(self, test_code: str) -> List[RuleViolation]:
        """
        Validate test names match what's being asserted (NEW CRITICAL CHECK - V3)
        """
        violations = []
        
        # Extract test blocks with names and bodies
        test_pattern = r'it\([\'"]([^\'"]+)[\'"],\s*(?:async\s*)?\([^)]*\)\s*=>\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}'
        tests = re.findall(test_pattern, test_code, re.DOTALL)
        
        for test_name, test_body in tests:
            test_name_lower = test_name.lower()
            test_body_lower = test_body.lower()
            
            # Check for common mismatches
            if 'error' in test_name_lower or 'please select' in test_name_lower:
                # Test mentions error but doesn't assert error text
                if 'error' not in test_body_lower and 'please' not in test_body_lower:
                    violations.append(RuleViolation(
                        rule_id='critical.test_name_mismatch',
                        severity='critical',
                        message=f'Test "{test_name}" promises to test error but assertions don\'t verify error',
                        suggestion='Add assertion for error message: expect(screen.getByText("error-key")).toBeVisible()'
                    ))
            
            if 'scroll' in test_name_lower:
                # Test mentions scroll but asserts opposite
                if 'not.toHaveBeenCalled' in test_body or 'not.toBeCalled' in test_body:
                    violations.append(RuleViolation(
                        rule_id='critical.inverted_scroll_logic',
                        severity='critical',
                        message=f'Test "{test_name}" says should scroll but asserts it did NOT scroll',
                        suggestion='Fix logic: test name says "should scroll" → assertion should verify it scrolled'
                    ))
        
        return violations
    
    def _validate_standard_wrapper_usage(self, test_code: str) -> List[RuleViolation]:
        """
        Validate standard wrapper usage pattern (NEW CHECK - V3)
        """
        violations = []
        
        # Check for non-standard wrapper invocation
        non_standard_patterns = [
            r'pdpWrapper\([^)]+\)\s*\(\s*\{',  # pdpWrapper(...)({ children: ... })
            r'renderWeb\s*\(\s*pdpWrapper\([^)]+\)\s*\(',  # renderWeb(pdpWrapper(...)(...))
        ]
        
        for pattern in non_standard_patterns:
            if re.search(pattern, test_code):
                violations.append(RuleViolation(
                    rule_id='structure.non_standard_wrapper',
                    severity='high',
                    message='Non-standard wrapper usage - couples test to wrapper implementation',
                    suggestion='Use standard pattern: const wrapper = pdpWrapper(mockProduct); renderWeb(<Component />, { wrapper })'
                ))
                break
        
        return violations
    
    def _validate_no_missing_react_import(self, test_code: str) -> List[RuleViolation]:
        """
        Validate React import if React is used (NEW CHECK - V3)
        """
        violations = []
        
        # Check if React is used without being imported
        uses_react = bool(re.search(r'React\.', test_code))
        has_react_import = bool(re.search(r'import\s+React', test_code))
        
        if uses_react and not has_react_import:
            violations.append(RuleViolation(
                rule_id='critical.missing_react_import',
                severity='critical',
                message='Test uses React.* but does not import React - will crash at runtime',
                suggestion='Add: import React from "react" OR remove React.* usage (preferred for feature tests)'
            ))
        
        return violations
    
    def _validate_no_feature_hook_mocking(self, test_code: str, source_code: str = "") -> List[RuleViolation]:
        """
        Validate that primary feature hooks are NOT mocked (CRITICAL RULE)
        Feature tests must use real feature hooks (e.g., useAddToCart)
        """
        violations = []
        
        # Detect common feature hook patterns in source code
        if source_code:
            # Look for hooks that are the primary feature logic
            feature_hook_patterns = [
                r'useAddToCart',
                r'useSelectSize',
                r'useWishlist',
                r'useCart',
                r'useCheckout',
            ]
            
            source_uses_hook = False
            hook_name = None
            for pattern in feature_hook_patterns:
                if re.search(pattern, source_code, re.IGNORECASE):
                    source_uses_hook = True
                    hook_name = re.search(pattern, source_code, re.IGNORECASE).group(0)
                    break
            
            # If source uses a feature hook, check if test mocks it
            if source_uses_hook and hook_name:
                # Check if test mocks this hook
                mock_pattern = rf"jest\.mock\(['\"][^'\"]*{re.escape(hook_name)}"
                if re.search(mock_pattern, test_code, re.IGNORECASE):
                    violations.append(RuleViolation(
                        rule_id='feature.mocked_primary_hook',
                        severity='critical',
                        message=f'Feature test mocks primary feature hook "{hook_name}" - MUST use real hook implementation',
                        suggestion=f'Remove jest.mock() for {hook_name}. Use real hook with real wrappers (pdpWrapper) and test user-visible behavior'
                    ))
        
        # Also check for common feature hook mocking patterns even without source
        common_feature_hook_mocks = [
            (r"jest\.mock\(['\"][^'\"]*useAddToCart", 'useAddToCart'),
            (r"jest\.mock\(['\"][^'\"]*useSelectSize", 'useSelectSize'),
            (r"jest\.mock\(['\"][^'\"]*useWishlist", 'useWishlist'),
        ]
        
        for pattern, hook_name in common_feature_hook_mocks:
            if re.search(pattern, test_code, re.IGNORECASE):
                violations.append(RuleViolation(
                    rule_id='feature.mocked_feature_hook',
                    severity='critical',
                    message=f'Feature test mocks feature hook "{hook_name}" - NEVER mock primary feature hooks',
                    suggestion=f'Remove jest.mock() for {hook_name}. Feature tests must use real implementations'
                ))
                break  # Only report once
        
        return violations
    
    def _validate_no_state_injection(self, test_code: str) -> List[RuleViolation]:
        """
        Validate that tests don't inject state directly (CRITICAL RULE)
        Feature tests must satisfy prerequisites through REAL UI components, not state injection
        """
        violations = []
        
        # Patterns indicating manual state injection
        state_injection_patterns = [
            # Direct state property setting
            (r'currentSku\s*[:=]\s*[\'"][^\'"]+[\'"]', 'currentSku'),
            (r'state\s*:\s*\{[^}]*currentSku', 'currentSku in state'),
            (r'showSelectVariantModal\s*[:=]\s*true', 'showSelectVariantModal'),
            (r'selectedSize\s*[:=]\s*[\'"][^\'"]+[\'"]', 'selectedSize'),
            # Context value manipulation
            (r'contextValue\s*=\s*\{[^}]*state\s*:', 'manual contextValue with state'),
            (r'createMockContext.*state\s*:', 'createMockContext with state'),
        ]
        
        for pattern, description in state_injection_patterns:
            if re.search(pattern, test_code, re.IGNORECASE):
                violations.append(RuleViolation(
                    rule_id='feature.state_injection',
                    severity='critical',
                    message=f'Feature test injects state directly ({description}) - MUST satisfy prerequisites through REAL UI components',
                    suggestion='Instead of setting state directly, render SelectSize component and simulate user interaction: await pdpActions.selectSize("UK 8")'
                ))
                break  # Only report once
        
        return violations
    
    def _validate_user_visible_behavior_only(self, test_code: str) -> List[RuleViolation]:
        """
        Validate that tests assert user-visible behavior, not implementation details (CRITICAL RULE)
        Feature tests must NOT assert internal callbacks, context setters, or hook internals
        """
        violations = []
        
        # Patterns indicating implementation detail assertions
        implementation_detail_patterns = [
            # Asserting callback calls
            (r'expect\(onToggle\)\.toHaveBeenCalled', 'onToggle callback call'),
            (r'expect\(onAddToCart\)\.toHaveBeenCalled', 'onAddToCart callback call'),
            (r'expect\(onSelectVariant\)\.toHaveBeenCalled', 'onSelectVariant callback call'),
            (r'expect\(.*on\w+\)\.toHaveBeenCalled', 'callback function calls'),
            # Asserting context setter calls
            (r'expect\(.*setState\)\.toHaveBeenCalled', 'setState calls'),
            (r'expect\(.*set\w+\)\.toHaveBeenCalled', 'setter function calls'),
            # Asserting hook internals
            (r'expect\(.*use\w+\)\.toHaveBeenCalled', 'hook function calls'),
        ]
        
        for pattern, description in implementation_detail_patterns:
            if re.search(pattern, test_code, re.IGNORECASE):
                violations.append(RuleViolation(
                    rule_id='feature.implementation_detail_assertion',
                    severity='critical',
                    message=f'Feature test asserts implementation detail ({description}) - MUST assert user-visible behavior only',
                    suggestion='Instead of asserting callback calls, assert UI state: expect(screen.getByText(/error/i)).toBeVisible() or expect(mockAppRouter.push).toHaveBeenCalledWith("/cart")'
                ))
                break  # Only report once
        
        return violations
    
    def _validate_real_user_actions(self, test_code: str) -> List[RuleViolation]:
        """
        Validate that prerequisites are satisfied through REAL UI components (CRITICAL RULE)
        Feature tests must model the real user journey: render → user interaction → outcome
        """
        violations = []
        
        # Check if test has state injection but no corresponding user action
        has_state_injection = bool(
            re.search(r'currentSku\s*[:=]', test_code, re.IGNORECASE) or
            re.search(r'state\s*:\s*\{[^}]*currentSku', test_code, re.IGNORECASE)
        )
        
        # Check if test uses user action helpers (good sign)
        has_user_actions = bool(
            re.search(r'pdpActions\.(selectSize|addToCart)', test_code, re.IGNORECASE) or
            re.search(r'await\s+user\.(click|type|select)', test_code, re.IGNORECASE) or
            re.search(r'userEvent\.(click|type)', test_code, re.IGNORECASE)
        )
        
        # If state is injected but no user actions, that's a violation
        if has_state_injection and not has_user_actions:
            violations.append(RuleViolation(
                rule_id='feature.no_user_actions',
                severity='critical',
                message='Feature test injects state but has no user actions - MUST satisfy prerequisites through REAL UI interactions',
                suggestion='Remove state injection. Instead, render SelectSize component and use: await pdpActions.selectSize("UK 8") before testing AddToCart'
            ))
        
        # Check if test uses SelectSize component (good sign for AddToCart tests)
        # This is a positive signal, but we don't fail if missing - just warn
        if 'AddToCart' in test_code and 'SelectSize' not in test_code:
            # Check if test manually sets currentSku instead
            if re.search(r'currentSku\s*[:=]', test_code, re.IGNORECASE):
                violations.append(RuleViolation(
                    rule_id='feature.missing_select_size',
                    severity='high',
                    message='AddToCart test sets currentSku directly instead of using SelectSize component - MUST render SelectSize and simulate user selection',
                    suggestion='Render SelectSize component and use: await pdpActions.selectSize("UK 8") to satisfy prerequisites'
                ))
        
        return violations
    
    def _validate_renders_complete_feature(self, test_code: str) -> List[RuleViolation]:
        """
        Validate that tests render complete features with all dependencies (CRITICAL RULE)
        Feature tests must render ALL components that a real user would see together
        """
        violations = []
        
        # Specific component dependency patterns
        component_dependencies = {
            'AddToCart': 'SelectSize',  # AddToCart requires SelectSize for size selection
            'AddToWishlist': 'SelectSize',  # AddToWishlist may require size selection
        }
        
        for primary_component, required_component in component_dependencies.items():
            # Check if test is about primary component
            has_primary = re.search(rf'<{primary_component}', test_code) or \
                         re.search(rf'describe\([\'"][^\'"]*{primary_component}', test_code)
            
            # Check if required component is rendered
            has_required = re.search(rf'<{required_component}', test_code)
            
            # Check if state is injected instead (bad pattern)
            has_state_injection = re.search(r'currentSku\s*[:=]|state\s*:\s*\{[^}]*currentSku', test_code, re.IGNORECASE)
            
            if has_primary and not has_required and has_state_injection:
                violations.append(RuleViolation(
                    rule_id='feature.missing_prerequisite_component',
                    severity='critical',
                    message=f'{primary_component} test sets state directly instead of rendering {required_component} - MUST render complete feature',
                    suggestion=f'Render {required_component} component: renderWeb(<><{required_component} /><{primary_component} /></>, {{ wrapper: pdpWrapper(mockProduct) }})'
                ))
        
        # Check for common pattern: testing AddToCart in isolation
        if 'AddToCart' in test_code and 'renderWeb' in test_code:
            # Check if it's rendered alone without SelectSize
            if '<AddToCart' in test_code and '<SelectSize' not in test_code:
                # And if state is being set instead
                if re.search(r'currentSku|selectedSize', test_code, re.IGNORECASE):
                    violations.append(RuleViolation(
                        rule_id='feature.incomplete_feature_rendering',
                        severity='critical',
                        message='AddToCart rendered without SelectSize but state is manually set - renders incomplete feature',
                        suggestion='Render complete feature: renderWeb(<><SelectSize /><AddToCart /></>)  and satisfy prerequisites via: await pdpActions.selectSize("UK 8")'
                    ))
        
        return violations
    
    def _validate_pdp_feature_template_compliance(self, test_code: str) -> List[RuleViolation]:
        """
        Validate PDP feature test follows exact template from reference tests
        Based on analysis of 15 reference tests
        """
        violations = []
        
        # Check if this is a PDP feature test
        if 'PDP' not in test_code or 'Feature' not in test_code:
            return violations  # Not a PDP test, skip template validation
        
        # Required imports (ALL must be present)
        required_imports = [
            ('@testing-library/react', 'screen'),
            ('@testing-library/user-event', 'userEvent'),
            ('@mocks/factories', 'mockPdpProduct or createMockProduct'),
            ('@test-utils/user-actions', 'pdpUserActions'),
            ('@test-utils/render', 'pdpWrapper and renderWeb'),
            ('@test-utils/apollo', 'cleanupApolloClient'),
        ]
        
        for import_path, import_items in required_imports:
            if import_path not in test_code:
                violations.append(RuleViolation(
                    rule_id='template.missing_required_import',
                    severity='critical',
                    message=f'Missing required import from {import_path} ({import_items})',
                    suggestion=f'Add: import {{ ... }} from "{import_path}"'
                ))
        
        return violations
    
    def _validate_import_order(self, test_code: str) -> List[RuleViolation]:
        """
        Validate imports are in correct order (from reference tests)
        """
        violations = []
        
        # Extract all import statements
        import_pattern = r"import\s+.*?from\s+['\"]([^'\"]+)['\"]"
        imports = re.findall(import_pattern, test_code)
        
        if not imports:
            return violations
        
        # Expected order
        expected_order = [
            '@testing-library/react',
            '@testing-library/user-event',
            # Component imports (relative paths)
            '@mocks',
            '@test-utils/user-actions',
            '@test-utils/render',
            '@test-utils/apollo',
        ]
        
        # Check if imports follow expected order (loosely)
        rtl_index = next((i for i, imp in enumerate(imports) if '@testing-library/react' in imp), -1)
        user_event_index = next((i for i, imp in enumerate(imports) if '@testing-library/user-event' in imp), -1)
        
        if rtl_index > user_event_index and user_event_index != -1:
            violations.append(RuleViolation(
                rule_id='template.import_order',
                severity='low',
                message='Imports not in standard order: userEvent should come after @testing-library/react',
                suggestion='Place @testing-library/react imports before @testing-library/user-event'
            ))
        
        return violations
    
    def _validate_type_annotations(self, test_code: str) -> List[RuleViolation]:
        """
        Validate ReturnType<typeof factory> pattern is used (from reference tests)
        """
        violations = []
        
        # Check for pdpActions type annotation
        if 'pdpUserActions' in test_code:
            if 'let pdpActions: ReturnType<typeof pdpUserActions>' not in test_code:
                violations.append(RuleViolation(
                    rule_id='template.missing_pdp_actions_type',
                    severity='high',
                    message='pdpActions not typed with ReturnType pattern',
                    suggestion='Add: let pdpActions: ReturnType<typeof pdpUserActions>'
                ))
        
        # Check for mockProduct type annotation
        if 'mockPdpProduct' in test_code or 'createMockProduct' in test_code:
            has_type = (
                'ReturnType<typeof mockPdpProduct>' in test_code or
                'ReturnType<typeof createMockProduct>' in test_code
            )
            if not has_type:
                violations.append(RuleViolation(
                    rule_id='template.missing_mock_product_type',
                    severity='medium',
                    message='mockProduct not typed with ReturnType pattern',
                    suggestion='Add: let mockProduct: ReturnType<typeof createMockProduct>'
                ))
        
        return violations
    
    def _validate_custom_render_function(self, test_code: str) -> List[RuleViolation]:
        """
        Validate custom render function pattern (from reference tests)
        All reference tests use: const render[Component]Pdp = ...
        """
        violations = []
        
        # Check for custom render function pattern
        custom_render_pattern = r'const\s+render\w+Pdp\s*='
        if not re.search(custom_render_pattern, test_code):
            violations.append(RuleViolation(
                rule_id='template.missing_custom_render',
                severity='high',
                message='Missing custom render function (render[Component]Pdp pattern)',
                suggestion='Add: const renderComponentPdp = (product = mockProduct) => renderWeb(<>...</>, { wrapper: pdpWrapper(product) })'
            ))
        
        return violations
    
    def _validate_test_naming_convention(self, test_code: str) -> List[RuleViolation]:
        """
        Validate test names follow reference pattern (lowercase with WHEN/WHILE/AFTER)
        """
        violations = []
        
        # Extract test names
        test_names = re.findall(r"it\(['\"]([^'\"]+)['\"]", test_code)
        
        for name in test_names:
            # Check for temporal clauses (from reference tests)
            has_temporal_clause = any(clause in name for clause in ['WHEN', 'WHILE', 'AFTER', 'when', 'while', 'after'])
            
            if not has_temporal_clause:
                violations.append(RuleViolation(
                    rule_id='template.test_name_missing_clause',
                    severity='medium',
                    message=f'Test name "{name}" missing temporal clause (WHEN/WHILE/AFTER)',
                    suggestion='Use format: "outcome WHEN action" or "outcome WHILE condition"'
                ))
            
            # Check for implementation details in name
            implementation_terms = ['callback', 'prop', 'state', 'setState', 'onClick', 'onSelect']
            if any(term in name.lower() for term in implementation_terms):
                violations.append(RuleViolation(
                    rule_id='template.test_name_implementation_detail',
                    severity='high',
                    message=f'Test name "{name}" mentions implementation details',
                    suggestion='Describe user-visible behavior only: "navigates to cart WHEN item added"'
                ))
        
        return violations
    
    def _validate_pdp_actions_usage(self, test_code: str) -> List[RuleViolation]:
        """
        Validate pdpActions is used instead of raw userEvent (from reference tests)
        ALL 15 reference tests use pdpActions, NEVER raw userEvent
        """
        violations = []
        
        # Check for raw userEvent usage (anti-pattern)
        raw_user_patterns = [
            r'await\s+user\.click\(',
            r'await\s+user\.type\(',
            r'await\s+userEvent\.click\(',
            r'await\s+userEvent\.type\(',
        ]
        
        for pattern in raw_user_patterns:
            if re.search(pattern, test_code):
                violations.append(RuleViolation(
                    rule_id='template.raw_user_event_usage',
                    severity='high',
                    message='Test uses raw userEvent instead of pdpActions helpers',
                    suggestion='Use pdpActions methods: await pdpActions.selectSize("UK 8"), await pdpActions.addToCart()'
                ))
                break  # Only report once
        
        # Check if pdpActions is initialized correctly
        if 'pdpUserActions' in test_code:
            if 'pdpActions = pdpUserActions(userEvent.setup())' not in test_code:
                violations.append(RuleViolation(
                    rule_id='template.pdp_actions_initialization',
                    severity='critical',
                    message='pdpActions not initialized correctly in beforeEach',
                    suggestion='Add in beforeEach: pdpActions = pdpUserActions(userEvent.setup())'
                ))
        
        return violations
    
    def _validate_cleanup_pattern(self, test_code: str) -> List[RuleViolation]:
        """
        Validate cleanup follows reference pattern
        ALL 15 reference tests use: await cleanupApolloClient() + jest.clearAllMocks()
        """
        violations = []
        
        # Check for cleanupApolloClient
        if 'cleanupApolloClient' in test_code:
            if 'await cleanupApolloClient()' not in test_code:
                violations.append(RuleViolation(
                    rule_id='template.cleanup_not_awaited',
                    severity='high',
                    message='cleanupApolloClient not awaited in afterEach',
                    suggestion='Use: await cleanupApolloClient() (with async afterEach)'
                ))
            
            # Check if afterEach is async
            if 'afterEach(async' not in test_code and 'await cleanupApolloClient()' in test_code:
                violations.append(RuleViolation(
                    rule_id='template.afterEach_not_async',
                    severity='critical',
                    message='afterEach not async but uses await cleanupApolloClient()',
                    suggestion='Change to: afterEach(async () => { await cleanupApolloClient() })'
                ))
        
        # Check for jest.clearAllMocks in afterEach
        if 'afterEach' in test_code and 'jest.clearAllMocks()' not in test_code:
            violations.append(RuleViolation(
                rule_id='template.missing_clear_all_mocks',
                severity='medium',
                message='Missing jest.clearAllMocks() in afterEach',
                suggestion='Add in afterEach: jest.clearAllMocks()'
            ))
        
        return violations
    
    def _calculate_score(self, violations: List[RuleViolation]) -> int:
        """
        Calculate validation score (0-100)
        
        Args:
            violations: List of violations
            
        Returns:
            int: Score from 0 to 100
        """
        if not violations:
            return 100
        
        # Deduct points based on severity
        points_deducted = 0
        for violation in violations:
            if violation.severity == 'critical':
                points_deducted += 30
            elif violation.severity == 'high':
                points_deducted += 15
            elif violation.severity == 'medium':
                points_deducted += 10
            elif violation.severity == 'low':
                points_deducted += 5
        
        score = max(0, 100 - points_deducted)
        return score
    
    def format_violations(self, result: ValidationResult) -> str:
        """
        Format violations for display or logging
        
        Args:
            result: Validation result
            
        Returns:
            str: Formatted violations
        """
        lines = []
        lines.append("=" * 70)
        lines.append("TEST VALIDATION REPORT")
        lines.append("=" * 70)
        lines.append(f"Status: {result.get_violation_summary()}")
        lines.append("")
        
        if result.violations:
            lines.append("VIOLATIONS:")
            for i, violation in enumerate(result.violations, 1):
                lines.append(f"\n{i}. [{violation.severity.upper()}] {violation.rule_id}")
                lines.append(f"   {violation.message}")
                if violation.suggestion:
                    lines.append(f"   💡 Suggestion: {violation.suggestion}")
        
        if result.warnings:
            lines.append("\nWARNINGS:")
            for i, warning in enumerate(result.warnings, 1):
                lines.append(f"{i}. {warning.message}")
        
        lines.append("\n" + "=" * 70)
        
        return "\n".join(lines)