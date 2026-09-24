# from typing import TypedDict, List, Dict, Literal
# from langgraph.graph import StateGraph, END
# from langchain_google_vertexai import ChatVertexAI
# import os
# import json
# import subprocess
# import git
# from pathlib import Path
# from dotenv import load_dotenv
# import vertexai
# from google.auth import default
# import tempfile
# import time
# import shutil
# import re

# # ============= CONFIGURATION =============

# # Load environment variables
# load_dotenv()

# # Get GCP configuration
# GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
# GCP_REGION = os.getenv("GCP_REGION", "us-central1")
# VERTEX_AI_LOCATION = os.getenv("VERTEX_AI_LOCATION", GCP_REGION)
# SERVICE_ACCOUNT_KEY = r"C:\Users\gudladhana.harshith\Pictures\Deployment\gcp_credits.json"

# if not GCP_PROJECT_ID:
#     raise ValueError("GCP_PROJECT_ID not found in environment variables")

# print(f"✅ Loaded configuration:")
# print(f"   - GCP Project: {GCP_PROJECT_ID}")
# print(f"   - GCP Region: {GCP_REGION}")
# print(f"   - Vertex AI Location: {VERTEX_AI_LOCATION}")

# # ============= STATE DEFINITION =============

# class DeploymentState(TypedDict):
#     # Input
#     repo_url: str
#     branch: str
#     gcp_project_id: str
#     gcp_region: str
    
#     # Repository Analysis
#     repo_structure: str
#     key_files_content: Dict[str, str]
#     repo_local_path: str
    
#     # LLM Analysis Results
#     analysis: Dict
#     deployment_plan: Dict
    
#     # Generated Artifacts
#     dockerfiles: Dict[str, str]
#     cloudbuild_config: str
    
#     # Build & Deploy
#     build_id: str
#     build_status: str
#     build_log_url: str
#     deployed_services: Dict[str, str]
    
#     # Agent State
#     messages: List[Dict]
#     errors: List[str]
#     current_step: str

# # ============= VERTEX AI INITIALIZATION =============

# try:
#     # Use Application Default Credentials or Service Account
#     if SERVICE_ACCOUNT_KEY and os.path.exists(SERVICE_ACCOUNT_KEY):
#         os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = SERVICE_ACCOUNT_KEY
#         print(f"   - Using Service Account: {SERVICE_ACCOUNT_KEY}")
    
#     credentials, project = default()
    
#     # Initialize Vertex AI
#     vertexai.init(
#         project=GCP_PROJECT_ID,
#         location=VERTEX_AI_LOCATION,
#         credentials=credentials
#     )
    
#     # Initialize Gemini via Vertex AI
#     llm = ChatVertexAI(
#         model="gemini-2.5-pro",
#         temperature=0.1,
#         max_retries=3,
#         project=GCP_PROJECT_ID,
#         location=VERTEX_AI_LOCATION,
#         credentials=credentials
#     )
    
#     print("✅ Vertex AI Gemini initialized successfully")
    
# except Exception as e:
#     raise RuntimeError(f"Failed to initialize Vertex AI: {e}")

# # ============= UTILITY FUNCTIONS =============

# def get_repo_structure(repo_path: str, max_depth: int = 5) -> str:
#     """Get complete repository structure as a tree"""
#     structure = []
    
#     def walk_dir(path: Path, prefix: str = "", depth: int = 0):
#         if depth > max_depth:
#             return
        
#         try:
#             items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
            
#             # Filter out common ignored directories
#             ignored = {'.git', 'node_modules', '__pycache__', '.next', 'build', 
#                       'dist', '.venv', 'venv', '.idea', '.vscode', 'coverage',
#                       '.cache', 'out', 'target', 'bin', 'obj', '.DS_Store'}
#             items = [item for item in items if item.name not in ignored]
            
#             for i, item in enumerate(items):
#                 is_last = i == len(items) - 1
#                 current_prefix = "└── " if is_last else "├── "
#                 structure.append(f"{prefix}{current_prefix}{item.name}")
                
#                 if item.is_dir():
#                     extension = "    " if is_last else "│   "
#                     walk_dir(item, prefix + extension, depth + 1)
#         except PermissionError:
#             pass
    
#     walk_dir(Path(repo_path))
#     return "\n".join(structure)

# def extract_key_files(repo_path: str) -> Dict[str, str]:
#     """Extract content of key configuration files"""
#     key_patterns = [
#         'package.json',
#         'package-lock.json',
#         'tsconfig.json',
#         'next.config.js',
#         'vite.config.js',
#         'Dockerfile',
#         'docker-compose.yml',
#         '.env.example',
#         'README.md',
#         'server.js',
#         'index.js',
#         'app.js',
#         'main.js',
#         'main.ts',
#         'index.ts'
#     ]
    
#     files_content = {}
    
#     for root, dirs, files in os.walk(repo_path):
#         # Skip ignored directories
#         dirs[:] = [d for d in dirs if d not in {'.git', 'node_modules', '__pycache__', 
#                                                  '.next', 'build', 'dist', '.venv', 'venv',
#                                                  '.cache', 'coverage', 'out'}]
        
#         for file in files:
#             if file in key_patterns or file.endswith(('.json', '.js', '.ts', '.jsx', '.tsx', '.yaml', '.yml')):
#                 file_path = os.path.join(root, file)
#                 relative_path = os.path.relpath(file_path, repo_path)
                
#                 try:
#                     # Only read text files under 100KB
#                     if os.path.getsize(file_path) < 100000:
#                         with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
#                             content = f.read()
#                             files_content[relative_path] = content
#                 except Exception as e:
#                     files_content[relative_path] = f"[Error reading file: {e}]"
    
#     return files_content

# def clean_directory(path: str) -> bool:
#     """Clean directory with proper Windows handling"""
#     if not os.path.exists(path):
#         return True
    
#     try:
#         if os.name == 'nt':
#             # Windows - use rmdir command
#             subprocess.run(['cmd', '/c', 'rmdir', '/s', '/q', path], 
#                          check=False, capture_output=True)
#             time.sleep(2)  # Give Windows time to release handles
#         else:
#             shutil.rmtree(path, ignore_errors=True)
#             time.sleep(1)
#         return True
#     except Exception as e:
#         print(f"   Warning during cleanup: {e}")
#         return False

# def remove_reserved_env_vars(env_vars: Dict[str, str]) -> Dict[str, str]:
#     """Remove Cloud Run reserved environment variables"""
#     # Cloud Run reserved variables that cannot be set by users
#     reserved_vars = {'PORT', 'K_SERVICE', 'K_REVISION', 'K_CONFIGURATION'}
    
#     cleaned = {k: v for k, v in env_vars.items() if k not in reserved_vars}
    
#     removed = set(env_vars.keys()) - set(cleaned.keys())
#     if removed:
#         print(f"   ℹ️  Removed reserved environment variables: {', '.join(removed)}")
    
#     return cleaned

# # ============= AGENT NODES =============

# def clone_and_analyze_repo(state: DeploymentState) -> DeploymentState:
#     """Clone repository and extract structure"""
#     print(f"\n{'='*60}")
#     print(f"📦 STEP 1: Cloning Repository")
#     print(f"{'='*60}")
#     print(f"Repository: {state['repo_url']}")
#     print(f"Branch: {state['branch']}")
    
#     # Create temp directory path - Windows compatible
#     if os.name == 'nt':
#         # Windows - use shorter path to avoid path length issues
#         temp_base = os.environ.get('TEMP', 'C:\\Temp')
#         repo_path = os.path.join(temp_base, 'deploy_repo')
#     else:
#         repo_path = "/tmp/deployment_repo"
    
#     # Clean up existing repo
#     if os.path.exists(repo_path):
#         print(f"🗑️  Cleaning up existing directory...")
#         clean_directory(repo_path)
    
#     # Ensure parent directory exists
#     os.makedirs(os.path.dirname(repo_path), exist_ok=True)
    
#     # Clone repository
#     try:
#         print("⏳ Cloning...")
#         git.Repo.clone_from(
#             state['repo_url'], 
#             repo_path, 
#             branch=state['branch'],
#             depth=1
#         )
#         print("✅ Repository cloned successfully")
#         print(f"   Location: {repo_path}")
#     except git.GitCommandError as e:
#         print(f"❌ Failed to clone repository: {e}")
#         state['errors'].append(f"Git clone failed: {e}")
#         state['current_step'] = 'failed'
#         return state
    
#     print("\n📊 Analyzing repository structure...")
    
#     # Get structure
#     structure = get_repo_structure(repo_path)
#     state['repo_structure'] = structure
#     state['repo_local_path'] = repo_path
    
#     # Extract key files
#     key_files = extract_key_files(repo_path)
#     state['key_files_content'] = key_files
    
#     print(f"✅ Found {len(key_files)} key files")
#     state['current_step'] = 'analyzed'
    
#     return state

# def llm_analyze_repository(state: DeploymentState) -> DeploymentState:
#     """Use LLM to understand the repository"""
#     print(f"\n{'='*60}")
#     print(f"🤖 STEP 2: AI Analysis")
#     print(f"{'='*60}")
#     print("Asking Gemini to analyze the repository structure...")
    
#     # Prepare context for LLM - limit to avoid token limits
#     files_summary = "\n\n".join([
#         f"=== {path} ===\n{content[:1000]}{'...' if len(content) > 1000 else ''}"
#         for path, content in list(state['key_files_content'].items())[:20]
#     ])
    
#     prompt = f"""You are analyzing a GitHub repository for deployment to GCP Cloud Run.

# REPOSITORY STRUCTURE:
# {state['repo_structure']}

# KEY FILES CONTENT:
# {files_summary}

# Analyze this repository and provide a JSON response with the following structure:
# {{
#     "applications": [
#         {{
#             "name": "backend" or "frontend" or custom name,
#             "type": "nodejs-backend" or "react-frontend" or "nextjs" etc,
#             "location": "relative/path/from/repo/root",
#             "main_file": "entry point file",
#             "framework": "express/fastify/nest/react/next/vite etc",
#             "dependencies": ["list", "of", "key", "dependencies"],
#             "build_command": "npm run build or similar",
#             "start_command": "npm start or similar",
#             "port": default port number,
#             "environment_variables": ["VAR1", "VAR2"]
#         }}
#     ],
#     "deployment_order": ["service1", "service2"],
#     "inter_dependencies": {{
#         "frontend_needs_backend_url": true/false,
#         "shared_database": true/false
#     }},
#     "recommendations": "Any deployment recommendations"
# }}

# Be thorough and accurate. Look at package.json files, main entry points, and folder structure.
# Return ONLY valid JSON, no additional text or markdown.
# """
    
#     try:
#         response = llm.invoke(prompt)
        
#         # Parse JSON response
#         content = response.content.strip()
#         if content.startswith("```json"):
#             content = content.split("```json")[1].split("```")[0].strip()
#         elif content.startswith("```"):
#             content = content.split("```")[1].split("```")[0].strip()
        
#         analysis = json.loads(content)
#         state['analysis'] = analysis
        
#         print(f"\n✅ AI Analysis Complete!")
#         print(f"   Detected {len(analysis['applications'])} applications:")
#         for app in analysis['applications']:
#             print(f"   • {app['name']} ({app['type']}) at {app['location']}")
        
#         state['current_step'] = 'analysis_complete'
        
#     except json.JSONDecodeError as e:
#         print(f"❌ Failed to parse LLM response: {e}")
#         print(f"Response was: {response.content[:500]}")
        
#         # Try to extract partial JSON or retry with a simpler request
#         print("⚠️  Attempting to extract partial JSON or use fallback...")
#         try:
#             # Try to find JSON object in the response even if incomplete
#             content = response.content.strip()
#             # Remove markdown code blocks
#             if "```json" in content:
#                 content = content.split("```json")[1].split("```")[0].strip()
#             elif "```" in content:
#                 content = content.split("```")[1].split("```")[0].strip()
            
#             # Try to find the start of applications array
#             if '"applications"' in content:
#                 # Extract up to the applications array
#                 start_idx = content.find('"applications"')
#                 # Try to find a closing bracket
#                 bracket_count = 0
#                 brace_count = 0
#                 in_string = False
#                 escape_next = False
                
#                 for i in range(start_idx, len(content)):
#                     char = content[i]
#                     if escape_next:
#                         escape_next = False
#                         continue
#                     if char == '\\':
#                         escape_next = True
#                         continue
#                     if char == '"':
#                         in_string = not in_string
#                         continue
#                     if not in_string:
#                         if char == '[':
#                             bracket_count += 1
#                         elif char == ']':
#                             bracket_count -= 1
#                         elif char == '{':
#                             brace_count += 1
#                         elif char == '}':
#                             brace_count -= 1
                        
#                         # If we found a complete applications array
#                         if bracket_count == 0 and brace_count >= 0 and i > start_idx + 50:
#                             partial_json = content[:i+1] + ']}'
#                             try:
#                                 analysis = json.loads(partial_json)
#                                 state['analysis'] = analysis
#                                 print(f"✅ Extracted partial analysis with {len(analysis.get('applications', []))} applications")
#                                 break
#                             except:
#                                 pass
                
#                 # If we couldn't extract partial, create a minimal fallback
#                 if 'analysis' not in state or 'applications' not in state.get('analysis', {}):
#                     print("⚠️  Creating fallback analysis from repository structure...")
#                     # Create a minimal analysis based on common patterns
#                     applications = []
#                     if 'backend' in state['repo_structure'].lower() or 'server.js' in state['repo_structure']:
#                         applications.append({
#                             "name": "backend",
#                             "type": "nodejs-backend",
#                             "location": "backend",
#                             "main_file": "server.js",
#                             "framework": "express",
#                             "dependencies": [],
#                             "build_command": None,
#                             "start_command": "npm start",
#                             "port": 8080
#                         })
#                     if 'web' in state['repo_structure'].lower() or 'frontend' in state['repo_structure'].lower() or 'src' in state['repo_structure']:
#                         applications.append({
#                             "name": "frontend",
#                             "type": "react-frontend",
#                             "location": "web",
#                             "main_file": "src/index.js",
#                             "framework": "react",
#                             "dependencies": [],
#                             "build_command": "npm run build",
#                             "start_command": "npm start",
#                             "port": 3000
#                         })
                    
#                     if applications:
#                         state['analysis'] = {
#                             "applications": applications,
#                             "deployment_order": [app['name'] for app in applications],
#                             "inter_dependencies": {},
#                             "recommendations": "Fallback analysis - please verify configuration"
#                         }
#                         print(f"✅ Created fallback analysis with {len(applications)} applications")
#             else:
#                 raise ValueError("No applications found in response")
                
#         except Exception as fallback_error:
#             print(f"❌ Fallback extraction also failed: {fallback_error}")
#             state['errors'].append(f"Failed to parse LLM analysis: {e}")
#             state['current_step'] = 'failed'
#             # Set empty analysis to prevent KeyError
#             state['analysis'] = {"applications": []}
#     except Exception as e:
#         print(f"❌ LLM analysis failed: {e}")
#         state['errors'].append(f"LLM analysis failed: {e}")
#         state['current_step'] = 'failed'
#         # Set empty analysis to prevent KeyError
#         state['analysis'] = {"applications": []}
    
#     return state

# def llm_generate_deployment_plan(state: DeploymentState) -> DeploymentState:
#     """Use LLM to create deployment strategy"""
#     print(f"\n{'='*60}")
#     print(f"📋 STEP 3: Deployment Plan")
#     print(f"{'='*60}")
#     print("Generating deployment strategy...")
    
#     prompt = f"""Based on this repository analysis:
# {json.dumps(state['analysis'], indent=2)}

# Create a detailed deployment plan for GCP Cloud Run. Provide JSON response:
# {{
#     "services": [
#         {{
#             "name": "service-name",
#             "type": "backend/frontend",
#             "cloud_run_config": {{
#                 "memory": "512Mi",
#                 "cpu": "1",
#                 "max_instances": 10,
#                 "min_instances": 0,
#                 "port": 8080,
#                 "timeout": 300,
#                 "startup_cpu_boost": true
#             }},
#             "environment_variables": {{
#                 "NODE_ENV": "production"
#             }},
#             "depends_on": ["other-service-name"]
#         }}
#     ],
#     "deployment_steps": [
#         "step 1 description",
#         "step 2 description"
#     ]
# }}

# CRITICAL: Do NOT include "PORT" in environment_variables - it's automatically set by Cloud Run.
# You can include other variables like NODE_ENV, API_KEY, DATABASE_URL, etc.

# Return ONLY valid JSON, no markdown.
# """
    
#     try:
#         response = llm.invoke(prompt)
        
#         content = response.content.strip()
#         if content.startswith("```json"):
#             content = content.split("```json")[1].split("```")[0].strip()
#         elif content.startswith("```"):
#             content = content.split("```")[1].split("```")[0].strip()
        
#         plan = json.loads(content)
        
#         # SAFETY CHECK: Remove PORT from any environment variables
#         for service in plan.get('services', []):
#             if 'environment_variables' in service:
#                 service['environment_variables'] = remove_reserved_env_vars(
#                     service['environment_variables']
#                 )
        
#         state['deployment_plan'] = plan
        
#         print(f"✅ Deployment plan created for {len(plan['services'])} services")
#         for service in plan['services']:
#             print(f"   • {service['name']}: {service['cloud_run_config']['memory']}, {service['cloud_run_config']['cpu']} CPU")
        
#         state['current_step'] = 'plan_ready'
        
#     except json.JSONDecodeError as e:
#         print(f"❌ Failed to parse deployment plan: {e}")
#         state['errors'].append(f"Failed to parse deployment plan: {e}")
#         state['current_step'] = 'failed'
#     except Exception as e:
#         print(f"❌ Deployment plan generation failed: {e}")
#         state['errors'].append(f"Deployment plan failed: {e}")
#         state['current_step'] = 'failed'
    
#     return state

# def validate_and_fix_port_listening(state: DeploymentState) -> DeploymentState:
#     """Validate and fix application code to ensure it listens on PORT env var"""
#     print(f"\n{'='*60}")
#     print(f"🔧 STEP 4: Validating PORT Configuration")
#     print(f"{'='*60}")
    
#     # Check if analysis exists and has applications
#     if 'analysis' not in state or 'applications' not in state['analysis']:
#         print("⚠️  No analysis data available - skipping PORT validation")
#         state['current_step'] = 'port_validated'
#         return state
    
#     if not state['analysis']['applications']:
#         print("⚠️  No applications found in analysis - skipping PORT validation")
#         state['current_step'] = 'port_validated'
#         return state
    
#     repo_path = state['repo_local_path']
#     fixes_applied = []
    
#     for app in state['analysis']['applications']:
#         print(f"\n   Checking {app['name']} for PORT configuration...")
        
#         # Find the main entry file
#         main_file = app.get('main_file', '')
#         app_location = os.path.join(repo_path, app['location'])
        
#         # Common entry point files
#         possible_entry_files = [
#             main_file,
#             'server.js',
#             'index.js',
#             'app.js',
#             'src/server.js',
#             'src/index.js',
#             'src/app.js',
#             'dist/server.js',
#             'dist/index.js'
#         ]
        
#         entry_file_path = None
#         for entry_file in possible_entry_files:
#             if not entry_file:
#                 continue
#             test_path = os.path.join(app_location, entry_file)
#             if os.path.exists(test_path):
#                 entry_file_path = test_path
#                 break
        
#         if not entry_file_path:
#             print(f"   ⚠️  Could not find entry file for {app['name']}")
#             continue
        
#         print(f"   Found entry file: {os.path.relpath(entry_file_path, repo_path)}")
        
#         try:
#             with open(entry_file_path, 'r', encoding='utf-8') as f:
#                 content = f.read()
            
#             # Check if PORT is being read from environment
#             has_port_env = bool(re.search(r'process\.env\.PORT|PORT\s*=\s*process\.env', content, re.IGNORECASE))
            
#             # Check for hardcoded ports
#             hardcoded_port_patterns = [
#                 r'\.listen\(\s*(\d{4})\s*[,\)]',  # .listen(3000)
#                 r'port\s*:\s*(\d{4})',  # port: 3000
#                 r'PORT\s*=\s*(\d{4})',  # PORT = 3000
#             ]
            
#             hardcoded_ports = []
#             for pattern in hardcoded_port_patterns:
#                 matches = re.findall(pattern, content)
#                 hardcoded_ports.extend(matches)
            
#             # Check if listening on correct host
#             listens_localhost = bool(re.search(r'\.listen\([^)]*[\'"]localhost[\'"]|\.listen\([^)]*[\'"]127\.0\.0\.1[\'"]', content))
            
#             if has_port_env and not hardcoded_ports and not listens_localhost:
#                 print(f"   ✅ Already correctly configured")
#             else:
#                 if not has_port_env:
#                     print(f"   ⚠️  Does NOT read PORT from environment")
#                 if hardcoded_ports:
#                     print(f"   ⚠️  Found hardcoded ports: {', '.join(set(hardcoded_ports))}")
#                 if listens_localhost:
#                     print(f"   ⚠️  Listening on localhost instead of 0.0.0.0")
                
#                 # Try to fix automatically
#                 print(f"   🔧 Attempting to fix PORT configuration...")
                
#                 # Add PORT reading at the beginning if not present
#                 if 'const PORT' not in content and 'let PORT' not in content and 'var PORT' not in content:
#                     # Find a good place to insert - after imports/requires
#                     lines = content.split('\n')
#                     insert_index = 0
                    
#                     # Find last import/require line
#                     for i, line in enumerate(lines):
#                         if 'require(' in line or 'import ' in line or 'from ' in line:
#                             insert_index = i + 1
                    
#                     # Insert PORT configuration
#                     port_config = "\n// 🔧 Added by deployment agent - Read PORT from Cloud Run environment\nconst PORT = process.env.PORT || 8080;\n"
#                     lines.insert(insert_index, port_config)
#                     content = '\n'.join(lines)
                    
#                     print(f"   ✅ Added PORT environment variable reading")
#                     fixes_applied.append(f"{app['name']}: Added PORT env reading")
                
#                 # Replace hardcoded .listen() calls
#                 # Pattern: .listen(3000, ...) -> .listen(PORT, '0.0.0.0', ...)
#                 original_content = content
#                 content = re.sub(
#                     r'\.listen\(\s*\d{4}\s*,',
#                     '.listen(PORT, \'0.0.0.0\',',
#                     content
#                 )
#                 # Pattern: .listen(3000) -> .listen(PORT, '0.0.0.0')
#                 content = re.sub(
#                     r'\.listen\(\s*\d{4}\s*\)',
#                     '.listen(PORT, \'0.0.0.0\')',
#                     content
#                 )
                
#                 # Fix localhost to 0.0.0.0
#                 content = re.sub(
#                     r'\.listen\(([^)]*)[\'"]localhost[\'"]',
#                     r'.listen(\1\'0.0.0.0\'',
#                     content
#                 )
#                 content = re.sub(
#                     r'\.listen\(([^)]*)[\'"]127\.0\.0\.1[\'"]',
#                     r'.listen(\1\'0.0.0.0\'',
#                     content
#                 )
                
#                 if content != original_content:
#                     # Write back the fixed file
#                     with open(entry_file_path, 'w', encoding='utf-8') as f:
#                         f.write(content)
                    
#                     print(f"   ✅ Fixed PORT configuration in {os.path.basename(entry_file_path)}")
#                     fixes_applied.append(f"{app['name']}: Fixed PORT listening")
        
#         except Exception as e:
#             print(f"   ⚠️  Could not validate/fix {app['name']}: {e}")
    
#     if fixes_applied:
#         print(f"\n✅ Applied {len(fixes_applied)} fixes:")
#         for fix in fixes_applied:
#             print(f"   • {fix}")
#     else:
#         print(f"\n✅ No PORT fixes needed or all apps already configured correctly")
    
#     state['current_step'] = 'port_validated'
#     return state

# def llm_generate_dockerfiles(state: DeploymentState) -> DeploymentState:
#     """Use LLM to generate Dockerfiles for each service"""
#     print(f"\n{'='*60}")
#     print(f"🐳 STEP 5: Dockerfile Generation")
#     print(f"{'='*60}")
    
#     # Check if analysis exists and has applications
#     if 'analysis' not in state or 'applications' not in state['analysis']:
#         print("⚠️  No analysis data available - skipping Dockerfile generation")
#         state['current_step'] = 'dockerfiles_ready'
#         return state
    
#     if not state['analysis']['applications']:
#         print("⚠️  No applications found in analysis - skipping Dockerfile generation")
#         state['current_step'] = 'dockerfiles_ready'
#         return state
    
#     dockerfiles = {}
#     repo_path = state['repo_local_path']
    
#     for app in state['analysis']['applications']:
#         print(f"\n   Generating Dockerfile for {app['name']}...")
        
#         # Get relevant package.json if exists
#         package_json_path = os.path.join(app['location'], 'package.json')
#         # Normalize path for the OS
#         package_json_key = package_json_path.replace('/', os.sep).replace('\\', os.sep)
        
#         # Try to find package.json in key files
#         package_json = "{}"
#         for key in state['key_files_content'].keys():
#             if 'package.json' in key and app['location'] in key:
#                 package_json = state['key_files_content'][key]
#                 break
        
#         # Check if app has a build script in package.json
#         has_build_script = False
#         try:
#             pkg_json = json.loads(package_json)
#             scripts = pkg_json.get('scripts', {})
#             has_build_script = 'build' in scripts
#             if has_build_script:
#                 print(f"   ℹ️  Detected build script in package.json")
#             else:
#                 print(f"   ℹ️  No build script found - using simplified Dockerfile")
#         except:
#             print(f"   ⚠️  Could not parse package.json - using simplified Dockerfile")
#             pass
        
#         if has_build_script:
#             # Check if this is a React app (react-scripts)
#             is_react_app = 'react-scripts' in package_json.lower() or 'react' in package_json.lower()
            
#             # Generate Dockerfile WITH build step
#             if is_react_app:
#                 prompt = f"""Generate a production-ready Dockerfile for this React application that HAS a build step.

# APPLICATION INFO:
# {json.dumps(app, indent=2)}

# PACKAGE.JSON:
# {package_json[:2000]}

# 🚨 CRITICAL REQUIREMENTS FOR REACT APPS:
# 1. **NEVER** set PORT environment variable in Dockerfile (Cloud Run sets it automatically via $PORT)
# 2. **NEVER** use EXPOSE directive
# 3. Detect the build output directory from the project tooling:
#    - Vite projects (have vite.config.ts/js) build to "dist" directory
#    - Create React App projects (use react-scripts) build to "build" directory
# 4. Use multi-stage build: builder → runner
# 5. Install 'serve' package globally to serve static files in production
# 6. Use 'npm install --legacy-peer-deps' for build dependencies
# 7. Run as non-root user (node)
# 8. Use 'serve -s <output_dir> -l $PORT' where <output_dir> is "dist" for Vite or "build" for CRA

# EXAMPLE DOCKERFILE FOR VITE REACT APP WITH BUILD STEP:
# ```dockerfile
# FROM node:20-alpine AS builder
# WORKDIR /app
# COPY package*.json ./
# RUN npm install --legacy-peer-deps
# COPY . .
# RUN npm run build

# FROM node:20-alpine AS runner
# WORKDIR /app
# ENV NODE_ENV=production
# RUN npm install -g serve
# COPY --from=builder /app/dist ./dist
# USER node
# CMD ["sh", "-c", "serve -s dist -l $PORT"]
# ```

# EXAMPLE DOCKERFILE FOR CRA REACT APP WITH BUILD STEP:
# ```dockerfile
# FROM node:20-alpine AS builder
# WORKDIR /app
# COPY package*.json ./
# RUN npm install --legacy-peer-deps
# COPY . .
# RUN npm run build

# FROM node:20-alpine AS runner
# WORKDIR /app
# ENV NODE_ENV=production
# RUN npm install -g serve
# COPY --from=builder /app/build ./build
# USER node
# CMD ["sh", "-c", "serve -s build -l $PORT"]
# ```

# CRITICAL PATH REQUIREMENTS:
# - Use RELATIVE paths from the application directory, NOT absolute paths
# - If the app is in "web/" directory, use "COPY package*.json ./" NOT "COPY web/package*.json ./"
# - The build context will be set to the app directory, so paths are relative to that
# - Example: For app at "web/", cloudbuild.yaml will have "dir: web" so Dockerfile uses relative paths
# - NEVER include the app directory name in COPY paths - the build context is already set to that directory
# - Vite apps build to "dist" directory, CRA apps build to "build" directory - check vite.config or react-scripts to determine which

# Return ONLY the Dockerfile content, no markdown.
# """
#             else:
#                 prompt = f"""Generate a production-ready Dockerfile for this Node.js application that HAS a build step.

# APPLICATION INFO:
# {json.dumps(app, indent=2)}

# PACKAGE.JSON:
# {package_json[:2000]}

# 🚨 CRITICAL REQUIREMENTS:
# 1. **NEVER** set PORT environment variable in Dockerfile (Cloud Run sets it automatically)
# 2. **NEVER** use EXPOSE directive
# 3. This app HAS a "build" script - use a builder stage
# 4. Use multi-stage build: deps → builder → runner
# 5. Use 'npm install --production --legacy-peer-deps' for production dependencies
# 6. Use 'npm install --legacy-peer-deps' for build dependencies
# 7. Run as non-root user (node)
# 8. Determine the build output directory (usually "dist" or "build") and copy from there
# 9. Use the appropriate start command for the built application

# EXAMPLE DOCKERFILE FOR APP WITH BUILD STEP:
# ```dockerfile
# FROM node:20-alpine AS builder
# WORKDIR /app
# COPY package*.json ./
# RUN npm install --legacy-peer-deps
# COPY . .
# RUN npm run build

# FROM node:20-alpine AS runner
# WORKDIR /app
# ENV NODE_ENV=production
# COPY --from=builder /app/dist ./dist
# COPY package*.json ./
# RUN npm install --production --legacy-peer-deps
# USER node
# CMD ["npm", "start"]
# ```

# CRITICAL PATH REQUIREMENTS:
# - Use RELATIVE paths from the application directory, NOT absolute paths
# - If the app is in "web/" directory, use "COPY package*.json ./" NOT "COPY web/package*.json ./"
# - The build context will be set to the app directory, so paths are relative to that
# - Example: For app at "web/", cloudbuild.yaml will have "dir: web" so Dockerfile uses relative paths
# - NEVER include the app directory name in COPY paths - the build context is already set to that directory
# - Check the build output directory in package.json or use common defaults (dist, build, out)

# Return ONLY the Dockerfile content, no markdown.
# """
#         else:
#             # Generate Dockerfile WITHOUT build step
#             prompt = f"""Generate a production-ready Dockerfile for this Node.js application that does NOT have a build step.

# APPLICATION INFO:
# {json.dumps(app, indent=2)}

# PACKAGE.JSON:
# {package_json[:2000]}

# 🚨 CRITICAL REQUIREMENTS:
# 1. **NEVER** set PORT environment variable in Dockerfile (Cloud Run sets it automatically)
# 2. **NEVER** use EXPOSE directive
# 3. This app does NOT have a "build" script - use simple single or two-stage build
# 4. Use 'npm install --production --legacy-peer-deps' for dependencies
# 5. Run as non-root user (node)
# 6. DO NOT include a builder stage since there's no build step
# 7. DO NOT try to COPY dist or build directories that don't exist

# EXAMPLE DOCKERFILE FOR APP WITHOUT BUILD STEP:
# ```dockerfile
# FROM node:20-alpine AS deps
# WORKDIR /app
# COPY package*.json ./
# RUN npm install --production --legacy-peer-deps

# FROM node:20-alpine AS runner
# WORKDIR /app
# ENV NODE_ENV=production
# COPY --from=deps /app/node_modules ./node_modules
# COPY . .
# USER node
# CMD ["npm", "start"]
# ```

# CRITICAL PATH REQUIREMENTS:
# - Use RELATIVE paths from the application directory, NOT absolute paths
# - If the app is in "web/" directory, use "COPY package*.json ./" NOT "COPY web/package*.json ./"
# - The build context will be set to the app directory, so paths are relative to that
# - Example: For app at "web/", cloudbuild.yaml will have "dir: web" so Dockerfile uses relative paths

# IMPORTANT: Since this app has NO build script, do NOT include:
# - A "builder" stage
# - "npm run build" commands
# - COPY commands for dist/ or build/ directories

# Return ONLY the Dockerfile content, no markdown.
# """
        
#         try:
#             response = llm.invoke(prompt)
#             dockerfile_content = response.content.strip()
            
#             # Clean up if LLM added markdown
#             if dockerfile_content.startswith("```dockerfile"):
#                 dockerfile_content = dockerfile_content.split("```dockerfile")[1].split("```")[0].strip()
#             elif dockerfile_content.startswith("```Dockerfile"):
#                 dockerfile_content = dockerfile_content.split("```Dockerfile")[1].split("```")[0].strip()
#             elif dockerfile_content.startswith("```"):
#                 dockerfile_content = dockerfile_content.split("```")[1].split("```")[0].strip()
            
#             # VALIDATION: Ensure no PORT is set in Dockerfile
#             if 'ENV PORT' in dockerfile_content or 'PORT=' in dockerfile_content:
#                 print(f"   ⚠️  Removing PORT environment variable from Dockerfile...")
#                 dockerfile_content = re.sub(r'ENV\s+PORT\s*=\s*\d+\s*\n', '', dockerfile_content)
#                 dockerfile_content = re.sub(r'PORT=\d+', '', dockerfile_content)
            
#             # VALIDATION: Remove EXPOSE if present
#             if 'EXPOSE' in dockerfile_content:
#                 print(f"   ℹ️  EXPOSE directive found (will be ignored by Cloud Run)")
            
#             # VALIDATION: Check if this is a React app and fix Dockerfile accordingly
#             is_react_app = 'react-scripts' in package_json.lower() or 'react' in package_json.lower()

#             # Detect build tool to determine output directory
#             is_vite = 'vite' in package_json.lower()
#             is_cra = 'react-scripts' in package_json.lower()
#             # Vite outputs to "dist", CRA outputs to "build"
#             build_output_dir = 'dist' if is_vite else 'build'

#             if is_react_app:
#                 # Fix React-specific issues
#                 print(f"   ℹ️  Detected React app ({'Vite' if is_vite else 'CRA'}) - build output dir: {build_output_dir}")

#                 # Fix: Change CMD from "npm start" to serve command
#                 if 'CMD ["npm", "start"]' in dockerfile_content or "CMD ['npm', 'start']" in dockerfile_content:
#                     print(f"   ⚠️  Fixing CMD for React app (changing from 'npm start' to 'serve' command)...")
#                     dockerfile_content = re.sub(
#                         r'CMD\s+\["npm",\s*"start"\]',
#                         f'CMD ["sh", "-c", "serve -s {build_output_dir} -l $PORT"]',
#                         dockerfile_content
#                     )
#                     dockerfile_content = re.sub(
#                         r"CMD\s+\['npm',\s*'start'\]",
#                         f"CMD ['sh', '-c', 'serve -s {build_output_dir} -l $PORT']",
#                         dockerfile_content
#                     )

#                 # Fix: Ensure serve is installed in runner stage
#                 if 'npm install -g serve' not in dockerfile_content:
#                     print(f"   ⚠️  Adding 'serve' installation for React app...")
#                     # Try to add after ENV NODE_ENV=production in runner stage
#                     if 'ENV NODE_ENV=production' in dockerfile_content:
#                         dockerfile_content = dockerfile_content.replace(
#                             'ENV NODE_ENV=production',
#                             'ENV NODE_ENV=production\nRUN npm install -g serve'
#                         )
#                     # Or add after WORKDIR in runner stage if ENV is not present
#                     elif 'AS runner' in dockerfile_content:
#                         # Find runner stage and add serve after WORKDIR
#                         runner_workdir_pattern = r'(FROM node[^\n]*AS runner[^\n]*\nWORKDIR[^\n]*\n)'
#                         if re.search(runner_workdir_pattern, dockerfile_content):
#                             dockerfile_content = re.sub(
#                                 runner_workdir_pattern,
#                                 r'\1RUN npm install -g serve\n',
#                                 dockerfile_content
#                             )

#                 # Fix: Ensure build output directory matches the build tool
#                 if is_vite:
#                     # Vite outputs to "dist" - fix if Dockerfile incorrectly uses "build"
#                     if '/app/build' in dockerfile_content and '/app/dist' not in dockerfile_content:
#                         print(f"   ⚠️  Fixing build directory path (changing /app/build to /app/dist for Vite)...")
#                         dockerfile_content = dockerfile_content.replace('/app/build', '/app/dist')
#                         dockerfile_content = dockerfile_content.replace('./build', './dist')
#                         dockerfile_content = dockerfile_content.replace('serve -s build', 'serve -s dist')
#                 elif is_cra:
#                     # CRA outputs to "build" - fix if Dockerfile incorrectly uses "dist"
#                     if '/app/dist' in dockerfile_content and '/app/build' not in dockerfile_content:
#                         print(f"   ⚠️  Fixing build directory path (changing /app/dist to /app/build for CRA)...")
#                         dockerfile_content = dockerfile_content.replace('/app/dist', '/app/build')
#                         dockerfile_content = dockerfile_content.replace('./dist', './build')
#                         dockerfile_content = dockerfile_content.replace('serve -s dist', 'serve -s build')
            
#             # VALIDATION: Fix incorrect COPY paths that include app directory name
#             # The build context is set to the app directory, so paths should be relative to that
#             app_location = app.get('location', '').strip()
#             if app_location:
#                 # Extract just the directory name (e.g., "Github/web" -> "web", "web" -> "web")
#                 app_dir_name = os.path.basename(app_location.rstrip('/\\'))
                
#                 # Check for incorrect COPY paths and fix them
#                 # Pattern to match: "COPY web/package*.json" or "COPY Github/web/package*.json"
#                 # Should be: "COPY package*.json"
#                 fixed = False
                
#                 # Fix patterns like "COPY web/package*.json" -> "COPY package*.json"
#                 pattern1 = rf'COPY\s+{re.escape(app_dir_name)}/package\*\.json'
#                 if re.search(pattern1, dockerfile_content, re.IGNORECASE):
#                     print(f"   ⚠️  Fixing incorrect COPY paths in Dockerfile (removing '{app_dir_name}/' prefix)...")
#                     dockerfile_content = re.sub(
#                         pattern1,
#                         'COPY package*.json',
#                         dockerfile_content,
#                         flags=re.IGNORECASE
#                     )
#                     fixed = True
                
#                 # Fix full path versions like "COPY Github/web/package*.json"
#                 normalized_location = app_location.replace('\\', '/').rstrip('/')
#                 if normalized_location != app_dir_name:
#                     pattern2 = rf'COPY\s+{re.escape(normalized_location)}/package\*\.json'
#                     if re.search(pattern2, dockerfile_content, re.IGNORECASE):
#                         if not fixed:
#                             print(f"   ⚠️  Fixing incorrect COPY paths in Dockerfile (removing '{normalized_location}/' prefix)...")
#                         dockerfile_content = re.sub(
#                             pattern2,
#                             'COPY package*.json',
#                             dockerfile_content,
#                             flags=re.IGNORECASE
#                         )
#                         fixed = True
                
#                 # Fix any other COPY commands with the app directory prefix
#                 # Pattern: "COPY web/something" -> "COPY something"
#                 pattern3 = rf'COPY\s+{re.escape(app_dir_name)}/([^\s]+)'
#                 if re.search(pattern3, dockerfile_content, re.IGNORECASE) and not fixed:
#                     print(f"   ⚠️  Fixing incorrect COPY paths in Dockerfile (removing '{app_dir_name}/' prefix)...")
#                     dockerfile_content = re.sub(
#                         pattern3,
#                         r'COPY \1',
#                         dockerfile_content,
#                         flags=re.IGNORECASE
#                     )
            
#             dockerfiles[app['name']] = dockerfile_content
            
#             # Save Dockerfile to repo
#             dockerfile_path = os.path.join(repo_path, app['location'], 'Dockerfile')
#             os.makedirs(os.path.dirname(dockerfile_path), exist_ok=True)
#             with open(dockerfile_path, 'w', encoding='utf-8') as f:
#                 f.write(dockerfile_content)
            
#             print(f"   ✅ Dockerfile for {app['name']} generated and saved")
            
#         except Exception as e:
#             print(f"   ❌ Failed to generate Dockerfile for {app['name']}: {e}")
#             state['errors'].append(f"Dockerfile generation failed for {app['name']}: {e}")
    
#     state['dockerfiles'] = dockerfiles
    
#     if dockerfiles:
#         state['current_step'] = 'dockerfiles_ready'
#     else:
#         state['current_step'] = 'failed'
    
#     return state

# def llm_generate_cloudbuild_config(state: DeploymentState) -> DeploymentState:
#     """Use LLM to generate cloudbuild.yaml with proper timeout settings"""
#     print(f"\n{'='*60}")
#     print(f"☁️  STEP 6: Cloud Build Configuration")
#     print(f"{'='*60}")
#     print("Generating cloudbuild.yaml...")
    
#     prompt = f"""Generate a MINIMAL cloudbuild.yaml for GCP Cloud Build.

# ANALYSIS:
# {json.dumps(state['analysis'], indent=2)}

# DEPLOYMENT PLAN:
# {json.dumps(state['deployment_plan'], indent=2)}

# GCP CONFIG:
# - Project ID: {state['gcp_project_id']}
# - Region: {state['gcp_region']}
# - Artifact Registry: {state['gcp_region']}-docker.pkg.dev/{state['gcp_project_id']}/apps

# 🚨 CRITICAL CLOUD RUN DEPLOYMENT FLAGS (MUST INCLUDE):
# For EVERY gcloud run deploy command, you MUST include these flags:
# - '--timeout=300' (5 minute request timeout)
# - '--cpu-boost' (faster container startup)
# - '--max-instances=10' (autoscaling limit)
# - '--min-instances=0' (scale to zero)
# - '--memory=512Mi' (memory allocation)
# - '--cpu=1' (CPU allocation)
# - '--allow-unauthenticated' (public access)

# 🚨 CRITICAL: HANDLING ENVIRONMENT VARIABLES
# If you need to set environment variables, you MUST use a TWO-STEP approach:

# STEP 1: Clear existing env vars (if service might already exist)
# - Use a bash step that checks if service exists, then clears env vars
# - If service doesn't exist, the step should succeed (not fail)
# - Use: name: 'gcr.io/cloud-builders/gcloud' with entrypoint: '/bin/bash' and args that check service existence first
# - Give this step an id: 'clear-env-SERVICE_NAME'
# - Example:
#   - name: 'gcr.io/cloud-builders/gcloud'
#     entrypoint: '/bin/bash'
#     args:
#       - '-c'
#       - 'gcloud run services describe SERVICE_NAME --region=REGION --format="value(metadata.name)" >/dev/null 2>&1 && gcloud run services update SERVICE_NAME --region=REGION --clear-env-vars || echo "Service does not exist, skipping clear-env-vars"'

# STEP 2: Deploy with new env vars
# - Use: gcloud run deploy with --set-env-vars flag
# - Make it wait for step 1: waitFor: ['clear-env-SERVICE_NAME']

# ❌ NEVER use --clear-env-vars and --set-env-vars in the SAME command - gcloud will reject it!

# CRITICAL REQUIREMENTS - COMMAND FORMAT:
# 1. For cloud-sdk steps (gcloud commands), NEVER use shell syntax (-c, sh -c, bash -c)
# 2. For cloud-sdk steps, ALWAYS pass gcloud commands as a LIST of individual arguments
# 3. Each flag and value must be a SEPARATE item in the args array
# 4. DO NOT concatenate arguments into a single string
# 5. For Docker build args, ALWAYS use '--build-arg' (double dash), NEVER '-build-arg' (single dash)
# 6. Each build arg must be passed as: '--build-arg' followed by 'KEY=VALUE' as separate list items
# 7. EXCEPTION: For clear-env-vars steps, use 'gcr.io/cloud-builders/gcloud' with entrypoint: '/bin/bash' and '-c' to check if service exists first (to avoid failure if service doesn't exist)
# 8. EXCEPTION: For any step that needs to get backend URL or run bash commands with gcloud, use 'gcr.io/cloud-builders/gcloud' with entrypoint: '/bin/bash' and args: ['-c', 'command']
# 9. NEVER use 'gcr.io/google.com/cloudsdktool/cloud-sdk' with bash commands - it will fail. Use 'gcr.io/cloud-builders/gcloud' instead.

# CRITICAL REQUIREMENTS - IMAGE TAGS:
# 1. EVERY image MUST have a tag like ":latest" or ":$SHORT_SHA" or ":$BUILD_ID"
# 2. NEVER leave a colon at the end without a tag (e.g., "image:" is WRONG)
# 3. Example CORRECT format: "us-central1-docker.pkg.dev/project/apps/backend:latest"
# 4. Example WRONG format: "us-central1-docker.pkg.dev/project/apps/backend:"

# CRITICAL REQUIREMENTS - ENVIRONMENT VARIABLES:
# 5. NEVER set the PORT environment variable in gcloud run deploy commands
# 6. Cloud Run automatically sets PORT - setting it manually will cause deployment to fail
# 7. You can set other environment variables like NODE_ENV, API_URL, etc.
# 8. Example CORRECT: --set-env-vars=NODE_ENV=production,API_KEY=xyz
# 9. Example WRONG: --set-env-vars=PORT=8080,NODE_ENV=production

# CRITICAL REQUIREMENTS - GCLOUD COMMANDS AND ENTRYPOINT:
# 10. 🚨 ALWAYS add 'entrypoint: gcloud' when using gcr.io/google.com/cloudsdktool/cloud-sdk
# 11. The entrypoint field is MANDATORY - without it, Cloud Build cannot execute gcloud commands
# 12. Example CORRECT:
#     - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
#       entrypoint: gcloud
#       args: ['run', 'deploy', 'service-name', '--image=...']
# 13. Example WRONG (will fail):
#     - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
#       args: ['run', 'deploy', ...] 
# 14. DO NOT include 'gcloud' as first arg - the entrypoint handles that
# 15. Start args directly with gcloud subcommand: 'run', 'services', 'builds', etc.

# CRITICAL REQUIREMENTS - NO SECRETS:
# 16. ⚠️ ABSOLUTELY NEVER use Secret Manager in deployment commands - the API may not be enabled
# 17. ⚠️ NEVER use --set-secrets flag in gcloud commands
# 18. ⚠️ Secret Manager secrets DO NOT EXIST in this project - referencing them will fail
# 19. ✅ ONLY use --set-env-vars with plain text values: --set-env-vars=NODE_ENV=production

# OTHER REQUIREMENTS:
# 20. Build Docker images for each application in their respective directories
# 21. Push to Artifact Registry with proper tags
# 22. **CRITICAL:** Use 'dir' field in build steps to set correct build context
# 23. Example: If app is at "web/", use "dir: 'web'" in the build step
# 24. Dockerfile paths are RELATIVE to the 'dir' specified, NOT from repo root
# 25. Deploy to Cloud Run in the correct order with ALL required flags
# 26. If frontend depends on backend, deploy backend first, get its URL in a SEPARATE step, then deploy frontend with that URL
# 27. **CRITICAL:** To get backend URL, use a SEPARATE step BEFORE the docker build:
#    - Use 'gcr.io/cloud-builders/gcloud' with entrypoint: '/bin/bash'
#    - Get URL with: 'gcloud run services describe backend --region=REGION --format="value(status.url)"'
#    - Store it in a file or use substitution, then pass as build-arg to docker build
#    - Example:
#      - name: 'gcr.io/cloud-builders/gcloud'
#        entrypoint: '/bin/bash'
#        args:
#          - '-c'
#          - 'gcloud run services describe backend --region=us-central1 --format="value(status.url)" > /workspace/backend-url.txt'
#        id: 'get-backend-url'
#        waitFor: ['deploy-backend']
#    - Then in docker build, read from file or use a static placeholder
# 28. **NEVER** use gcloud commands inside docker build args - docker build cannot execute gcloud
# 29. Use ONLY built-in substitutions: $PROJECT_ID, $BUILD_ID, $SHORT_SHA
# 28. Use machine type: E2_MEDIUM (8 CPUs)
# 29. Set timeout: 1800s (at top level if needed)
# 30. ONLY include these top-level sections: steps, options (optional), timeout (optional)
# 31. DO NOT include: substitutions, secrets, availableSecrets, serviceAccount, logsBucket

# Example MINIMAL structure with CORRECT TWO-STEP approach for env vars:
# ```yaml
# steps:
#   # Build backend
#   - name: 'gcr.io/cloud-builders/docker'
#     args: ['build', '-t', 'us-central1-docker.pkg.dev/$PROJECT_ID/apps/backend:latest', '.']
#     dir: 'backend'
#     id: 'build-backend'
  
#   # Push backend
#   - name: 'gcr.io/cloud-builders/docker'
#     args: ['push', 'us-central1-docker.pkg.dev/$PROJECT_ID/apps/backend:latest']
#     id: 'push-backend'
#     waitFor: ['build-backend']
  
#   # STEP 1: Clear existing env vars (if service exists)
#   - name: 'gcr.io/cloud-builders/gcloud'
#     entrypoint: '/bin/bash'
#     args:
#       - '-c'
#       - 'gcloud run services describe backend --region=us-central1 --format="value(metadata.name)" >/dev/null 2>&1 && gcloud run services update backend --region=us-central1 --clear-env-vars || echo "Service does not exist, skipping clear-env-vars"'
#     id: 'clear-env-backend'
#     waitFor: ['push-backend']
  
#   # STEP 2: Deploy backend with new env vars
#   - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
#     entrypoint: gcloud
#     args:
#       - 'run'
#       - 'deploy'
#       - 'backend'
#       - '--image=us-central1-docker.pkg.dev/$PROJECT_ID/apps/backend:latest'
#       - '--region=us-central1'
#       - '--platform=managed'
#       - '--allow-unauthenticated'
#       - '--timeout=300'
#       - '--cpu-boost'
#       - '--max-instances=10'
#       - '--min-instances=0'
#       - '--memory=512Mi'
#       - '--cpu=1'
#       - '--set-env-vars=NODE_ENV=production,MONGODB_URI=your_mongodb_uri'
#     id: 'deploy-backend'
#     waitFor: ['clear-env-backend']
  
#   # Build frontend (if exists) - with React build args
#   - name: 'gcr.io/cloud-builders/docker'
#     args: 
#       - 'build'
#       - '--build-arg'
#       - 'REACT_APP_API_URL=https://backend-xxx.run.app'
#       - '--build-arg'
#       - 'REACT_APP_GOOGLE_MAPS_API_KEY=your_google_maps_api_key'
#       - '-t'
#       - 'us-central1-docker.pkg.dev/$PROJECT_ID/apps/frontend:latest'
#       - '.'
#     dir: 'web'
#     id: 'build-frontend'
#     waitFor: ['deploy-backend']
  
#   # Push frontend
#   - name: 'gcr.io/cloud-builders/docker'
#     args: ['push', 'us-central1-docker.pkg.dev/$PROJECT_ID/apps/frontend:latest']
#     id: 'push-frontend'
#     waitFor: ['build-frontend']
  
#   # STEP 1: Clear env vars for frontend
#   - name: 'gcr.io/cloud-builders/gcloud'
#     entrypoint: '/bin/bash'
#     args:
#       - '-c'
#       - 'gcloud run services describe frontend --region=us-central1 --format="value(metadata.name)" >/dev/null 2>&1 && gcloud run services update frontend --region=us-central1 --clear-env-vars || echo "Service does not exist, skipping clear-env-vars"'
#     id: 'clear-env-frontend'
#     waitFor: ['push-frontend']
  
#   # STEP 2: Deploy frontend with env vars
#   - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
#     entrypoint: gcloud
#     args:
#       - 'run'
#       - 'deploy'
#       - 'frontend'
#       - '--image=us-central1-docker.pkg.dev/$PROJECT_ID/apps/frontend:latest'
#       - '--region=us-central1'
#       - '--platform=managed'
#       - '--allow-unauthenticated'
#       - '--timeout=300'
#       - '--cpu-boost'
#       - '--max-instances=10'
#       - '--min-instances=0'
#       - '--memory=512Mi'
#       - '--cpu=1'
#       - '--set-env-vars=NODE_ENV=production,VITE_BACKEND_URL=https://backend-xxx.run.app'
#     waitFor: ['clear-env-frontend']

# options:
#   machineType: 'E2_MEDIUM'

# timeout: '1800s'
# ```

# CRITICAL: Use 'dir' field to specify build context for each application.
# The Dockerfile paths are relative to this directory.

# 🚨 REMEMBER: 
# - Every cloud-sdk step MUST have 'entrypoint: gcloud' or it will fail!
# - NEVER combine --clear-env-vars with --set-env-vars in one command!
# - Use TWO separate steps: one to clear, one to deploy with new vars

# Return ONLY the cloudbuild.yaml content in valid YAML format. NO markdown, NO explanations.
# KEEP IT MINIMAL - only steps, options (optional), and timeout (optional).
# DO NOT add substitutions, secrets, or any other sections.
# DO NOT set PORT environment variable - Cloud Run handles this automatically.
# ALWAYS include --timeout=300, --cpu-boost, and resource flags in deploy commands.
# ALWAYS include 'entrypoint: gcloud' for every cloud-sdk step.
# ALWAYS use TWO steps for env vars: clear first, then deploy with new values.
# """
    
#     try:
#         response = llm.invoke(prompt)
#         config_content = response.content.strip()
        
#         # Clean up if LLM added markdown
#         if config_content.startswith("```yaml"):
#             config_content = config_content.split("```yaml")[1].split("```")[0].strip()
#         elif config_content.startswith("```yml"):
#             config_content = config_content.split("```yml")[1].split("```")[0].strip()
#         elif config_content.startswith("```"):
#             content_split = config_content.split("```")
#             if len(content_split) >= 3:
#                 config_content = content_split[1].strip()
        
#         # VALIDATION AND FIXING OF IMAGE TAGS
#         print("\n🔍 Validating image tags...")
        
#         issues_found = 0
        
#         # Pattern 1: ANY pkg.dev path ending with : followed by non-word character
#         pattern1 = r'((?:us-|europe-|asia-)[a-z0-9-]+\.pkg\.dev/[a-zA-Z0-9$_/-]+):(?!\w)'
#         matches1 = list(re.finditer(pattern1, config_content))
#         if matches1:
#             print(f"⚠️  Found {len(matches1)} images with colons but no tag - fixing...")
#             config_content = re.sub(pattern1, r'\1:latest', config_content)
#             issues_found += len(matches1)
        
#         # Pattern 2: pkg.dev followed by colon at end of line
#         pattern2 = r'((?:us-|europe-|asia-)[a-z0-9-]+\.pkg\.dev/[a-zA-Z0-9$_/-]+):\s*$'
#         matches2 = list(re.finditer(pattern2, config_content, re.MULTILINE))
#         if matches2:
#             print(f"⚠️  Found {len(matches2)} images with colons at line end - fixing...")
#             config_content = re.sub(pattern2, r'\1:latest', config_content, flags=re.MULTILINE)
#             issues_found += len(matches2)
        
#         # BRUTE FORCE FIX: Simple string replacements
#         if 'analysis' in state and 'applications' in state['analysis']:
#             for app in state['analysis']['applications']:
#                 app_name = app['name']
#                 old_pattern = f"apps/{app_name}:"
#                 new_pattern = f"apps/{app_name}:latest"
                
#                 temp_content = config_content
#                 temp_content = temp_content.replace(f"{new_pattern}", "###ALREADY_FIXED###")
#                 count = temp_content.count(old_pattern)
#                 if count > 0:
#                     print(f"⚠️  Fixing {count} occurrences of '{old_pattern}'")
#                     temp_content = temp_content.replace(old_pattern, new_pattern)
#                     issues_found += count
#                 temp_content = temp_content.replace("###ALREADY_FIXED###", new_pattern)
#                 config_content = temp_content
        
#         # Clean up any double-tag artifacts
#         config_content = config_content.replace(':latest:latest', ':latest')
        
#         if issues_found > 0:
#             print(f"✅ Fixed {issues_found} image tag issues")
#         else:
#             print("✅ All images have proper tags")
        
#         # VALIDATION: Remove PORT from environment variables
#         print("\n🔍 Checking for PORT environment variable...")
#         port_pattern = r'--set-env-vars=([^\'"\n]*\bPORT=\d+[^\'"\n]*)'
#         port_matches = list(re.finditer(port_pattern, config_content, re.IGNORECASE))
        
#         if port_matches:
#             print(f"⚠️  Found {len(port_matches)} instances of PORT in env vars - removing...")
#             for match in port_matches:
#                 env_string = match.group(1)
#                 env_vars = env_string.split(',')
#                 filtered_vars = [v for v in env_vars if not v.strip().upper().startswith('PORT=')]
                
#                 if filtered_vars:
#                     new_env_string = ','.join(filtered_vars)
#                     config_content = config_content.replace(
#                         f"--set-env-vars={env_string}",
#                         f"--set-env-vars={new_env_string}"
#                     )
#                 else:
#                     config_content = config_content.replace(f"--set-env-vars={env_string}", "")
#             print(f"✅ Removed PORT from {len(port_matches)} deployment commands")
#         else:
#             print("✅ No PORT environment variable found")
        
#         # VALIDATION: Remove secret references
#         print("\n🔍 Checking for secret references...")
#         config_content = re.sub(r'--set-secrets=[^\s\'\"]+', '', config_content)
#         config_content = re.sub(r'--set-secrets=[\'\"][^\'\"]+[\'\"]', '', config_content)
#         print("✅ No secret references")
        
#         # VALIDATION: Fix -build-arg typo (should be --build-arg)
#         print("\n🔍 Checking for build-arg typos...")
#         # Use regex to replace only standalone -build-arg (not --build-arg or ---build-arg)
#         # Match -build-arg that is not preceded by another dash
#         pattern = r'(?<!-)-build-arg'
#         matches = list(re.finditer(pattern, config_content))
#         if matches:
#             print(f"⚠️  Found {len(matches)} instances of '-build-arg' typo - fixing to '--build-arg'")
#             config_content = re.sub(pattern, '--build-arg', config_content)
#             print(f"✅ Fixed {len(matches)} build-arg typos")
#         else:
#             print("✅ No build-arg typos found")
        
#         # Also check for triple-dash typos (---build-arg) and fix them
#         triple_dash_count = config_content.count('---build-arg')
#         if triple_dash_count > 0:
#             print(f"⚠️  Found {triple_dash_count} instances of '---build-arg' typo - fixing to '--build-arg'")
#             config_content = config_content.replace('---build-arg', '--build-arg')
#             print(f"✅ Fixed {triple_dash_count} triple-dash build-arg typos")
        
#         # VALIDATION: Check for gcloud commands in docker build steps
#         print("\n🔍 Checking for gcloud commands in docker build steps...")
#         try:
#             import yaml
#             yaml_data = yaml.safe_load(config_content)
#             docker_build_fixed = 0
            
#             for i, step in enumerate(yaml_data.get('steps', [])):
#                 step_name = step.get('name', '')
#                 step_id = step.get('id', f'step-{i}')
#                 args = step.get('args', [])
                
#                 # Check if this is a docker build step
#                 if 'cloud-builders/docker' in step_name and 'build' in str(args).lower():
#                     # Check if args contain gcloud commands or substitutions that might execute gcloud
#                     args_str = ' '.join(str(arg) for arg in args)
                    
#                     # Check for gcloud commands, command substitutions, or backticks in build args
#                     problematic_patterns = ['gcloud', '$(', '`', '$(gcloud']
#                     has_problem = any(pattern in args_str for pattern in problematic_patterns)
                    
#                     if has_problem and ('--build-arg' in args_str or '-build-arg' in args_str):
#                         print(f"⚠️  Step {i} ({step_id}): Found gcloud command/substitution in docker build args - this will fail!")
#                         print(f"   Docker build steps cannot execute gcloud commands")
#                         print(f"   Removing problematic build args...")
                        
#                         # Fix by removing problematic build args
#                         fixed_args = []
#                         skip_next = False
#                         for j, arg in enumerate(args):
#                             if skip_next:
#                                 skip_next = False
#                                 continue
                            
#                             if arg == '--build-arg' and j + 1 < len(args):
#                                 next_arg = args[j + 1]
#                                 # Check if next_arg contains problematic patterns
#                                 if any(pattern in str(next_arg) for pattern in problematic_patterns):
#                                     print(f"   ⚠️  Removing problematic build-arg: {str(next_arg)[:80]}...")
#                                     skip_next = True
#                                     continue
#                                 else:
#                                     fixed_args.append(arg)
#                             elif not any(pattern in str(arg) for pattern in problematic_patterns):
#                                 fixed_args.append(arg)
                        
#                         if len(fixed_args) < len(args):
#                             step['args'] = fixed_args
#                             docker_build_fixed += 1
#                             print(f"   ✅ Fixed docker build step by removing gcloud commands")
#                             print(f"   ⚠️  NOTE: Backend URL should be retrieved in a separate step before build")
#                             print(f"   ⚠️  NOTE: For React apps, consider using runtime env vars or a placeholder URL")
            
#             if docker_build_fixed > 0:
#                 config_content = yaml.dump(yaml_data, default_flow_style=False, sort_keys=False)
#                 print(f"✅ Fixed {docker_build_fixed} docker build steps with gcloud commands")
#             else:
#                 print("✅ No gcloud commands found in docker build steps")
#         except Exception as e:
#             print(f"⚠️  Could not validate docker build steps: {e}")
        
#         # VALIDATION: Fix incorrect 'dir' paths in build steps
#         print("\n🔍 Checking for correct 'dir' paths in build steps...")
#         if 'analysis' in state and 'applications' in state['analysis']:
#             for app in state['analysis']['applications']:
#                 app_location = app.get('location', '').strip()
#                 if app_location:
#                     # Normalize the path - use forward slashes for YAML
#                     normalized_location = app_location.replace('\\', '/').rstrip('/')
#                     # Extract just the directory name for matching
#                     app_dir_name = os.path.basename(normalized_location)
                    
#                     # Check if dir field uses incorrect path
#                     # Pattern: dir: 'web' when it should be dir: 'Github/web' or vice versa
#                     # We need to ensure the dir matches the actual app location
#                     dir_pattern = rf"dir:\s*['\"]?{re.escape(app_dir_name)}['\"]?"
#                     if re.search(dir_pattern, config_content):
#                         # Check if the full path is different
#                         if normalized_location != app_dir_name:
#                             # Replace dir: 'web' with dir: 'Github/web' (or whatever the full path is)
#                             old_dir = f"dir: '{app_dir_name}'"
#                             new_dir = f"dir: '{normalized_location}'"
#                             if old_dir in config_content:
#                                 print(f"   ⚠️  Fixing 'dir' path for {app['name']}: '{app_dir_name}' -> '{normalized_location}'")
#                                 config_content = config_content.replace(old_dir, new_dir)
#                             old_dir_quoted = f'dir: "{app_dir_name}"'
#                             new_dir_quoted = f'dir: "{normalized_location}"'
#                             if old_dir_quoted in config_content:
#                                 print(f"   ⚠️  Fixing 'dir' path for {app['name']}: \"{app_dir_name}\" -> \"{normalized_location}\"")
#                                 config_content = config_content.replace(old_dir_quoted, new_dir_quoted)
#         print("✅ 'dir' paths validated")
        
#         # VALIDATION: Fix clear-env-vars steps to handle non-existent services
#         print("\n🔍 Checking for clear-env-vars steps that might fail on non-existent services...")
#         try:
#             import yaml
#             yaml_data = yaml.safe_load(config_content)
#             clear_env_fixed = 0
            
#             for i, step in enumerate(yaml_data.get('steps', [])):
#                 step_id = step.get('id', '')
#                 step_name = step.get('name', '')
#                 # Check for old format: cloud-sdk with direct update, or cloud-sdk with bash entrypoint that might not work
#                 if 'clear-env' in step_id and ('cloudsdktool/cloud-sdk' in step_name or 'cloud-builders/gcloud' in step_name):
#                     args = step.get('args', [])
#                     entrypoint = step.get('entrypoint', '')
                    
#                     # Check if it's using the old format (direct gcloud update without check)
#                     if 'services' in args and 'update' in args and '--clear-env-vars' in str(args):
#                         # Extract service name and region from args
#                         service_name = None
#                         region = None
#                         for j, arg in enumerate(args):
#                             if arg == '--region':
#                                 region = args[j + 1] if j + 1 < len(args) else 'us-central1'
#                             elif j > 0 and args[j-1] not in ['run', 'services', 'update', '--region'] and not arg.startswith('-'):
#                                 if not service_name:
#                                     service_name = arg
                        
#                         if service_name and region:
#                             print(f"⚠️  Step {i} ({step_id}): Converting to safe clear-env-vars format")
#                             step['name'] = 'gcr.io/cloud-builders/gcloud'
#                             step['entrypoint'] = '/bin/bash'
#                             step['args'] = [
#                                 '-c',
#                                 f'gcloud run services describe {service_name} --region={region} --format="value(metadata.name)" >/dev/null 2>&1 && gcloud run services update {service_name} --region={region} --clear-env-vars || echo "Service does not exist, skipping clear-env-vars"'
#                             ]
#                             clear_env_fixed += 1
#                     # Also fix if entrypoint is 'bash' instead of '/bin/bash' or if using wrong image
#                     elif entrypoint in ['bash', 'sh'] and 'cloudsdktool/cloud-sdk' in step_name:
#                         # Extract service name and region from the bash command
#                         bash_cmd = ' '.join(args) if isinstance(args, list) else str(args)
#                         match = re.search(r"describe\s+(\w+)\s+--region=(\w+)", bash_cmd)
#                         if match:
#                             service_name = match.group(1)
#                             region = match.group(2)
#                             print(f"⚠️  Step {i} ({step_id}): Fixing bash entrypoint and image")
#                             step['name'] = 'gcr.io/cloud-builders/gcloud'
#                             step['entrypoint'] = '/bin/bash'
#                             step['args'] = [
#                                 '-c',
#                                 f'gcloud run services describe {service_name} --region={region} --format="value(metadata.name)" >/dev/null 2>&1 && gcloud run services update {service_name} --region={region} --clear-env-vars || echo "Service does not exist, skipping clear-env-vars"'
#                             ]
#                             clear_env_fixed += 1
            
#             if clear_env_fixed > 0:
#                 config_content = yaml.dump(yaml_data, default_flow_style=False, sort_keys=False)
#                 print(f"✅ Fixed {clear_env_fixed} clear-env-vars steps to handle non-existent services")
#             else:
#                 print("✅ All clear-env-vars steps are safe")
#         except Exception as e:
#             print(f"⚠️  Could not validate clear-env-vars steps: {e}")
        
#         # VALIDATION: Check that build steps use correct Docker image
#         print("\n🔍 Validating Docker build steps use correct image...")
#         import yaml
#         try:
#             yaml_data = yaml.safe_load(config_content)
#             build_steps_fixed = 0
#             bash_steps_fixed = 0
            
#             for i, step in enumerate(yaml_data.get('steps', [])):
#                 step_id = step.get('id', '')
#                 step_name = step.get('name', '')
#                 entrypoint = step.get('entrypoint', '')
#                 args = step.get('args', [])
                
#                 # Check if this is a build step (id contains "build-")
#                 if 'build-' in step_id.lower() and step_name:
#                     # Build steps should use gcr.io/cloud-builders/docker
#                     if 'cloudsdktool/cloud-sdk' in step_name or 'cloud-builders/gcloud' in step_name:
#                         print(f"⚠️  Step {i} ({step_id}): Wrong image for build step - fixing to docker builder")
#                         step['name'] = 'gcr.io/cloud-builders/docker'
#                         build_steps_fixed += 1
#                     elif 'cloud-builders/docker' not in step_name:
#                         # If it's not docker and not gcloud, it might be wrong
#                         print(f"⚠️  Step {i} ({step_id}): Unexpected image '{step_name}' for build step - fixing to docker builder")
#                         step['name'] = 'gcr.io/cloud-builders/docker'
#                         build_steps_fixed += 1
                
#                 # Check for bash commands using wrong image (get-backend-url, etc.)
#                 if step_name and 'cloudsdktool/cloud-sdk' in step_name:
#                     # Check if args contain '-c' (bash command)
#                     if isinstance(args, list) and '-c' in args:
#                         print(f"⚠️  Step {i} ({step_id}): Bash command using wrong image - fixing to gcloud builder")
#                         step['name'] = 'gcr.io/cloud-builders/gcloud'
#                         if entrypoint != '/bin/bash':
#                             step['entrypoint'] = '/bin/bash'
#                         bash_steps_fixed += 1
#                     # Check if entrypoint is bash but using cloudsdktool
#                     elif entrypoint in ['bash', '/bin/bash', 'sh', '/bin/sh']:
#                         print(f"⚠️  Step {i} ({step_id}): Bash entrypoint with wrong image - fixing to gcloud builder")
#                         step['name'] = 'gcr.io/cloud-builders/gcloud'
#                         if entrypoint not in ['/bin/bash', '/bin/sh']:
#                             step['entrypoint'] = '/bin/bash'
#                         bash_steps_fixed += 1
            
#             if build_steps_fixed > 0 or bash_steps_fixed > 0:
#                 config_content = yaml.dump(yaml_data, default_flow_style=False, sort_keys=False)
#                 if build_steps_fixed > 0:
#                     print(f"✅ Fixed {build_steps_fixed} build steps to use correct Docker image")
#                 if bash_steps_fixed > 0:
#                     print(f"✅ Fixed {bash_steps_fixed} bash command steps to use correct image")
#             else:
#                 print("✅ All build steps use correct Docker image")
#         except Exception as e:
#             print(f"⚠️  Could not validate build step images: {e}")
        
#         # VALIDATION: Check for required Cloud Run flags and ENTRYPOINT
#         print("\n🔍 Validating Cloud Run deployment flags and entrypoint...")
        
#         try:
#             yaml_data = yaml.safe_load(config_content)
            
#             required_flags = ['--timeout', '--cpu-boost', '--memory', '--cpu']
            
#             for i, step in enumerate(yaml_data.get('steps', [])):
#                 step_name = step.get('name', '')
                
#                 if 'cloudsdktool/cloud-sdk' in step_name:
#                     args = step.get('args', [])
                    
#                     # CRITICAL: Check for entrypoint
#                     if 'entrypoint' not in step:
#                         print(f"⚠️  Step {i}: MISSING ENTRYPOINT - adding 'entrypoint: gcloud'")
#                         step['entrypoint'] = 'gcloud'
#                         print(f"   ✅ Added entrypoint")
#                     elif step['entrypoint'] != 'gcloud':
#                         print(f"⚠️  Step {i}: Wrong entrypoint '{step['entrypoint']}' - fixing to 'gcloud'")
#                         step['entrypoint'] = 'gcloud'
#                     else:
#                         print(f"✅ Step {i}: Entrypoint 'gcloud' present")
                    
#                     # Check if this is a deploy command
#                     if 'deploy' in args:
#                         missing_flags = []
#                         for flag in required_flags:
#                             if not any(flag in str(arg) for arg in args):
#                                 missing_flags.append(flag)
                        
#                         if missing_flags:
#                             print(f"⚠️  Step {i}: Missing flags: {', '.join(missing_flags)}")
#                             print(f"   Adding required flags...")
                            
#                             # Add missing flags
#                             if '--timeout' not in str(args):
#                                 args.append('--timeout=300')
#                             if '--cpu-boost' not in str(args):
#                                 args.append('--cpu-boost')
#                             if '--memory' not in str(args):
#                                 args.append('--memory=512Mi')
#                             if '--cpu' not in str(args):
#                                 args.append('--cpu=1')
#                             if '--max-instances' not in str(args):
#                                 args.append('--max-instances=10')
#                             if '--min-instances' not in str(args):
#                                 args.append('--min-instances=0')
                            
#                             step['args'] = args
#                             print(f"   ✅ Added missing flags")
#                         else:
#                             print(f"✅ Step {i}: All required flags present")
            
#             # Convert back to YAML
#             config_content = yaml.dump(yaml_data, default_flow_style=False, sort_keys=False)
            
#         except Exception as e:
#             print(f"⚠️  Could not validate flags: {e}")
        
#         # Validate the YAML
#         try:
#             yaml_data = yaml.safe_load(config_content)
#             print(f"\n✅ YAML is valid with {len(yaml_data.get('steps', []))} steps")
#         except yaml.YAMLError as e:
#             print(f"⚠️  YAML validation warning: {e}")
        
#         state['cloudbuild_config'] = config_content
        
#         # Save to repository
#         repo_path = state['repo_local_path']
#         cloudbuild_path = os.path.join(repo_path, 'cloudbuild.yaml')
#         with open(cloudbuild_path, 'w', encoding='utf-8') as f:
#             f.write(config_content)
        
#         print("✅ Cloud Build configuration generated and saved")
#         print(f"   Location: {cloudbuild_path}")
        
#         # Print a preview
#         print("\n📄 Preview of cloudbuild.yaml:")
#         print("-" * 60)
#         print(config_content[:1500])
#         if len(config_content) > 1500:
#             print("... (truncated)")
#         print("-" * 60)
        
#         state['current_step'] = 'config_ready'
        
#     except Exception as e:
#         print(f"❌ Cloud Build config generation failed: {e}")
#         state['errors'].append(f"Cloud Build config failed: {e}")
#         state['current_step'] = 'failed'
    
#     return state

# def upload_source_to_gcs(state: DeploymentState) -> DeploymentState:
#     """Upload source code to GCS for Cloud Build (optional step)"""
#     print(f"\n{'='*60}")
#     print(f"📤 STEP 7: Preparing Source")
#     print(f"{'='*60}")
    
#     # This step is now optional - we'll submit directly
#     # Just verify the repository exists
#     repo_path = state['repo_local_path']
    
#     if not repo_path or not os.path.exists(repo_path):
#         print(f"⚠️  Repository path not valid: {repo_path}")
#         state['errors'].append(f"Repository path invalid: {repo_path}")
#         state['current_step'] = 'upload_failed'
#         return state
    
#     print(f"✅ Source ready at: {repo_path}")
#     print(f"   Will submit directly to Cloud Build")
#     state['current_step'] = 'source_ready'
    
#     return state

# def trigger_cloud_build(state: DeploymentState) -> DeploymentState:
#     """Trigger Cloud Build to build and deploy"""
#     print(f"\n{'='*60}")
#     print(f"🚀 STEP 8: Triggering Cloud Build")
#     print(f"{'='*60}")
    
#     try:
#         repo_path = state['repo_local_path']
        
#         if not repo_path or not os.path.exists(repo_path):
#             print(f"❌ Repository path not valid: {repo_path}")
#             state['errors'].append(f"Repository path invalid: {repo_path}")
#             state['current_step'] = 'build_failed'
#             return state
        
#         cloudbuild_path = os.path.join(repo_path, 'cloudbuild.yaml')
#         if not os.path.exists(cloudbuild_path):
#             print(f"❌ cloudbuild.yaml not found at: {cloudbuild_path}")
#             state['errors'].append("cloudbuild.yaml not found")
#             state['current_step'] = 'build_failed'
#             return state
        
#         print("⏳ Submitting build to Cloud Build...")
#         print(f"   Working directory: {repo_path}")
        
#         # Test if gcloud is available
#         try:
#             test_result = subprocess.run(
#                 'gcloud version',
#                 capture_output=True,
#                 text=True,
#                 shell=True,
#                 timeout=10
#             )
#             if test_result.returncode != 0:
#                 raise FileNotFoundError("gcloud not working")
#             print(f"   ✅ gcloud CLI detected")
#         except Exception as e:
#             print(f"❌ gcloud CLI not accessible: {e}")
#             state['errors'].append("gcloud CLI not accessible from Python")
#             state['current_step'] = 'build_failed'
#             return state
        
#         # Build command as a single string for shell=True
#         cmd = f'gcloud builds submit --config=cloudbuild.yaml --project={state["gcp_project_id"]} --region={state["gcp_region"]} .'
        
#         print(f"   Command: {cmd}")
#         print(f"   This will take 5-15 minutes...\n")
        
#         # Run command with shell=True for Windows PATH compatibility
#         result = subprocess.run(
#             cmd,
#             capture_output=True,
#             text=True,
#             cwd=repo_path,
#             shell=True,  # Required for Windows to find gcloud in PATH
#             timeout=600  # 10 minute timeout for submission
#         )
        
#         output = result.stdout + result.stderr
        
#         # Print real-time output for user feedback
#         if output:
#             print("📋 Build Output:")
#             print("-" * 60)
#             # Print first 2000 chars
#             print(output[:2000])
#             if len(output) > 2000:
#                 print("... (truncated)")
#             print("-" * 60)
        
#         if result.returncode == 0 or 'Created' in output or 'ID:' in output:
#             # Extract build ID from output
#             import re
            
#             patterns = [
#                 r'ID:\s+([a-f0-9-]+)',
#                 r'id:\s+([a-f0-9-]+)',
#                 r'BUILD\s+([a-f0-9-]+)',
#                 r'/builds/([a-f0-9-]+)',
#                 r'Created \[https://.*?/builds/([a-f0-9-]+)\]'
#             ]
            
#             build_id = None
#             for pattern in patterns:
#                 match = re.search(pattern, output, re.IGNORECASE)
#                 if match:
#                     build_id = match.group(1)
#                     break
            
#             if build_id:
#                 state['build_id'] = build_id
#                 state['build_log_url'] = f"https://console.cloud.google.com/cloud-build/builds/{build_id}?project={state['gcp_project_id']}"
                
#                 print(f"\n✅ Build triggered successfully!")
#                 print(f"   Build ID: {build_id}")
#                 print(f"   Logs: {state['build_log_url']}")
#             else:
#                 print(f"\n✅ Build submitted!")
#                 print(f"   Check: https://console.cloud.google.com/cloud-build/builds?project={state['gcp_project_id']}")
#                 state['build_id'] = 'submitted'
#                 state['build_log_url'] = f"https://console.cloud.google.com/cloud-build/builds?project={state['gcp_project_id']}"
            
#             print(f"\n⏳ Build is in progress...")
#             print(f"   This may take 5-15 minutes...")
            
#             state['build_status'] = 'WORKING'
#             state['current_step'] = 'building'
            
#         else:
#             print(f"\n❌ Build submission failed!")
#             print(f"\n📋 Full Error Output:")
#             print(result.stderr)
            
#             # Common error help
#             error_msg = result.stderr.lower()
#             if 'api not enabled' in error_msg or 'api is not enabled' in error_msg:
#                 print("\n💡 Fix: Enable Cloud Build API:")
#                 print(f"   gcloud services enable cloudbuild.googleapis.com --project={state['gcp_project_id']}")
#             elif 'permission' in error_msg or 'denied' in error_msg:
#                 print("\n💡 Fix: Check permissions:")
#                 print("   gcloud auth list")
#                 print(f"   gcloud config set project {state['gcp_project_id']}")
#             elif 'repository' in error_msg and ('not' in error_msg or 'does not exist' in error_msg):
#                 print("\n💡 Fix: Create Artifact Registry:")
#                 print(f"   gcloud artifacts repositories create apps --repository-format=docker --location={state['gcp_region']} --project={state['gcp_project_id']}")
#             elif 'billing' in error_msg:
#                 print("\n💡 Fix: Enable billing:")
#                 print(f"   https://console.cloud.google.com/billing/linkedaccount?project={state['gcp_project_id']}")
#             elif 'invalid image name' in error_msg or 'could not parse reference' in error_msg:
#                 print("\n💡 Fix: Image tag issue detected!")
#                 print("   The cloudbuild.yaml has incomplete image tags.")
#                 print(f"   Check the file at: {cloudbuild_path}")
#                 print("   Ensure all images end with :latest or :$SHORT_SHA")
#             elif 'port' in error_msg and 'reserved' in error_msg:
#                 print("\n💡 Fix: PORT environment variable issue!")
#                 print("   The deployment tried to set PORT, which is reserved by Cloud Run.")
#                 print("   This should have been caught earlier - check the cloudbuild.yaml")
#             elif 'exec:' in error_msg and 'executable file not found' in error_msg:
#                 print("\n💡 Fix: Entrypoint issue detected!")
#                 print("   The cloudbuild.yaml is missing 'entrypoint: gcloud' for cloud-sdk steps.")
#                 print(f"   Check the file at: {cloudbuild_path}")
#                 print("   Add 'entrypoint: gcloud' to all cloudsdktool/cloud-sdk steps")
#             elif 'already been set with a different type' in error_msg or 'cannot update environment variable' in error_msg:
#                 print("\n💡 Fix: Environment variable type conflict!")
#                 print("   A Cloud Run service already exists with environment variables set differently.")
#                 print("   Options:")
#                 print("   1. Delete the service: gcloud run services delete SERVICE_NAME --region=us-central1")
#                 print("   2. Use the two-step approach: clear env vars first, then deploy")
#                 print("   3. The agent should automatically use the two-step approach - check cloudbuild.yaml")
#             elif 'at most one of' in error_msg and ('clear-env-vars' in error_msg or 'set-env-vars' in error_msg):
#                 print("\n💡 Fix: Conflicting env var flags detected!")
#                 print("   You cannot use --clear-env-vars and --set-env-vars in the same command.")
#                 print("   Use TWO separate steps:")
#                 print("   1. gcloud run services update SERVICE --clear-env-vars")
#                 print("   2. gcloud run deploy SERVICE --set-env-vars=...")
            
#             state['errors'].append(f"Cloud Build submission failed")
#             state['current_step'] = 'build_failed'
        
#     except subprocess.TimeoutExpired:
#         print(f"❌ Command timeout!")
#         print("   Build submission took too long (>10 minutes)")
#         state['errors'].append("Build submission timeout")
#         state['current_step'] = 'build_failed'
        
#     except FileNotFoundError as e:
#         print(f"❌ gcloud command not found: {e}")
#         print("\n💡 Troubleshooting:")
#         print("   1. Restart PowerShell/Terminal")
#         print("   2. Or run: refreshenv (if you have Chocolatey)")
#         print("   3. Or log out and log back in")
#         state['errors'].append("gcloud CLI not accessible")
#         state['current_step'] = 'build_failed'
        
#     except Exception as e:
#         print(f"❌ Failed to trigger Cloud Build: {e}")
#         import traceback
#         traceback.print_exc()
#         state['errors'].append(f"Cloud Build trigger failed: {str(e)}")
#         state['current_step'] = 'build_failed'
    
#     return state

# def monitor_build(state: DeploymentState) -> DeploymentState:
#     """Monitor Cloud Build progress"""
#     print(f"\n{'='*60}")
#     print(f"👀 STEP 9: Monitoring Build")
#     print(f"{'='*60}")
    
#     if state['current_step'] == 'build_failed':
#         return state
    
#     try:
#         from google.cloud import cloudbuild_v1
        
#         client = cloudbuild_v1.CloudBuildClient()
#         build_id = state.get('build_id')
        
#         if not build_id or build_id in ['unknown', 'submitted']:
#             print("⚠️  Build ID not available for monitoring")
#             print("   Check build status in Cloud Console")
#             state['current_step'] = 'monitor_skipped'
#             return state
        
#         print(f"Monitoring build: {build_id}")
#         print("Status checks every 30 seconds...")
        
#         max_wait = 1800  # 30 minutes
#         start_time = time.time()
#         last_status = None
        
#         while time.time() - start_time < max_wait:
#             try:
#                 build = client.get_build(
#                     project_id=state['gcp_project_id'],
#                     id=build_id
#                 )
                
#                 status = build.status.name
                
#                 if status != last_status:
#                     timestamp = time.strftime('%H:%M:%S')
#                     print(f"   [{timestamp}] Status: {status}")
#                     last_status = status
                
#                 state['build_status'] = status
                
#                 if status == 'SUCCESS':
#                     print(f"\n✅ Build completed successfully!")
#                     state['current_step'] = 'build_complete'
#                     return state
                    
#                 elif status in ['FAILURE', 'TIMEOUT', 'CANCELLED', 'INTERNAL_ERROR']:
#                     print(f"\n❌ Build failed with status: {status}")
#                     if state.get('build_log_url'):
#                         print(f"   View logs: {state['build_log_url']}")
#                     state['errors'].append(f"Build failed: {status}")
#                     state['current_step'] = 'build_failed'
#                     return state
                
#             except Exception as e:
#                 print(f"   Error checking build status: {e}")
            
#             time.sleep(30)
        
#         print(f"\n⏰ Monitoring timeout (30 minutes)")
#         if state.get('build_log_url'):
#             print(f"   Build may still be running. Check: {state['build_log_url']}")
#         state['current_step'] = 'monitor_timeout'
        
#     except Exception as e:
#         print(f"❌ Monitoring failed: {e}")
#         state['errors'].append(f"Build monitoring failed: {e}")
#         state['current_step'] = 'monitor_failed'
    
#     return state

# def get_deployed_urls(state: DeploymentState) -> DeploymentState:
#     """Get URLs of deployed Cloud Run services"""
#     print(f"\n{'='*60}")
#     print(f"🌐 STEP 10: Getting Service URLs")
#     print(f"{'='*60}")
    
#     if state['current_step'] not in ['build_complete', 'monitor_skipped', 'monitor_timeout']:
#         print("⚠️  Skipping URL retrieval due to build issues")
#         return state
    
#     try:
#         from google.cloud import run_v2
        
#         client = run_v2.ServicesClient()
#         deployed_services = {}
        
#         print("Fetching deployed service URLs...\n")
        
#         # Check if analysis exists and has applications
#         if 'analysis' not in state or 'applications' not in state['analysis']:
#             print("⚠️  No analysis data available - skipping URL retrieval")
#             state['current_step'] = 'complete'
#             return state
        
#         if not state['analysis']['applications']:
#             print("⚠️  No applications found in analysis - skipping URL retrieval")
#             state['current_step'] = 'complete'
#             return state
        
#         for app in state['analysis']['applications']:
#             service_name = app['name']
            
#             try:
#                 service_path = f"projects/{state['gcp_project_id']}/locations/{state['gcp_region']}/services/{service_name}"
#                 service = client.get_service(name=service_path)
                
#                 deployed_services[service_name] = service.uri
#                 print(f"   ✅ {service_name}: {service.uri}")
                
#             except Exception as e:
#                 print(f"   ⚠️  {service_name}: Not found yet")
#                 # Try to get URL via gcloud as fallback
#                 try:
#                     result = subprocess.run(
#                         ['gcloud', 'run', 'services', 'describe', service_name,
#                          '--region', state['gcp_region'],
#                          '--project', state['gcp_project_id'],
#                          '--format=value(status.url)'],
#                         capture_output=True,
#                         text=True,
#                         timeout=10
#                     )
#                     if result.returncode == 0 and result.stdout.strip():
#                         url = result.stdout.strip()
#                         deployed_services[service_name] = url
#                         print(f"   ✅ {service_name}: {url}")
#                 except Exception:
#                     pass
        
#         state['deployed_services'] = deployed_services
#         state['current_step'] = 'complete'
        
#         if not deployed_services:
#             print("\n⚠️  No service URLs retrieved yet.")
#             print("   Services may still be initializing.")
#             print("   Check Cloud Console in a few minutes:")
#             print(f"   https://console.cloud.google.com/run?project={state['gcp_project_id']}")
        
#     except Exception as e:
#         print(f"❌ Failed to get service URLs: {e}")
#         state['errors'].append(f"Failed to get URLs: {e}")
#         state['current_step'] = 'complete_with_errors'
    
#     return state

# # ============= BUILD GRAPH =============

# def create_deployment_agent():
#     """Create and compile the LangGraph agent"""
    
#     workflow = StateGraph(DeploymentState)
    
#     # Add all nodes
#     workflow.add_node("clone_repo", clone_and_analyze_repo)
#     workflow.add_node("analyze", llm_analyze_repository)
#     workflow.add_node("plan", llm_generate_deployment_plan)
#     workflow.add_node("validate_port", validate_and_fix_port_listening)
#     workflow.add_node("generate_dockerfiles", llm_generate_dockerfiles)
#     workflow.add_node("generate_cloudbuild", llm_generate_cloudbuild_config)
#     workflow.add_node("upload_source", upload_source_to_gcs)
#     workflow.add_node("trigger_build", trigger_cloud_build)
#     workflow.add_node("monitor_build", monitor_build)
#     workflow.add_node("get_urls", get_deployed_urls)
    
#     # Define the workflow
#     workflow.add_edge("clone_repo", "analyze")
#     workflow.add_edge("analyze", "plan")
#     workflow.add_edge("plan", "validate_port")
#     workflow.add_edge("validate_port", "generate_dockerfiles")
#     workflow.add_edge("generate_dockerfiles", "generate_cloudbuild")
#     workflow.add_edge("generate_cloudbuild", "upload_source")
#     workflow.add_edge("upload_source", "trigger_build")
#     workflow.add_edge("trigger_build", "monitor_build")
#     workflow.add_edge("monitor_build", "get_urls")
#     workflow.add_edge("get_urls", END)
    
#     # Set entry point
#     workflow.set_entry_point("clone_repo")
    
#     return workflow.compile()

# # ============= MAIN EXECUTION =============

# if __name__ == "__main__":
#     print("\n" + "="*60)
#     print("🚀 Deployment Agent - Direct Execution")
#     print("="*60)
#     print("\nUse main.py for interactive deployment")
#     print("This file contains the agent logic only\n")




from typing import TypedDict, List, Dict
from langgraph.graph import StateGraph, END
from langchain_google_vertexai import ChatVertexAI
import os
import json
import subprocess
import git
from pathlib import Path
from dotenv import load_dotenv
import vertexai
from google.auth import default
import time

load_dotenv()

GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCP_REGION = os.getenv("GCP_REGION", "us-central1")
VERTEX_AI_LOCATION = os.getenv("VERTEX_AI_LOCATION", GCP_REGION)
SERVICE_ACCOUNT_KEY = r"C:\Users\gudladhana.harshith\Pictures\Deployment\gcp_credits.json"

if not GCP_PROJECT_ID:
    raise ValueError("GCP_PROJECT_ID not found in environment variables")

class DeploymentState(TypedDict):
    repo_url: str
    branch: str
    gcp_project_id: str
    gcp_region: str
    repo_local_path: str
    repo_structure: str
    analysis: Dict
    backend_dockerfile_content: str
    backend_cloudbuild_content: str
    backend_url: str
    backend_deployed: bool
    frontend_dockerfile_content: str
    frontend_cloudbuild_content: str
    frontend_url: str
    frontend_deployed: bool
    messages: List[Dict]
    errors: List[str]
    current_step: str

try:
    if SERVICE_ACCOUNT_KEY and os.path.exists(SERVICE_ACCOUNT_KEY):
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = SERVICE_ACCOUNT_KEY
    
    credentials, project = default()
    vertexai.init(project=GCP_PROJECT_ID, location=VERTEX_AI_LOCATION, credentials=credentials)
    
    llm = ChatVertexAI(
        model="gemini-2.5-pro",
        temperature=0.1,
        max_retries=3,
        project=GCP_PROJECT_ID,
        location=VERTEX_AI_LOCATION,
        credentials=credentials
    )
except Exception as e:
    raise RuntimeError(f"Failed to initialize Vertex AI: {e}")

def clone_repository(state: DeploymentState) -> DeploymentState:
    print(f"\nSTEP 1: Cloning Repository")
    
    repo_path = f"/tmp/deploy_{int(time.time())}" if os.name != 'nt' else f"C:\\Temp\\deploy_{int(time.time())}"
    
    try:
        git.Repo.clone_from(state['repo_url'], repo_path, branch=state['branch'], depth=1)
        state['repo_local_path'] = repo_path
        print(f"Cloned to: {repo_path}")
        state['current_step'] = 'cloned'
    except Exception as e:
        print(f"Clone failed: {e}")
        state['errors'].append(f"Clone failed: {e}")
        state['current_step'] = 'failed'
    
    return state

def analyze_structure(state: DeploymentState) -> DeploymentState:
    print(f"\nSTEP 2: Analyzing Repository")
    
    repo_path = state['repo_local_path']
    backend_dir = None
    frontend_dir = None
    
    if os.path.exists(os.path.join(repo_path, 'backend')):
        backend_dir = 'backend'
    elif os.path.exists(os.path.join(repo_path, 'server')):
        backend_dir = 'server'
    
    if os.path.exists(os.path.join(repo_path, 'web')):
        frontend_dir = 'web'
    elif os.path.exists(os.path.join(repo_path, 'frontend')):
        frontend_dir = 'frontend'
    elif os.path.exists(os.path.join(repo_path, 'client')):
        frontend_dir = 'client'
    
    state['analysis'] = {
        'backend_dir': backend_dir,
        'frontend_dir': frontend_dir,
        'has_backend': backend_dir is not None,
        'has_frontend': frontend_dir is not None
    }
    
    print(f"Backend: {backend_dir or 'Not found'}")
    print(f"Frontend: {frontend_dir or 'Not found'}")
    state['current_step'] = 'analyzed'
    return state

def create_backend_dockerfile(state: DeploymentState) -> DeploymentState:
    print(f"\nSTEP 3: Generating Backend Dockerfile")
    
    if not state['analysis']['has_backend']:
        print("No backend detected, skipping")
        state['current_step'] = 'backend_dockerfile_skipped'
        return state
    
    backend_dir = state['analysis']['backend_dir']
    dockerfile_path = os.path.join(state['repo_local_path'], backend_dir, 'Dockerfile')
    
    if os.path.exists(dockerfile_path):
        print("Dockerfile already exists")
        with open(dockerfile_path, 'r') as f:
            state['backend_dockerfile_content'] = f.read()
        state['current_step'] = 'backend_dockerfile_ready'
        return state
    
    dockerfile_content = """FROM node:20-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm install --production --legacy-peer-deps

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=deps /app/node_modules ./node_modules
COPY . .
USER node
CMD ["npm", "start"]
"""
    
    with open(dockerfile_path, 'w') as f:
        f.write(dockerfile_content)
    
    state['backend_dockerfile_content'] = dockerfile_content
    print("Backend Dockerfile generated")
    state['current_step'] = 'backend_dockerfile_ready'
    return state

def create_frontend_dockerfile(state: DeploymentState) -> DeploymentState:
    print(f"\nSTEP 4: Generating Frontend Dockerfile")
    
    if not state['analysis']['has_frontend']:
        print("No frontend detected, skipping")
        state['current_step'] = 'frontend_dockerfile_skipped'
        return state
    
    frontend_dir = state['analysis']['frontend_dir']
    dockerfile_path = os.path.join(state['repo_local_path'], frontend_dir, 'Dockerfile')
    
    if os.path.exists(dockerfile_path):
        print("Dockerfile already exists")
        with open(dockerfile_path, 'r') as f:
            state['frontend_dockerfile_content'] = f.read()
        state['current_step'] = 'frontend_dockerfile_ready'
        return state
    
    package_json_path = os.path.join(state['repo_local_path'], frontend_dir, 'package.json')
    build_output_dir = 'dist'
    
    if os.path.exists(package_json_path):
        with open(package_json_path, 'r') as f:
            try:
                package_data = json.load(f)
                if 'react-scripts' in str(package_data.get('dependencies', {})):
                    build_output_dir = 'build'
            except:
                pass
    
    dockerfile_content = f"""FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install --legacy-peer-deps
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN npm install -g serve
COPY --from=builder /app/{build_output_dir} ./{build_output_dir}
USER node
CMD ["sh", "-c", "serve -s {build_output_dir} -l $PORT"]
"""
    
    with open(dockerfile_path, 'w') as f:
        f.write(dockerfile_content)
    
    state['frontend_dockerfile_content'] = dockerfile_content
    print(f"Frontend Dockerfile generated (build output: {build_output_dir})")
    state['current_step'] = 'frontend_dockerfile_ready'
    return state

def create_backend_cloudbuild(state: DeploymentState) -> DeploymentState:
    print(f"\nSTEP 5: Generating Backend Cloud Build Config")
    
    if not state['analysis']['has_backend']:
        print("No backend, skipping")
        state['current_step'] = 'backend_cloudbuild_skipped'
        return state
    
    backend_dir = state['analysis']['backend_dir']
    region = state["gcp_region"]
    
    # Use raw string or escape $ to prevent f-string interpolation
    cloudbuild_content = f"""steps:
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'build'
      - '-t'
      - '{region}-docker.pkg.dev/$PROJECT_ID/apps/backend:latest'
      - '.'
    dir: '{backend_dir}'
    id: 'build-backend'
  
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'push'
      - '{region}-docker.pkg.dev/$PROJECT_ID/apps/backend:latest'
    id: 'push-backend'
    waitFor: ['build-backend']
  
  - name: 'gcr.io/cloud-builders/gcloud'
    entrypoint: '/bin/bash'
    args:
      - '-c'
      - |
        gcloud run services describe backend --region={region} --format="value(metadata.name)" >/dev/null 2>&1 && \\
        gcloud run services update backend --region={region} --clear-env-vars || \\
        echo "Service does not exist, skipping clear"
    id: 'clear-env-backend'
    waitFor: ['push-backend']
  
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - 'run'
      - 'deploy'
      - 'backend'
      - '--image={region}-docker.pkg.dev/$PROJECT_ID/apps/backend:latest'
      - '--region={region}'
      - '--platform=managed'
      - '--allow-unauthenticated'
      - '--timeout=300'
      - '--cpu-boost'
      - '--max-instances=10'
      - '--min-instances=0'
      - '--memory=512Mi'
      - '--cpu=1'
      - '--set-env-vars=NODE_ENV=production'
    id: 'deploy-backend'
    waitFor: ['clear-env-backend']

options:
  machineType: 'E2_HIGHCPU_8'

timeout: '1200s'
"""
    
    cloudbuild_path = os.path.join(state['repo_local_path'], 'cloudbuild-backend.yaml')
    with open(cloudbuild_path, 'w') as f:
        f.write(cloudbuild_content)
    
    state['backend_cloudbuild_content'] = cloudbuild_content
    print("Backend cloudbuild.yaml generated")
    state['current_step'] = 'backend_cloudbuild_ready'
    return state

def create_frontend_cloudbuild(state: DeploymentState) -> DeploymentState:
    print(f"\nSTEP 6: Generating Frontend Cloud Build Config")
    
    if not state['analysis']['has_frontend']:
        print("No frontend, skipping")
        state['current_step'] = 'frontend_cloudbuild_skipped'
        return state
    
    frontend_dir = state['analysis']['frontend_dir']
    region = state["gcp_region"]
    
    # Use $$ to escape $ in f-strings, or use raw string sections
    cloudbuild_content = f"""steps:
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'build'
      - '--build-arg'
      - 'REACT_APP_API_URL=${{_BACKEND_URL}}'
      - '--build-arg'
      - 'VITE_API_URL=${{_BACKEND_URL}}'
      - '--build-arg'
      - 'NEXT_PUBLIC_API_URL=${{_BACKEND_URL}}'
      - '-t'
      - '{region}-docker.pkg.dev/$PROJECT_ID/apps/frontend:latest'
      - '.'
    dir: '{frontend_dir}'
    id: 'build-frontend'
  
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'push'
      - '{region}-docker.pkg.dev/$PROJECT_ID/apps/frontend:latest'
    id: 'push-frontend'
    waitFor: ['build-frontend']
  
  - name: 'gcr.io/cloud-builders/gcloud'
    entrypoint: '/bin/bash'
    args:
      - '-c'
      - |
        gcloud run services describe frontend --region={region} --format="value(metadata.name)" >/dev/null 2>&1 && \\
        gcloud run services update frontend --region={region} --clear-env-vars || \\
        echo "Service does not exist, skipping clear"
    id: 'clear-env-frontend'
    waitFor: ['push-frontend']
  
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - 'run'
      - 'deploy'
      - 'frontend'
      - '--image={region}-docker.pkg.dev/$PROJECT_ID/apps/frontend:latest'
      - '--region={region}'
      - '--platform=managed'
      - '--allow-unauthenticated'
      - '--timeout=300'
      - '--cpu-boost'
      - '--max-instances=10'
      - '--min-instances=0'
      - '--memory=512Mi'
      - '--cpu=1'
      - '--set-env-vars=NODE_ENV=production,BACKEND_URL=${{_BACKEND_URL}}'
    id: 'deploy-frontend'
    waitFor: ['clear-env-frontend']

substitutions:
  _BACKEND_URL: 'http://localhost:8080'

options:
  machineType: 'E2_HIGHCPU_8'

timeout: '1200s'
"""
    
    cloudbuild_path = os.path.join(state['repo_local_path'], 'cloudbuild-frontend.yaml')
    with open(cloudbuild_path, 'w') as f:
        f.write(cloudbuild_content)
    
    state['frontend_cloudbuild_content'] = cloudbuild_content
    print("Frontend cloudbuild.yaml generated")
    state['current_step'] = 'frontend_cloudbuild_ready'
    return state

def deploy_backend_service(state: DeploymentState) -> DeploymentState:
    print(f"\nSTEP 7: Deploying Backend")
    
    if not state['analysis']['has_backend']:
        print("No backend, skipping")
        state['backend_deployed'] = False
        state['current_step'] = 'backend_deploy_skipped'
        return state
    
    repo_path = state['repo_local_path']
    
    try:
        print("Submitting backend build...")
        cmd = f'gcloud builds submit --config=cloudbuild-backend.yaml --project={state["gcp_project_id"]} --region={state["gcp_region"]} .'
        
        result = subprocess.run(
            cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            shell=True,
            timeout=900
        )
        
        if result.returncode == 0:
            print("Backend deployed successfully")
            
            url_cmd = f'gcloud run services describe backend --region={state["gcp_region"]} --project={state["gcp_project_id"]} --format=value(status.url)'
            url_result = subprocess.run(url_cmd, capture_output=True, text=True, shell=True)
            backend_url = url_result.stdout.strip()
            
            state['backend_url'] = backend_url
            state['backend_deployed'] = True
            print(f"Backend URL: {backend_url}")
            state['current_step'] = 'backend_deployed'
        else:
            print(f"Backend deployment failed: {result.stderr}")
            state['errors'].append(f"Backend deployment failed: {result.stderr}")
            state['backend_deployed'] = False
            state['current_step'] = 'backend_deploy_failed'
            
    except Exception as e:
        print(f"Backend deployment error: {e}")
        state['errors'].append(f"Backend deployment error: {e}")
        state['backend_deployed'] = False
        state['current_step'] = 'backend_deploy_failed'
    
    return state

def deploy_frontend_service(state: DeploymentState) -> DeploymentState:
    print(f"\nSTEP 8: Deploying Frontend")
    
    if not state['analysis']['has_frontend']:
        print("No frontend, skipping")
        state['frontend_deployed'] = False
        state['current_step'] = 'frontend_deploy_skipped'
        return state
    
    if not state.get('backend_url'):
        print("No backend URL available, using placeholder")
        backend_url = "http://localhost:8080"
    else:
        backend_url = state['backend_url']
    
    repo_path = state['repo_local_path']
    
    try:
        print(f"Submitting frontend build with backend URL: {backend_url}")
        cmd = f'gcloud builds submit --config=cloudbuild-frontend.yaml --project={state["gcp_project_id"]} --region={state["gcp_region"]} --substitutions=_BACKEND_URL={backend_url} .'
        
        result = subprocess.run(
            cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            shell=True,
            timeout=900
        )
        
        if result.returncode == 0:
            print("Frontend deployed successfully")
            
            url_cmd = f'gcloud run services describe frontend --region={state["gcp_region"]} --project={state["gcp_project_id"]} --format=value(status.url)'
            url_result = subprocess.run(url_cmd, capture_output=True, text=True, shell=True)
            frontend_url = url_result.stdout.strip()
            
            state['frontend_url'] = frontend_url
            state['frontend_deployed'] = True
            print(f"Frontend URL: {frontend_url}")
            state['current_step'] = 'complete'
        else:
            print(f"Frontend deployment failed: {result.stderr}")
            state['errors'].append(f"Frontend deployment failed: {result.stderr}")
            state['frontend_deployed'] = False
            state['current_step'] = 'frontend_deploy_failed'
            
    except Exception as e:
        print(f"Frontend deployment error: {e}")
        state['errors'].append(f"Frontend deployment error: {e}")
        state['frontend_deployed'] = False
        state['current_step'] = 'frontend_deploy_failed'
    
    return state

def print_summary(state: DeploymentState) -> DeploymentState:
    print(f"\nDEPLOYMENT SUMMARY")
    print(f"Project: {state['gcp_project_id']}")
    print(f"Region: {state['gcp_region']}")
    
    if state.get('backend_deployed'):
        print(f"\nBackend: {state.get('backend_url', 'N/A')}")
    
    if state.get('frontend_deployed'):
        print(f"Frontend: {state.get('frontend_url', 'N/A')}")
    
    if state.get('errors'):
        print(f"\nErrors:")
        for error in state['errors']:
            print(f"  {error}")
    
    state['current_step'] = 'done'
    return state

def create_deployment_agent():
    workflow = StateGraph(DeploymentState)
    
    workflow.add_node("clone", clone_repository)
    workflow.add_node("analyze", analyze_structure)
    workflow.add_node("gen_backend_dockerfile", create_backend_dockerfile)
    workflow.add_node("gen_frontend_dockerfile", create_frontend_dockerfile)
    workflow.add_node("gen_backend_cloudbuild", create_backend_cloudbuild)
    workflow.add_node("gen_frontend_cloudbuild", create_frontend_cloudbuild)
    workflow.add_node("deploy_backend", deploy_backend_service)
    workflow.add_node("deploy_frontend", deploy_frontend_service)
    workflow.add_node("summary", print_summary)
    
    workflow.add_edge("clone", "analyze")
    workflow.add_edge("analyze", "gen_backend_dockerfile")
    workflow.add_edge("gen_backend_dockerfile", "gen_frontend_dockerfile")
    workflow.add_edge("gen_frontend_dockerfile", "gen_backend_cloudbuild")
    workflow.add_edge("gen_backend_cloudbuild", "gen_frontend_cloudbuild")
    workflow.add_edge("gen_frontend_cloudbuild", "deploy_backend")
    workflow.add_edge("deploy_backend", "deploy_frontend")
    workflow.add_edge("deploy_frontend", "summary")
    workflow.add_edge("summary", END)
    
    workflow.set_entry_point("clone")
    
    return workflow.compile()