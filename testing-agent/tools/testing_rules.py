"""
Testing Rules - Project-Aware Rule Extraction
Extracts enforceable rules from project's existing tests and infrastructure
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass

from config.testing_patterns import detect_test_infrastructure, get_mock_factory_names, get_test_utils_exports

logger = logging.getLogger(__name__)


@dataclass
class ProjectTestingRules:
    """
    Extracted testing rules specific to a project
    These are NOT hardcoded - they're derived from the project itself
    """
    # Infrastructure-based rules
    detected_wrappers: List[str]  # From test-utils
    detected_factories: List[str]  # From mocks/factories
    detected_msw_handlers: List[str]  # From mocks/handlers
    
    # Pattern-based rules (from existing tests)
    import_patterns: Set[str]  # Common import statements
    wrapper_patterns: Set[str]  # How wrappers are used
    selector_patterns: Set[str]  # getByRole, getByTestId, etc.
    
    # Structure rules (universal)
    require_describe: bool = True
    require_test_or_it: bool = True
    forbid_top_level_logic: bool = True
    
    # Test level specific rules
    feature_test_rules: Dict[str, Any] = None
    integration_test_rules: Dict[str, Any] = None
    unit_test_rules: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.feature_test_rules is None:
            self.feature_test_rules = {}
        if self.integration_test_rules is None:
            self.integration_test_rules = {}
        if self.unit_test_rules is None:
            self.unit_test_rules = {}


class TestingRulesExtractor:
    """
    Extracts testing rules from a project
    Makes rules project-aware, not hardcoded
    """
    
    def __init__(self, project_root: Path):
        """
        Initialize rules extractor
        
        Args:
            project_root: Root directory of project
        """
        self.project_root = project_root
    
    def extract_rules(self, existing_tests: Optional[Dict[str, str]] = None) -> ProjectTestingRules:
        """
        Extract all testing rules from project
        
        Args:
            existing_tests: Optional dict of existing test files {path: content}
            
        Returns:
            ProjectTestingRules: Extracted rules
        """
        logger.info(f"Extracting testing rules from: {self.project_root}")
        
        # Detect infrastructure
        infrastructure = detect_test_infrastructure(self.project_root)
        
        # Extract from infrastructure
        detected_wrappers = get_test_utils_exports(self.project_root) or []
        detected_factories = get_mock_factory_names(self.project_root) or []
        detected_msw_handlers = infrastructure.msw_handlers or []
        
        # Extract patterns from existing tests
        import_patterns = set()
        wrapper_patterns = set()
        selector_patterns = set()
        
        if existing_tests:
            for test_content in existing_tests.values():
                import_patterns.update(self._extract_imports(test_content))
                wrapper_patterns.update(self._extract_wrapper_usage(test_content))
                selector_patterns.update(self._extract_selectors(test_content))
        
        # Build level-specific rules
        feature_rules = self._build_feature_rules(detected_wrappers, detected_factories)
        integration_rules = self._build_integration_rules(detected_msw_handlers)
        unit_rules = self._build_unit_rules()
        
        rules = ProjectTestingRules(
            detected_wrappers=detected_wrappers,
            detected_factories=detected_factories,
            detected_msw_handlers=detected_msw_handlers,
            import_patterns=import_patterns,
            wrapper_patterns=wrapper_patterns,
            selector_patterns=selector_patterns,
            feature_test_rules=feature_rules,
            integration_test_rules=integration_rules,
            unit_test_rules=unit_rules
        )
        
        logger.info(f"Extracted rules: {len(detected_wrappers)} wrappers, {len(detected_factories)} factories")
        return rules
    
    def _extract_imports(self, test_content: str) -> Set[str]:
        """Extract common import patterns from test"""
        imports = set()
        
        # Find import statements
        import_pattern = r"import\s+.*?from\s+['\"]([^'\"]+)['\"]"
        matches = re.findall(import_pattern, test_content, re.MULTILINE)
        
        # Filter to test-related imports
        for match in matches:
            if any(keyword in match for keyword in ['test', 'mock', 'factory', '@testing-library']):
                imports.add(match)
        
        return imports
    
    def _extract_wrapper_usage(self, test_content: str) -> Set[str]:
        """Extract how wrappers/render functions are used"""
        wrappers = set()
        
        # Look for render calls
        render_pattern = r'(render\w*|.*Wrapper)\s*\('
        matches = re.findall(render_pattern, test_content)
        wrappers.update(matches)
        
        return wrappers
    
    def _extract_selectors(self, test_content: str) -> Set[str]:
        """Extract selector patterns (getBy*, queryBy*, etc.)"""
        selectors = set()
        
        # Find all screen.getBy* calls
        selector_pattern = r'screen\.(getBy\w+|queryBy\w+|findBy\w+)'
        matches = re.findall(selector_pattern, test_content)
        selectors.update(matches)
        
        return selectors
    
    def _build_feature_rules(self, wrappers: List[str], factories: List[str]) -> Dict[str, Any]:
        """Build feature test specific rules"""
        return {
            "require_user_event": True,
            "require_wrapper": True,
            "available_wrappers": wrappers,
            "available_factories": factories,
            "forbid_jest_mock": True,
            "forbid_shallow_render": True,
            "prefer_semantic_queries": True,
            "require_cleanup": True
        }
    
    def _build_integration_rules(self, msw_handlers: List[str]) -> Dict[str, Any]:
        """Build integration test specific rules"""
        return {
            "use_msw_if_available": len(msw_handlers) > 0,
            "available_handlers": msw_handlers,
            "allow_partial_mocks": True,
            "require_api_mocking": True
        }
    
    def _build_unit_rules(self) -> Dict[str, Any]:
        """Build unit test specific rules"""
        return {
            "allow_jest_mock": True,
            "allow_shallow_render": True,
            "focus_on_isolation": True
        }
    
    def format_rules_for_prompt(self, rules: ProjectTestingRules, test_level: str) -> str:
        """
        Format rules as strict constraints for LLM prompt
        
        Args:
            rules: Extracted project rules
            test_level: 'unit', 'integration', or 'feature'
            
        Returns:
            str: Formatted rules section for prompt
        """
        lines = []
        lines.append("═══════════════════════════════════════════════════════════════════════")
        lines.append("ENFORCED TESTING RULES (MANDATORY - VIOLATIONS WILL BE REJECTED)")
        lines.append("═══════════════════════════════════════════════════════════════════════")
        lines.append("")
        
        # Universal structure rules
        lines.append("🔒 UNIVERSAL STRUCTURE RULES:")
        lines.append("❌ INVALID: Missing describe() block")
        lines.append("❌ INVALID: Missing test() or it() blocks")
        lines.append("❌ INVALID: Logic outside test blocks")
        lines.append("✅ VALID: Proper describe/test structure with cleanup")
        lines.append("")
        
        # Infrastructure-based rules
        if rules.detected_wrappers:
            lines.append("🔒 DETECTED TEST UTILITIES (MUST USE THESE):")
            for wrapper in rules.detected_wrappers[:10]:
                lines.append(f"✅ Use: {wrapper}()")
            lines.append("❌ INVALID: Inventing new render utilities")
            lines.append("")
        
        if rules.detected_factories:
            lines.append("🔒 DETECTED MOCK FACTORIES (MUST USE THESE):")
            for factory in rules.detected_factories[:10]:
                lines.append(f"✅ Use: {factory}()")
            lines.append("❌ INVALID: Creating inline mock data instead of using factories")
            lines.append("")
        
        # Test level specific rules
        if test_level == 'feature':
            lines.append("🔒 FEATURE TEST RULES (NON-NEGOTIABLE):")
            lines.append("✅ MUST: Use userEvent for interactions (not fireEvent)")
            lines.append("✅ MUST: Use real wrappers from test utilities")
            if rules.detected_wrappers:
                lines.append(f"✅ MUST: Use one of: {', '.join(rules.detected_wrappers[:3])}")
            lines.append("✅ MUST: Test user-visible behavior, not implementation")
            lines.append("✅ MUST: Use semantic queries (getByRole preferred)")
            lines.append("❌ INVALID: jest.mock() on application code")
            lines.append("❌ INVALID: Shallow rendering (render(<Component />))")
            lines.append("❌ INVALID: Testing CSS classes or internal state")
            lines.append("❌ INVALID: Hardcoded text strings (use regex: /text/i)")
            
        elif test_level == 'integration':
            lines.append("🔒 INTEGRATION TEST RULES:")
            lines.append("✅ MUST: Use MSW for API mocking (if available)")
            if rules.detected_msw_handlers:
                lines.append(f"✅ Available handlers: {', '.join(rules.detected_msw_handlers[:3])}")
            lines.append("✅ MUST: Test component interactions")
            lines.append("✅ ALLOWED: Partial mocking of dependencies")
            
        elif test_level == 'unit':
            lines.append("🔒 UNIT TEST RULES:")
            lines.append("✅ ALLOWED: jest.mock() for dependencies")
            lines.append("✅ ALLOWED: Isolated component rendering")
            lines.append("✅ FOCUS: Edge cases and error handling")
        
        lines.append("")
        lines.append("🔒 SELECTOR RULES:")
        lines.append("✅ PREFER: screen.getByRole('button', { name: /text/i })")
        lines.append("✅ ACCEPTABLE: screen.getByTestId('component-id')")
        lines.append("❌ INVALID: document.querySelector()")
        lines.append("❌ INVALID: Exact text matching without regex")
        lines.append("")
        
        lines.append("⚠️ VIOLATION HANDLING:")
        lines.append("If your generated test violates ANY of these rules, it will be:")
        lines.append("1. Flagged as INVALID")
        lines.append("2. Sent back for repair")
        lines.append("3. Re-validated before acceptance")
        lines.append("")
        lines.append("═══════════════════════════════════════════════════════════════════════")
        
        return "\n".join(lines)


def extract_project_rules(
    project_root: Path,
    existing_tests: Optional[Dict[str, str]] = None
) -> ProjectTestingRules:
    """
    Convenience function to extract project testing rules
    
    Args:
        project_root: Root directory of project
        existing_tests: Optional existing test files
        
    Returns:
        ProjectTestingRules: Extracted rules
    """
    extractor = TestingRulesExtractor(project_root)
    return extractor.extract_rules(existing_tests)
