"""
Context Parser and Contract Extractor
Parses uploaded context files to extract component contracts
Merges with project-level rules for complete utility detection
"""

import re
import ast
from typing import Dict, List, Optional, Set, TYPE_CHECKING
from dataclasses import dataclass
from pathlib import Path

if TYPE_CHECKING:
    from tools.testing_rules import ProjectTestingRules


@dataclass
class PropContract:
    """Contract for a component prop"""
    name: str
    type: str
    required: bool
    default_value: Optional[str] = None


@dataclass
class TestUtility:
    """Contract for a test utility function"""
    name: str
    type: str  # 'wrapper', 'render', 'user_actions', 'factory', 'cleanup', 'utility'
    import_path: str
    description: str


@dataclass
class ComponentContract:
    """Contract extracted from a component file"""
    name: str
    file_path: str
    props: List[PropContract]
    test_ids: List[str]
    aria_roles: List[str]
    translation_keys: List[str]
    exports: List[str]
    hooks_used: List[str]
    child_components: List[str]


@dataclass
class HookContract:
    """Contract for a custom hook"""
    name: str
    file_path: str
    return_type: Dict[str, str]
    parameters: List[PropContract]


@dataclass
class ContextContracts:
    """All contracts extracted from context files"""
    components: Dict[str, ComponentContract]
    hooks: Dict[str, HookContract]
    test_utilities: Dict[str, TestUtility]  # NEW: Test utilities
    target_file: str
    

class ContextParser:
    """
    Parses React/TypeScript files to extract component contracts
    Merges with project-level testing rules for complete utility detection
    """
    
    def __init__(self, project_rules: Optional['ProjectTestingRules'] = None):
        """
        Initialize parser
        
        Args:
            project_rules: Optional project-level testing rules for utility detection
        """
        self.project_rules = project_rules
        self.test_id_pattern = r'data-test-id=[\'"]([^\'"]+)[\'"]'
        self.aria_role_pattern = r'role=[\'"]([^\'"]+)[\'"]'
        self.translation_pattern = r't\([\'"]([^\'"]+)[\'"]'
        self.export_pattern = r'export\s+(?:const|function|class|type|interface)\s+(\w+)'
        self.hook_pattern = r'use[A-Z]\w+'
        self.component_ref_pattern = r'<([A-Z][A-Za-z0-9]+)'
        
    def parse_context_files(
        self, 
        context_files: Dict[str, str],
        target_file: str
    ) -> ContextContracts:
        """
        Parse all context files and extract contracts
        
        Args:
            context_files: Dict of {file_path: file_content}
            target_file: Path to the target component being tested
            
        Returns:
            ContextContracts with all extracted contracts
        """
        components = {}
        hooks = {}
        test_utilities = {}
        
        for file_path, content in context_files.items():
            if self._is_test_file(file_path):
                # Extract test utilities from test files
                utilities = self._extract_test_utilities(file_path, content)
                test_utilities.update(utilities)
            elif self._is_hook_file(file_path):
                hook_contract = self._parse_hook(file_path, content)
                if hook_contract:
                    hooks[hook_contract.name] = hook_contract
            elif self._is_component_file(file_path):
                component_contract = self._parse_component(file_path, content)
                if component_contract:
                    components[component_contract.name] = component_contract
        
        # Merge utilities from project rules (filesystem scan)
        if self.project_rules:
            utilities_from_project = self._merge_project_utilities(self.project_rules)
            # Uploaded utilities override project utilities (more specific)
            test_utilities = {**utilities_from_project, **test_utilities}
        
        return ContextContracts(
            components=components,
            hooks=hooks,
            test_utilities=test_utilities,
            target_file=target_file
        )
    
    def _is_hook_file(self, file_path: str) -> bool:
        """Check if file is a custom hook"""
        return 'use' in file_path.lower() and (file_path.endswith('.ts') or file_path.endswith('.tsx'))
    
    def _is_component_file(self, file_path: str) -> bool:
        """Check if file is a component"""
        return file_path.endswith('.tsx') or file_path.endswith('.jsx')
    
    def _is_test_file(self, file_path: str) -> bool:
        """Check if file is a test file"""
        return '.test.' in file_path or '.spec.' in file_path or '/test-utils/' in file_path or '/@test-utils/' in file_path or '/mocks/' in file_path or '/@mocks/' in file_path
    
    def _extract_test_utilities(self, file_path: str, content: str) -> Dict[str, TestUtility]:
        """
        Extract test utility functions from test files or test utility files
        
        Returns:
            Dict of utility_name -> TestUtility
        """
        utilities = {}
        
        # Patterns to find utility exports
        patterns = [
            # export const pdpWrapper = ...
            (r'export\s+const\s+((?:pdp|app|render|mock|cleanup|create)\w+)\s*=', 'export_const'),
            # export function renderWeb(...) 
            (r'export\s+function\s+((?:pdp|app|render|mock|cleanup|create)\w+)', 'export_function'),
            # export { pdpWrapper, renderWeb } from '@test-utils/render'
            (r'export\s+\{\s*([^}]+)\s*\}\s+from\s+[\'"](@test-utils|@mocks)[^\'"]+[\'"]', 'export_from'),
        ]
        
        for pattern, pattern_type in patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                if pattern_type == 'export_from':
                    # Multiple utilities in one export
                    utilities_str = match.group(1)
                    import_path = match.group(2)
                    util_names = [u.strip() for u in utilities_str.split(',')]
                    for util_name in util_names:
                        util_type = self._infer_utility_type(util_name)
                        utilities[util_name] = TestUtility(
                            name=util_name,
                            type=util_type,
                            import_path=import_path,
                            description=self._get_utility_description(util_name, util_type)
                        )
                else:
                    # Single utility
                    util_name = match.group(1)
                    util_type = self._infer_utility_type(util_name)
                    utilities[util_name] = TestUtility(
                        name=util_name,
                        type=util_type,
                        import_path=self._extract_import_path(file_path),
                        description=self._get_utility_description(util_name, util_type)
                    )
        
        return utilities
    
    def _infer_utility_type(self, name: str) -> str:
        """Infer what type of utility this is based on naming"""
        name_lower = name.lower()
        
        if 'wrapper' in name_lower:
            return 'wrapper'
        elif 'render' in name_lower:
            return 'render'
        elif 'actions' in name_lower or ('user' in name_lower and 'actions' in name_lower):
            return 'user_actions'
        elif 'mock' in name_lower or 'create' in name_lower or 'factory' in name_lower:
            return 'factory'
        elif 'cleanup' in name_lower:
            return 'cleanup'
        else:
            return 'utility'
    
    def _get_utility_description(self, name: str, util_type: str) -> str:
        """Get description of what this utility does"""
        descriptions = {
            'wrapper': f'Component wrapper - use {name}(mockData) instead of custom context',
            'render': f'Render utility - use {name}(<Component />, {{ wrapper }}) instead of plain render()',
            'user_actions': f'User action helpers - use {name}() instead of raw user.click()',
            'factory': f'Factory function - use {name}() to create test data',
            'cleanup': f'Cleanup utility - call {name}() in afterEach block',
            'utility': f'Test utility function - {name}'
        }
        return descriptions.get(util_type, f'Utility: {name}')
    
    def _extract_import_path(self, file_path: str) -> str:
        """Extract import path from file path"""
        if '@test-utils' in file_path or '/test-utils/' in file_path:
            return '@test-utils'
        elif '@mocks' in file_path or '/mocks/' in file_path:
            return '@mocks'
        else:
            return file_path
    
    def _merge_project_utilities(self, project_rules: 'ProjectTestingRules') -> Dict[str, TestUtility]:
        """
        Convert project rules into TestUtility objects
        Merges wrappers, factories, and handlers from filesystem scan
        
        Args:
            project_rules: Project testing rules from filesystem scan
            
        Returns:
            Dict of utility_name -> TestUtility
        """
        utilities = {}
        
        # Add detected wrappers
        for wrapper_name in project_rules.detected_wrappers:
            util_type = self._infer_utility_type(wrapper_name)
            utilities[wrapper_name] = TestUtility(
                name=wrapper_name,
                type=util_type,
                import_path='@test-utils',
                description=self._get_utility_description(wrapper_name, util_type)
            )
        
        # Add detected factories
        for factory_name in project_rules.detected_factories:
            util_type = self._infer_utility_type(factory_name)
            utilities[factory_name] = TestUtility(
                name=factory_name,
                type=util_type,
                import_path='@mocks/factories',
                description=self._get_utility_description(factory_name, util_type)
            )
        
        # Add detected MSW handlers
        for handler_name in project_rules.detected_msw_handlers:
            utilities[handler_name] = TestUtility(
                name=handler_name,
                type='utility',
                import_path='@mocks/handlers',
                description=f'MSW handler - use {handler_name} for API mocking'
            )
        
        return utilities
    
    def _parse_component(self, file_path: str, content: str) -> Optional[ComponentContract]:
        """
        Parse a component file and extract contract
        
        Returns:
            ComponentContract with extracted information
        """
        # Extract component name from file
        component_name = self._extract_component_name(file_path, content)
        if not component_name:
            return None
        
        # Extract all contract elements
        props = self._extract_props(content)
        test_ids = self._extract_test_ids(content)
        aria_roles = self._extract_aria_roles(content)
        translation_keys = self._extract_translation_keys(content)
        exports = self._extract_exports(content)
        hooks_used = self._extract_hooks_used(content)
        child_components = self._extract_child_components(content)
        
        return ComponentContract(
            name=component_name,
            file_path=file_path,
            props=props,
            test_ids=test_ids,
            aria_roles=aria_roles,
            translation_keys=translation_keys,
            exports=exports,
            hooks_used=hooks_used,
            child_components=child_components
        )
    
    def _parse_hook(self, file_path: str, content: str) -> Optional[HookContract]:
        """
        Parse a hook file and extract contract
        
        Returns:
            HookContract with extracted information
        """
        hook_name = self._extract_hook_name(file_path, content)
        if not hook_name:
            return None
        
        return_type = self._extract_hook_return_type(content)
        parameters = self._extract_hook_parameters(content)
        
        return HookContract(
            name=hook_name,
            file_path=file_path,
            return_type=return_type,
            parameters=parameters
        )
    
    def _extract_component_name(self, file_path: str, content: str) -> Optional[str]:
        """Extract component name from export or filename"""
        # Try export default function ComponentName
        match = re.search(r'export\s+default\s+function\s+(\w+)', content)
        if match:
            return match.group(1)
        
        # Try export function ComponentName
        match = re.search(r'export\s+function\s+([A-Z]\w+)', content)
        if match:
            return match.group(1)
        
        # Try export const ComponentName
        match = re.search(r'export\s+(?:const|let)\s+([A-Z]\w+)', content)
        if match:
            return match.group(1)
        
        # Fallback to filename
        return Path(file_path).stem.replace('-', '_')
    
    def _extract_props(self, content: str) -> List[PropContract]:
        """
        Extract prop types from TypeScript interface or type
        
        Example:
            type Props = {
              name: string
              age?: number
            }
        """
        props = []
        
        # Find type/interface definitions
        type_patterns = [
            r'type\s+\w+Props\s*=\s*\{([^}]+)\}',
            r'interface\s+\w+Props\s*\{([^}]+)\}',
        ]
        
        for pattern in type_patterns:
            matches = re.finditer(pattern, content, re.DOTALL)
            for match in matches:
                props_block = match.group(1)
                props.extend(self._parse_props_block(props_block))
        
        return props
    
    def _parse_props_block(self, props_block: str) -> List[PropContract]:
        """Parse individual props from a props block"""
        props = []
        
        # Match: propName?: propType
        # or: propName: propType
        prop_pattern = r'(\w+)(\?)?:\s*([^\n]+)'
        
        for match in re.finditer(prop_pattern, props_block):
            prop_name = match.group(1)
            optional = match.group(2) == '?'
            prop_type = match.group(3).strip().rstrip(',')
            
            props.append(PropContract(
                name=prop_name,
                type=prop_type,
                required=not optional
            ))
        
        return props
    
    def _extract_test_ids(self, content: str) -> List[str]:
        """Extract all data-test-id values"""
        return list(set(re.findall(self.test_id_pattern, content)))
    
    def _extract_aria_roles(self, content: str) -> List[str]:
        """Extract all ARIA role values"""
        return list(set(re.findall(self.aria_role_pattern, content)))
    
    def _extract_translation_keys(self, content: str) -> List[str]:
        """Extract all translation keys t('key')"""
        return list(set(re.findall(self.translation_pattern, content)))
    
    def _extract_exports(self, content: str) -> List[str]:
        """Extract all exported names"""
        return list(set(re.findall(self.export_pattern, content)))
    
    def _extract_hooks_used(self, content: str) -> List[str]:
        """Extract all React hooks used (useEffect, useState, custom hooks)"""
        hooks = set()
        
        # Built-in hooks
        builtin_hooks = ['useState', 'useEffect', 'useContext', 'useReducer', 'useCallback', 'useMemo', 'useRef']
        for hook in builtin_hooks:
            if hook in content:
                hooks.add(hook)
        
        # Custom hooks (use[A-Z]...)
        custom_hooks = re.findall(self.hook_pattern, content)
        hooks.update(custom_hooks)
        
        return list(hooks)
    
    def _extract_child_components(self, content: str) -> List[str]:
        """Extract all child component references"""
        return list(set(re.findall(self.component_ref_pattern, content)))
    
    def _extract_hook_name(self, file_path: str, content: str) -> Optional[str]:
        """Extract hook name from export"""
        # Try export function useHookName
        match = re.search(r'export\s+function\s+(use[A-Z]\w+)', content)
        if match:
            return match.group(1)
        
        # Fallback to filename
        filename = Path(file_path).stem
        if filename.startswith('use'):
            return filename
        
        return None
    
    def _extract_hook_return_type(self, content: str) -> Dict[str, str]:
        """
        Extract hook return type
        
        Example:
            type UseWishlist = {
              updating: string[]
              handleRemoveFromWishlist: (sku: string) => void
            }
        """
        return_type = {}
        
        # Find type definition
        type_pattern = r'type\s+Use\w+\s*=\s*\{([^}]+)\}'
        match = re.search(type_pattern, content, re.DOTALL)
        
        if match:
            type_block = match.group(1)
            # Parse each field
            field_pattern = r'(\w+):\s*([^\n]+)'
            for field_match in re.finditer(field_pattern, type_block):
                field_name = field_match.group(1)
                field_type = field_match.group(2).strip().rstrip(',')
                return_type[field_name] = field_type
        
        return return_type
    
    def _extract_hook_parameters(self, content: str) -> List[PropContract]:
        """Extract hook parameters"""
        # Find parameter type
        param_pattern = r'type\s+Use\w+Props\s*=\s*\{([^}]+)\}'
        match = re.search(param_pattern, content, re.DOTALL)
        
        if match:
            return self._parse_props_block(match.group(1))
        
        return []


class ContextContractValidator:
    """
    Validates generated tests against extracted context contracts
    """
    
    def validate_mock_against_contract(
        self,
        mock_code: str,
        component_name: str,
        contract: ComponentContract
    ) -> List[str]:
        """
        Validate that a mock matches the real component contract
        
        Returns:
            List of validation errors
        """
        errors = []
        
        # Check if mock uses correct props
        for prop in contract.props:
            if prop.required and prop.name not in mock_code:
                errors.append(
                    f"Mock for {component_name} missing required prop: {prop.name}"
                )
        
        # Check if mock uses real test-ids
        mock_test_ids = re.findall(r'data-testid=[\'"]([^\'"]+)[\'"]', mock_code)
        for test_id in mock_test_ids:
            if test_id.startswith('mock-') or test_id not in contract.test_ids:
                errors.append(
                    f"Mock for {component_name} uses fabricated test-id '{test_id}'. "
                    f"Real test-ids: {contract.test_ids}"
                )
        
        return errors
    
    def validate_test_assertions(
        self,
        test_code: str,
        contracts: ContextContracts
    ) -> List[str]:
        """
        Validate that test assertions use real test-ids from contracts
        
        Returns:
            List of validation errors
        """
        errors = []
        
        # Extract all test-id queries from test
        test_id_queries = re.findall(
            r'getByTestId\([\'"]([^\'"]+)[\'"]', 
            test_code
        )
        
        # Get all valid test-ids from all contracts
        valid_test_ids = set()
        for contract in contracts.components.values():
            valid_test_ids.update(contract.test_ids)
        
        # Check each query
        for query_id in test_id_queries:
            if query_id.startswith('mock-'):
                continue  # Skip mocked component test-ids
            
            if query_id not in valid_test_ids:
                errors.append(
                    f"Test queries test-id '{query_id}' which doesn't exist in any context file. "
                    f"Valid test-ids: {sorted(valid_test_ids)}"
                )
        
        return errors


def create_context_aware_prompt_section(contracts: ContextContracts) -> str:
    """
    Create prompt section with extracted context contracts
    
    This forces the LLM to use actual contracts instead of guessing
    """
    sections = []
    
    sections.append("## 📋 CONTEXT CONTRACTS (USE THESE - DON'T GUESS)")
    sections.append("")
    sections.append("The following contracts were extracted from uploaded context files.")
    sections.append("You MUST use these exact contracts when mocking or testing.")
    sections.append("")
    
    # Components
    if contracts.components:
        sections.append("### Component Contracts:")
        for name, contract in contracts.components.items():
            sections.append(f"\n**{name}** ({contract.file_path}):")
            
            if contract.props:
                sections.append(f"  Props:")
                for prop in contract.props:
                    required = "required" if prop.required else "optional"
                    sections.append(f"    - {prop.name}: {prop.type} ({required})")
            
            if contract.test_ids:
                sections.append(f"  Test IDs: {', '.join(contract.test_ids)}")
            
            if contract.aria_roles:
                sections.append(f"  ARIA Roles: {', '.join(contract.aria_roles)}")
            
            if contract.translation_keys:
                sections.append(f"  Translation Keys: {', '.join(sorted(contract.translation_keys)[:10])}")
            
            if contract.child_components:
                sections.append(f"  Child Components: {', '.join(contract.child_components)}")
    
    # Hooks
    if contracts.hooks:
        sections.append("\n### Hook Contracts:")
        for name, contract in contracts.hooks.items():
            sections.append(f"\n**{name}** ({contract.file_path}):")
            
            if contract.parameters:
                sections.append(f"  Parameters:")
                for param in contract.parameters:
                    required = "required" if param.required else "optional"
                    sections.append(f"    - {param.name}: {param.type} ({required})")
            
            if contract.return_type:
                sections.append(f"  Returns:")
                for field, field_type in contract.return_type.items():
                    sections.append(f"    - {field}: {field_type}")
    
    # Test Utilities (CRITICAL for feature tests)
    if contracts.test_utilities:
        sections.append("\n### 🧪 Test Utilities Available:")
        sections.append("**CRITICAL:** These utility functions are available in the project.")
        sections.append("**YOU MUST USE THESE instead of creating custom mocks or wrappers!**")
        sections.append("")
        
        for util_name, utility in contracts.test_utilities.items():
            sections.append(f"**{util_name}** ({utility.type}):")
            sections.append(f"  - Import: `{utility.import_path}`")
            sections.append(f"  - Purpose: {utility.description}")
            
            # Add specific usage examples
            if utility.type == 'wrapper':
                sections.append(f"  - Usage: `const wrapper = {util_name}(mockProduct); renderWeb(<Component />, {{ wrapper }})`")
            elif utility.type == 'render':
                sections.append(f"  - Usage: `{util_name}(<Component />, {{ wrapper: pdpWrapper(mockData) }})`")
            elif utility.type == 'user_actions':
                sections.append(f"  - Usage: `const actions = {util_name}(userEvent.setup()); await actions.selectSize('UK 8')`")
            elif utility.type == 'factory':
                sections.append(f"  - Usage: `const mockData = {util_name}()`")
            elif utility.type == 'cleanup':
                sections.append(f"  - Usage: `afterEach(async () => {{ await {util_name}() }})`")
            sections.append("")
    
    sections.append("\n## 🛑 HARD RULES:")
    sections.append("1. MUST use exact test-ids from contracts above")
    sections.append("2. MUST use exact prop types from contracts")
    sections.append("3. MUST NOT fabricate test-ids with 'mock-' prefix")
    sections.append("4. MUST match hook return types exactly")
    sections.append("5. IF contract is missing → ASK USER, don't guess")
    if contracts.test_utilities:
        sections.append("6. MUST use test utilities listed above instead of custom mocks/wrappers")
    
    return "\n".join(sections)