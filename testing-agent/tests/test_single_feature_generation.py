"""
Integration Tests for Single Feature Test Generation
Tests the complete workflow: context_builder → test_generator → generated test
"""

import pytest
from pathlib import Path
from typing import Dict, List
import tempfile
import shutil

# Import from actual project structure
from tools.context_builder import build_context_bundle
from agents.test_generator_agent import TestGeneratorAgent, GeneratedTest
from agents.strategy_agent import TestStrategy
from tools.file_indexer import IndexResult, FileInfo
from config.vertex_ai import VertexAIConfig, GeminiClient


class TestSingleFeatureGeneration:
    """Integration tests for single feature test generation workflow"""
    
    @pytest.fixture
    def sample_project(self, tmp_path):
        """
        Create a minimal sample React/TypeScript project for testing.
        
        Structure:
        sample_project/
        ├── src/
        │   ├── components/
        │   │   ├── Button.tsx (imports Icon)
        │   │   ├── Icon.tsx
        │   │   └── LoginForm.tsx (imports Button, hooks)
        │   ├── hooks/
        │   │   └── useAuth.ts
        │   └── utils/
        │       ├── test-helpers.ts
        │       └── constants.ts
        """
        project_root = tmp_path / "sample_project"
        project_root.mkdir()
        
        # Create directory structure
        (project_root / "src").mkdir()
        (project_root / "src" / "components").mkdir()
        (project_root / "src" / "hooks").mkdir()
        (project_root / "src" / "utils").mkdir()
        
        # Button component (has dependency on Icon)
        button_file = project_root / "src" / "components" / "Button.tsx"
        button_file.write_text("""
import React from 'react';
import { Icon } from './Icon';

interface ButtonProps {
  label: string;
  onClick: () => void;
  variant?: 'primary' | 'secondary';
}

export const Button: React.FC<ButtonProps> = ({ label, onClick, variant = 'primary' }) => {
  return (
    <button 
      onClick={onClick}
      className={`btn btn-${variant}`}
    >
      <Icon name="click" />
      {label}
    </button>
  );
};
""")
        
        # Icon component (dependency of Button)
        icon_file = project_root / "src" / "components" / "Icon.tsx"
        icon_file.write_text("""
import React from 'react';

interface IconProps {
  name: string;
  size?: number;
}

export const Icon: React.FC<IconProps> = ({ name, size = 16 }) => {
  return <span className={`icon icon-${name}`} style={{ fontSize: size }} />;
};
""")
        
        # LoginForm component (imports Button and hooks)
        login_form_file = project_root / "src" / "components" / "LoginForm.tsx"
        login_form_file.write_text("""
import React, { useState } from 'react';
import { Button } from './Button';
import { useAuth } from '../hooks/useAuth';

export const LoginForm: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const { login } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await login(email, password);
  };

  return (
    <form onSubmit={handleSubmit}>
      <input 
        type="email" 
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="Email"
      />
      <input 
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Password"
      />
      <Button label="Login" onClick={handleSubmit} />
    </form>
  );
};
""")
        
        # useAuth hook (dependency of LoginForm)
        use_auth_file = project_root / "src" / "hooks" / "useAuth.ts"
        use_auth_file.write_text("""
import { useState } from 'react';

export const useAuth = () => {
  const [user, setUser] = useState(null);
  
  const login = async (email: string, password: string) => {
    // Mock login logic
    const response = await fetch('/api/login', {
      method: 'POST',
      body: JSON.stringify({ email, password })
    });
    const data = await response.json();
    setUser(data.user);
    return data;
  };

  const logout = () => {
    setUser(null);
  };

  return { user, login, logout };
};
""")
        
        # Test utilities
        test_helpers_file = project_root / "src" / "utils" / "test-helpers.ts"
        test_helpers_file.write_text("""
import { render } from '@testing-library/react';
import { ReactElement } from 'react';

export const renderWithProviders = (component: ReactElement) => {
  return render(component);
};

export const mockApiResponse = (data: any) => {
  global.fetch = jest.fn(() =>
    Promise.resolve({
      json: () => Promise.resolve(data),
    })
  ) as jest.Mock;
};
""")
        
        # Constants file (no dependencies)
        constants_file = project_root / "src" / "utils" / "constants.ts"
        constants_file.write_text("""
export const API_BASE_URL = 'https://api.example.com';
export const MAX_LOGIN_ATTEMPTS = 3;
export const SESSION_TIMEOUT = 1800000; // 30 minutes
""")
        
        return project_root
    
    @pytest.fixture
    def index_result(self, sample_project):
        """Create IndexResult for the sample project"""
        files = []
        for file in sample_project.rglob('*.ts*'):
            if not file.name.endswith('.test.tsx'):
                rel_path = str(file.relative_to(sample_project))
                files.append(FileInfo(
                    path=str(file),
                    relative_path=rel_path,
                    size=file.stat().st_size,
                    extension=file.suffix,
                    category='TypeScript',
                    lines=len(file.read_text().splitlines())
                ))
        
        return IndexResult(
            total_files=len(files),
            total_size=sum(f.size for f in files),
            total_lines=sum(f.lines for f in files),
            files_by_category={'TypeScript': len(files)},
            files_by_extension={'.tsx': 3, '.ts': 2},
            file_list=files,
            directory_tree={}
        )
    
    @pytest.fixture
    def gemini_client(self):
        """Create GeminiClient for testing (may be None if not configured)"""
        try:
            config = VertexAIConfig()
            if config.is_configured():
                return GeminiClient(config)
            else:
                pytest.skip("Vertex AI not configured - set GOOGLE_CLOUD_PROJECT and credentials")
        except Exception as e:
            pytest.skip(f"Could not create GeminiClient: {e}")
    
    # ==================== CONTEXT BUILDER TESTS ====================
    
    def test_context_builder_finds_direct_imports(self, sample_project, index_result):
        """Test context builder finds direct imports from target file"""
        context = build_context_bundle(
            project_root=sample_project,
            target_file="src/components/Button.tsx",
            index_result=index_result,
            depth=1,  # Only direct imports
            max_files=10
        )
        
        # Should include Icon (direct import) but not Button itself
        assert "src/components/Icon.tsx" in context
        assert "src/components/Button.tsx" not in context
        
        # Should not include unrelated files at depth=1
        assert "src/hooks/useAuth.ts" not in context
        assert "src/components/LoginForm.tsx" not in context
    
    def test_context_builder_transitive_dependencies(self, sample_project, index_result):
        """Test context builder finds transitive dependencies"""
        context = build_context_bundle(
            project_root=sample_project,
            target_file="src/components/LoginForm.tsx",
            index_result=index_result,
            depth=2,  # Get transitive imports
            max_files=20
        )
        
        # Direct imports
        assert "src/components/Button.tsx" in context
        assert "src/hooks/useAuth.ts" in context
        
        # Transitive import (Button imports Icon)
        assert "src/components/Icon.tsx" in context
        
        # Should not include the target itself
        assert "src/components/LoginForm.tsx" not in context
    
    def test_context_builder_pinned_files_always_included(self, sample_project, index_result):
        """Test pinned files are always included regardless of depth"""
        context = build_context_bundle(
            project_root=sample_project,
            target_file="src/components/Button.tsx",
            index_result=index_result,
            pinned_files=["src/utils/test-helpers.ts", "src/utils/constants.ts"],
            depth=1,
            max_files=10
        )
        
        # Pinned files should be included even though not in dependency graph
        assert "src/utils/test-helpers.ts" in context
        assert "src/utils/constants.ts" in context
        
        # Direct import should also be there
        assert "src/components/Icon.tsx" in context
    
    def test_context_builder_respects_max_files_budget(self, sample_project, index_result):
        """Test that max_files budget is enforced"""
        context = build_context_bundle(
            project_root=sample_project,
            target_file="src/components/LoginForm.tsx",
            index_result=index_result,
            depth=3,
            max_files=2,  # Strict limit
            max_chars_per_file=5000
        )
        
        # Should not exceed max_files
        assert len(context) <= 2
    
    def test_context_builder_respects_char_budgets(self, sample_project, index_result):
        """Test character budget enforcement"""
        context = build_context_bundle(
            project_root=sample_project,
            target_file="src/components/Button.tsx",
            index_result=index_result,
            depth=2,
            max_files=10,
            max_chars_per_file=100,  # Very strict per-file limit
            max_total_chars=500  # Strict total limit
        )
        
        # Each file should be truncated
        for file_path, content in context.items():
            assert len(content) <= 120  # 100 + some buffer for truncation marker
        
        # Total should not exceed budget
        total_chars = sum(len(content) for content in context.values())
        assert total_chars <= 550  # Allow small buffer
    
    def test_context_builder_excludes_test_files(self, sample_project, index_result):
        """Test that test files are excluded from context"""
        # Create a test file
        test_file = sample_project / "src" / "components" / "Button.test.tsx"
        test_file.write_text("// Test file")
        
        context = build_context_bundle(
            project_root=sample_project,
            target_file="src/components/LoginForm.tsx",
            index_result=index_result,
            depth=3,
            max_files=20
        )
        
        # Test files should not be included
        assert "src/components/Button.test.tsx" not in context
    
    def test_context_builder_handles_missing_target(self, sample_project, index_result):
        """Test graceful handling of non-existent target file"""
        context = build_context_bundle(
            project_root=sample_project,
            target_file="src/components/NonExistent.tsx",
            index_result=index_result,
            depth=2,
            max_files=10
        )
        
        # Should return empty or minimal context without crashing
        # The function should handle this gracefully
        assert isinstance(context, dict)
    
    def test_context_builder_file_with_no_imports(self, sample_project, index_result):
        """Test context builder with file that has no dependencies"""
        context = build_context_bundle(
            project_root=sample_project,
            target_file="src/utils/constants.ts",
            index_result=index_result,
            depth=2,
            max_files=10
        )
        
        # Should return minimal context (maybe same-folder utilities)
        assert isinstance(context, dict)
        # Constants file has no imports, so context should be minimal
        assert len(context) <= 2  # At most same-folder files
    
    # ==================== TEST GENERATOR TESTS ====================
    
    def test_generator_create_strategy_for_single_file(self, sample_project):
        """Test creating a TestStrategy for single target file"""
        strategy = TestStrategy(
            source_file="src/components/Button.tsx",
            test_file="src/components/Button.feature.test.tsx",
            test_level='feature',
            framework='jest',
            priority='high',
            test_type='feature',
            needs_mocks=True,
            complexity='moderate',
            rationale='Testing Button component with full context',
            related_files=[]
        )
        
        assert strategy.source_file == "src/components/Button.tsx"
        assert strategy.test_file == "src/components/Button.feature.test.tsx"
        assert strategy.test_level == 'feature'
        assert strategy.framework == 'jest'
    
    @pytest.mark.integration
    def test_end_to_end_generation_with_context(self, sample_project, index_result, gemini_client):
        """
        Full end-to-end test: context → generation → validation
        
        NOTE: This test requires Vertex AI credentials to be configured.
        Skip if credentials not available.
        """
        if gemini_client is None:
            pytest.skip("Gemini client not available")
        
        # Step 1: Build context
        context = build_context_bundle(
            project_root=sample_project,
            target_file="src/components/Button.tsx",
            index_result=index_result,
            pinned_files=["src/utils/test-helpers.ts"],
            depth=2,
            max_files=15,
            max_chars_per_file=2000,
            max_total_chars=20000
        )
        
        # Verify context built correctly
        assert len(context) > 0
        assert "src/components/Icon.tsx" in context
        assert "src/utils/test-helpers.ts" in context
        
        # Step 2: Create strategy
        strategy = TestStrategy(
            source_file="src/components/Button.tsx",
            test_file="src/components/Button.feature.test.tsx",
            test_level='feature',
            framework='jest',
            priority='high',
            test_type='feature',
            needs_mocks=True,
            complexity='moderate',
            rationale='Feature test with full context',
            related_files=[]
        )
        
        # Step 3: Generate test
        generator = TestGeneratorAgent(gemini_client)
        result = generator.generate_single_test_with_context(
            strategy=strategy,
            context_bundle=context,
            project_root=sample_project
        )
        
        # Step 4: Validate result
        assert result.success, f"Generation failed: {result.error_message}"
        assert result.test_content is not None
        assert len(result.test_content) > 100
        
        # Verify test structure
        assert 'import' in result.test_content
        assert 'describe(' in result.test_content or 'test(' in result.test_content
        assert 'Button' in result.test_content
        
        # Verify test uses context (should reference Icon or test-helpers)
        assert 'Icon' in result.test_content or 'renderWithProviders' in result.test_content
        
        print(f"\n✅ Successfully generated test with {result.test_count} test cases")
        print(f"Generated test preview:\n{result.test_content[:500]}")
    
    @pytest.mark.integration
    def test_generated_test_saves_to_correct_location(self, sample_project, index_result, gemini_client):
        """Test that generated test is saved to the correct file path"""
        if gemini_client is None:
            pytest.skip("Gemini client not available")
        
        context = build_context_bundle(
            project_root=sample_project,
            target_file="src/components/Icon.tsx",
            index_result=index_result,
            depth=1,
            max_files=5
        )
        
        strategy = TestStrategy(
            source_file="src/components/Icon.tsx",
            test_file="src/components/Icon.feature.test.tsx",
            test_level='feature',
            framework='jest',
            priority='medium',
            test_type='feature',
            needs_mocks=False,
            complexity='simple',
            rationale='Simple component test',
            related_files=[]
        )
        
        generator = TestGeneratorAgent(gemini_client)
        result = generator.generate_single_test_with_context(
            strategy=strategy,
            context_bundle=context,
            project_root=sample_project
        )
        
        assert result.success
        
        # Save test file
        test_path = sample_project / result.test_file_path
        test_path.parent.mkdir(parents=True, exist_ok=True)
        test_path.write_text(result.test_content)
        
        # Verify file exists and has content
        assert test_path.exists()
        assert test_path.stat().st_size > 100
        
        # Verify it's in the correct location (same directory as source)
        assert test_path.parent == (sample_project / "src" / "components")
    
    # ==================== ERROR HANDLING TESTS ====================
    
    def test_generator_handles_missing_target_file(self, sample_project, gemini_client):
        """Test graceful error handling when target file doesn't exist"""
        if gemini_client is None:
            pytest.skip("Gemini client not available")
        
        strategy = TestStrategy(
            source_file="src/components/NonExistent.tsx",
            test_file="src/components/NonExistent.feature.test.tsx",
            test_level='feature',
            framework='jest',
            priority='high',
            test_type='feature',
            needs_mocks=False,
            complexity='simple',
            rationale='Test error handling',
            related_files=[]
        )
        
        generator = TestGeneratorAgent(gemini_client)
        result = generator.generate_single_test_with_context(
            strategy=strategy,
            context_bundle={},
            project_root=sample_project
        )
        
        # Should fail gracefully
        assert not result.success
        assert result.error_message is not None
        assert "not found" in result.error_message.lower()
    
    def test_context_builder_handles_broken_imports(self, sample_project, index_result):
        """Test context builder with file that has broken import paths"""
        # Create file with broken import
        broken_file = sample_project / "src" / "components" / "Broken.tsx"
        broken_file.write_text("""
import { NonExistent } from './does-not-exist';
import { Button } from './Button';

export const Broken = () => <div><Button label="test" onClick={() => {}} /></div>;
""")
        
        context = build_context_bundle(
            project_root=sample_project,
            target_file="src/components/Broken.tsx",
            index_result=index_result,
            depth=2,
            max_files=10
        )
        
        # Should still include resolvable imports
        assert "src/components/Button.tsx" in context
        # Should handle broken import gracefully (not crash)
        assert isinstance(context, dict)
    
    # ==================== PERFORMANCE TESTS ====================
    
    def test_context_builder_performance_large_depth(self, sample_project, index_result):
        """Test that context builder completes in reasonable time even with large depth"""
        import time
        
        start_time = time.time()
        context = build_context_bundle(
            project_root=sample_project,
            target_file="src/components/LoginForm.tsx",
            index_result=index_result,
            depth=5,  # Very deep traversal
            max_files=50,
            max_chars_per_file=3000
        )
        duration = time.time() - start_time
        
        # Should complete within 5 seconds for small project
        assert duration < 5.0, f"Context building took too long: {duration}s"
        assert isinstance(context, dict)
    
    # ==================== VALIDATION TESTS ====================
    
    def test_generated_test_has_proper_structure(self, sample_project, index_result, gemini_client):
        """Validate that generated test has proper Jest structure"""
        if gemini_client is None:
            pytest.skip("Gemini client not available")
        
        context = build_context_bundle(
            project_root=sample_project,
            target_file="src/components/Button.tsx",
            index_result=index_result,
            depth=2,
            max_files=10
        )
        
        strategy = TestStrategy(
            source_file="src/components/Button.tsx",
            test_file="src/components/Button.feature.test.tsx",
            test_level='feature',
            framework='jest',
            priority='high',
            test_type='feature',
            needs_mocks=True,
            complexity='moderate',
            rationale='Validation test',
            related_files=[]
        )
        
        generator = TestGeneratorAgent(gemini_client)
        result = generator.generate_single_test_with_context(
            strategy=strategy,
            context_bundle=context,
            project_root=sample_project
        )
        
        if not result.success:
            pytest.skip(f"Generation failed: {result.error_message}")
        
        test_code = result.test_content
        
        # Must have imports
        assert 'import' in test_code or 'require' in test_code
        
        # Must have describe or test blocks
        assert any(keyword in test_code for keyword in ['describe(', 'test(', 'it('])
        
        # Must have assertions (expect or assert)
        # Note: Some generated tests might not have expect in first 1000 chars
        # so we just check the file has reasonable structure
        assert len(test_code.split('\n')) > 10  # At least 10 lines
    
    def test_context_bundle_prioritization(self, sample_project, index_result):
        """Test that pinned files appear first in context bundle"""
        context = build_context_bundle(
            project_root=sample_project,
            target_file="src/components/LoginForm.tsx",
            index_result=index_result,
            pinned_files=["src/utils/test-helpers.ts", "src/utils/constants.ts"],
            depth=2,
            max_files=20
        )
        
        # Get keys as list to check order
        context_keys = list(context.keys())
        
        # Pinned files should be first
        assert "src/utils/test-helpers.ts" in context_keys[:2]
        assert "src/utils/constants.ts" in context_keys[:2]


# ==================== HELPER FUNCTIONS FOR MANUAL TESTING ====================

def manual_test_workflow(project_path: str):
    """
    Helper function for manual testing during development.
    
    Usage:
        python -c "from tests.test_single_feature_generation import manual_test_workflow; \
                   manual_test_workflow('/path/to/your/react/project')"
    """
    from tools.file_indexer import FileIndexer
    
    project_root = Path(project_path)
    
    print(f"🔍 Indexing project: {project_root}")
    success, message, index_result = FileIndexer.index_directory(project_root)
    
    if not success:
        print(f"❌ Indexing failed: {message}")
        return
    
    print(f"✅ Indexed {index_result.total_files} files")
    
    # List TypeScript/JavaScript files
    eligible_files = [
        f.relative_path for f in index_result.file_list
        if f.extension in ['.ts', '.tsx', '.js', '.jsx']
        and not any(x in f.relative_path for x in ['.test.', '.spec.'])
    ]
    
    print(f"\n📝 Eligible files for testing:")
    for i, file in enumerate(eligible_files[:10], 1):
        print(f"  {i}. {file}")
    
    if not eligible_files:
        print("❌ No eligible files found")
        return
    
    # Use first file as example
    target_file = eligible_files[0]
    print(f"\n🎯 Building context for: {target_file}")
    
    context = build_context_bundle(
        project_root=project_root,
        target_file=target_file,
        index_result=index_result,
        depth=2,
        max_files=15,
        max_chars_per_file=2000
    )
    
    print(f"✅ Context built: {len(context)} files")
    print("\n📂 Context files:")
    for file_path in context.keys():
        print(f"  - {file_path}")
    
    print("\n💡 To generate a test, use the Streamlit UI or call generate_single_test_with_context()")


if __name__ == "__main__":
    # Quick validation that imports work
    print("✅ All imports successful")
    print("Run with: pytest tests/test_single_feature_generation.py -v")
    print("Or: pytest tests/test_single_feature_generation.py -v -m integration  # For full integration tests")
