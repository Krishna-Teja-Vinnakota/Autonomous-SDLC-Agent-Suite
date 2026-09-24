"""
Test Generator Agent
Generates actual test code for files using Gemini AI
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
import re

from config.vertex_ai import GeminiClient
from agents.strategy_agent import TestStrategy
from agents.analyze_agent import ProjectAnalysisResult
# Removed: TestValidator (redundant - using TestRulesValidator instead)
from config.testing_patterns import (
    get_testing_patterns,
    detect_test_infrastructure,
    build_infrastructure_context
)
from tools.testing_rules import TestingRulesExtractor, ProjectTestingRules, extract_project_rules
from tools.test_rules_validator import TestRulesValidator, ValidationResult
from tools.context_parser import (
    ContextParser,
    ContextContracts,
    ContextContractValidator,
    create_context_aware_prompt_section
)

logger = logging.getLogger(__name__)


@dataclass
class GeneratedTest:
    """Data class for a generated test file"""
    test_file_path: str
    source_file_path: str
    test_content: str
    framework: str
    test_count: int
    success: bool
    test_level: str = "unit"  # NEW: unit, integration, or feature
    error_message: Optional[str] = None


class TestGeneratorAgent:
    """
    Agent for generating test code
    Uses Gemini AI to create high-quality, contextual tests
    """
    
    def __init__(self, gemini_client: GeminiClient):
        """
        Initialize test generator agent
        
        Args:
            gemini_client: Initialized GeminiClient instance
        """
        self.client = gemini_client
        # Removed: self.validator (redundant - using test_rules_validator instead)
        self._infrastructure_cache = {}
        self._rules_cache = {}  # NEW: Cache for project rules
        self._rules_validators = {}  # NEW: Cache for validators
        self._context_cache = {}  # NEW: Cache for parsed context contracts
    
    def _get_infrastructure(self, project_path: Path):
        """
        Get or detect infrastructure for project (with caching)
        
        Args:
            project_path: Root path of project
            
        Returns:
            TestInfrastructure: Detected infrastructure
        """
        cache_key = str(project_path)
        
        if cache_key not in self._infrastructure_cache:
            logger.info(f"Detecting testing infrastructure for: {project_path}")
            self._infrastructure_cache[cache_key] = detect_test_infrastructure(project_path)
        
        return self._infrastructure_cache[cache_key]
    
    def _check_semantic_queries(self, test_code: str) -> List[str]:
        """
        Check if test uses semantic queries properly
        
        Returns:
            List of violations
        """
        violations = []
        
        # Check for getByTestId on interactive elements
        interactive_elements = ["button", "link", "input", "checkbox", "radio", "select", "textarea"]
        for element in interactive_elements:
            pattern = rf'getByTestId\([\'"](?!.*container|.*wrapper|.*root).*?{element}'
            if re.search(pattern, test_code, re.IGNORECASE):
                violations.append(f"Using getByTestId for {element} - MUST use getByRole instead")
                break
        
        # Check if getByRole is used for buttons/links when getByTestId is used
        has_testid = 'getByTestId' in test_code
        has_semantic = 'getByRole' in test_code or re.search(r'getByText\(/.*?/i?\)', test_code)
        
        if has_testid and not has_semantic:
            violations.append("Only using getByTestId, no semantic queries found - MUST prefer getByRole/getByText")
        
        return violations
    
    def _check_root_assertion(self, test_code: str, test_level: str) -> List[str]:
        """
        Check if feature test asserts root container
        
        Returns:
            List of violations
        """
        violations = []
        
        if test_level == 'feature':
            # Look for root container assertion patterns
            root_patterns = [
                r'expect\(screen\.getByTestId\([\'"].*?container[\'"].*?\)\)\.toBeInTheDocument\(\)',
                r'expect\(screen\.getByTestId\([\'"].*?root[\'"].*?\)\)\.toBeInTheDocument\(\)',
                r'expect\(screen\.getByTestId\([\'"].*?wrapper[\'"].*?\)\)\.toBeInTheDocument\(\)',
                r'expect\(.*?container.*?\)\.toBeInTheDocument\(\)',
            ]
            
            has_root_assertion = any(re.search(pattern, test_code) for pattern in root_patterns)
            
            if not has_root_assertion:
                violations.append("Feature test MUST assert root container exists (e.g., expect(screen.getByTestId('feature-container')).toBeInTheDocument())")
        
        return violations
    
    def _check_aaa_structure(self, test_code: str) -> List[str]:
        """
        Check if test follows Arrange-Act-Assert structure
        
        Returns:
            List of violations
        """
        violations = []
        
        # Check for typical AAA pattern: setup -> action -> assertion
        has_render = 'render' in test_code.lower()
        has_user_action = 'user.' in test_code or 'userEvent' in test_code
        has_expect = 'expect(' in test_code
        
        if not (has_render and has_expect):
            violations.append("Test doesn't follow basic AAA structure (missing render or assertions)")
        
        # For feature tests, should have user actions
        if has_render and has_expect and not has_user_action:
            violations.append("Feature test should include user actions (Arrange -> Act -> Assert)")
        
        return violations
    
    def _check_factory_cleanliness(self, test_code: str) -> List[str]:
        """
        Check if factory calls include only necessary fields
        
        Returns:
            List of violations  
        """
        violations = []
        
        # Look for factories with many fields (likely including setup fields)
        factory_pattern = r'(createMock\w+|mock\w+Factory)\(\{([^}]+)\}\)'
        matches = re.finditer(factory_pattern, test_code, re.DOTALL)
        
        for match in matches:
            fields_block = match.group(2)
            # Count number of fields (approximate by counting commas)
            field_count = fields_block.count(',') + 1
            
            # Flag if more than 10 fields (likely includes unnecessary setup fields)
            if field_count > 10:
                violations.append(f"Factory call has {field_count} fields - likely includes unnecessary setup fields")
                break
        
        # Check for __typename in factory calls (GraphQL setup field)
        if '__typename' in test_code and 'createMock' in test_code:
            violations.append("Factory includes __typename (setup field) - remove fields not used by component")
        
        return violations
    
    def _check_i18n_mocking(self, test_code: str, source_code: str) -> List[str]:
        """
        Check if test properly mocks i18n when component uses it
        
        Returns:
            List of violations
        """
        violations = []
        
        # Check if source uses translations
        uses_translations = 'useTranslations' in source_code or 'useTranslate' in source_code or 'useT(' in source_code
        
        if not uses_translations:
            return violations
        
        # Check if test mocks i18n
        has_i18n_mock = 'jest.mock' in test_code and ('next-intl' in test_code or 'react-i18next' in test_code or 'i18n' in test_code)
        
        if not has_i18n_mock:
            violations.append("Component uses i18n but test does not mock translation library - MUST add jest.mock('next-intl')")
        
        # Check for English text assertions instead of translation keys
        # Pattern: getByText(/English Text/i) or getByText('English Text')
        english_text_pattern = r'getByText\(\s*[\'"](?![a-z]+\.[a-zA-Z]+)[^\'\"]+[\'"]'
        if re.search(english_text_pattern, test_code) and uses_translations:
            violations.append("Test asserts English text instead of translation keys - use translation keys like 'pdp.labelSelectSize'")
        
        return violations
    
    def _check_child_component_boundaries(self, test_code: str) -> List[str]:
        """
        Check if test violates child component boundaries
        
        Returns:
            List of violations
        """
        violations = []
        
        # Look for test-ids that suggest child component internals
        # Pattern: getByTestId with names like 'product-variants-menu', 'child-component-modal'
        child_patterns = [
            r'getByTestId\([\'"][a-z-]+-(?:menu|modal|dialog|dropdown|list|grid|table)[\'"]',
            r'getByTestId\([\'"][a-z-]+-(?:component|widget|element)[\'"]',
        ]
        
        for pattern in child_patterns:
            match = re.search(pattern, test_code)
            if match:
                violations.append(f"Feature test asserts child component internal test-id: {match.group(0)} - use user-visible behavior instead")
                break
        
        return violations
    
    def _check_no_react_hooks(self, test_code: str) -> List[str]:
        """
        Check if test uses React hooks (V3 CRITICAL CHECK)
        Feature tests are NOT components
        """
        violations = []
        
        react_hooks = [
            'useState', 'useContext', 'useEffect', 'useReducer',
            'useMemo', 'useCallback', 'useRef', 'useLayoutEffect'
        ]
        
        for hook in react_hooks:
            if f'React.{hook}' in test_code or re.search(rf'\b{hook}\s*\(', test_code):
                violations.append(f"Test uses {hook} - feature tests MUST NOT use React hooks (test from outside, not as component)")
                return violations
        
        return violations
    
    def _check_no_custom_context(self, test_code: str) -> List[str]:
        """
        Check if test creates custom context (V3 CRITICAL CHECK)
        Must use real wrappers
        """
        violations = []
        
        # Check for context provider creation
        if re.search(r'<\w+Context\.Provider', test_code):
            violations.append("Test creates custom <Context.Provider> - MUST use real wrappers (pdpWrapper)")
        
        # Check for manual context value creation
        if 'contextValue' in test_code and ('state:' in test_code or 'product:' in test_code):
            violations.append("Test manually creates context values - this is unit test behavior, use real wrappers")
        
        # Check for React hooks used to create context
        if ('useState' in test_code or 'React.useState' in test_code) and 'const wrapper' in test_code:
            violations.append("Test uses useState in wrapper - creating custom context instead of using real wrappers")
        
        return violations
    
    def _check_test_name_matches_assertions(self, test_code: str) -> List[str]:
        """
        Check if test names match what's being asserted (V3 CRITICAL CHECK)
        """
        violations = []
        
        # Simple pattern matching for common mismatches
        tests = re.findall(r'it\([\'"]([^\'"]+)[\'"].*?\{([^}]+)\}', test_code, re.DOTALL)
        
        for test_name, test_body in tests:
            test_name_lower = test_name.lower()
            test_body_lower = test_body.lower()
            
            # Check if test mentions error but doesn't assert error
            if ('error' in test_name_lower or 'please select' in test_name_lower):
                if 'error' not in test_body_lower and 'please' not in test_body_lower and 'labelPleaseSelectSize' not in test_body:
                    violations.append(f"Test '{test_name}' promises error but doesn't assert error text")
            
            # Check for inverted scroll logic
            if 'scroll' in test_name_lower and '.not.toHaveBeenCalled' in test_body:
                violations.append(f"Test '{test_name}' says should scroll but asserts it did NOT scroll - inverted logic")
        
        return violations
    
    def _check_standard_wrapper_usage(self, test_code: str) -> List[str]:
        """
        Check if test uses standard wrapper pattern (V3 CHECK)
        """
        violations = []
        
        # Check for non-standard wrapper usage
        if 'pdpWrapper(mockProduct)({' in test_code or 'pdpWrapper(mockProduct)({ children' in test_code:
            violations.append("Non-standard wrapper usage - use: const wrapper = pdpWrapper(...); renderWeb(<Component />, { wrapper })")
        
        return violations
    
    def _validate_test_quality(self, test_code: str, test_level: str, source_code: str = "") -> Tuple[bool, List[str]]:
        """
        Validate test quality against strict rules
        
        Args:
            test_code: Generated test code
            test_level: Test level (unit/integration/feature)
            source_code: Source code being tested (for i18n detection)
            
        Returns:
            Tuple of (is_valid, violations)
        """
        violations = []
        
        # Run all quality checks
        violations.extend(self._check_semantic_queries(test_code))
        violations.extend(self._check_root_assertion(test_code, test_level))
        violations.extend(self._check_aaa_structure(test_code))
        violations.extend(self._check_factory_cleanliness(test_code))
        
        # NEW: i18n and child component checks
        if source_code:
            violations.extend(self._check_i18n_mocking(test_code, source_code))
        violations.extend(self._check_child_component_boundaries(test_code))
        
        # V3: Critical feature test prohibitions (ONLY for feature tests)
        if test_level == 'feature':
            violations.extend(self._check_no_react_hooks(test_code))
            violations.extend(self._check_no_custom_context(test_code))
            violations.extend(self._check_test_name_matches_assertions(test_code))
            violations.extend(self._check_standard_wrapper_usage(test_code))
        
        is_valid = len(violations) == 0
        
        if violations:
            logger.warning(f"Quality violations detected: {violations}")
        else:
            logger.info("✅ Test passed all quality checks")
        
        return is_valid, violations
    
    def _get_project_rules(self, project_path: Path, existing_tests: Optional[Dict[str, str]] = None) -> ProjectTestingRules:
        """
        Get or extract project testing rules (with caching)
        
        Args:
            project_path: Root path of project
            existing_tests: Optional existing test files
            
        Returns:
            ProjectTestingRules: Extracted rules
        """
        cache_key = str(project_path)
        
        if cache_key not in self._rules_cache:
            logger.info(f"Extracting testing rules for: {project_path}")
            self._rules_cache[cache_key] = extract_project_rules(project_path, existing_tests)
        
        return self._rules_cache[cache_key]
    
    def _get_rules_validator(self, project_path: Path, existing_tests: Optional[Dict[str, str]] = None) -> TestRulesValidator:
        """
        Get or create rules validator for project (with caching)
        
        Args:
            project_path: Root path of project
            existing_tests: Optional existing test files
            
        Returns:
            TestRulesValidator: Validator instance
        """
        cache_key = str(project_path)
        
        if cache_key not in self._rules_validators:
            rules = self._get_project_rules(project_path, existing_tests)
            self._rules_validators[cache_key] = TestRulesValidator(rules)
        
        return self._rules_validators[cache_key]
    
    def _parse_context_contracts(
        self,
        context_bundle: Dict[str, str],
        target_file: str,
        project_root: Path
    ) -> ContextContracts:
        """
        Parse context files to extract component and hook contracts
        
        Args:
            context_bundle: Dict[relative_path -> file_content] from context_builder
            target_file: Relative path to target file being tested
            project_root: Root directory of the project
            
        Returns:
            ContextContracts with extracted component/hook contracts
        """
        # Create cache key
        cache_key = f"{target_file}:{len(context_bundle)}"
        
        # Return cached contracts if available
        if cache_key in self._context_cache:
            logger.info(f"Using cached context contracts for {target_file}")
            return self._context_cache[cache_key]
        
        logger.info(f"📋 Parsing {len(context_bundle)} context files to extract contracts...")
        
        try:
            # Extract project-level testing rules (filesystem scan)
            logger.info(f"🔍 Extracting project testing rules from {project_root}")
            project_rules = extract_project_rules(project_root)
            
            logger.info(f"✅ Found {len(project_rules.detected_wrappers)} wrappers, "
                       f"{len(project_rules.detected_factories)} factories from project")
            
            # Initialize parser with project rules
            parser = ContextParser(project_rules=project_rules)
            
            # Convert relative paths to absolute paths for parser
            context_files = {}
            for rel_path, content in context_bundle.items():
                abs_path = str(project_root / rel_path)
                context_files[abs_path] = content
            
            # Parse all context files (will merge with project rules)
            contracts = parser.parse_context_files(
                context_files=context_files,
                target_file=str(project_root / target_file)
            )
            
            # Log what was extracted
            component_count = len(contracts.components)
            hook_count = len(contracts.hooks)
            testid_count = sum(len(c.test_ids) for c in contracts.components.values())
            utility_count = len(contracts.test_utilities)
            
            logger.info(f"✅ Extracted {component_count} components, {hook_count} hooks, "
                       f"{testid_count} test-ids, {utility_count} test utilities (merged)")
            
            # Log utilities found
            if contracts.test_utilities:
                logger.info(f"🧪 Test Utilities Available:")
                for util_name, utility in list(contracts.test_utilities.items())[:10]:
                    logger.info(f"  - {util_name} ({utility.type}) from {utility.import_path}")
            
            # Log each contract briefly
            for name, contract in contracts.components.items():
                logger.debug(f"  Component: {name} ({len(contract.props)} props, {len(contract.test_ids)} test-ids)")
            
            for name, contract in contracts.hooks.items():
                logger.debug(f"  Hook: {name} ({len(contract.return_type)} return fields)")
            
            # Cache the contracts
            self._context_cache[cache_key] = contracts
            
            return contracts
            
        except Exception as e:
            logger.warning(f"Failed to parse context contracts: {e}")
            # Return empty contracts on error
            return ContextContracts(
                components={},
                hooks={},
                test_utilities={},
                target_file=target_file
            )
    
    # ==================== NEW PHASE 3 METHODS ====================
    
    def _find_existing_test_examples(
        self,
        project_root: Path,
        test_level: str,
        framework: str = 'jest'
    ) -> Dict[str, str]:
        """
        Find existing test files that match the test level and framework.
        These will be used as examples to match the project's testing patterns.
        
        Args:
            project_root: Root directory of the project
            test_level: Test level (unit, integration, feature)
            framework: Test framework (jest, pytest)
        
        Returns:
            Dict[relative_path -> file_content] of existing test examples
        """
        existing_tests = {}
        
        try:
            # Test file patterns based on framework
            if framework == 'jest':
                test_patterns = [
                    f'**/*.{test_level}.test.tsx',
                    f'**/*.{test_level}.test.ts',
                    f'**/*.{test_level}.test.jsx',
                    f'**/*.{test_level}.test.js',
                    f'**/*.{test_level}.feature.test.tsx',
                    f'**/*.{test_level}.feature.test.ts',
                ]
            else:  # pytest
                test_patterns = [
                    f'**/test_*_{test_level}.py',
                    f'**/*_{test_level}_test.py',
                ]
            
            # Also look for any feature test files if generating feature tests
            if test_level == 'feature':
                test_patterns.extend([
                    '**/*.feature.test.tsx',
                    '**/*.feature.test.ts',
                ])
            
            # Find matching test files
            found_tests = []
            for pattern in test_patterns:
                found = list(project_root.glob(pattern))
                found_tests.extend(found)
            
            # Remove duplicates and filter out node_modules
            found_tests = [
                f for f in set(found_tests)
                if 'node_modules' not in str(f) and 'coverage' not in str(f)
            ]
            
            # Limit to 3 most relevant examples (to avoid token overflow)
            found_tests = found_tests[:3]
            
            for test_file in found_tests:
                try:
                    rel_path = str(test_file.relative_to(project_root))
                    content = test_file.read_text(encoding='utf-8', errors='ignore')
                    # Limit content to 2000 chars per example
                    if len(content) > 2000:
                        content = content[:2000] + "\n... [truncated]"
                    existing_tests[rel_path] = content
                    logger.info(f"Found existing test example: {rel_path}")
                except Exception as e:
                    logger.warning(f"Could not read test file {test_file}: {e}")
                    continue
            
        except Exception as e:
            logger.warning(f"Error finding existing test examples: {e}")
        
        return existing_tests
    
    def _validate_and_repair(
        self,
        test_code: str,
        strategy: TestStrategy,
        project_path: Optional[Path],
        max_repair_attempts: int = 2,
        source_code: str = "",
        attempt_number: int = 1
    ) -> Tuple[str, bool]:
        """
        Validate generated test and auto-repair if needed
        
        Args:
            test_code: Generated test code
            strategy: Test strategy
            project_path: Project root path
            max_repair_attempts: Maximum repair attempts
            source_code: Source code being tested (for i18n detection)
            attempt_number: Current attempt number (for logging)
            
        Returns:
            Tuple[str, bool]: (final_code, is_valid)
        """
        if not project_path:
            logger.warning("No project path - skipping validation")
            return test_code, True
        
        test_level = getattr(strategy, 'test_level', 'unit')
        
        try:
            # Log validation attempt
            logger.info(f"🔍 Validating test (attempt {attempt_number}/{max_repair_attempts + 1})...")
            
            # Get validator
            validator = self._get_rules_validator(project_path)
            
            # Validate with source code for i18n detection
            result = validator.validate(
                test_code=test_code,
                test_level=test_level,
                test_file_path=strategy.test_file,
                source_code=source_code
            )
            
            # Log detailed results
            violation_counts = {
                'critical': len([v for v in result.violations if v.severity == 'critical']),
                'high': len([v for v in result.violations if v.severity == 'high']),
                'medium': len([v for v in result.violations if v.severity == 'medium']),
                'low': len([v for v in result.violations if v.severity == 'low'])
            }
            
            if result.is_valid:
                logger.info(f"✅ Validation PASSED")
                logger.info(f"   Score: {result.score}/100")
                logger.info(f"   Violations: {len(result.violations)} total")
                if result.violations:
                    logger.info(f"   - Critical: {violation_counts['critical']}")
                    logger.info(f"   - High: {violation_counts['high']}")
                    logger.info(f"   - Medium: {violation_counts['medium']}")
                    logger.info(f"   - Low: {violation_counts['low']}")
                return test_code, True
            
            # Log failure details
            logger.warning(f"❌ Validation FAILED")
            logger.warning(f"   Score: {result.score}/100 (minimum: 70)")
            logger.warning(f"   Total violations: {len(result.violations)}")
            logger.warning(f"   - Critical: {violation_counts['critical']}")
            logger.warning(f"   - High: {violation_counts['high']}")
            logger.warning(f"   - Medium: {violation_counts['medium']}")
            logger.warning(f"   - Low: {violation_counts['low']}")
            
            # Show top violations
            if result.violations:
                logger.warning(f"   Top violations:")
                for i, v in enumerate(result.violations[:5], 1):
                    logger.warning(f"      {i}. [{v.severity.upper()}] {v.message}")
            
            # Auto-repair if we have attempts left
            if max_repair_attempts > 0:
                logger.info(f"🔄 Attempting auto-repair (attempts remaining: {max_repair_attempts})...")
                
                repaired_code = self._repair_test(
                    test_code=test_code,
                    validation_result=result,
                    strategy=strategy,
                    project_path=project_path,
                    attempt_number=attempt_number
                )
                
                if repaired_code and repaired_code != test_code:
                    logger.info(f"🔧 Repair generated new code ({len(repaired_code)} chars vs {len(test_code)} chars)")
                    # Recursive validation with incremented attempt number
                    return self._validate_and_repair(
                        test_code=repaired_code,
                        strategy=strategy,
                        project_path=project_path,
                        max_repair_attempts=max_repair_attempts - 1,
                        source_code=source_code,
                        attempt_number=attempt_number + 1
                    )
                else:
                    logger.warning(f"⚠️ Repair did not generate different code")
            else:
                logger.warning(f"⚠️ Max repair attempts ({attempt_number}) reached")
            
            # Return original if repair failed or not attempted
            logger.warning(f"⚠️ Returning test with violations (score: {result.score}/100)")
            return test_code, False
            
        except Exception as e:
            logger.error(f"Validation error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return test_code, True  # Don't block on validation errors
    
    def _repair_test(
        self,
        test_code: str,
        validation_result: ValidationResult,
        strategy: TestStrategy,
        project_path: Path,
        attempt_number: int = 1
    ) -> Optional[str]:
        """
        Attempt to auto-repair test violations using LLM
        
        Args:
            test_code: Test code with violations
            validation_result: Validation result with violations
            strategy: Test strategy
            project_path: Project root path
            attempt_number: Current attempt number
            
        Returns:
            Optional[str]: Repaired test code or None
        """
        try:
            # Get rules for context
            rules = self._get_project_rules(project_path)
            test_level = getattr(strategy, 'test_level', 'unit')
            
            # Categorize violations by severity
            critical_violations = [v for v in validation_result.violations if v.severity == 'critical']
            high_violations = [v for v in validation_result.violations if v.severity == 'high']
            medium_violations = [v for v in validation_result.violations if v.severity == 'medium']
            low_violations = [v for v in validation_result.violations if v.severity == 'low']
            
            # Build categorized violations text
            violations_text = ""
            
            if critical_violations:
                violations_text += "🔴 CRITICAL VIOLATIONS (blocks acceptance):\n"
                for v in critical_violations:
                    violations_text += f"   Rule: {v.rule_id}\n"
                    violations_text += f"   Issue: {v.message}\n"
                    if v.suggestion:
                        violations_text += f"   Fix: {v.suggestion}\n"
                    violations_text += "\n"
            
            if high_violations:
                violations_text += "🟠 HIGH VIOLATIONS (major quality issues):\n"
                for v in high_violations:
                    violations_text += f"   Rule: {v.rule_id}\n"
                    violations_text += f"   Issue: {v.message}\n"
                    if v.suggestion:
                        violations_text += f"   Fix: {v.suggestion}\n"
                    violations_text += "\n"
            
            if medium_violations:
                violations_text += "🟡 MEDIUM VIOLATIONS (quality improvements):\n"
                for v in medium_violations:
                    violations_text += f"   Rule: {v.rule_id}\n"
                    violations_text += f"   Issue: {v.message}\n"
                    if v.suggestion:
                        violations_text += f"   Fix: {v.suggestion}\n"
                    violations_text += "\n"
            
            if low_violations:
                violations_text += "🟢 LOW VIOLATIONS (minor improvements):\n"
                for v in low_violations:
                    violations_text += f"   Rule: {v.rule_id}\n"
                    violations_text += f"   Issue: {v.message}\n"
                    if v.suggestion:
                        violations_text += f"   Fix: {v.suggestion}\n"
                    violations_text += "\n"
            
            # Add template reference for feature tests
            template_reminder = ""
            if test_level == 'feature':
                template_reminder = """
🎯 REMEMBER: PDP Feature tests MUST follow this EXACT structure:

```typescript
import { screen, waitFor } from '@testing-library/react'
import { userEvent } from '@testing-library/user-event'
import { Component } from '../component/index'
import { SelectSize } from '../select-size'
import { createMockProduct, mockPdpProduct } from '@mocks/factories'
import { pdpUserActions } from '@test-utils/user-actions'
import { pdpWrapper, renderWeb } from '@test-utils/render'
import { cleanupApolloClient } from '@test-utils/apollo'

describe('PDP Component Feature', () => {
  let pdpActions: ReturnType<typeof pdpUserActions>
  let mockProduct: ReturnType<typeof createMockProduct>

  const renderComponentPdp = (product = mockProduct) =>
    renderWeb(
      <>
        <SelectSize />
        <Component />
      </>,
      { wrapper: pdpWrapper(product) },
    )

  beforeEach(() => {
    pdpActions = pdpUserActions(userEvent.setup())
    mockProduct = mockPdpProduct()
  })

  afterEach(async () => {
    await cleanupApolloClient()
    jest.clearAllMocks()
  })

  it('outcome WHEN/WHILE/AFTER action', async () => {
    renderComponentPdp()
    await pdpActions.doAction()
    await waitFor(() => expect(result).toBe(expected))
  })
})
```

KEY REQUIREMENTS:
- Import order: RTL → userEvent → Components → Factories → Test Utils
- Type annotations: ReturnType<typeof factory>
- Custom render function: render[Component]Pdp
- Use pdpActions methods (NOT raw userEvent)
- Test names: "outcome WHEN/WHILE/AFTER action"
- Async cleanup: await cleanupApolloClient()
"""
            
            # Build repair prompt
            repair_prompt = f"""Your previous test scored {validation_result.score}/100.

Fix these violations:

{violations_text}
{template_reminder}

ORIGINAL TEST CODE (has violations):
```typescript
{test_code}
```

PROJECT CONTEXT:
- Test Level: {test_level}
- Available Wrappers: {', '.join(rules.detected_wrappers[:5]) if rules.detected_wrappers else 'None'}
- Available Factories: {', '.join(rules.detected_factories[:5]) if rules.detected_factories else 'None'}

REPAIR INSTRUCTIONS:
1. Fix ALL violations listed above (prioritize CRITICAL, then HIGH)
2. Follow the EXACT template structure shown above
3. Preserve the test's intent and coverage
4. Use ONLY detected wrappers and factories (do not invent new ones)
5. Match existing project patterns
6. Return ONLY the complete corrected test code
7. Do NOT add explanations or markdown - just the test code

Generate the repaired test code:
"""
            
            logger.info(f"🔧 Building repair prompt (attempt {attempt_number})...")
            logger.info(f"   Critical violations: {len(critical_violations)}")
            logger.info(f"   High violations: {len(high_violations)}")
            logger.info(f"   Medium violations: {len(medium_violations)}")
            logger.info(f"   Low violations: {len(low_violations)}")
            
            # Generate repair
            generation_config = {
                "max_output_tokens": 4000,
                "temperature": 0.2  # Lower temperature for repairs
            }
            
            logger.info("📤 Sending repair request to LLM...")
            response = self.client.generate_content(
                prompt=repair_prompt,
                generation_config=generation_config
            )
            
            if response:
                # Extract code
                repaired_code = self._extract_code_from_response(response)
                
                if repaired_code:
                    logger.info("✅ Repair completed - received new code")
                    logger.info(f"   Original length: {len(test_code)} chars")
                    logger.info(f"   Repaired length: {len(repaired_code)} chars")
                    return repaired_code
                else:
                    logger.warning("⚠️ Repair response did not contain valid code")
            else:
                logger.warning("⚠️ No response from LLM for repair")
            
            logger.warning("Repair failed - no valid response")
            return None
            
        except Exception as e:
            logger.error(f"Error during repair: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def generate_single_test_with_context(
        self,
        strategy: TestStrategy,
        context_bundle: Dict[str, str],
        project_root: Path
    ) -> GeneratedTest:
        """
        Generate a single test with full repo context.
        
        This is the new method for single-target feature test generation with
        dependency-aware context from context_builder.
        
        Args:
            strategy: Test strategy for the target file
            context_bundle: Dict[relative_path -> file_content] from context_builder
            project_root: Root directory of the project
        
        Returns:
            GeneratedTest with generated test code
        """
        try:
            logger.info(f"Generating single test for {strategy.source_file} with {len(context_bundle)} context files")
            
            # Read target file content
            target_path = project_root / strategy.source_file
            if not target_path.exists():
                logger.error(f"Target file not found: {target_path}")
                return GeneratedTest(
                    test_file_path=strategy.test_file,
                    source_file_path=strategy.source_file,
                    test_content="",
                    framework=strategy.framework,
                    test_count=0,
                    test_level=getattr(strategy, 'test_level', 'feature'),
                    success=False,
                    error_message=f"Target file not found: {strategy.source_file}"
                )
            
            target_content = target_path.read_text(encoding='utf-8', errors='ignore')
            
            # Find existing test examples to match patterns
            test_level = getattr(strategy, 'test_level', 'feature')
            existing_tests = self._find_existing_test_examples(
                project_root=project_root,
                test_level=test_level,
                framework=strategy.framework
            )
            
            # NEW: Parse context files to extract contracts
            logger.info("📋 Parsing context files to extract component/hook contracts...")
            context_contracts = self._parse_context_contracts(
                context_bundle=context_bundle,
                target_file=strategy.source_file,
                project_root=project_root
            )
            
            # Build prompt with context bundle, contracts, and existing test examples
            prompt = self._build_jest_prompt_with_context(
                strategy=strategy,
                target_content=target_content,
                context_bundle=context_bundle,
                existing_test_examples=existing_tests,
                project_path=project_root,  # NEW: Pass project_path for rule extraction
                context_contracts=context_contracts  # NEW: Pass contracts
            )
            
            # Generate test using Gemini
            logger.info("Calling Gemini API to generate test...")
            generation_config = {
                "max_output_tokens": 4000,  # Increased for comprehensive feature tests
                "temperature": 0.3
            }
            response = self.client.generate_content(
                prompt=prompt,
                generation_config=generation_config
            )
            
            if not response:
                logger.error("Gemini API returned empty response")
                return GeneratedTest(
                    test_file_path=strategy.test_file,
                    source_file_path=strategy.source_file,
                    test_content="",
                    framework=strategy.framework,
                    test_count=0,
                    test_level=getattr(strategy, 'test_level', 'feature'),
                    success=False,
                    error_message="Empty response from Gemini API"
                )
            
            # Extract code from response (reusing existing robust extraction logic)
            test_code = self._extract_code_from_response(response)
            
            if not test_code or len(test_code) < 50:
                logger.error("Failed to extract valid test code from response")
                return GeneratedTest(
                    test_file_path=strategy.test_file,
                    source_file_path=strategy.source_file,
                    test_content="",
                    framework=strategy.framework,
                    test_count=0,
                    test_level=getattr(strategy, 'test_level', 'feature'),
                    success=False,
                    error_message="Failed to extract valid test code"
                )
            
            # NEW: Validate and repair test against project rules
            test_code, is_valid = self._validate_and_repair(
                test_code=test_code,
                strategy=strategy,
                project_path=project_root,
                max_repair_attempts=2,
                source_code=target_content  # Pass source for i18n detection
            )
            
            if not is_valid:
                logger.warning(f"⚠️ Test generated but has validation warnings")
            
            # NEW: Quality validation with auto-repair
            test_level = getattr(strategy, 'test_level', 'unit')
            quality_valid, quality_violations = self._validate_test_quality(test_code, test_level, target_content)
            
            if not quality_valid and quality_violations:
                logger.warning(f"❌ Quality violations detected: {quality_violations}")
                logger.info("🔧 Attempting quality-focused repair...")
                
                # Create a mock validation result for quality repair
                from tools.test_rules_validator import ValidationResult, RuleViolation
                quality_result = ValidationResult(
                    is_valid=False,
                    violations=[
                        RuleViolation(
                            rule_id=f'quality.{i}',
                            severity='critical',
                            message=violation,
                            suggestion=None
                        ) for i, violation in enumerate(quality_violations)
                    ],
                    warnings=[],
                    score=50
                )
                
                # Attempt repair with quality violations
                repaired_code = self._repair_test(
                    test_code=test_code,
                    validation_result=quality_result,
                    strategy=strategy,
                    project_path=project_root
                )
                
                if repaired_code and repaired_code != test_code:
                    logger.info("✅ Quality repair completed - re-validating...")
                    # Re-validate quality
                    quality_valid_after, quality_violations_after = self._validate_test_quality(repaired_code, test_level, target_content)
                    
                    if quality_valid_after:
                        logger.info("✅ Quality validation passed after repair!")
                        test_code = repaired_code
                    elif len(quality_violations_after) < len(quality_violations):
                        logger.info(f"✓ Partial improvement: {len(quality_violations)} → {len(quality_violations_after)} violations")
                        test_code = repaired_code
                    else:
                        logger.warning("⚠️ Quality repair did not improve test - using original")
                else:
                    logger.warning("⚠️ Quality repair failed - using test as-is")
            else:
                if quality_valid:
                    logger.info("✅ Test passed all quality checks")
            
            # Validate test completeness (non-blocking)
            validation_error = self._validate_test_file(test_code, strategy.framework)
            if validation_error:
                logger.warning(f"Test validation warning: {validation_error}")
            
            # Count tests
            test_count = self._count_tests(test_code, strategy.framework)
            
            logger.info(f"Successfully generated test with {test_count} test cases")
            
            return GeneratedTest(
                test_file_path=strategy.test_file,
                source_file_path=strategy.source_file,
                test_content=test_code,
                framework=strategy.framework,
                test_count=test_count,
                test_level=getattr(strategy, 'test_level', 'feature'),
                success=True,
                error_message=None
            )
            
        except Exception as e:
            logger.error(f"Test generation failed: {e}", exc_info=True)
            return GeneratedTest(
                test_file_path=strategy.test_file,
                source_file_path=strategy.source_file,
                test_content="",
                framework=strategy.framework,
                test_count=0,
                test_level=getattr(strategy, 'test_level', 'feature'),
                success=False,
                error_message=str(e)
            )
    
    def _build_jest_prompt_with_context(
        self,
        strategy: TestStrategy,
        target_content: str,
        context_bundle: Dict[str, str],
        existing_test_examples: Optional[Dict[str, str]] = None,
        project_path: Optional[Path] = None,  # NEW: Added for rule extraction
        context_contracts: Optional[ContextContracts] = None  # NEW: Added for context awareness
    ) -> str:
        """
        Build Jest/Vitest prompt with full context bundle for tests.
        
        This is specifically designed for single-target test generation
        with comprehensive repository context. Supports unit, integration, and feature tests.
        
        Args:
            strategy: Test strategy for the target file
            target_content: Content of the target file to test
            context_bundle: Dict of relative_path -> file_content for context
            existing_test_examples: Dict of existing test files to use as pattern examples
            project_path: Project root path for rule extraction
            context_contracts: Optional parsed contracts from context files
        
        Returns:
            Formatted prompt string for Gemini
        """
        
        # Get test level from strategy
        test_level = getattr(strategy, 'test_level', 'unit')
        
        # NEW: Get project-specific rules
        rules_section = ""
        if project_path:
            try:
                rules = self._get_project_rules(project_path, existing_tests=existing_test_examples)
                
                # Format rules as constraints
                rules_extractor = TestingRulesExtractor(project_path)
                rules_section = "\n" + rules_extractor.format_rules_for_prompt(rules, test_level) + "\n"
                
                logger.info(f"Injected {len(rules.detected_wrappers)} wrappers, {len(rules.detected_factories)} factories into prompt")
            except Exception as e:
                logger.warning(f"Could not extract rules: {e}")
        
        # Format context files section
        context_section = "## REPOSITORY CONTEXT\n\n"
        context_section += "These files provide context for dependencies, utilities, and related components:\n\n"
        
        for rel_path, content in context_bundle.items():
            # Truncate very long context files to avoid token overflow
            display_content = content[:3000] if len(content) > 3000 else content
            context_section += f"### File: `{rel_path}`\n```typescript\n{display_content}\n```\n\n"
        
        # NEW: Add context contracts section (CRITICAL - prevents guessing)
        context_contracts_section = ""
        if context_contracts and (context_contracts.components or context_contracts.hooks):
            logger.info(f"📋 Adding {len(context_contracts.components)} component contracts + {len(context_contracts.hooks)} hook contracts to prompt")
            context_contracts_section = "\n" + create_context_aware_prompt_section(context_contracts) + "\n"
        
        # Format existing test examples section (CRITICAL for matching patterns)
        existing_tests_section = ""
        if existing_test_examples:
            existing_tests_section = "\n## EXISTING TEST EXAMPLES (MATCH THIS PATTERN)\n\n"
            existing_tests_section += "**IMPORTANT**: These are existing test files from this project. You MUST match their pattern exactly:\n"
            existing_tests_section += "- Use the same imports (test utilities, mocks, wrappers)\n"
            existing_tests_section += "- Use the same test structure and naming conventions\n"
            existing_tests_section += "- Use the same helper functions and utilities\n"
            existing_tests_section += "- Match the describe block naming pattern\n"
            existing_tests_section += "- Match the import path structure\n\n"
            
            for rel_path, content in existing_test_examples.items():
                existing_tests_section += f"### Example Test: `{rel_path}`\n```typescript\n{content}\n```\n\n"
        
        # Get test level specific instructions
        test_level_instructions = self._get_test_level_instructions(test_level)
        
        # Determine test type description
        test_type_desc = {
            'unit': 'unit tests focusing on individual functions/components in isolation',
            'integration': 'integration tests verifying interactions between components',
            'feature': 'feature tests covering complete user workflows and scenarios'
        }.get(test_level, 'unit tests')
        
        prompt = f"""You are an expert at writing comprehensive {test_type_desc} for React/TypeScript applications.

## TARGET FILE TO TEST
File: `{strategy.source_file}`

```typescript
{target_content}
```

{context_section}{context_contracts_section}{existing_tests_section}{rules_section}

## TEST GENERATION REQUIREMENTS

### Test Type
- **Level**: {test_level.upper()} test
{test_level_instructions}
- **Framework**: {strategy.framework}
- **File**: `{strategy.test_file}`

### Critical Instructions
1. **MATCH EXISTING TEST PATTERNS** (HIGHEST PRIORITY):
   - If existing test examples are provided above, you MUST match their pattern exactly
   - Use the same imports (e.g., `@test-utils/render`, `@test-utils/user-actions`, `@mocks/factories`)
   - Use the same test utilities (e.g., `renderWeb`, `pdpWrapper`, `pdpUserActions`, `mockPdpProduct`)
   - Match the describe block naming (e.g., "PDP ComponentName Feature" for feature tests)
   - Match the import path structure (relative paths should match project structure)
   - Use the same setup/teardown patterns (e.g., `beforeEach`, `afterEach` with `cleanupApolloClient`)

2. **Use the repository context** to:
   - Import correct utilities, wrappers, and test helpers
   - Understand component dependencies and props
   - Use actual implementations appropriately based on test level
   - Match the project's testing patterns

3. **DO NOT invent APIs** - Only use:
   - Imports that exist in the context files or existing test examples
   - Test utilities that are actually present in the project
   - Props/hooks/functions that are defined in dependencies

4. **Test level-specific requirements**:
   - **Unit tests**: Mock all external dependencies, test in isolation
   - **Integration tests**: Use real implementations where possible, mock only external services
   - **Feature tests**: Test real user workflows, use real wrappers (pdpWrapper, renderWeb), include setup/teardown for providers/contexts/stores, use proper async handling

5. **Code quality**:
   - Use proper TypeScript types
   - Follow existing test patterns from context and examples
   - Include descriptive test names
   - Add comments for complex setup logic

### Output Format
- Return ONLY the test code
- NO explanations, preambles, or markdown code fences
- Valid TypeScript that can be directly saved and executed
- Start with imports, end with closing brace of describe block
- MUST match the pattern from existing test examples if provided

Generate the complete {test_level} test now:
"""
        
        return prompt
    
  
    
    def generate_tests(
        self,
        strategies: List[TestStrategy],
        project_path: Path,
        analysis_result: Optional[ProjectAnalysisResult],
        workspace_path: Optional[Path] = None,
        previous_coverage: Optional[Dict[str, Any]] = None
    ) -> List[GeneratedTest]:
        """
        Generate test files based on strategies
        
        Args:
            strategies: List of test strategies
            project_path: Path to main project directory (where tests will be saved)
            analysis_result: Project analysis results
            workspace_path: Optional workspace path (for saving a copy)
            
        Returns:
            List[GeneratedTest]: Generated test results
        """
        generated_tests = []
        
        for strategy in strategies:
            logger.info(f"Generating test for: {strategy.source_file}")
            
            try:
                # Read source file from workspace (where uploaded files are)
                # Use workspace_path if provided, otherwise fallback to project_path
                source_base_path = workspace_path if workspace_path else project_path
                source_path = source_base_path / strategy.source_file
                if not source_path.exists():
                    logger.warning(f"Source file not found: {source_path}")
                    test_level = getattr(strategy, 'test_level', 'unit')
                    generated_tests.append(GeneratedTest(
                        test_file_path=strategy.test_file,
                        source_file_path=strategy.source_file,
                        test_content="",
                        framework=strategy.framework,
                        test_count=0,
                        test_level=test_level,
                        success=False,
                        error_message="Source file not found"
                    ))
                    continue
                
                source_content = source_path.read_text(encoding='utf-8', errors='ignore')
                
                # Get coverage info for this specific file if available
                file_coverage_info = None
                if previous_coverage:
                    # Look for coverage data for this specific source file
                    source_file_key = strategy.source_file
                    file_coverage_info = previous_coverage.get(source_file_key)
                    if not file_coverage_info:
                        # Try with full path
                        for key, cov_data in previous_coverage.items():
                            if source_file_key in key or key.endswith(source_file_key):
                                file_coverage_info = cov_data
                                break
                
                # For integration/feature tests, load related files context
                related_contents = {}
                if hasattr(strategy, 'test_level') and strategy.test_level in ['integration', 'feature']:
                    if hasattr(strategy, 'related_files') and strategy.related_files:
                        for related_file in strategy.related_files[:7]:  # Limit to 7 files
                            related_path = source_base_path / related_file
                            if related_path.exists():
                                try:
                                    related_contents[related_file] = related_path.read_text(encoding='utf-8', errors='ignore')[:3000]  # Limit to 3k chars
                                except Exception as e:
                                    logger.warning(f"Could not read related file {related_file}: {e}")
                
                # Generate test with appropriate level
                test_content = self._generate_test_content(
                    strategy=strategy,
                    source_content=source_content,
                    analysis_result=analysis_result,
                    coverage_info=file_coverage_info,
                    related_contents=related_contents,
                    project_path=project_path
                )
                
                if test_content:
                    # Validate test file completeness (non-blocking - just log warnings)
                    validation_error = self._validate_test_file(test_content, strategy.framework)
                    if validation_error:
                        logger.warning(f"Test file validation warning: {validation_error} (will still save and attempt to run)")
                    
                    # Removed: Old validator classification (using TestRulesValidator in new generation method)
                    # Legacy generate_tests() method - classification logging removed as it's redundant
                    # New generate_single_test_with_context() uses comprehensive TestRulesValidator instead
                    # Always count tests regardless of framework
                    test_count = self._count_tests(test_content, strategy.framework)
                    
                    # Save test file to project path (where user's project is)
                    test_file_path = project_path / strategy.test_file
                    test_file_path.parent.mkdir(parents=True, exist_ok=True)
                    test_file_path.write_text(test_content, encoding='utf-8')
                    logger.info(f"Test saved to: {test_file_path}")
                    
                    # Also save to workspace path if provided (for execution)
                    if workspace_path:
                        workspace_test_path = workspace_path / strategy.test_file
                        workspace_test_path.parent.mkdir(parents=True, exist_ok=True)
                        workspace_test_path.write_text(test_content, encoding='utf-8')
                        logger.debug(f"Test also saved to workspace: {workspace_test_path}")
                    
                    generated_tests.append(GeneratedTest(
                        test_file_path=strategy.test_file,
                        source_file_path=strategy.source_file,
                        test_content=test_content,
                        framework=strategy.framework,
                        test_count=test_count,
                        test_level=test_level,
                        success=True
                    ))
                else:
                    logger.error(f"No test content generated for {strategy.source_file}")
                    test_level = getattr(strategy, 'test_level', 'unit')
                    generated_tests.append(GeneratedTest(
                        test_file_path=strategy.test_file,
                        source_file_path=strategy.source_file,
                        test_content="",
                        framework=strategy.framework,
                        test_count=0,
                        test_level=test_level,
                        success=False,
                        error_message="Failed to generate test content"
                    ))
                    
            except Exception as e:
                logger.error(f"Error generating test for {strategy.source_file}: {e}")
                test_level = getattr(strategy, 'test_level', 'unit')
                generated_tests.append(GeneratedTest(
                    test_file_path=strategy.test_file,
                    source_file_path=strategy.source_file,
                    test_content="",
                    framework=strategy.framework,
                    test_count=0,
                    test_level=test_level,
                    success=False,
                    error_message=str(e)
                ))
        
        return generated_tests
    
    def _generate_test_content(
        self,
        strategy: TestStrategy,
        source_content: str,
        analysis_result: Optional[ProjectAnalysisResult],
        coverage_info: Optional[Dict[str, Any]],
        related_contents: Optional[Dict[str, str]],
        project_path: Path
    ) -> Optional[str]:
        """
        Generate test content for a single file
        
        Args:
            strategy: Test strategy
            source_content: Source file content
            analysis_result: Project analysis
            coverage_info: Coverage data for this specific file (if available)
            related_contents: Contents of related files for context
            
        Returns:
            str: Generated test content or None
        """
        try:
            # Get test level - default to unit if not specified
            test_level = getattr(strategy, 'test_level', 'unit')
            logger.info(f"🎯 _generate_test_content: Using test_level='{test_level}' from strategy (strategy.test_level={getattr(strategy, 'test_level', 'NOT SET')})")
            
            # Get infrastructure for this project (cached)
            infrastructure = self._get_infrastructure(project_path)
            
            # Build infrastructure context (includes patterns + detected infrastructure)
            infra_context = build_infrastructure_context(
                project_root=project_path,
                framework=strategy.framework
            )
            
            # Get testing patterns based on framework
            patterns = get_testing_patterns(strategy.framework)
            
            # Build related files context
            related_files_context = ""
            if related_contents:
                related_files_context = "\n## RELATED FILES (For Context)\n\n"
                for file_path, content in related_contents.items():
                    related_files_context += f"### File: {file_path}\n```\n{content}\n```\n\n"
            
            # Build coverage improvement context if available
            coverage_context = ""
            if coverage_info:
                coverage_context = self._build_coverage_context(coverage_info)
            
            # Find existing test examples to match patterns
            existing_tests = self._find_existing_test_examples(
                project_root=project_path,
                test_level=test_level,
                framework=strategy.framework
            )
            
            # Generate appropriate prompt based on framework and test level
            if strategy.framework == 'jest':
                prompt = self._build_jest_prompt(
                    strategy, 
                    source_content, 
                    patterns,
                    infra_context,
                    related_files_context,
                    coverage_context,
                    test_level,
                    existing_test_examples=existing_tests
                )
            elif strategy.framework == 'pytest':
                prompt = self._build_pytest_prompt(
                    strategy, 
                    source_content, 
                    patterns,
                    infra_context,
                    coverage_context
                )
            else:
                logger.error(f"Unsupported framework: {strategy.framework}")
                return None
            
            # Call Gemini with retry logic
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    logger.info(f"Generating test (attempt {attempt + 1}/{max_retries})...")
                    
                    # Adjust max_output_tokens based on test level
                    max_output_tokens = 4000 if test_level == 'feature' else 3000 if test_level == 'integration' else 2000
                    
                    generation_config = {
                        "max_output_tokens": max_output_tokens,
                        "temperature": 0.3
                    }
                    response = self.client.generate_content(
                        prompt=prompt,
                        generation_config=generation_config
                    )
                    
                    if response:
                        # Extract code from response
                        test_code = self._extract_code_from_response(response)
                        
                        # Verify we got valid test code
                        if test_code and len(test_code) > 50:
                            # Basic validation: ensure it has test structure
                            if strategy.framework == 'jest':
                                if 'describe(' in test_code or 'test(' in test_code or 'it(' in test_code:
                                    # Validate code completeness
                                    if self._is_code_complete(test_code):
                                        return test_code
                                    else:
                                        logger.warning(f"Attempt {attempt + 1}: Generated code appears incomplete, retrying...")
                                        # If last attempt, return anyway
                                        if attempt == max_retries - 1:
                                            logger.info("Last attempt - returning code even if incomplete")
                                            return test_code
                                        continue
                                else:
                                    logger.warning(f"Attempt {attempt + 1}: Code missing test structure")
                            elif strategy.framework == 'pytest':
                                if 'def test_' in test_code:
                                    if self._is_code_complete(test_code):
                                        return test_code
                                    else:
                                        logger.warning(f"Attempt {attempt + 1}: Generated code appears incomplete, retrying...")
                                        if attempt == max_retries - 1:
                                            logger.info("Last attempt - returning code even if incomplete")
                                            return test_code
                                        continue
                                else:
                                    logger.warning(f"Attempt {attempt + 1}: Code missing test functions")
                        
                        logger.warning(f"Attempt {attempt + 1}: Could not extract valid test code")
                        
                except Exception as e:
                    logger.error(f"Attempt {attempt + 1} failed: {e}")
                    if attempt == max_retries - 1:
                        raise
            
            logger.error("Failed to generate test after all retries")
            return None
            
        except Exception as e:
            logger.error(f"Error generating test content: {e}")
            return None
    
    def _build_coverage_context(self, coverage_info: Dict[str, Any]) -> str:
        """
        Build coverage improvement context from coverage data
        
        Args:
            coverage_info: Coverage data for a file
            
        Returns:
            Formatted coverage context string
        """
        try:
            context = "\n## COVERAGE IMPROVEMENT FOCUS\n\n"
            
            # Check if we have line coverage data
            if 'lines' in coverage_info:
                uncovered_lines = coverage_info['lines'].get('uncovered', [])
                if uncovered_lines:
                    context += f"The following lines are currently uncovered by tests:\n"
                    context += f"Lines: {', '.join(map(str, uncovered_lines[:20]))}\n"  # Limit to first 20
                    context += "Please ensure your tests cover these areas.\n\n"
            
            # Check if we have branch coverage data
            if 'branches' in coverage_info:
                uncovered_branches = coverage_info['branches'].get('uncovered', [])
                if uncovered_branches:
                    context += "Focus on testing conditional branches and edge cases.\n\n"
            
            # Add general coverage guidance
            current_coverage = coverage_info.get('coverage_percent', 0)
            if current_coverage < 80:
                context += f"Current coverage is {current_coverage:.1f}%. Aim for comprehensive test coverage.\n"
            
            return context
            
        except Exception as e:
            logger.warning(f"Error building coverage context: {e}")
            return ""
    
    def _build_jest_prompt(
        self, 
        strategy: TestStrategy, 
        source_content: str, 
        patterns: str,
        infrastructure_context: str,
        related_files_context: str = "",
        coverage_context: str = "",
        test_level: str = "unit",
        existing_test_examples: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Build Jest/Vitest test generation prompt
        
        BACKWARD COMPATIBLE: This is the original method for multi-file workflows.
        For single-target with context bundle, use _build_jest_prompt_with_context instead.
        """
        
        # Format existing test examples section (CRITICAL for matching patterns)
        existing_tests_section = ""
        if existing_test_examples:
            existing_tests_section = "\n## EXISTING TEST EXAMPLES (MATCH THIS PATTERN)\n\n"
            existing_tests_section += "**IMPORTANT**: These are existing test files from this project. You MUST match their pattern exactly:\n"
            existing_tests_section += "- Use the same imports (test utilities, mocks, wrappers)\n"
            existing_tests_section += "- Use the same test structure and naming conventions\n"
            existing_tests_section += "- Use the same helper functions and utilities\n"
            existing_tests_section += "- Match the describe block naming pattern\n"
            existing_tests_section += "- Match the import path structure\n\n"
            
            for rel_path, content in existing_test_examples.items():
                existing_tests_section += f"### Example Test: `{rel_path}`\n```typescript\n{content}\n```\n\n"
        
        # Determine test type description
        test_type_desc = {
            'unit': 'unit tests focusing on individual functions/components in isolation',
            'integration': 'integration tests verifying interactions between components',
            'feature': 'feature tests covering complete user workflows and scenarios'
        }.get(test_level, 'unit tests')
        
        prompt = f"""You are an expert at writing comprehensive {test_type_desc} for JavaScript/TypeScript applications.

## SOURCE FILE TO TEST
File: {strategy.source_file}

```typescript
{source_content}
```

{related_files_context}

{coverage_context}

## TESTING INFRASTRUCTURE DETECTED
{infrastructure_context}

## TESTING PATTERNS AND EXAMPLES
{patterns}
{existing_tests_section}

## YOUR TASK
Generate a comprehensive test file for the source code above.

### Test Level: {test_level.upper()}
{self._get_test_level_instructions(test_level)}

### Requirements:
1. **MATCH EXISTING TEST PATTERNS** (HIGHEST PRIORITY if examples provided above):
   - Use the same imports (e.g., `@test-utils/render`, `@test-utils/user-actions`, `@mocks/factories`)
   - Use the same test utilities (e.g., `renderWeb`, `pdpWrapper`, `pdpUserActions`, `mockPdpProduct`)
   - Match the describe block naming (e.g., "PDP ComponentName Feature" for feature tests)
   - Match the import path structure
   - Use the same setup/teardown patterns

2. Create tests using {strategy.framework}
3. Follow the testing patterns shown above
4. Test file should be saved as: {strategy.test_file}
5. Include proper imports from the source file
6. Use the detected testing infrastructure (setup files, utilities, etc.)
7. Add descriptive test names that explain what is being tested
8. Include edge cases and error scenarios
9. Use proper assertions and matchers
10. Mock external dependencies appropriately
11. Ensure tests are isolated and can run independently

### Output Format:
- Provide ONLY the test code
- Do not include explanations or markdown
- Start with imports
- Include all necessary test cases
- End with a complete, runnable test file
- MUST match the pattern from existing test examples if provided

Generate the test file now:
"""
        return prompt
    
    def _get_test_level_instructions(self, test_level: str) -> str:
        """Get specific instructions based on test level"""
        if test_level == 'unit':
            return """
- Focus on testing individual functions/components in isolation
- Mock all external dependencies
- Test edge cases, error handling, and boundary conditions
- Keep tests fast and focused on single units of work

🚨 COMPONENT-LEVEL TESTING RULES (For React/TypeScript Components):

🛑 HARD RULE #1: COMPONENT MOCKING REQUIREMENT
   If a component is imported and used, it MUST be either:
   1. Explicitly mocked at the top of the file with jest.mock(), OR
   2. The test will be REJECTED
   
   ❌ FORBIDDEN: Using real child components in component-level tests
   ✅ REQUIRED: Mock ALL child components, hooks, and side-effects

🛑 HARD RULE #2: JEST.MOCK() PLACEMENT (CRITICAL - AUTOMATIC REJECTION IF VIOLATED):
   ✅ ALL jest.mock() calls MUST be at the TOP of the file, BEFORE any imports
   ❌ NEVER declare jest.mock() inside test cases, beforeEach blocks, or after imports
   ❌ NEVER use jest.mock() conditionally or inside functions
   
   MANDATORY STRUCTURE:
   ```typescript
   // Line 1: First jest.mock() call
   jest.mock('...')
   // ... all other jest.mock() calls
   // THEN imports
   import { ... }
   ```
   
   ```typescript
   // ✅ CORRECT - At top of file
   jest.mock('next-intl', () => ({
     useTranslations: () => (key: string) => key,
   }))
   
   jest.mock('@components/wishlist/useWishlist', () => ({
     useWishlist: jest.fn(),
   }))
   
   jest.mock('./wishlist-product-card', () => ({
     WishlistProductCard: jest.fn(({ item, onRemove }) => (
       <div data-testid="mock-product-card">
         <button onClick={() => onRemove(item.sku)}>Remove</button>
       </div>
     )),
   }))
   
   import { render, screen } from '@testing-library/react'
   // ... rest of imports
   
   // ❌ WRONG - Inside test case
   it('should test something', () => {
     jest.mock('@components/wishlist/useWishlist', ...)  // ❌ FORBIDDEN
   })
   ```

🛑 HARD RULE #3: HOOK MOCKING PATTERN (CRITICAL - AUTOMATIC REJECTION IF VIOLATED):
   ✅ REQUIRED: Use controllable mock pattern with jest.fn()
   ✅ REQUIRED: Mock hook at top, control per test with mockReturnValue
   ❌ FORBIDDEN: Using jest.mocked(require(...)) pattern
   ❌ FORBIDDEN: Inline hook mocks that cannot be controlled
   
   MANDATORY PATTERN:
   ```typescript
   // At top of file (before imports)
   const mockUseWishlist = jest.fn()
   jest.mock('@components/wishlist/useWishlist', () => ({
     useWishlist: () => mockUseWishlist(),
   }))
   
   // In beforeEach - set default
   beforeEach(() => {
     mockUseWishlist.mockReturnValue({
       updating: [],
       handleRemoveFromWishlist: jest.fn(),
     })
   })
   
   // In each test - override as needed
   it('should handle loading state', () => {
     mockUseWishlist.mockReturnValue({
       updating: ['SKU1'],
       handleRemoveFromWishlist: jest.fn(),
     })
     // ... test code
   })
   ```

🛑 HARD RULE #4: CHILD COMPONENT MOCKING (CRITICAL - AUTOMATIC REJECTION IF VIOLATED):
   ✅ REQUIRED: Mock ALL child components imported from relative paths (./ or ../)
   ✅ REQUIRED: Mock ALL UI components from @components
   ❌ FORBIDDEN: Using real child components - creates coupling and brittleness
   ❌ FORBIDDEN: Testing child component internals
   
   MANDATORY: For every component import, add jest.mock() at top:
   - If import is: import { ChildComponent } from './child-component'
   - Then MUST have: jest.mock('./child-component', () => ({ ... }))
   
   ```typescript
   // Mock child components at top
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
     ClearWishlist: jest.fn(({ listName }) => (
       <button data-testid="clear-wishlist-button">Clear</button>
     )),
   }))
   
   jest.mock('./wishlist-empty', () => ({
     WishlistEmpty: jest.fn(() => (
       <div data-testid="wishlist-empty">
         <h1>Empty List</h1>
       </div>
     )),
   }))
   
   jest.mock('@components/ui/loading-spinner', () => ({
     LoadingSpinner: jest.fn(() => <div data-testid="loading-spinner">Loading...</div>),
   }))
   ```

4. **ANALYTICS MOCKING (CRITICAL)**:
   ✅ Mock analytics side-effects to prevent real calls
   
   ```typescript
   jest.mock('@lib/analytics/gtm-triggers', () => ({
     sendGTMEvent: jest.fn(),
   }))
   ```

🛑 HARD RULE #5: TRANSLATION ASSERTIONS (CRITICAL - AUTOMATIC REJECTION IF VIOLATED):
   ❌ ABSOLUTELY FORBIDDEN: Asserting translation string internals
   ❌ FORBIDDEN: getByText('(wishlist.itemsCount)')
   ❌ FORBIDDEN: getByText('wishlist.itemsCount')
   ❌ FORBIDDEN: Any pattern matching translation key format with parentheses
   
   ✅ REQUIRED: Use semantic/partial text with regex
   ✅ REQUIRED: Match visible text, not translation keys
   
   ```typescript
   // ❌ FORBIDDEN - Will cause REJECTION
   expect(screen.getByText('(wishlist.itemsCount)')).toBeInTheDocument()
   expect(screen.getByText('wishlist.itemsCount')).toBeInTheDocument()
   
   // ✅ REQUIRED - Use regex for semantic matching
   expect(screen.getByText(/items/i)).toBeInTheDocument()
   expect(screen.getByText(/\d+.*items?/i)).toBeInTheDocument()
   expect(screen.getByText(/wishlist/i)).toBeInTheDocument()
   ```

6. **ARIA ROLES (CRITICAL)**:
   ❌ DO NOT assume ARIA roles unless explicitly defined in mocked components
   ✅ Use data-testid for mocked components
   ✅ Use getByText/getByTestId instead of getByRole for mocked elements
   
   ```typescript
   // ❌ BAD - Assumes progressbar role
   expect(screen.getByRole('progressbar')).toBeInTheDocument()
   
   // ✅ GOOD - Use testid from mocked component
   expect(screen.getByTestId('loading-spinner')).toBeInTheDocument()
   ```

🛑 HARD RULE #6: CLEANUP (REQUIRED - AUTOMATIC REJECTION IF MISSING):
   ✅ REQUIRED: Must have afterEach block
   ✅ REQUIRED: Must have beforeEach block for mock reset
   ❌ FORBIDDEN: Missing cleanup blocks
   
   MANDATORY STRUCTURE:
   ```typescript
   describe('Component', () => {
     beforeEach(() => {
       jest.clearAllMocks()
       // Reset default mock return values
       mockUseWishlist.mockReturnValue({ ... })
     })
     
     afterEach(() => {
       jest.clearAllMocks()
     })
     
     // ... tests
   })
   ```

8. **TEST ISOLATION**:
   ✅ Each test should control mock behavior independently
   ✅ Reset mocks in beforeEach if needed
   
   ```typescript
   beforeEach(() => {
     jest.clearAllMocks()
     // Reset default mock return values
     mockUseWishlist.mockReturnValue({
       updating: [],
       handleRemoveFromWishlist: jest.fn(),
     })
   })
   ```

⚠️ VIOLATION HANDLING:
If your generated test violates ANY of these HARD RULES, it will be:
1. Flagged as CRITICAL VIOLATION
2. Automatically REJECTED (score < 70)
3. Sent back for repair
4. Re-validated before acceptance

These are NON-NEGOTIABLE rules for component-level tests.
"""
        elif test_level == 'integration':
            return """
- Test how components interact with each other
- Use real implementations where possible, mock only external services
- Verify data flow between components
- Test state management and side effects
- Include setup/teardown for shared state
"""
        else:  # feature
            return """
- Test complete user workflows and scenarios
- Use real component implementations with proper providers
- Verify end-to-end functionality from user perspective
- Include realistic user interactions (clicks, form inputs, navigation)
- Test multiple related components working together
- Mock only external APIs and services

📚 REFERENCE QUALITY TEST (MATCH THIS EXACTLY)

This is a PERFECT example from the project. Your test should match this quality:

```typescript
import { screen, waitFor } from '@testing-library/react'
import { userEvent } from '@testing-library/user-event'
import { AddToCart } from '../add-to-cart/index'
import { SelectSize } from '../select-size'
import { createMockProduct, mockPdpProduct, getMockCart, resetMockCart } from '@mocks/factories'
import { mockAppRouter } from 'jest/mocks/mockNavigation'
import { pdpUserActions } from '@test-utils/user-actions'
import { pdpWrapper, renderWeb } from '@test-utils/render'
import { cleanupApolloClient } from '@test-utils/apollo'

type RenderAddToCartOptions = {
  product?: ReturnType<typeof createMockProduct>
  selectSizeProps?: React.ComponentProps<typeof SelectSize>
  addToCartProps?: React.ComponentProps<typeof AddToCart>
}

describe('PDP AddToCart Feature', () => {
  let pdpActions: ReturnType<typeof pdpUserActions>
  let mockProduct: ReturnType<typeof createMockProduct>

  const renderAddToCartPdp = ({
    product = mockProduct,
    selectSizeProps = {},
    addToCartProps = {},
  }: RenderAddToCartOptions = {}) =>
    renderWeb(
      <>
        <SelectSize {...selectSizeProps} />
        <AddToCart {...addToCartProps} />
      </>,
      { wrapper: pdpWrapper(product) },
    )

  beforeEach(() => {
    pdpActions = pdpUserActions(userEvent.setup())
    resetMockCart()
    mockProduct = mockPdpProduct()
  })

  afterEach(async () => {
    await cleanupApolloClient()
    jest.clearAllMocks()
  })

  it('disables Add to Cart button WHILE add to cart request is in progress', async () => {
    renderAddToCartPdp()

    await pdpActions.selectSize('UK 8')
    await pdpActions.addToCart()

    const addButton = await screen.findByTestId('add-to-cart-button')

    expect(addButton).toBeDisabled()
    await waitFor(() => expect(addButton).toBeEnabled())
  })

  it('navigates to cart page WHEN an item is added successfully', async () => {
    renderAddToCartPdp()

    await pdpActions.selectSize('UK 8')
    await pdpActions.addToCart()

    await waitFor(() => expect(mockAppRouter.push).toHaveBeenCalledWith('/cart'))
  })
})
```

**Why this is PERFECT (100/100):**
✅ Import order: RTL → userEvent → Components → Factories → UserActions → Render → Cleanup
✅ Type annotations: ReturnType<typeof factory>, React.ComponentProps<typeof Component>
✅ Custom render function with options: renderAddToCartPdp
✅ beforeEach: Initializes pdpActions + mockProduct
✅ afterEach: async with await cleanupApolloClient()
✅ Test names: "outcome WHILE condition" and "outcome WHEN action"
✅ Uses pdpActions methods: selectSize(), addToCart()
✅ Renders prerequisites: SelectSize + AddToCart together
✅ User-visible assertions: toBeDisabled(), toHaveBeenCalledWith('/cart')
✅ Proper async handling: await, waitFor

MATCH THIS QUALITY EXACTLY!

🎯 EXACT PDP FEATURE TEST TEMPLATE (MANDATORY - USE THIS STRUCTURE)

Based on analysis of 15 high-quality reference tests, ALL PDP feature tests MUST follow this EXACT structure:

```typescript
import { screen, waitFor } from '@testing-library/react'
import { userEvent } from '@testing-library/user-event'
import { ComponentName } from '../component-path/index'
import { SelectSize } from '../select-size'
import { createMockProduct, mockPdpProduct } from '@mocks/factories'
import { pdpUserActions } from '@test-utils/user-actions'
import { pdpWrapper, renderWeb } from '@test-utils/render'
import { cleanupApolloClient } from '@test-utils/apollo'

describe('PDP ComponentName Feature', () => {
  let pdpActions: ReturnType<typeof pdpUserActions>
  let mockProduct: ReturnType<typeof createMockProduct>

  const renderComponentNamePdp = (product = mockProduct) =>
    renderWeb(
      <>
        <SelectSize />
        <ComponentName />
      </>,
      { wrapper: pdpWrapper(product) },
    )

  beforeEach(() => {
    pdpActions = pdpUserActions(userEvent.setup())
    mockProduct = mockPdpProduct()
  })

  afterEach(async () => {
    await cleanupApolloClient()
    jest.clearAllMocks()
  })

  it('describes outcome WHEN user performs action', async () => {
    renderComponentNamePdp()

    await pdpActions.selectSize('UK 8')
    await pdpActions.addToCart()

    await waitFor(() => {
      expect(mockAppRouter.push).toHaveBeenCalledWith('/cart')
    })
  })
})
```

🛑 TEMPLATE REQUIREMENTS (ALL MANDATORY):

1. **IMPORT ORDER (STRICT):**
   - Line 1: React Testing Library (@testing-library/react)
   - Line 2: userEvent (@testing-library/user-event)
   - Line 3-4: Component imports (test target + prerequisites)
   - Line 5: Factory imports (@mocks/factories)
   - Line 6: User actions (@test-utils/user-actions)
   - Line 7: Render utilities (@test-utils/render)
   - Line 8: Cleanup (@test-utils/apollo)

2. **TYPE ANNOTATIONS (MANDATORY):**
   - MUST use: `let pdpActions: ReturnType<typeof pdpUserActions>`
   - MUST use: `let mockProduct: ReturnType<typeof createMockProduct>`
   - For options: `React.ComponentProps<typeof Component>`

3. **CUSTOM RENDER FUNCTION (MANDATORY):**
   - MUST create: `const render[ComponentName]Pdp = (product = mockProduct) => ...`
   - MUST use Fragment: `<><SelectSize /><ComponentName /></>`
   - MUST render prerequisites BEFORE main component

4. **SETUP BOILERPLATE (MANDATORY):**
   - beforeEach MUST initialize: `pdpActions = pdpUserActions(userEvent.setup())`
   - beforeEach MUST initialize: `mockProduct = mockPdpProduct()`
   - afterEach MUST call: `await cleanupApolloClient()` (async!)
   - afterEach MUST call: `jest.clearAllMocks()`

5. **TEST NAMING (MANDATORY):**
   - Format: "outcome WHEN/WHILE/AFTER action"
   - Examples:
     ✅ "disables Add to Cart button WHILE request is in progress"
     ✅ "navigates to cart page WHEN item is added successfully"
     ✅ "shows modal when button clicked without selecting size"
   - ALWAYS lowercase (except proper nouns)
   - ALWAYS describe user-visible behavior
   - NEVER mention implementation (callbacks, props, state)

6. **USER ACTIONS (MANDATORY):**
   - MUST use: `await pdpActions.selectSize('UK 8')`
   - MUST use: `await pdpActions.addToCart()`
   - MUST use: `await pdpActions.addToWishList()`
   - MUST use: `await pdpActions.selectColour('Black')`
   - NEVER use: `await user.click(...)` directly
   - NEVER use: `await userEvent.click(...)` directly

7. **PREREQUISITE COMPONENTS (MANDATORY):**
   - AddToCart → MUST render SelectSize
   - Price → MUST render SelectSize
   - Wishlist → MUST render SelectSize
   - Any size-dependent component → MUST render SelectSize
   - Render prerequisites BEFORE main component in JSX

8. **WAITFOR USAGE (CONDITIONAL):**
   - USE for: async state changes, navigation, cart updates
   - DON'T USE for: elements already in DOM after render
   - Examples:
     ✅ `await waitFor(() => expect(button).toBeEnabled())`
     ✅ `await waitFor(() => expect(router.push).toHaveBeenCalled())`
     ❌ `expect(screen.getByRole('button')).toBeInTheDocument()` (no waitFor)

9. **FACTORY USAGE (MANDATORY):**
   - ALWAYS use: `mockPdpProduct()`, `createMockProduct()`
   - For complex data, create preset objects OUTSIDE tests
   - NEVER create inline product/variant objects
   - Example:
     ```typescript
     const variantPresets = {
       uk8_sale: { sku: 'SKU-UK8', size: 'UK 8', price: {...} }
     }
     mockProduct = mockPdpProduct([variantPresets.uk8_sale])
     ```

10. **CHILD COMPONENT MOCKING (CONDITIONAL):**
    - Mock ONLY components NOT part of feature
    - NEVER mock components that ARE part of feature
    - Example of ALLOWED mocking:
      ```typescript
      jest.mock('@components/partner-program/disclaimer', () => ({
        PartnerProgramDisclaimer: ({ model, name }) => (
          <div data-test-id='partner-program-disclaimer'>
            Partner Program: {name} ({model})
          </div>
        )
      }))
      ```

🚨 CRITICAL FEATURE TEST RULES (VIOLATIONS = AUTOMATIC REJECTION)

These rules enforce the fundamental difference between feature tests and unit tests.
Feature tests test from OUTSIDE the component, like a real user.

🛑 HARD RULE #1: NEVER MOCK PRIMARY FEATURE LOGIC (CRITICAL)
   ❌ ABSOLUTELY FORBIDDEN: Mocking the feature you're testing
   
   **Bad Example - Testing AddToCart:**
   ```typescript
   // ❌ FORBIDDEN - Mocks the thing being tested!
   jest.mock('@components/product-details-page/add-to-cart/useAddToCart', () => ({
     useAddToCart: jest.fn(() => ({ ... }))
   }))
   
   describe('AddToCart Feature', () => {
     // This tests NOTHING - the logic is mocked!
   })
   ```
   
   **Good Example - Testing AddToCart:**
   ```typescript
   // ✅ REQUIRED - Use REAL feature hook
   // NO jest.mock() for useAddToCart!
   
   import { AddToCart } from './add-to-cart'
   import { pdpWrapper, renderWeb } from '@test-utils/render'
   import { mockPdpProduct } from '@mocks/factories'
   
   describe('AddToCart Feature', () => {
     const mockProduct = mockPdpProduct()
     
     it('should add to cart when size is selected', async () => {
       const wrapper = pdpWrapper(mockProduct)
       renderWeb(<><SelectSize /><AddToCart /></>, { wrapper })
       
       // Real useAddToCart hook runs here!
       await pdpActions.selectSize('UK 8')
       await pdpActions.addToCart()
       
       expect(mockAppRouter.push).toHaveBeenCalledWith('/cart')
     })
   })
   ```
   
   **Rule:** If testing AddToCart → useAddToCart MUST be real
   **Rule:** If testing Wishlist → useWishlist MUST be real
   **Rule:** If testing Checkout → useCheckout MUST be real

🛑 HARD RULE #2: NEVER CREATE CUSTOM CONTEXT (CRITICAL)
   ❌ ABSOLUTELY FORBIDDEN: Manual context creation
   
   **Bad Example:**
   ```typescript
   // ❌ FORBIDDEN - Creating custom context wrapper
   const wrapper = ({ children }) => (
     <ProductDetailsPageProvider 
       product={mockProduct}
       initialState={{ currentSku: 'SKU-123', showModal: true }}
     >
       {children}
     </ProductDetailsPageProvider>
   )
   
   render(<AddToCart />, { wrapper })
   ```
   
   **Good Example:**
   ```typescript
   // ✅ REQUIRED - Use real test utilities
   const wrapper = pdpWrapper(mockProduct)
   renderWeb(<AddToCart />, { wrapper })
   ```
   
   **Rule:** ALWAYS use project test utilities (pdpWrapper, renderWeb)
   **Rule:** NEVER create <Context.Provider> manually

🛑 HARD RULE #3: NEVER INJECT STATE DIRECTLY (CRITICAL)
   ❌ ABSOLUTELY FORBIDDEN: Setting state without user action
   
   **Bad Example:**
   ```typescript
   // ❌ FORBIDDEN - Injecting state
   <ProductDetailsPageProvider initialState={{ currentSku: 'SKU-123' }}>
     <AddToCart />
   </ProductDetailsPageProvider>
   
   // This is a unit test pattern, NOT feature test!
   ```
   
   **Good Example:**
   ```typescript
   // ✅ REQUIRED - Satisfy prerequisites through REAL UI
   renderWeb(
     <>
       <SelectSize />
       <AddToCart />
     </>,
     { wrapper: pdpWrapper(mockProduct) }
   )
   
   // Prerequisites satisfied through USER ACTIONS
   await pdpActions.selectSize('UK 8')  // User selects size
   await pdpActions.addToCart()         // User adds to cart
   
   expect(screen.getByText(/success/i)).toBeVisible()
   ```
   
   **Rule:** State changes ONLY through user actions
   **Rule:** No initialState, no contextValue, no state injection

🛑 HARD RULE #4: RENDER COMPLETE FEATURES (CRITICAL)
   ✅ REQUIRED: Render ALL components user sees together
   
   **Bad Example - AddToCart alone:**
   ```typescript
   // ❌ FORBIDDEN - Incomplete feature
   renderWeb(<AddToCart />)
   // How does user select size? They can't!
   ```
   
   **Good Example - Complete feature:**
   ```typescript
   // ✅ REQUIRED - Complete feature
   renderWeb(
     <>
       <SelectSize />  {/* User needs this to select size */}
       <AddToCart />   {/* Then can add to cart */}
     </>,
     { wrapper: pdpWrapper(mockProduct) }
   )
   ```
   
   **Rule:** If AddToCart depends on size selection → Render SelectSize too
   **Rule:** Test the COMPLETE user journey, not isolated components

🛑 HARD RULE #5: USE USER ACTION HELPERS (REQUIRED)
   ✅ REQUIRED: Use project-specific user action utilities
   
   **Bad Example:**
   ```typescript
   // ❌ DISCOURAGED - Raw userEvent
   const user = userEvent.setup()
   await user.click(screen.getByRole('button', { name: /uk 8/i }))
   await user.click(screen.getByRole('button', { name: /add to cart/i }))
   ```
   
   **Good Example:**
   ```typescript
   // ✅ REQUIRED - Project user action helpers
   const pdpActions = pdpUserActions(userEvent.setup())
   await pdpActions.selectSize('UK 8')
   await pdpActions.addToCart()
   ```
   
   **Rule:** Use pdpActions, appActions, etc. when available
   **Rule:** Encapsulates common workflows, more maintainable

🛑 HARD RULE #6: ASSERT USER-VISIBLE BEHAVIOR ONLY (CRITICAL)
   ✅ REQUIRED: Test what user SEES/EXPERIENCES
   ❌ FORBIDDEN: Test implementation details
   
   **Bad Example:**
   ```typescript
   // ❌ FORBIDDEN - Asserting callback calls
   expect(errorCapture).toHaveBeenCalledWith(true)
   expect(onToggle).toHaveBeenCalledWith('SELECT_VARIANT_MODAL', false)
   expect(onAddToCart).toHaveBeenCalled()
   ```
   
   **Good Example:**
   ```typescript
   // ✅ REQUIRED - User-visible outcomes
   expect(screen.getByText(/error/i)).toBeVisible()           // User sees error
   expect(screen.queryByTestId('modal')).not.toBeInTheDocument()  // Modal closed
   expect(mockAppRouter.push).toHaveBeenCalledWith('/cart')  // Navigated to cart
   ```
   
   **Rule:** Assert modal visibility, error messages, navigation
   **Rule:** NOT callback calls, context setters, hook internals

🛑 HARD RULE #7: USE FACTORIES AND CLEANUP (REQUIRED)
   ✅ REQUIRED: Factory functions for test data
   ✅ REQUIRED: Proper cleanup in afterEach
   
   ```typescript
   import { mockPdpProduct, resetMockCart } from '@mocks/factories'
   import { cleanupApolloClient } from '@test-utils/apollo'
   
   describe('AddToCart Feature', () => {
     let mockProduct
     
     beforeEach(() => {
       mockProduct = mockPdpProduct()
       resetMockCart()
     })
     
     afterEach(async () => {
       await cleanupApolloClient()
       jest.clearAllMocks()
     })
     
     // ... tests
   })
   ```

📋 FEATURE TEST CHECKLIST (ALL MUST BE TRUE):

Before submitting, verify:
- [ ] Primary feature hook is REAL (not mocked)
- [ ] Using project wrappers (pdpWrapper, renderWeb)
- [ ] NO state injection (currentSku, initialState, etc.)
- [ ] Complete feature rendered (SelectSize + AddToCart together)
- [ ] User actions used (pdpActions.selectSize, pdpActions.addToCart)
- [ ] Only user-visible behavior asserted (no callback assertions)
- [ ] Factories used (mockPdpProduct, not inline objects)
- [ ] Cleanup in afterEach (cleanupApolloClient, clearAllMocks)

IF ANY CHECKBOX IS UNCHECKED → TEST WILL BE REJECTED

---

🚨 STRICT QUALITY RULES (MANDATORY - TEST WILL BE REJECTED IF VIOLATED):

1. **SEMANTIC QUERIES (CRITICAL)**:
   ✅ ALWAYS PREFER: screen.getByRole('button', { name: /text/i })
   ✅ ACCEPTABLE: screen.getByText(/visible text/i)
   ⚠️ ONLY FOR NON-INTERACTIVE CONTAINERS: screen.getByTestId('feature-container')
   ❌ FORBIDDEN: screen.getByTestId('submit-button') // Use getByRole instead!
   ❌ FORBIDDEN: screen.getByTestId('login-link')   // Use getByRole instead!
   
   Example violations that will be REJECTED:
   - getByTestId for buttons → Must use getByRole('button')
   - getByTestId for links → Must use getByRole('link')
   - getByTestId for inputs → Must use getByRole('textbox')
   
2. **ROOT CONTAINER ASSERTION (CRITICAL)**:
   ✅ REQUIRED: Assert the root feature container FIRST
   
   ```typescript
   it('should display feature', () => {
     renderFeature()
     
     // MUST be first assertion
     expect(screen.getByTestId('partner-program-container')).toBeInTheDocument()
     
     // Then check feature content
     expect(screen.getByRole('heading', { name: /benefits/i })).toBeInTheDocument()
   })
   ```
   
3. **ARRANGE-ACT-ASSERT STRUCTURE (CRITICAL)**:
   ✅ REQUIRED: Every test MUST follow AAA pattern
   
   ```typescript
   it('should submit form when valid', async () => {
     // Arrange: Setup test data and render
     const mockData = createMockUser({ email: 'test@example.com' })
     const user = userEvent.setup()
     renderFeature(<Form data={mockData} />)
     
     // Act: Perform user action
     const submitButton = screen.getByRole('button', { name: /submit/i })
     await user.click(submitButton)
     
     // Assert: Verify outcome
     expect(screen.getByText(/success/i)).toBeInTheDocument()
   })
   ```
   
4. **FACTORY DATA CLEANLINESS (CRITICAL)**:
   ❌ BAD: Including fields component doesn't use
   ```typescript
   const product = createMockProduct({
     __typename: 'Product',  // ❌ Remove - setup field
     id: '123',
     sku: 'ABC',
     name: 'Test Product',
     price: 99.99,
     category: 'Test',       // ❌ Remove if component doesn't use
     brand: 'Test Brand',    // ❌ Remove if component doesn't use
     // ... 15 more unused fields
   })
   ```
   
   ✅ GOOD: Only fields component uses
   ```typescript
   const product = createMockProduct({
     id: '123',
     name: 'Test Product',
     price: 99.99
   })
   ```
   
5. **USER INTERACTION (CRITICAL)**:
   ✅ ALWAYS use userEvent:
   ```typescript
   const user = userEvent.setup()
   await user.click(button)
   await user.type(input, 'test')
   ```
   
   ❌ NEVER use fireEvent:
   ```typescript
   fireEvent.click(button)  // ❌ REJECTED - not realistic
   ```

6. **I18N MOCKING (CRITICAL)**:
   ✅ IF component uses useTranslations, useTranslate, or i18n:
   
   ```typescript
   // MUST mock at top of file
   jest.mock('next-intl', () => ({
     useTranslations: () => (key: string) => key
   }))
   
   // Then use translation KEYS in assertions
   expect(screen.getByText('pdp.labelSelectSize')).toBeInTheDocument()  // ✅ Key
   expect(screen.getByText(/Select Size/i)).toBeInTheDocument()  // ❌ English text
   ```
   
   ❌ FORBIDDEN: Asserting English text when component uses i18n
   ❌ FORBIDDEN: Not mocking i18n library when component uses it
   
7. **CHILD COMPONENT BOUNDARIES (CRITICAL)**:
   ✅ DO: Assert user-visible behavior from child components
   ❌ DON'T: Assert child component internal test-ids
   
   ```typescript
   // ❌ BAD - Asserts child internal
   expect(screen.getByTestId('product-variants-menu')).toBeInTheDocument()
   
   // ✅ GOOD - Asserts child's visible behavior
   expect(screen.getByRole('button', { name: /UK 8/i })).toBeInTheDocument()
   ```
   
   Child components can refactor their internals.
   Feature tests must only care about user-visible outputs.
   
8. **IMPLEMENTATION DETAILS (MEDIUM)**:
   ✅ DO: Test THAT something happens
   ❌ DON'T: Test HOW it happens
   
   ```typescript
   // ❌ BAD - Tests exact parameters
   expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'nearest' })
   
   // ✅ GOOD - Tests that it happened
   expect(scrollIntoView).toHaveBeenCalled()
   ```

⛔ ABSOLUTE PROHIBITIONS (V3 - CRITICAL - WILL CRASH OR BREAK):

9. **NO REACT HOOKS IN TESTS (CRITICAL)**:
   Feature tests are NOT components. They test components from the outside.
   
   ❌ ABSOLUTELY FORBIDDEN:
   ```typescript
   const wrapper = ({ children }) => {
     const [state, setState] = React.useState(...)  // ❌ WILL CRASH!
     const value = React.useContext(...)            // ❌ WRONG!
     return ...
   }
   ```
   
   ✅ CORRECT:
   ```typescript
   const wrapper = pdpWrapper(mockProduct)  // ✅ Use real wrapper
   renderWeb(<Component />, { wrapper })
   ```
   
   NEVER use: useState, useContext, useEffect, useReducer, useMemo, useCallback

10. **NO CUSTOM CONTEXT CREATION (CRITICAL)**:
    Feature tests MUST use real wrappers, NOT recreate context.
    
    ❌ ABSOLUTELY FORBIDDEN:
    ```typescript
    const contextValue = {
      state: { showSelectVariantError: true },  // ❌ Manual state injection
      product: mockProduct
    }
    return <ProductDetailsPageContext.Provider value={contextValue}>  // ❌ Context hacking
    ```
    
    ✅ CORRECT:
    ```typescript
    const wrapper = pdpWrapper(mockProduct)  // ✅ Real wrapper with real context
    renderWeb(<SelectSize />, { wrapper })
    
    // Trigger behavior through USER ACTIONS:
    await user.click(addToCartButton)  // ✅ User triggers error state
    ```
    
    NEVER manually create: context values, providers, state

11. **TEST NAME MUST MATCH ASSERTIONS (CRITICAL)**:
    If test name mentions behavior, assertions MUST verify that behavior.
    
    ❌ ABSOLUTELY FORBIDDEN:
    ```typescript
    it('should display error message when...', () => {
      expect(screen.getByTestId('select-size')).toBeInTheDocument()  // ❌ Not testing error!
    })
    ```
    
    ✅ CORRECT:
    ```typescript
    it('should display error message when...', async () => {
      await user.click(addToCartButton)  // Trigger error
      expect(screen.getByText('pdp.labelPleaseSelectSize')).toBeVisible()  // ✅ Test error!
    })
    ```

12. **TRIGGER BEHAVIOR VIA USER ACTIONS (CRITICAL)**:
    Feature tests trigger state changes through user actions, NOT state injection.
    
    ❌ ABSOLUTELY FORBIDDEN:
    ```typescript
    const [showError, setShowError] = useState(true)  // ❌ State injection
    ```
    
    ✅ CORRECT:
    ```typescript
    await user.click(addToCartButton)  // ✅ User action triggers error
    await waitFor(() => {
      expect(screen.getByText('error')).toBeVisible()
    })
    ```

13. **STANDARD WRAPPER USAGE ONLY (HIGH)**:
    Use wrappers through render options, NOT inline JSX composition.
    
    ❌ FORBIDDEN:
    ```typescript
    renderWeb(pdpWrapper(mockProduct)({ children: <Component /> }))
    ```
    
    ✅ CORRECT - ONLY PATTERN ALLOWED:
    ```typescript
    const wrapper = pdpWrapper(mockProduct)
    renderWeb(<Component />, { wrapper })
    ```

⚠️ VIOLATIONS = AUTOMATIC REJECTION:
If your generated test violates ANY of these rules, it will be flagged, sent back for repair, and re-validated. Generate clean, high-quality tests on the first attempt.
"""
    
    def _build_pytest_prompt(
        self, 
        strategy: TestStrategy, 
        source_content: str, 
        patterns: str,
        infrastructure_context: str,
        coverage_context: str = ""
    ) -> str:
        """Build pytest test generation prompt"""
        
        prompt = f"""You are an expert at writing comprehensive pytest tests for Python applications.

## SOURCE FILE TO TEST
File: {strategy.source_file}

```python
{source_content}
```

{coverage_context}

## TESTING INFRASTRUCTURE DETECTED
{infrastructure_context}

## TESTING PATTERNS AND EXAMPLES
{patterns}

## YOUR TASK
Generate a comprehensive test file for the Python source code above.

### Requirements:
1. Create tests using pytest
2. Follow the testing patterns shown above
3. Test file should be saved as: {strategy.test_file}
4. Include proper imports from the source file
5. Use pytest fixtures for setup/teardown
6. Use the detected testing infrastructure (conftest, fixtures, etc.)
7. Add descriptive test function names (test_*)
8. Include edge cases and error scenarios
9. Use appropriate pytest assertions and markers
10. Mock external dependencies using pytest-mock or unittest.mock

### Output Format:
- Provide ONLY the test code
- Do not include explanations or markdown
- Start with imports
- Include all necessary test functions
- End with a complete, runnable test file

Generate the test file now:
"""
        return prompt
    
    def _extract_code_from_response(self, response: str) -> Optional[str]:
        """
        Extract test code from Gemini response with robust handling of various formats
        
        Args:
            response: Raw response from Gemini
            
        Returns:
            Extracted code or None if extraction fails
        """
        try:
            if not response:
                return None
            
            # Remove common markdown formatting
            response = response.strip()
            
            # Method 1: Try to extract from code blocks (most common case)
            # Match ```language or just ```
            code_block_pattern = r'```(?:typescript|javascript|tsx|jsx|python|ts|js)?\n(.*?)\n```'
            matches = re.findall(code_block_pattern, response, re.DOTALL)
            
            if matches:
                # Use the longest match (most likely to be complete)
                code = max(matches, key=len)
                if code and len(code) > 50:
                    logger.debug("Extracted code from markdown code block")
                    return code
            
            # Method 2: Look for code without markdown fences
            # Check if response starts with typical code patterns
            if response.startswith(('import ', 'from ', 'const ', 'describe(', 'test(', 'it(', 'def ')):
                # Remove any trailing markdown or explanations
                # Find the last line that looks like code
                lines = response.split('\n')
                code_end = len(lines)
                
                # Work backwards to find last line of code
                for i in range(len(lines) - 1, -1, -1):
                    line = lines[i].strip()
                    # If we hit markdown or explanation text, stop
                    if line.startswith('#') and not line.startswith('# ') and not line.startswith('##'):
                        continue  # This is a comment, not markdown
                    if line.startswith('```'):
                        code_end = i
                        break
                    # If line looks like code, this might be the end
                    if line.endswith((';', '}', ')', ']', ',')) or line.startswith(('import ', 'export ', 'const ', 'let ', 'var ', 'function ', 'class ')):
                        break
                
                code = '\n'.join(lines[:code_end])
                if code and len(code) > 50:
                    logger.debug("Extracted code without markdown fences")
                    return code
            
            # Method 3: Try to find code between common delimiters
            # Sometimes LLM adds explanatory text before/after
            import_start = response.find('import ')
            if import_start == -1:
                import_start = response.find('from ')
            if import_start == -1:
                import_start = response.find('describe(')
            if import_start == -1:
                import_start = response.find('def test_')
            
            if import_start != -1:
                # Find the end - look for common ending patterns
                # For JS/TS: closing brace and semicolon, or just closing brace
                # For Python: last test function
                code = response[import_start:]
                
                # Remove any trailing explanations or markdown
                if '```' in code:
                    # If there's a closing fence, cut there
                    fence_end = code.find('```')
                    if fence_end > 0:
                        code = code[:fence_end]
                
                # Check for common ending patterns
                # Look for the last substantial closing brace
                lines = code.split('\n')
                last_code_line = len(lines)
                
                for i in range(len(lines) - 1, -1, -1):
                    line = lines[i].strip()
                    if not line or line.startswith('//') or line.startswith('#'):
                        continue
                    # If we find a closing brace/paren at root level, likely end of file
                    if line in ('});', '}', '};'):
                        last_code_line = i + 1
                        break
                    # For Python, if we see a blank line after test functions, stop there
                    if 'def test_' in '\n'.join(lines[:i]) and not line:
                        last_code_line = i
                        break
                
                code = '\n'.join(lines[:last_code_line])
                
                # Final cleanup - remove any remaining markdown
                if code.startswith('```'):
                    code = '\n'.join(code.split('\n')[1:])
                if code.endswith('```'):
                    code = code.split('```')[0]
                if code and len(code) > 50:
                    logger.debug("Extracted code by finding import/test patterns")
                    return code
            
            # Method 4: If response looks like code (has imports and test functions), return as-is
            has_imports = bool(re.search(r'(import|from\s+.*\s+import)', response, re.IGNORECASE))
            has_tests = bool(re.search(r'(describe|test\(|it\(|def\s+test_)', response, re.IGNORECASE))
            if has_imports and has_tests:
                # Clean up any leading/trailing text
                lines = response.split('\n')
                code_start = 0
                code_end = len(lines)
                
                # Find first import/test statement
                for i, line in enumerate(lines):
                    if re.search(r'(import|from\s+.*\s+import|describe|def\s+test_)', line, re.IGNORECASE):
                        code_start = i
                        break
                
                # Find last meaningful line (not empty, not just closing brace)
                # Look for complete test blocks by checking for balanced braces
                for i in range(len(lines) - 1, code_start, -1):
                    line = lines[i].strip()
                    # Stop at a line that looks like a complete closing (ending with } or });)
                    if line and (line.endswith('});') or (line.endswith('}') and i < len(lines) - 1)):
                        # Check if this looks like a complete file ending
                        # Count braces to see if we're at the root level
                        code_so_far = '\n'.join(lines[code_start:i+1])
                        open_braces = code_so_far.count('{')
                        close_braces = code_so_far.count('}')
                        # If braces are balanced or close to balanced, this might be the end
                        if abs(open_braces - close_braces) <= 2:  # Allow some imbalance for incomplete extraction
                            code_end = i + 1
                            break
                
                code = '\n'.join(lines[code_start:code_end]).strip()
                
                # Check for incomplete strings (unterminated quotes)
                if code:
                    # Count quotes - if odd, might be incomplete
                    single_quotes = code.count("'") - code.count("\\'")
                    double_quotes = code.count('"') - code.count('\\"')
                    # If quotes are very unbalanced, might be incomplete
                    if abs(single_quotes % 2) == 1 or abs(double_quotes % 2) == 1:
                        logger.warning("Extracted code may have incomplete strings - checking for unterminated quotes")
                        # Try to find the last complete line
                        code_lines = code.split('\n')
                        for i in range(len(code_lines) - 1, -1, -1):
                            line = code_lines[i]
                            # If line has an unterminated string, remove it and everything after
                            if ("'" in line and line.count("'") - line.count("\\'") == 1) or \
                               ('"' in line and line.count('"') - line.count('\\"') == 1):
                                if i > 0:  # Don't remove everything
                                    code = '\n'.join(code_lines[:i]).strip()
                                    logger.warning(f"Removed incomplete line {i+1} from extracted code")
                                    break
                
                if code and len(code) > 50:
                    logger.debug("Extracted code by detecting code structure")
                    return code
            
            # Fallback: return response as-is if it's substantial
            if len(response) > 100:
                logger.warning("Could not extract code cleanly, returning response as-is")
                return response
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting code: {e}")
            # Fallback to original response
            return response if len(response) > 50 else None
    
    def _is_code_complete(self, code: str) -> bool:
        """
        Check if extracted code appears to be complete (not truncated)
        
        Args:
            code: Extracted code string
            
        Returns:
            bool: True if code appears complete, False if it might be truncated
        """
        if not code or len(code) < 50:
            return False
        
        # Check for balanced braces (rough check)
        open_braces = code.count('{')
        close_braces = code.count('}')
        open_parens = code.count('(')
        close_parens = code.count(')')
        open_brackets = code.count('[')
        close_brackets = code.count(']')
        
        # Allow some imbalance (e.g., if code ends mid-statement)
        # But if it's very unbalanced, it's likely incomplete
        brace_diff = abs(open_braces - close_braces)
        paren_diff = abs(open_parens - close_parens)
        bracket_diff = abs(open_brackets - close_brackets)
        
        # If braces are very unbalanced (> 5 difference), likely incomplete
        if brace_diff > 5:
            logger.warning(f"Code appears incomplete: {open_braces} open braces, {close_braces} close braces")
            return False
        
        # Check for incomplete statements at the end
        last_lines = code.strip().split('\n')[-3:]  # Last 3 lines
        for line in reversed(last_lines):
            stripped = line.strip()
            if not stripped:
                continue
            # If last non-empty line ends with certain patterns, might be incomplete
            if stripped.endswith(('await', 'expect(', 'fireEvent.', 'screen.', 'render(')):
                logger.warning("Code appears to end mid-statement")
                return False
            # If it ends with a closing brace/paren, likely complete
            if stripped.endswith(('});', '});', '}', ')')):
                return True
        
        # If we have reasonable balance and ends properly, assume complete
        return True
    
    def _validate_test_file(self, test_content: str, framework: str) -> Optional[str]:
        """
        Validate that the test file is syntactically complete
        Returns warning message if validation issues found, None if valid
        NOTE: This is non-blocking - tests will still be saved and executed
        """
        try:
            # Only check for obvious issues - don't be too strict
            # The test runner will catch actual syntax errors
            
            if framework == 'jest':
                # Check for at least one import and one test (basic sanity check)
                if 'import' not in test_content and 'require' not in test_content:
                    return "Test file missing import statements"
                if 'test(' not in test_content and 'it(' not in test_content and 'describe(' not in test_content:
                    return "Test file missing test cases"
            
            elif framework == 'pytest':
                # Check for at least one import and one test function
                if 'import' not in test_content and 'from' not in test_content:
                    return "Test file missing import statements"
                if 'def test_' not in test_content:
                    return "Test file missing test functions"
            
            return None  # Validation passed
            
        except Exception as e:
            logger.warning(f"Error validating test file: {e}")
            return None  # Don't fail on validation errors, just log
    
    def _count_tests(self, test_content: str, framework: str) -> int:
        """Count number of tests in generated content"""
        try:
            if framework == 'jest':
                # Count 'test(' and 'it(' occurrences
                count = test_content.count('test(') + test_content.count('it(')
            elif framework == 'pytest':
                # Count 'def test_' occurrences
                count = test_content.count('def test_')
            else:
                count = 0
            
            return count
        except Exception:
            return 0