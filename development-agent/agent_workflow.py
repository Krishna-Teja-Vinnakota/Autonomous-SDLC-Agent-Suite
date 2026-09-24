"""
Developer Agent Workflow V2.0 - Complete Implementation
Direct modification → Validation + Auto-fix → HITL approval
"""

import os
import json
import re
from typing import TypedDict, Annotated, List, Dict, Any, Optional
from pathlib import Path
import operator

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_google_vertexai import ChatVertexAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

import requests
from requests.auth import HTTPBasicAuth
from github import Github
import git

from repo_indexer import create_indexer
from vector_search import create_vector_search
from incremental_indexer import create_incremental_indexer


class AgentState(TypedDict):
    """State for the developer agent workflow V2.0"""
    jira_ticket_id: str
    jira_content: Dict[str, Any]
    repo_path: str
    developer_id: str
    identified_files: List[str]
    file_vector_ids: Dict[str, Any]
    file_analysis: str
    modifications: Dict[str, str]  # {file_path: modified_content}
    validation_report: Dict[str, Any]  # NEW: Validation results
    approval_status: str
    modification_feedback: str
    pr_url: Optional[str]
    current_stage: str
    error_message: Optional[str]
    messages: Annotated[List, operator.add]
    iteration_count: int


class DeveloperAgent:
    """Enhanced Developer Agent V2.0 with Validation Agent"""
    
    def __init__(self, service_account_path: str, project_id: str):
        self.llm = ChatVertexAI(
            model_name="gemini-2.5-pro",
            project=project_id,
            max_output_tokens=50000,
            temperature=0.1
        )
        
        self.jira_base_url = os.getenv("JIRA_BASE_URL")
        self.jira_email = os.getenv("JIRA_EMAIL")
        self.jira_token = os.getenv("JIRA_API_TOKEN")
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.github_repo_url = os.getenv("GITHUB_REPO_URL")
        self.github_base_branch = os.getenv("GITHUB_BASE_BRANCH", "main")
        
        # Initialize vector search and incremental indexer
        qdrant_url = os.getenv("QDRANT_URL")
        qdrant_api_key = os.getenv("QDRANT_API_KEY")
        collection_name = os.getenv("QDRANT_COLLECTION_NAME", "code_repository")
        
        self.indexer = create_incremental_indexer(
            service_account_path, project_id,
            qdrant_url, qdrant_api_key, collection_name
        )
        
        self.vector_search = create_vector_search(
            service_account_path, project_id,
            qdrant_url, qdrant_api_key, collection_name
        )
        
        self.workflow = self._create_workflow()
        self.memory = MemorySaver()
        self.app = self.workflow.compile(
            checkpointer=self.memory, 
            interrupt_before=["wait_for_file_approval", "wait_for_validation_approval"]
        )
    
    def _create_workflow(self):
        """Create the enhanced workflow with validation agent"""
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("fetch_jira", self.fetch_jira_ticket)
        workflow.add_node("setup_incremental_session", self.setup_incremental_session)
        workflow.add_node("analyze_repo", self.analyze_repo_and_identify_files)
        workflow.add_node("wait_for_file_approval", self.wait_for_file_approval)
        workflow.add_node("modify_code_directly", self.modify_code_directly)
        workflow.add_node("validate_and_autofix", self.validate_and_autofix)
        workflow.add_node("wait_for_validation_approval", self.wait_for_validation_approval)
        workflow.add_node("handle_human_feedback", self.handle_human_feedback)
        workflow.add_node("create_pr", self.create_github_pr)
        workflow.add_node("handle_error", self.handle_error)
        
        # Set entry point
        workflow.set_entry_point("fetch_jira")
        
        # Add edges
        workflow.add_edge("fetch_jira", "setup_incremental_session")
        workflow.add_edge("setup_incremental_session", "analyze_repo")
        workflow.add_edge("analyze_repo", "wait_for_file_approval")
        workflow.add_conditional_edges(
            "wait_for_file_approval",
            self.route_after_file_approval,
            {
                "approved": "modify_code_directly",
                "rejected": END
            }
        )
        workflow.add_edge("modify_code_directly", "validate_and_autofix")
        workflow.add_edge("validate_and_autofix", "wait_for_validation_approval")
        
        # Conditional edges for validation approval
        workflow.add_conditional_edges(
            "wait_for_validation_approval",
            self.route_after_validation,
            {
                "approved": "create_pr",
                "rejected": END,
                "feedback": "handle_human_feedback"
            }
        )
        
        workflow.add_edge("handle_human_feedback", "validate_and_autofix")
        workflow.add_edge("create_pr", END)
        workflow.add_edge("handle_error", END)
        
        return workflow

    def fetch_jira_ticket(self, state: AgentState) -> AgentState:
        """Fetch JIRA ticket details"""
        try:
            print(f"🎫 [fetch_jira_ticket] Fetching ticket: {state['jira_ticket_id']}")
            
            if not all([self.jira_base_url, self.jira_email, self.jira_token]):
                raise Exception("JIRA configuration incomplete. Please check JIRA_BASE_URL, JIRA_EMAIL, and JIRA_API_TOKEN")
            
            auth = HTTPBasicAuth(self.jira_email, self.jira_token)
            
            url = f"{self.jira_base_url}/rest/api/2/issue/{state['jira_ticket_id']}"
            
            response = requests.get(url, auth=auth)
            
            if response.status_code == 404:
                raise Exception(f"JIRA ticket {state['jira_ticket_id']} not found")
            elif response.status_code != 200:
                raise Exception(f"Failed to fetch JIRA ticket: {response.status_code} - {response.text}")
            
            issue_data = response.json()
            
            jira_content = {
                "key": issue_data["key"],
                "summary": issue_data["fields"]["summary"],
                "description": issue_data["fields"]["description"] or "",
                "status": issue_data["fields"]["status"]["name"],
                "issue_type": issue_data["fields"]["issuetype"]["name"],
                "priority": issue_data["fields"]["priority"]["name"] if issue_data["fields"]["priority"] else "Medium",
                "assignee": issue_data["fields"]["assignee"]["displayName"] if issue_data["fields"]["assignee"] else "Unassigned",
                "components": [comp["name"] for comp in issue_data["fields"]["components"]] if issue_data["fields"]["components"] else []
            }
            
            state["jira_content"] = jira_content
            state["current_stage"] = "jira_fetched"
            state["messages"].append(f"✓ Fetched JIRA ticket: {jira_content['key']} - {jira_content['summary']}")
            
            print(f"🎫 [fetch_jira_ticket] Success: {jira_content['key']}")
            return state
            
        except Exception as e:
            error_msg = f"Error fetching JIRA ticket: {str(e)}"
            print(f"🎫 [fetch_jira_ticket] ERROR: {error_msg}")
            state["error_message"] = error_msg
            state["current_stage"] = "error"
            state["messages"].append(f"✗ {error_msg}")
            return state

    def setup_incremental_session(self, state: AgentState) -> AgentState:
        """Setup incremental indexing session"""
        try:
            print(f"🔧 [setup_incremental_session] Starting session setup...")
            
            repo_path = state["repo_path"]
            developer_id = state["developer_id"]
            jira_ticket_id = state["jira_ticket_id"]
            
            print(f"🔧 [setup_incremental_session] Repo: {repo_path}")
            print(f"🔧 [setup_incremental_session] Developer: {developer_id}")
            print(f"🔧 [setup_incremental_session] Ticket: {jira_ticket_id}")
            
            if not os.path.exists(repo_path):
                raise Exception(f"Repository path does not exist: {repo_path}")
            
            state["messages"].append("🔧 Setting up incremental indexing session...")
            
            # Check and update embeddings for any changed files
            print(f"🔧 [setup_incremental_session] Processing incremental updates...")
            
            session_result = self.indexer.start_developer_session(
                repo_path=repo_path,
                jira_ticket=jira_ticket_id,
                developer_id=developer_id
            )
            
            if session_result["status"] == "ready":
                tracked_files_found = session_result.get("tracked_files_found", 0)
                embeddings_refreshed = session_result.get("embeddings_refreshed", 0)
                is_indexed = session_result.get("is_indexed", False)
                
                if embeddings_refreshed > 0:
                    print(f"🔄 Refreshed embeddings for {embeddings_refreshed} files")
                    state["messages"].append(f"🔄 Updated embeddings for {embeddings_refreshed} modified files")
                
                if tracked_files_found > embeddings_refreshed:
                    deleted_files = tracked_files_found - embeddings_refreshed
                    print(f"🗑️ Cleaned up embeddings for {deleted_files} deleted files")
                    state["messages"].append(f"🗑️ Cleaned up embeddings for {deleted_files} deleted files")
                
                if tracked_files_found == 0:
                    state["messages"].append("✅ Repository embeddings are up-to-date")
                    
                if not is_indexed:
                    state["messages"].append("⚠️ Repository needs initial indexing")
                
                # Add session info to state
                state["session_info"] = session_result
                
            state["current_stage"] = "session_ready"
            print(f"🔧 [setup_incremental_session] Session ready")
            return state
            
        except Exception as e:
            error_msg = f"Error setting up incremental session: {str(e)}"
            print(f"❌ {error_msg}")
            state["error_message"] = error_msg
            state["current_stage"] = "error"
            state["messages"].append(f"❌ {error_msg}")
            return state

    def analyze_repo_and_identify_files(self, state: AgentState) -> AgentState:
        """Analyze repository and identify relevant files using semantic search"""
        try:
            print(f"🔎 [analyze_repo] Starting analysis...")
            
            jira_content = state["jira_content"]
            repo_path = state["repo_path"]
            
            # Create search query from JIRA content
            search_query = f"{jira_content['summary']} {jira_content['description']}"
            
            state["messages"].append("🔎 Analyzing codebase to identify relevant files...")
            
            # Search for relevant files
            print(f"🔎 [analyze_repo] Searching with query: {search_query[:100]}...")
            
            search_results = self.vector_search.search_relevant_files(
                query=search_query,
                repo_path=repo_path,
                top_k=12,  # Get top 12 files for analysis
                include_dependencies=True
            )
            
            if not search_results:
                raise Exception("No relevant files found for the given JIRA ticket")
            
            print(f"🔎 [analyze_repo] Found {len(search_results)} relevant files")
            
            # Use LLM to analyze and select files that need modification
            analysis_result = self._analyze_files_for_modification(
                jira_content, search_results
            )
            
            if not analysis_result["files_to_modify"]:
                raise Exception("No files identified for modification")
            
            # Store file vector IDs for tracking
            file_vector_ids = {}
            for file_result in search_results:
                if file_result["file_path"] in analysis_result["files_to_modify"]:
                    file_vector_ids[file_result["file_path"]] = [file_result.get("vector_db_id")]
            
            state["identified_files"] = analysis_result["files_to_modify"]
            state["file_vector_ids"] = file_vector_ids
            state["file_analysis"] = analysis_result["analysis"]
            state["current_stage"] = "files_identified"
            
            files_count = len(analysis_result["files_to_modify"])
            state["messages"].append(f"✓ Identified {files_count} files: {', '.join(analysis_result['files_to_modify'])}")
            
            print(f"🔎 [analyze_repo] Analysis complete - {files_count} files identified")
            
            # Auto-transition to awaiting approval
            state["current_stage"] = "awaiting_file_approval"
            
            return state
            
        except Exception as e:
            error_msg = f"Error analyzing repository: {str(e)}"
            print(f"❌ {error_msg}")
            state["error_message"] = error_msg
            state["current_stage"] = "error"
            state["messages"].append(f"❌ {error_msg}")
            return state

    def _analyze_files_for_modification(self, jira_content: Dict[str, Any], 
                                      search_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze search results to identify which files need modification based on JIRA ticket requirements"""
        
        # Prepare detailed file information for analysis
        files_info = []
        for result in search_results:
            file_path = result['file_path']
            file_ext = Path(file_path).suffix.lower()
            
            
            files_info.append(f"""
File: {file_path}
Summary: {result['file_summary']}
Key Functions: {', '.join(result.get('primary_functions', [])[:5])}
Similarity Score: {result['similarity_score']:.3f}
Size: {result.get('file_size_lines', 0)} lines
""")
        
        prompt = f"""**TASK:** You are an expert code analyst. Analyze these files to identify ONLY the files that need direct modification to implement the JIRA ticket requirements.

**JIRA TICKET ANALYSIS:**
- **ID:** {jira_content['key']}
- **Summary:** {jira_content['summary']}  
- **Description:** {jira_content['description']}
- **Type:** {jira_content.get('issue_type', 'Unknown')}
- **Components:** {', '.join(jira_content.get('components', []))}

**CANDIDATE FILES:**
{chr(10).join(files_info)}

**CRITICAL ANALYSIS REQUIREMENTS:**

1. **ANALYZE TICKET TITLE AND SCOPE INDICATORS**:
   - Title contains "BACKEND" → Backend-only scope (select only backend files)
   - Title contains "FRONTEND" or "UI" → Frontend-only scope (select only frontend files)
   - Title contains "FULL-STACK" or no scope indicator → May be full-stack

2. **CRITICAL: DO NOT WORRY ABOUT CROSS-LAYER DEPENDENCIES**:
   
   **When solving BACKEND tickets:**
   - Backend changes may affect frontend, but that's NOT YOUR CONCERN
   - Frontend will be updated in separate tickets later
   - Focus ONLY on backend files - ignore frontend implications
   
   **When solving FRONTEND tickets:**
   - Frontend may need new backend APIs, but they're ALREADY IMPLEMENTED
   - Don't select backend files - the APIs already exist
   - Focus ONLY on frontend files - ignore backend dependencies
   
   **Only select BOTH backend AND frontend files when:**
   - Ticket EXPLICITLY states "implement both backend and frontend"
   - Ticket EXPLICITLY mentions "full-stack changes required"
   - Acceptance criteria EXPLICITLY define both API and UI changes

3. **ANALYZE ACCEPTANCE CRITERIA PATTERNS** (Most Important):
   **BACKEND-ONLY indicators:**
   - "API must return/accept..." → API contract change only
   - "Database schema must support..." → Database change only  
   - "Endpoint should validate..." → Backend validation only
   - "WHEN querying by X THEN return Y" → API behavior definition
   - "POST /api/X must accept array" → API endpoint specification
   
   **FRONTEND-REQUIRED indicators:**
   - "User can see/click/select..." → UI interaction required
   - "GIVEN user logs into mobile app WHEN they view X THEN they see Y" → UI behavior
   - "Form must allow selection of multiple..." → UI component change
   - "Dashboard must display..." → Frontend rendering change
   - "Mobile app shows..." → Mobile UI change

4. **IDENTIFY SCOPE**: Determine if this is:
   - Backend-only change (API, database, server logic)
   - Frontend-only change (UI, components, styling) 
   - Full-stack change (both backend and frontend)
   - Configuration/Infrastructure change

5. **SELECT PRECISE FILES**: Choose ONLY files that need direct code modification:

   **BACKEND TICKETS (API, database, server logic):**
   - Select ONLY backend files (server.js, api files, database files)
   - DO NOT select frontend files even if they might be affected later
   - Frontend updates will be handled in separate tickets
   
   **FRONTEND TICKETS (UI, components, forms, dashboards):**
   - Select ONLY frontend files (React components, pages, services)
   - DO NOT select backend files even if they need to receive new data
   - Backend APIs are already implemented and ready
   
   **FULL-STACK TICKETS (explicitly mentions both):**
   - Select both backend and frontend files
   - Only when ticket explicitly requires implementing both layers
   
   **FILE PATH PRIORITY:**
   - If ticket mentions specific file names/paths → prioritize those files

6. **AVOID OVER-SELECTION - BE SURGICAL**: 
   - Don't select frontend files for backend-only tickets
   - Don't select backend files for frontend-only tickets  
   - Don't select files just because they "might be affected"
   - Don't select test files unless the ticket specifically mentions testing
   - Don't select files based on assumptions about what "might need to change"

7. **REMEMBER: STAY IN YOUR LANE**:
   - Backend ticket = Backend files only (frontend effects handled later)
   - Frontend ticket = Frontend files only (backend APIs already ready)
   - Full-stack ticket = Both (only when explicitly stated)

8. Do not include files just because they are "related" — include them only if changes are **required** to fulfill the ticket.
9. Do not include configuration, dependency, or documentation files unless the ticket explicitly requests changes to them.
10. Be **surgical and precise** — fewer files with clear purpose is better than a broad, uncertain selection.

11. **NO ARBITRARY LIMITS**: Select all files that truly need modification - don't artificially limit to 1-3 files if the ticket genuinely requires changes to more files

**OUTPUT FORMAT (JSON):**
{{
    "files_to_modify": ["file1.js", "file2.py"],
    "analysis": "Detailed explanation of why these specific files were selected, what changes are needed in each file, and why other files were excluded",
    "scope_category": "backend" | "frontend" | "fullstack" | "database" | "configuration",
    "reasoning": "Brief explanation of the ticket scope and selection logic"
}}

**EXAMPLES:**
- JIRA: "Add validation to user registration API" → Select backend API files only
- JIRA: "Change button color on login page" → Select frontend component/CSS files only  
- JIRA: "Allow users to edit profile and see changes immediately" → Select both backend (API) and frontend (UI) files
- JIRA: "Fix database schema for user table" → Select migration/schema files only

Be precise and conservative in file selection, but don't artificially limit the number of files if multiple files genuinely need modification."""

        messages = [HumanMessage(content=prompt)]
        response = self.llm.invoke(messages)
        
        try:
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                
                # Validate the result has required fields
                if "files_to_modify" in result and "analysis" in result:
                    return result
                else:
                    # Fallback with basic structure
                    return {
                        "files_to_modify": [search_results[0]["file_path"]] if search_results else [],
                        "analysis": "Selected most relevant file based on similarity score",
                        "scope_category": "unknown",
                        "reasoning": "Fallback selection due to parsing error"
                    }
            else:
                # Fallback: select top file
                return {
                    "files_to_modify": [search_results[0]["file_path"]] if search_results else [],
                    "analysis": "Selected most relevant file based on similarity score",
                    "scope_category": "unknown", 
                    "reasoning": "Fallback selection - no JSON found in response"
                }
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            print(f"⚠️ Error parsing file analysis result: {e}")
            # Fallback: select top file  
            return {
                "files_to_modify": [search_results[0]["file_path"]] if search_results else [],
                "analysis": "Selected most relevant file based on similarity score",
                "scope_category": "unknown",
                "reasoning": f"Fallback selection due to error: {str(e)}"
            }

    def wait_for_file_approval(self, state: AgentState) -> AgentState:
        """Wait for human approval of identified files"""
        state["current_stage"] = "awaiting_file_approval"
        return state

    def modify_code_directly(self, state: AgentState) -> AgentState:
        """Directly modify identified files based on JIRA requirements"""
        try:
            print(f"🔧 [modify_code_directly] Starting direct modification...")
            
            jira_content = state["jira_content"]
            repo_path = state["repo_path"]
            identified_files = state["identified_files"]
            
            if not identified_files:
                raise Exception("No files identified for modification")
            
            state["messages"].append(f"🔧 Modifying {len(identified_files)} files directly...")
            
            modifications = {}
            
            for file_path in identified_files:
                print(f"🔧 [modify_code_directly] Processing: {file_path}")
                
                full_path = os.path.join(repo_path, file_path)
                if not os.path.exists(full_path):
                    print(f"⚠ File not found: {full_path}")
                    continue
                
                # Read current file content
                with open(full_path, 'r', encoding='utf-8') as f:
                    current_content = f.read()
                
                # Generate modification using focused prompt
                modified_content = self._generate_targeted_modification(
                    file_path, current_content, jira_content, state
                )
                
                if modified_content and modified_content != current_content:
                    modifications[file_path] = modified_content
                    
                    # Write the modified file
                    with open(full_path, 'w', encoding='utf-8') as f:
                        f.write(modified_content)
                    
                    print(f"✓ Modified: {file_path}")
                    
                    # Update tracking in MongoDB
                    from file_tracker import file_tracker, get_repo_url_from_path, get_relative_path
                    repo_url = get_repo_url_from_path(repo_path)
                    relative_path = get_relative_path(full_path, repo_path)
                    vector_ids = state["file_vector_ids"].get(file_path, [])
                    
                    file_tracker.track_file_modification(
                        repo_url=repo_url,
                        file_path=relative_path,
                        developer_id=state["developer_id"],
                        jira_ticket=state["jira_ticket_id"],
                        modification_type='updated',
                        embedding_ids=vector_ids
                    )
                else:
                    print(f"⚠ No changes made to: {file_path}")
            
            state["modifications"] = modifications
            state["current_stage"] = "code_modified"
            state["messages"].append(f"✓ Modified {len(modifications)} files successfully")
            
            print(f"🔧 [modify_code_directly] Complete - {len(modifications)} files modified")
            return state
            
        except Exception as e:
            error_msg = f"Error in direct modification: {str(e)}"
            print(f"❌ {error_msg}")
            state["error_message"] = error_msg
            state["current_stage"] = "error"
            state["messages"].append(f"❌ {error_msg}")
            return state
    
    def _generate_targeted_modification(self, file_path: str, current_content: str, 
                                      jira_content: Dict[str, Any], state: AgentState) -> str:
        """Generate targeted code modification focused on specific JIRA requirements"""
        
        # Get file extension for context
        file_extension = Path(file_path).suffix.lower()
        
        prompt = f"""**TARGETED CODE MODIFICATION TASK:**

You are an expert developer. Make ONLY the specific changes required by the JIRA ticket. Do NOT rewrite the entire file.

**CRITICAL REQUIREMENTS:**

✅ **FOCUS ON JIRA TICKET ONLY**: Implement ONLY what the ticket specifically requests
✅ **MINIMAL CHANGES**: Modify only the code sections that need to change  
✅ **PRESERVE EVERYTHING ELSE**: Keep all existing functionality, imports, styles, comments exactly as they are
✅ **OUTPUT COMPLETE FILE**: Return the entire file with your targeted changes integrated
✅ **NO MARKDOWN**: Do not use ``` code fences in your response

**JIRA TICKET DETAILS:**
- **ID:** {jira_content['key']}
- **Summary:** {jira_content['summary']}
- **Description:** {jira_content['description']}
- **Type:** {jira_content.get('issue_type', 'Task')}

**FILE TO MODIFY:** {file_path} ({file_extension} file)

**CURRENT FILE CONTENT:**
{current_content}

**MODIFICATION INSTRUCTIONS:**

1. **READ THE JIRA TICKET CAREFULLY**: Understand exactly what needs to be implemented
2. **IDENTIFY TARGET AREAS**: Find the specific code sections that need modification
3. **MAKE SURGICAL CHANGES**: 
   - Add new functions/methods only if required
   - Modify existing functions only where necessary
   - Add new imports only if you use new libraries
   - Update configuration/constants only if required by the ticket

4. **COMMON CHANGE PATTERNS:**
   - **New Feature**: Add new function/component/endpoint as specified
   - **Bug Fix**: Modify the specific buggy logic only
   - **UI Change**: Update the specific UI element/styling mentioned
   - **Validation**: Add validation logic where specified
   - **API Change**: Modify the specific endpoint/route mentioned

5. **AVOID THESE MISTAKES:**
   ❌ Don't rewrite functions that don't need changes
   ❌ Don't change variable/function names unless required
   ❌ Don't add features not mentioned in the ticket
   ❌ Don't remove existing functionality
   ❌ Don't change code style/formatting unless required

**OUTPUT:** Return the complete file with your targeted modifications. Start with line 1 and end with the last line of the file."""

        messages = [HumanMessage(content=prompt)]
        response = self.llm.invoke(messages)
        
        # Clean response (remove markdown if accidentally added)
        modified_content = response.content.strip()
        
        # Remove markdown code fences if present
        if modified_content.startswith('```'):
            lines = modified_content.split('\n')
            # Find start and end of actual code
            start_idx = 0
            for i, line in enumerate(lines):
                if not line.strip().startswith('```'):
                    start_idx = i
                    break
            
            end_idx = len(lines)
            for i in range(len(lines) - 1, -1, -1):
                if not lines[i].strip().startswith('```'):
                    end_idx = i + 1
                    break
            
            modified_content = '\n'.join(lines[start_idx:end_idx])
        
        return modified_content.strip()
    
    def validate_and_autofix(self, state: AgentState) -> AgentState:
        """Validate modified files against JIRA requirements and apply auto-fixes"""
        try:
            print(f"🔍 [validate_and_autofix] Starting validation...")
            
            jira_content = state["jira_content"]
            repo_path = state["repo_path"]
            modifications = state["modifications"]
            
            if not modifications:
                raise Exception("No modifications to validate")
            
            state["messages"].append(f"🔍 Validating {len(modifications)} modified files...")
            
            validation_report = {
                "files_validated": len(modifications),
                "total_issues": 0,
                "auto_fixes_applied": 0,
                "validation_results": {}
            }
            
            # Validate each modified file
            for file_path, modified_content in modifications.items():
                print(f"🔍 [validate_and_autofix] Validating: {file_path}")
                
                validation_result, fixed_content = self._validate_against_jira_requirements(
                    file_path, modified_content, jira_content
                )
                
                # Count issues
                issues_count = len(validation_result.get("issues", []))
                validation_report["total_issues"] += issues_count
                
                # Apply auto-fixes if needed
                if fixed_content != modified_content:
                    print(f"🔧 [validate_and_autofix] Auto-fixing: {file_path}")
                    
                    # Write the auto-fixed file
                    full_path = os.path.join(repo_path, file_path)
                    with open(full_path, 'w', encoding='utf-8') as f:
                        f.write(fixed_content)
                    
                    # Update modifications with fixed content
                    modifications[file_path] = fixed_content
                    validation_report["auto_fixes_applied"] += 1
                
                validation_report["validation_results"][file_path] = validation_result
            
            state["modifications"] = modifications
            state["validation_report"] = validation_report
            state["current_stage"] = "awaiting_validation_approval"
            
            # Clear approval status for fresh approval
            state["approval_status"] = ""
            
            state["messages"].append("✅ Validation & Auto-fix Completed")
            
            print(f"🔍 [validate_and_autofix] Complete - {validation_report['total_issues']} issues found, {validation_report['auto_fixes_applied']} auto-fixes applied")
            
            return state
            
        except Exception as e:
            error_msg = f"Error in validation: {str(e)}"
            print(f"❌ {error_msg}")
            state["error_message"] = error_msg
            state["current_stage"] = "error"
            state["messages"].append(f"❌ {error_msg}")
            return state
    
    def _validate_against_jira_requirements(self, file_path: str, modified_content: str,
                                          jira_content: Dict[str, Any]) -> tuple:
        """Validate modified code against specific JIRA requirements with targeted auto-fixes"""
        
        validation_prompt = f"""**JIRA VALIDATION TASK:**

You are a code validation expert. Validate that the code changes correctly implement the JIRA ticket requirements.

**JIRA TICKET:**
- **ID:** {jira_content['key']}
- **Summary:** {jira_content['summary']}
- **Description:** {jira_content['description']}
- **Type:** {jira_content.get('issue_type', 'Task')}

**FILE:** {file_path}

**MODIFIED CODE:**
{modified_content}

**VALIDATION CRITERIA:**

1. **REQUIREMENT COMPLIANCE**: Does the code implement exactly what the JIRA ticket asks for?
2. **COMPLETENESS**: Are all aspects of the ticket requirement implemented?
3. **CORRECTNESS**: Is the implementation logic correct and bug-free?
4. **CONSISTENCY**: Does the implementation follow the existing code patterns?
5. **MISSING ELEMENTS**: Are there any obvious gaps in the implementation?

**VALIDATION PROCESS:**

1. Read the JIRA ticket requirements carefully
2. Analyze the modified code section by section
3. Check if each requirement is properly implemented
4. Identify any issues or missing implementations
5. If issues found, provide targeted fixes

**OUTPUT FORMAT:**

First, provide validation results in JSON:
```json
{{
    "requirements_satisfied": ["list of implemented requirements"],
    "requirements_missing": ["list of missing implementations"],
    "issues": [
        {{
            "type": "missing_implementation" | "incorrect_logic" | "incomplete_feature",
            "description": "Specific description of the issue",
            "location": "function/line where issue exists",
            "fixed": true/false
        }}
    ],
    "overall_status": "complete" | "incomplete" | "needs_fix"
}}
```

If fixes are needed, provide the COMPLETE fixed file:
FIXED_CODE_START
[Complete corrected file content - no markdown fences, just the code]
FIXED_CODE_END

**CRITICAL FIX REQUIREMENTS:**
✅ Output the COMPLETE file from first to last line
✅ Make ONLY the specific fixes needed for JIRA compliance  
✅ Preserve ALL existing functionality not related to the ticket
✅ Maintain the same code structure and style
✅ Do NOT add features not mentioned in the JIRA ticket
✅ Do NOT remove existing functionality

If the implementation is correct, provide only the JSON validation without fixes."""

        messages = [HumanMessage(content=validation_prompt)]
        response = self.llm.invoke(messages)
        
        response_text = response.content.strip()
        
        # Extract validation JSON
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        validation_result = {}
        
        if json_match:
            try:
                validation_result = json.loads(json_match.group(1))
            except json.JSONDecodeError:
                validation_result = {
                    "requirements_satisfied": [],
                    "requirements_missing": ["Could not parse validation results"],
                    "issues": [{"type": "validation_error", "description": "Failed to parse validation", "location": "unknown", "fixed": False}],
                    "overall_status": "incomplete"
                }
        else:
            # Try to find JSON without markdown
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    validation_result = json.loads(json_match.group())
                except json.JSONDecodeError:
                    validation_result = {
                        "requirements_satisfied": [],
                        "requirements_missing": ["Could not parse validation"],
                        "issues": [{"type": "validation_error", "description": "Invalid JSON format", "location": "unknown", "fixed": False}],
                        "overall_status": "incomplete"
                    }
            else:
                validation_result = {
                    "requirements_satisfied": [],
                    "requirements_missing": ["No validation response"],
                    "issues": [{"type": "validation_error", "description": "No validation performed", "location": "unknown", "fixed": False}],
                    "overall_status": "incomplete"
                }
        
        # Extract fixed code if present
        fixed_content = modified_content  # Default to original
        fixed_code_match = re.search(r'FIXED_CODE_START\s*(.*?)\s*FIXED_CODE_END', response_text, re.DOTALL)
        if fixed_code_match:
            fixed_content = fixed_code_match.group(1).strip()
            print(f"    🔧 Auto-fix content extracted for {file_path}")
        
        return validation_result, fixed_content
    
    def wait_for_validation_approval(self, state: AgentState) -> AgentState:
        """Wait for human approval after validation"""
        state["current_stage"] = "awaiting_validation_approval"
        return state
    
    def route_after_file_approval(self, state: AgentState) -> str:
        """Route after file approval based on user decision"""
        approval_status = state.get("approval_status", "")
        print(f"🔀 [route_after_file_approval] Approval status: '{approval_status}'")
        print(f"🔀 [route_after_file_approval] Full state keys: {list(state.keys())}")
        
        if approval_status == "approved":
            print(f"🔀 → Files approved, proceeding to modification")
            # Clear the approval status after using it
            state["approval_status"] = ""
            return "approved"
        elif approval_status == "rejected":
            print(f"🔀 → Files rejected, ending workflow")
            state["current_stage"] = "cancelled"
            state["messages"].append("❌ Workflow cancelled - files rejected by user")
            # Clear the approval status
            state["approval_status"] = ""
            return "rejected"
        else:
            print(f"🔀 → Unknown or empty approval status, THIS SHOULD NOT HAPPEN!")
            print(f"🔀 → State dump: {state}")
            # Don't default to approved - this is wrong
            raise Exception(f"Invalid approval status: '{approval_status}' - workflow state corrupted")

    def route_after_validation(self, state: AgentState) -> str:
        """Route after validation based on approval status"""
        approval_status = state.get("approval_status", "")
        print(f"🔀 [route_after_validation] Approval status: '{approval_status}'")
        
        # Clear approval_status after reading it to prevent confusion
        if approval_status == "approved":
            print(f"🔀 → Validation approved, creating PR")
            state["approval_status"] = ""  # Clear status
            return "approved"
        elif approval_status == "rejected":
            print(f"🔀 → Validation rejected, ending workflow")
            state["approval_status"] = ""  # Clear status
            return "rejected"
        elif approval_status == "feedback":
            print(f"🔀 → Human feedback provided, applying changes")
            # Don't clear status yet - handle_human_feedback will need it
            return "feedback"
        else:
            print(f"🔀 → No approval status, waiting for user input")
            return "feedback"  # Default to feedback state to wait for user
    
    def handle_human_feedback(self, state: AgentState) -> AgentState:
        """Handle human feedback and apply modifications"""
        try:
            print(f"💬 [handle_human_feedback] Processing human feedback...")
            
            feedback = state.get("modification_feedback", "")
            if not feedback or feedback.strip() == "":
                # Instead of error, just wait for feedback
                print("⏳ Waiting for human feedback...")
                state["current_stage"] = "awaiting_validation_approval"
                return state
            
            print(f"💬 [handle_human_feedback] Feedback: {feedback}")
            
            # Clear the feedback and approval status
            state["modification_feedback"] = ""
            state["approval_status"] = ""
            
            # Add feedback to messages
            state["messages"].append(f"💬 Processing feedback: {feedback}")
            
            # Increment iteration counter
            state["iteration_count"] = state.get("iteration_count", 0) + 1
            
            print(f"💬 [handle_human_feedback] Feedback processed, re-validating...")
            
            return state
            
        except Exception as e:
            error_msg = f"Error handling human feedback: {str(e)}"
            print(f"❌ {error_msg}")
            state["error_message"] = error_msg
            state["current_stage"] = "error"
            state["messages"].append(f"❌ {error_msg}")
            return state
    
    def _apply_human_feedback(self, file_path: str, current_content: str,
                             feedback: str, jira_content: Dict[str, Any]) -> str:
        """Apply human feedback to modify the file with targeted changes"""
        
        prompt = f"""**HUMAN FEEDBACK APPLICATION:**

Apply the specific feedback provided by the human reviewer while maintaining all existing functionality.

**HUMAN FEEDBACK:**
{feedback}

**ORIGINAL JIRA TICKET:**
- **ID:** {jira_content['key']}  
- **Summary:** {jira_content['summary']}
- **Description:** {jira_content['description']}

**FILE:** {file_path}

**CURRENT CONTENT:**
{current_content}

**INSTRUCTIONS:**

1. **UNDERSTAND THE FEEDBACK**: Read the human feedback carefully to understand what specific changes are requested
2. **APPLY TARGETED CHANGES**: Make only the changes mentioned in the feedback
3. **PRESERVE EVERYTHING ELSE**: Keep all existing code, functionality, and structure intact
4. **MAINTAIN QUALITY**: Ensure the changes integrate smoothly with existing code

**REQUIREMENTS:**
✅ Apply ONLY the changes requested in the feedback
✅ Output the COMPLETE file from first to last line
✅ Preserve ALL existing functionality not mentioned in feedback
✅ Maintain the same code style and patterns
✅ Keep all imports and dependencies unless feedback specifies changes
✅ Do NOT add markdown code fences in your response

**OUTPUT:** Return the complete updated file with the feedback changes applied."""

        messages = [HumanMessage(content=prompt)]
        response = self.llm.invoke(messages)
        
        return self._clean_llm_response(response.content)
    
    def _clean_llm_response(self, content: str) -> str:
        """Clean LLM response to extract just the code"""
        content = content.strip()
        
        # Remove markdown code fences if present
        if content.startswith('```'):
            lines = content.split('\n')
            # Find the first non-fence line
            start_idx = 0
            for i, line in enumerate(lines):
                if not line.strip().startswith('```'):
                    start_idx = i
                    break
            
            # Find the last non-fence line
            end_idx = len(lines)
            for i in range(len(lines) - 1, -1, -1):
                if not lines[i].strip().startswith('```'):
                    end_idx = i + 1
                    break
            
            content = '\n'.join(lines[start_idx:end_idx])
        
        return content.strip()
    
    def create_github_pr(self, state: AgentState) -> AgentState:
        """Create a pull request on GitHub"""
        try:
            print("🚀 Starting PR creation process...")
            
            repo_path = state["repo_path"]
            jira_content = state["jira_content"]
            
            print(f"📁 Repository path: {repo_path}")
            print(f"🎫 Jira content: {jira_content.get('key')} - {jira_content.get('summary')}")
            
            # Check if repository exists
            if not os.path.exists(repo_path):
                raise Exception(f"Repository path does not exist: {repo_path}")
            
            repo = git.Repo(repo_path)
            print(f"✓ Git repository loaded successfully")
            
            branch_name = f"fix/{jira_content['key'].lower()}-{jira_content['summary'][:30].replace(' ', '-').lower()}"
            branch_name = re.sub(r'[^a-z0-9\\-]', '', branch_name)
            print(f"🌿 Creating branch: {branch_name}")
            
            # Check if there are changes to commit
            if not repo.is_dirty() and not repo.untracked_files:
                print("⚠ No changes detected in repository")
                # Check if changes were actually made to identified files
                modified_files_exist = False
                for file_path in state.get("identified_files", []):
                    full_path = os.path.join(repo_path, file_path)
                    if os.path.exists(full_path):
                        # Check if file was modified recently (within last 10 minutes)
                        import time
                        file_mod_time = os.path.getmtime(full_path)
                        if time.time() - file_mod_time < 600:  # 10 minutes
                            modified_files_exist = True
                            break
                
                if not modified_files_exist:
                    raise Exception("No recent modifications found in identified files")
            
            # Check if branch already exists
            try:
                repo.heads[branch_name]
                # Branch exists, delete it first
                print(f"⚠ Branch {branch_name} already exists, deleting...")
                repo.delete_head(branch_name, force=True)
            except IndexError:
                # Branch doesn't exist, which is good
                pass
            
            # Create and checkout new branch
            new_branch = repo.create_head(branch_name)
            new_branch.checkout()
            print(f"✓ Created and checked out branch: {branch_name}")
            
            # Add all changes
            repo.git.add(A=True)
            print(f"✓ Added changes to staging area")
            
            # Commit changes
            commit_message = f"[{jira_content['key']}] {jira_content['summary']}"
            repo.index.commit(commit_message)
            print(f"✓ Committed changes: {commit_message}")
            
            # Push to remote
            origin = repo.remote(name='origin')
            try:
                origin.push(branch_name)
                print(f"✓ Pushed branch to remote: {branch_name}")
            except git.exc.GitCommandError as e:
                print(f"⚠ Push error: {e}")
                # Try to set upstream and push
                repo.git.push('--set-upstream', 'origin', branch_name)
                print(f"✓ Pushed branch with upstream: {branch_name}")
            
            # Create GitHub PR
            print(f"🔗 Creating GitHub PR...")
            
            if not self.github_token:
                raise Exception("GITHUB_TOKEN environment variable not set")
            if not self.github_repo_url:
                raise Exception("GITHUB_REPO_URL environment variable not set")
            
            # Parse GitHub repo info from URL
            import re
            github_url_pattern = r'github\.com[:/]([^/]+)/([^/.]+)'
            match = re.search(github_url_pattern, self.github_repo_url)
            if not match:
                raise Exception(f"Invalid GitHub repo URL format: {self.github_repo_url}")
            
            repo_owner = match.group(1)
            repo_name = match.group(2)
            print(f"🏢 GitHub repo: {repo_owner}/{repo_name}")
            
            g = Github(self.github_token)
            
            # Test GitHub authentication
            try:
                user = g.get_user()
                print(f"✓ GitHub authenticated as: {user.login}")
            except Exception as e:
                raise Exception(f"GitHub authentication failed: {e}")
            
            # Get the repository
            try:
                github_repo = g.get_repo(f"{repo_owner}/{repo_name}")
                print(f"✓ Found GitHub repository: {github_repo.full_name}")
            except Exception as e:
                raise Exception(f"Could not access GitHub repository {repo_owner}/{repo_name}: {e}")
            
            # Create PR
            pr_title = f"[{jira_content['key']}] {jira_content['summary']}"
            pr_body = f"""## Jira Ticket
**{jira_content['key']}**: {jira_content['summary']}

## Description
{jira_content.get('description', 'No description provided')}

## Changes Made
Modified the following files:
{chr(10).join(f"- `{f}`" for f in state.get('identified_files', []))}

## Validation Results
- Files validated: {state.get('validation_report', {}).get('files_validated', 0)}
- Issues found: {state.get('validation_report', {}).get('total_issues', 0)}
- Auto-fixes applied: {state.get('validation_report', {}).get('auto_fixes_applied', 0)}

## Type
- {jira_content.get('issue_type', 'Task')}

## Priority  
- {jira_content.get('priority', 'Medium')}

---
*This PR was automatically generated by the Developer Agent V2.0*
"""
            
            print(f"📝 Creating PR: {pr_title}")
            try:
                pr = github_repo.create_pull(
                    title=pr_title,
                    body=pr_body,
                    head=branch_name,
                    base=self.github_base_branch
                )
                
                state["pr_url"] = pr.html_url
                state["current_stage"] = "completed"
                state["messages"].append(f"✅ Pull Request created successfully: {pr.html_url}")
                
                print(f"🎉 PR created successfully: {pr.html_url}")
                
            except Exception as e:
                raise Exception(f"Failed to create PR: {e}")
            
            return state
            
        except Exception as e:
            error_msg = f"Error creating PR: {str(e)}"
            print(f"❌ {error_msg}")
            import traceback
            traceback.print_exc()
            
            state["error_message"] = error_msg
            state["current_stage"] = "error"
            state["messages"].append(f"❌ {error_msg}")
            return state
    
    def handle_error(self, state: AgentState) -> AgentState:
        """Handle errors"""
        print(f"❌ [handle_error] Error: {state.get('error_message')}")
        return state


def create_agent(service_account_path: str, project_id: str) -> DeveloperAgent:
    """Factory function to create developer agent"""
    return DeveloperAgent(service_account_path, project_id)