"""
Streamlit UI for Enhanced SDLC Automation
=========================================
Clean interface without verbose context engineering logs
"""

import streamlit as st
import json
import uuid
import operator
import sqlite3
from typing import TypedDict, Dict, List, Optional, Annotated
from datetime import datetime
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt, Command
from langchain_google_vertexai import ChatVertexAI
from google.oauth2 import service_account
import os

try:
    from jira import JIRA
    JIRA_INSTALLED = True
except ImportError:
    JIRA_INSTALLED = False

# ============================================================================
# Page Configuration
# ============================================================================

st.set_page_config(
    page_title="SDLC Automation",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# Configuration
# ============================================================================

SERVICE_ACCOUNT_FILE = 
API_TOKEN = 
EPIC_ISSUE_TYPE = "Epic"
STORY_ISSUE_TYPE = "Story"
TASK_ISSUE_TYPE = "Subtask"

# Initialize LLM
@st.cache_resource
def get_llm():
    if SERVICE_ACCOUNT_FILE and os.path.exists(SERVICE_ACCOUNT_FILE):
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        return ChatVertexAI(model_name="gemini-2.5-pro", credentials=credentials, temperature=0.4)
    else:
        return ChatVertexAI(model_name="gemini-2.5-pro", temperature=0.4)

llm = get_llm()

# ============================================================================
# Context Store (Silent Mode)
# ============================================================================

class PersistentContextStore:
    """Silent context store - no print statements"""
    
    def __init__(self, db_path: str = "sdlc_context.sqlite"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS requirement_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                requirement_type TEXT NOT NULL,
                compressed_requirement TEXT NOT NULL,
                priority TEXT,
                complexity TEXT,
                outcome_quality INTEGER,
                story_count INTEGER,
                task_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                access_count INTEGER DEFAULT 0
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS story_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                story_type TEXT NOT NULL,
                story_template TEXT NOT NULL,
                quality_score INTEGER,
                reuse_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tech_context_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                tech_stack TEXT NOT NULL,
                dependencies TEXT,
                patterns TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS compressed_requirements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                original_hash TEXT NOT NULL,
                compressed_text TEXT NOT NULL,
                key_features TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_type ON requirement_patterns(user_id, requirement_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_story_type ON story_templates(user_id, story_type, quality_score)")
        
        conn.commit()
        conn.close()
    
    def save_requirement_pattern(self, user_id: str, req_type: str, compressed_req: str, 
                                 priority: str, complexity: str, outcome_quality: int,
                                 story_count: int, task_count: int):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO requirement_patterns 
            (user_id, requirement_type, compressed_requirement, priority, complexity, 
             outcome_quality, story_count, task_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, req_type, compressed_req, priority, complexity, outcome_quality, story_count, task_count))
        conn.commit()
        conn.close()
    
    def get_similar_patterns(self, user_id: str, req_type: str, limit: int = 3):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT compressed_requirement, priority, complexity, outcome_quality, 
                   story_count, task_count
            FROM requirement_patterns
            WHERE user_id = ? AND requirement_type = ?
            ORDER BY outcome_quality DESC, created_at DESC
            LIMIT ?
        """, (user_id, req_type, limit))
        
        patterns = []
        for row in cursor.fetchall():
            patterns.append({
                "compressed_requirement": row[0],
                "priority": row[1],
                "complexity": row[2],
                "outcome_quality": row[3],
                "story_count": row[4],
                "task_count": row[5]
            })
        
        conn.close()
        return patterns
    
    def save_story_template(self, user_id: str, story_type: str, story_data: Dict, quality_score: int):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = conn.cursor()
        
        template = json.dumps({
            "title_pattern": story_data.get("title"),
            "user_story_pattern": story_data.get("user_story"),
            "ac_count": len(story_data.get("acceptance_criteria", [])),
            "tags": story_data.get("tags", [])
        })
        
        cursor.execute("""
            INSERT INTO story_templates (user_id, story_type, story_template, quality_score)
            VALUES (?, ?, ?, ?)
        """, (user_id, story_type, template, quality_score))
        conn.commit()
        conn.close()
    
    def get_relevant_story_templates(self, user_id: str, story_type: str, limit: int = 5):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT story_template, quality_score, reuse_count
            FROM story_templates
            WHERE user_id = ? AND story_type = ?
            ORDER BY quality_score DESC, reuse_count DESC
            LIMIT ?
        """, (user_id, story_type, limit))
        
        templates = []
        for row in cursor.fetchall():
            templates.append({
                "template": json.loads(row[0]),
                "quality_score": row[1],
                "reuse_count": row[2]
            })
        
        if templates:
            cursor.execute("""
                UPDATE story_templates 
                SET reuse_count = reuse_count + 1, last_used = CURRENT_TIMESTAMP
                WHERE user_id = ? AND story_type = ?
            """, (user_id, story_type))
            conn.commit()
        
        conn.close()
        return templates
    
    def cache_tech_context(self, user_id: str, tech_stack: List[str], dependencies: List[str]):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO tech_context_cache (user_id, tech_stack, dependencies)
            VALUES (?, ?, ?)
        """, (user_id, json.dumps(tech_stack), json.dumps(dependencies)))
        conn.commit()
        conn.close()
    
    def get_cached_tech_context(self, user_id: str):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT tech_stack, dependencies
            FROM tech_context_cache
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "tech_stack": json.loads(row[0]),
                "dependencies": json.loads(row[1])
            }
        return None

# ============================================================================
# Context Compression (Silent Mode)
# ============================================================================

class ContextCompressor:
    """Silent compressor - no print statements"""
    
    @staticmethod
    def compress_requirements(requirements: str, llm) -> Dict:
        compress_prompt = f"""
        Remove unnecessary parts and provide compressed summary of requirements.
        Focus on:
        1. Core functionality (bullet points)
        2. Key user roles
        3. Critical constraints
        4. Key features and important points
        5. Technical stack or other important requirements
        6. Specific business rules or acceptance criteria
        
        Requirements:
        ---
        {requirements}
        ---
        
        Provide JSON:
        {{
          "summary": "overview",
          "key_features": ["Feature 1", "Feature 2"],
          "user_roles": ["Role 1"],
          "constraints": ["Constraint 1"]
        }}
        """
        
        try:
            response = llm.invoke(compress_prompt)
            compressed = _extract_json(response)
            return compressed if compressed else {"summary": requirements[:200], "key_features": [], "user_roles": [], "constraints": []}
        except Exception:
            return {"summary": requirements[:200], "key_features": [], "user_roles": [], "constraints": []}
    
    @staticmethod
    def compress_analyzed_requirements(analyzed_data: Dict) -> Dict:
        return {
            "overview": analyzed_data.get("project_overview", "")[:150],
            "features": analyzed_data.get("key_features", [])[:5],
            "roles": analyzed_data.get("user_roles", [])[:3],
            "tech": analyzed_data.get("technical_stack", [])[:5]
        }
    
    @staticmethod
    def create_context_summary(state: Dict) -> str:
        summary_parts = []
        
        if state.get("requirement_type"):
            summary_parts.append(f"Type: {state['requirement_type']}")
        if state.get("priority"):
            summary_parts.append(f"Priority: {state['priority']}")
        if state.get("complexity"):
            summary_parts.append(f"Complexity: {state['complexity']}")
        if state.get("dependencies"):
            deps = ", ".join(state["dependencies"][:3])
            summary_parts.append(f"Deps: {deps}")
        
        return " | ".join(summary_parts)

# ============================================================================
# Hierarchical Context Loader (Silent Mode)
# ============================================================================

class HierarchicalContextLoader:
    """Silent loader - no print statements"""
    
    @staticmethod
    def load_global_context(state: Dict) -> str:
        compressed_req = state.get("compressed_requirements", {})
        
        global_context = f"""
GLOBAL CONTEXT (Shared across workflow):
Type: {state.get('requirement_type', 'N/A')}
Priority: {state.get('priority', 'N/A')}
Complexity: {state.get('complexity', 'N/A')}

Summary: {compressed_req.get('summary', 'N/A')}
Key Features: {', '.join(compressed_req.get('key_features', [])[:3])}
"""
        return global_context.strip()
    
    @staticmethod
    def load_business_context(state: Dict) -> str:
        if state.get("requirement_type") != "New Feature":
            return ""
        
        business_ctx = state.get("business_context", {})
        return f"""
BUSINESS CONTEXT:
Goal: {business_ctx.get('goal', 'N/A')[:100]}
Target User: {business_ctx.get('target_user', 'N/A')[:80]}
Value: {business_ctx.get('expected_value', 'N/A')[:80]}
""".strip()
    
    @staticmethod
    def load_technical_context(state: Dict) -> str:
        compressed_analysis = state.get("compressed_analysis", {})
        
        return f"""
TECHNICAL CONTEXT:
Tech Stack: {', '.join(compressed_analysis.get('tech', [])[:4])}
Dependencies: {', '.join(state.get('dependencies', [])[:3])}
""".strip()
    
    @staticmethod
    def load_story_context(state: Dict, past_templates: List) -> str:
        context = ""
        
        if past_templates:
            context += "\nPAST SUCCESSFUL PATTERNS:\n"
            for i, template in enumerate(past_templates[:2], 1):
                t = template["template"]
                context += f"{i}. Quality: {template['quality_score']}/10 | Pattern: {t.get('user_story_pattern', 'N/A')[:80]}\n"
        
        return context.strip()

# ============================================================================
# State Definition
# ============================================================================

class GraphState(TypedDict):
    raw_requirements: str
    requirement_type: str
    business_context: Optional[Dict]
    priority: str
    complexity: str
    dependencies: List[str]
    analyzed_requirements: Dict
    epic_info: Optional[Dict]
    created_epic_key: Optional[str]
    created_jira_tickets: Optional[Dict]
    pending_review_stories: List[Dict]
    approved_stories: Annotated[Dict[str, Dict], operator.ior]
    current_story_for_review: Optional[Dict]
    review_choice: str
    feedback: str
    generated_tasks: Dict[str, List[Dict]]
    output_format: str
    errors: Annotated[List[str], operator.add]
    compressed_requirements: Optional[Dict]
    compressed_analysis: Optional[Dict]
    context_summary: str
    similar_patterns: List[Dict]
    story_templates: List[Dict]
    cached_tech_context: Optional[Dict]
    token_savings: int

# ============================================================================
# Helper Functions
# ============================================================================

def _extract_json(response: BaseMessage) -> Optional[Dict]:
    content = response.content
    try:
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0].strip()
        else:
            json_str = content.strip()
        return json.loads(json_str)
    except (json.JSONDecodeError, IndexError):
        return None

# Initialize stores
context_store = PersistentContextStore()
compressor = ContextCompressor()
context_loader = HierarchicalContextLoader()

# ============================================================================
# Workflow Nodes (Silent Mode)
# ============================================================================

def compress_requirements_node(state: GraphState) -> GraphState:
    """Compress requirements silently"""
    requirements = state["raw_requirements"]
    original_tokens = len(requirements.split())
    
    compressed = compressor.compress_requirements(requirements, llm)
    state["compressed_requirements"] = compressed
    
    compressed_tokens = len(json.dumps(compressed).split())
    state["token_savings"] = original_tokens - compressed_tokens
    
    return state

def classify_requirement_enhanced(state: GraphState, config: RunnableConfig) -> GraphState:
    """Enhanced classification silently"""
    user_id = config["configurable"].get("user_id", "default")
    compressed_req = state["compressed_requirements"]
    
    classification_prompt = f"""
    Classify this requirement. Use ONLY the compressed context provided.
    
    Compressed Requirements:
    {json.dumps(compressed_req, indent=2)}
    
    Classify as: New Feature, Enhancement, Bug/Defect, Spike/Research, Technical Debt, Infrastructure/DevOps, or Documentation
    
    Also determine: Priority (Low/Medium/High/Urgent), Complexity (S/M/L/XL), Dependencies
    
    JSON format:
    {{
      "requirement_type": "...",
      "priority": "...",
      "complexity": "...",
      "dependencies": [],
      "reasoning": "..."
    }}
    """
    
    try:
        response = llm.invoke(classification_prompt)
        classification_data = _extract_json(response)
        
        if classification_data:
            state["requirement_type"] = classification_data.get("requirement_type", "New Feature")
            state["priority"] = classification_data.get("priority", "Medium")
            state["complexity"] = classification_data.get("complexity", "M")
            state["dependencies"] = classification_data.get("dependencies", [])
            
            similar_patterns = context_store.get_similar_patterns(user_id, state["requirement_type"], limit=3)
            state["similar_patterns"] = similar_patterns
        else:
            raise ValueError("Classification failed")
            
    except Exception as e:
        state["errors"].append(f"Classification error: {e}")
        state["requirement_type"] = "New Feature"
        state["priority"] = "Medium"
        state["complexity"] = "M"
        state["dependencies"] = []
        state["similar_patterns"] = []
    
    state["context_summary"] = compressor.create_context_summary(state)
    return state

def analyze_requirements_enhanced(state: GraphState) -> GraphState:
    """Enhanced analysis silently"""
    compressed_req = state["compressed_requirements"]
    context_summary = state["context_summary"]
    
    analysis_prompt = f"""
    Analyze these requirements. Be concise and clear.
    
    {context_summary}
    
    Compressed Requirements:
    {json.dumps(compressed_req, indent=2)}
    
    Provide concise analysis:
    {{
      "project_overview": "overall summary",
      "key_features": ["Key features"],
      "user_roles": ["key roles"],
      "technical_stack": ["technologies"],
      "constraints": ["constraints"]
    }}
    """
    
    try:
        response = llm.invoke(analysis_prompt)
        analyzed_data = _extract_json(response)
        
        if analyzed_data:
            state["analyzed_requirements"] = analyzed_data
            state["compressed_analysis"] = compressor.compress_analyzed_requirements(analyzed_data)
        else:
            raise ValueError("Analysis failed")
            
    except Exception as e:
        state["errors"].append(f"Analysis error: {e}")
        state["analyzed_requirements"] = {}
        state["compressed_analysis"] = {}
    
    return state

def extract_business_context_enhanced(state: GraphState) -> GraphState:
    """Extract business context silently"""
    if state["requirement_type"] != "New Feature":
        state["business_context"] = None
        return state
    
    compressed_req = state["compressed_requirements"]
    
    context_prompt = f"""
    Extract ONLY business context. Be concise.
    
    Requirements Summary: {compressed_req.get('summary', 'N/A')}
    Key Features: {', '.join(compressed_req.get('key_features', []))}
    
    Extract:
    {{
      "goal": "One sentence",
      "target_user": "One sentence",
      "business_problem": "One sentence",
      "expected_value": "One sentence",
      "success_metrics": ["2-3 metrics max"]
    }}
    """
    
    try:
        response = llm.invoke(context_prompt)
        context_data = _extract_json(response)
        
        if context_data:
            state["business_context"] = context_data
        else:
            raise ValueError("Extraction failed")
            
    except Exception as e:
        state["errors"].append(f"Business context error: {e}")
        state["business_context"] = {}
    
    return state

def generate_epic(state: GraphState) -> GraphState:
    """Generate Epic silently"""
    if state["requirement_type"] != "New Feature":
        state["epic_info"] = None
        return state
    
    business_context = state.get("business_context", {})
    compressed_analysis = state.get("compressed_analysis", {})
    
    epic_prompt = f"""
    Create an Epic using the following context.
    
    Business Context:
    {json.dumps(business_context, indent=2)}
    
    Technical Overview:
    {json.dumps(compressed_analysis, indent=2)}
    
    JSON:
    {{
      "epic_name": "...",
      "epic_description": "...",
      "acceptance_criteria": [],
      "business_value": "...",
      "related_links": {{}},
      "labels": []
    }}
    """
    
    try:
        response = llm.invoke(epic_prompt)
        epic_data = _extract_json(response)
        
        if epic_data:
            state["epic_info"] = epic_data
        else:
            raise ValueError("Epic generation failed")
            
    except Exception as e:
        state["errors"].append(f"Epic generation error: {e}")
        state["epic_info"] = None
    
    return state

def generate_user_stories_enhanced(state: GraphState, config: RunnableConfig) -> GraphState:
    """Generate stories silently"""
    user_id = config["configurable"].get("user_id", "default")
    req_type = state["requirement_type"]
    
    story_templates = context_store.get_relevant_story_templates(user_id, req_type, limit=5)
    state["story_templates"] = story_templates
    
    global_context = context_loader.load_global_context(state)
    story_context = context_loader.load_story_context(state, story_templates)
    compressed_analysis = state["compressed_analysis"]
    
    story_prompt = f"""
    Generate user stories using the following context.
    
    {global_context}
    
    {story_context}
    
    Analysis:
    {json.dumps(compressed_analysis, indent=4)}
    
    Generate stories following INVEST principles. Focus on:
    - Clear user value
    - Independent and negotiable
    - Valuable to end user
    - Estimable
    - Small enough to complete in a sprint
    - Testable acceptance criteria
    - Right-sized (not too big)
    
    IMPORTANT: Every story MUST have ALL fields populated:
    - id: unique identifier like "US-001"
    - title: short descriptive title
    - user_story: "As a [role], I want to [action], so that [benefit]"
    - description: detailed description
    - acceptance_criteria: array of testable criteria
    - priority: {state['priority']}
    - complexity: {state['complexity']}
    - tags: relevant tags
    - story_type: {req_type}
    
    JSON format (strictly follow this structure):
    {{
      "stories": [
        {{
          "id": "US-001",
          "title": "User Registration",
          "user_story": "As a customer, I want to register an account, so that I can make purchases",
          "description": "Detailed description here",
          "acceptance_criteria": [
            "Given a new user, When they fill the registration form, Then an account is created",
            "Given registration, When successful, Then user receives confirmation email"
          ],
          "priority": "{state['priority']}",
          "complexity": "{state['complexity']}",
          "tags": ["authentication", "user-management"],
          "story_type": "{req_type}"
        }}
      ]
    }}
    """
    
    try:
        response = llm.invoke(story_prompt)
        stories_data = _extract_json(response)
        
        if stories_data and "stories" in stories_data:
            validated_stories = []
            for story in stories_data["stories"]:
                if all(k in story for k in ["id", "title", "user_story", "description", "acceptance_criteria"]):
                    validated_stories.append(story)
            
            state["pending_review_stories"] = validated_stories
        else:
            raise ValueError("Story generation failed")
            
    except Exception as e:
        state["errors"].append(f"Story generation error: {e}")
        state["pending_review_stories"] = []
    
    return state

def validate_stories(state: GraphState) -> GraphState:
    """Validate stories silently"""
    stories = state["pending_review_stories"]
    
    if not stories:
        return state
    
    validated_stories = []
    for story in stories:
        required_fields = ["id", "title", "user_story", "acceptance_criteria"]
        if all(field in story and story[field] for field in required_fields):
            validated_stories.append(story)
    
    state["pending_review_stories"] = validated_stories
    return state

def human_review_gate(state: GraphState, config: RunnableConfig) -> GraphState:
    """Human review gate - handles interrupts"""
    pending = state["pending_review_stories"]
    
    if not pending:
        state["review_choice"] = "finalize"
        return state
    
    story_to_review = pending.pop(0)
    state["current_story_for_review"] = story_to_review
    state["pending_review_stories"] = pending
    
    payload = {"type": "review_story", "story": story_to_review}
    choice = interrupt(payload)
    
    state["review_choice"] = choice
    
    if choice == 'y':
        story_id = story_to_review.get("id")
        if story_id:
            state["approved_stories"][story_id] = story_to_review
        state["current_story_for_review"] = None
        
    elif choice == 'n':
        state["current_story_for_review"] = None
    
    return state

def regenerate_story_with_feedback(state: GraphState) -> GraphState:
    """Regenerate story with feedback"""
    current_story = state["current_story_for_review"]
    
    payload = {"type": "get_feedback", "story": current_story}
    feedback = interrupt(payload)
    
    state["feedback"] = feedback
    
    regen_prompt = f"""
    Regenerate story based on feedback.
    
    Original:
    {json.dumps(current_story, indent=2)}
    
    Feedback: {feedback}
    
    Keep ID: {current_story.get('id')}
    Provide complete revised JSON with ALL fields:
    {{
      "id": "{current_story.get('id')}",
      "title": "...",
      "user_story": "As a..., I want to..., so that...",
      "description": "...",
      "acceptance_criteria": ["..."],
      "priority": "{current_story.get('priority')}",
      "complexity": "{current_story.get('complexity')}",
      "tags": [...],
      "story_type": "{current_story.get('story_type')}"
    }}
    """
    
    try:
        response = llm.invoke(regen_prompt)
        regenerated = _extract_json(response)
        
        if regenerated and all(k in regenerated for k in ["id", "title", "user_story"]):
            state["pending_review_stories"].insert(0, regenerated)
            state["current_story_for_review"] = None
        else:
            raise ValueError("Regeneration failed")
            
    except Exception as e:
        state["errors"].append(f"Regeneration error: {e}")
        state["pending_review_stories"].insert(0, current_story)
    
    return state

def edit_story_manually(state: GraphState) -> GraphState:
    """Manual edit mode"""
    story_to_edit = state["current_story_for_review"]
    
    payload = {"type": "edit_story", "story": story_to_edit}
    edited_story = interrupt(payload)
    
    state["pending_review_stories"].insert(0, edited_story)
    state["current_story_for_review"] = None
    
    return state

def generate_tasks_enhanced(state: GraphState) -> GraphState:
    """Generate tasks silently"""
    approved_stories = state.get("approved_stories", {})
    if not approved_stories:
        return state
    
    technical_context = context_loader.load_technical_context(state)
    generated_tasks = {}
    
    for story_id, story in approved_stories.items():
        task_prompt = f"""
        Generate implementation tasks. Use minimal context.
        
        {technical_context}
        
        Story: {story.get('title')}
        User Story: {story.get('user_story')}
        
        Generate 4-8 technical tasks covering: Frontend, Backend, Database, Testing, DevOps, Docs
        
        JSON:
        {{
          "tasks": [
            {{
              "task_id": "TASK-001",
              "title": "...",
              "description": "...",
              "category": "Frontend|Backend|Database|Testing|DevOps|Documentation",
              "estimated_hours": 4,
              "dependencies": [],
              "assignee_hint": "..."
            }}
          ]
        }}
        """
        
        try:
            response = llm.invoke(task_prompt)
            tasks_data = _extract_json(response)
            
            if tasks_data and "tasks" in tasks_data:
                generated_tasks[story_id] = tasks_data["tasks"]
            else:
                generated_tasks[story_id] = []
                
        except Exception as e:
            state["errors"].append(f"Task generation error: {e}")
            generated_tasks[story_id] = []
    
    state["generated_tasks"] = generated_tasks
    return state

def save_workflow_context(state: GraphState, config: RunnableConfig) -> GraphState:
    """Save workflow context silently"""
    user_id = config["configurable"].get("user_id", "default")
    
    approved_count = len(state.get("approved_stories", {}))
    task_count = sum(len(tasks) for tasks in state.get("generated_tasks", {}).values())
    errors = len(state.get("errors", []))
    
    outcome_quality = min(10, max(1, (approved_count * 2) + (task_count // 3) - errors))
    
    compressed_req = state.get("compressed_requirements", {})
    if compressed_req:
        context_store.save_requirement_pattern(
            user_id=user_id,
            req_type=state["requirement_type"],
            compressed_req=json.dumps(compressed_req),
            priority=state["priority"],
            complexity=state["complexity"],
            outcome_quality=outcome_quality,
            story_count=approved_count,
            task_count=task_count
        )
    
    for story_id, story in state.get("approved_stories", {}).items():
        if outcome_quality >= 7:
            context_store.save_story_template(
                user_id=user_id,
                story_type=state["requirement_type"],
                story_data=story,
                quality_score=outcome_quality
            )
    
    tech_stack = state.get("analyzed_requirements", {}).get("technical_stack", [])
    dependencies = state.get("dependencies", [])
    
    if tech_stack or dependencies:
        context_store.cache_tech_context(user_id, tech_stack, dependencies)
    
    return state

def create_jira_tickets(state: GraphState) -> GraphState:
    """Create JIRA tickets with improved error handling"""
    if not JIRA_INSTALLED:
        state["errors"].append("JIRA library not installed. Run: pip install jira")
        return state
    
    try:
        jira = JIRA(server=JIRA_URL, basic_auth=(JIRA_EMAIL, API_TOKEN))
        
        # Store created ticket keys for reference
        created_tickets = {
            "epic": None,
            "stories": {},
            "tasks": {}
        }
        
        # Step 1: Create Epic (if applicable)
        epic_key = None
        if state.get("epic_info"):
            try:
                epic_info = state["epic_info"]
                epic_fields = {
                    "project": {"key": PROJECT_KEY},
                    "summary": epic_info.get("epic_name", "Untitled Epic"),
                    "description": epic_info.get("epic_description", ""),
                    "issuetype": {"name": EPIC_ISSUE_TYPE}
                }
                
                epic_issue = jira.create_issue(fields=epic_fields)
                epic_key = epic_issue.key
                state["created_epic_key"] = epic_key
                created_tickets["epic"] = epic_key
                
            except Exception as e:
                error_msg = f"Epic creation failed: {str(e)}"
                state["errors"].append(error_msg)
                # Continue without epic - stories can still be created
        
        # Step 2: Create User Stories
        for story_id, story in state.get("approved_stories", {}).items():
            try:
                story_fields = {
                    "project": {"key": PROJECT_KEY},
                    "summary": story.get("title", "Untitled Story"),
                    "description": f"{story.get('user_story', '')}\n\n{story.get('description', '')}",
                    "issuetype": {"name": STORY_ISSUE_TYPE}
                }
                
                # Only link to epic if it was successfully created
                if epic_key:
                    story_fields["parent"] = {"key": epic_key}
                
                story_issue = jira.create_issue(fields=story_fields)
                story_jira_key = story_issue.key
                created_tickets["stories"][story_id] = story_jira_key
                
                # Step 3: Create Tasks for this story
                tasks = state.get("generated_tasks", {}).get(story_id, [])
                created_tickets["tasks"][story_id] = []
                
                for task in tasks:
                    try:
                        task_fields = {
                            "project": {"key": PROJECT_KEY},
                            "summary": task.get("title", "Untitled Task"),
                            "description": task.get("description", ""),
                            "issuetype": {"name": TASK_ISSUE_TYPE},
                            "parent": {"key": story_jira_key}  # Link to the story we just created
                        }
                        
                        task_issue = jira.create_issue(fields=task_fields)
                        created_tickets["tasks"][story_id].append({
                            "task_id": task.get("task_id"),
                            "jira_key": task_issue.key
                        })
                        
                    except Exception as e:
                        error_msg = f"Task creation failed for {task.get('task_id', 'unknown')}: {str(e)}"
                        state["errors"].append(error_msg)
                        # Continue with other tasks
                
            except Exception as e:
                error_msg = f"Story creation failed for {story_id}: {str(e)}"
                state["errors"].append(error_msg)
                # Continue with other stories
        
        # Store the created tickets mapping in state for reference
        state["created_jira_tickets"] = created_tickets
        
    except Exception as e:
        error_msg = f"JIRA connection error: {str(e)}"
        state["errors"].append(error_msg)
    
    return state

def format_output(state: GraphState) -> GraphState:
    """Format output silently"""
    output_data = {
        "requirement_classification": {
            "type": state.get("requirement_type"),
            "priority": state.get("priority"),
            "complexity": state.get("complexity"),
            "dependencies": state.get("dependencies", [])
        },
        "context_engineering_metrics": {
            "token_savings": state.get("token_savings", 0),
            "similar_patterns_used": len(state.get("similar_patterns", [])),
            "story_templates_used": len(state.get("story_templates", []))
        },
        "epic": state.get("epic_info"),
        "epic_jira_key": state.get("created_epic_key"),
        "user_stories": list(state.get("approved_stories", {}).values()),
        "tasks": state.get("generated_tasks", {}),
        "created_jira_tickets": state.get("created_jira_tickets", {}),
        "errors": state.get("errors", [])
    }
    
    try:
        with open("sdlc_output_enhanced.json", "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        state["errors"].append(f"Save error: {e}")
    
    return state

# ============================================================================
# Conditional Edge
# ============================================================================

def decide_next_step_after_review(state: GraphState) -> str:
    choice = state.get("review_choice")
    
    if choice == 'f':
        return "regenerate_with_feedback"
    elif choice == 'e':
        return "edit_manually"
    
    if state.get("pending_review_stories"):
        return "review_gate"
    else:
        return "save_context"

# ============================================================================
# Workflow Construction
# ============================================================================

@st.cache_resource
def create_enhanced_workflow():
    """Create enhanced workflow"""
    workflow = StateGraph(GraphState)
    
    workflow.add_node("compress_requirements", compress_requirements_node)
    workflow.add_node("classify_requirement", classify_requirement_enhanced)
    workflow.add_node("extract_business_context", extract_business_context_enhanced)
    workflow.add_node("analyze_requirements", analyze_requirements_enhanced)
    workflow.add_node("generate_epic", generate_epic)
    workflow.add_node("generate_user_stories", generate_user_stories_enhanced)
    workflow.add_node("validate_stories", validate_stories)
    workflow.add_node("human_review_gate", human_review_gate)
    workflow.add_node("regenerate_story_with_feedback", regenerate_story_with_feedback)
    workflow.add_node("edit_story_manually", edit_story_manually)
    workflow.add_node("save_context", save_workflow_context)
    workflow.add_node("generate_tasks", generate_tasks_enhanced)
    workflow.add_node("create_jira_tickets", create_jira_tickets)
    workflow.add_node("format_output", format_output)
    
    workflow.set_entry_point("compress_requirements")
    workflow.add_edge("compress_requirements", "classify_requirement")
    workflow.add_edge("classify_requirement", "extract_business_context")
    workflow.add_edge("extract_business_context", "analyze_requirements")
    workflow.add_edge("analyze_requirements", "generate_epic")
    workflow.add_edge("generate_epic", "generate_user_stories")
    workflow.add_edge("generate_user_stories", "validate_stories")
    workflow.add_edge("validate_stories", "human_review_gate")
    workflow.add_edge("regenerate_story_with_feedback", "human_review_gate")
    workflow.add_edge("edit_story_manually", "human_review_gate")
    
    workflow.add_conditional_edges(
        "human_review_gate",
        decide_next_step_after_review,
        {
            "regenerate_with_feedback": "regenerate_story_with_feedback",
            "edit_manually": "edit_story_manually",
            "review_gate": "human_review_gate",
            "save_context": "save_context"
        }
    )
    
    workflow.add_edge("save_context", "generate_tasks")
    workflow.add_edge("generate_tasks", "create_jira_tickets")
    workflow.add_edge("create_jira_tickets", "format_output")
    workflow.add_edge("format_output", END)
    
    checkpointer = InMemorySaver()
    return workflow.compile(checkpointer=checkpointer)

# ============================================================================
# Streamlit UI
# ============================================================================

def main():
    st.title("🚀 SDLC Automation System")
    st.markdown("AI-powered workflow for generating Epics, User Stories, and Tasks")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configuration")
        user_id = st.text_input("User ID", value="user_001")
        
        st.markdown("---")
        st.header("📊 Session Info")
        if "workflow_state" in st.session_state:
            state = st.session_state.workflow_state
            st.metric("Token Savings", f"~{state.get('token_savings', 0)}")
            st.metric("Approved Stories", len(state.get("approved_stories", {})))
            st.metric("Generated Tasks", sum(len(t) for t in state.get("generated_tasks", {}).values()))
    
    # Main area
    if "workflow_active" not in st.session_state:
        st.session_state.workflow_active = False
    
    if not st.session_state.workflow_active:
        # Initial input
        requirements = st.text_area(
            "📝 Enter Requirements",
            height=200,
            placeholder="Example: As a user I want a profile page with a form to edit my name, email, phone, age, and optional bio..."
        )
        
        if st.button("🚀 Start Workflow", type="primary"):
            if requirements.strip():
                st.session_state.requirements = requirements
                st.session_state.user_id = user_id
                st.session_state.workflow_active = True
                st.session_state.thread_id = str(uuid.uuid4())
                st.rerun()
            else:
                st.error("Please enter requirements")
    
    else:
        # Workflow is active
        if "app" not in st.session_state:
            st.session_state.app = create_enhanced_workflow()
            st.session_state.config = {
                "configurable": {
                    "thread_id": st.session_state.thread_id,
                    "user_id": st.session_state.user_id
                }
            }
            st.session_state.initial_state = {
                "raw_requirements": st.session_state.requirements,
                "output_format": "detailed",
                "approved_stories": {},
                "errors": [],
                "token_savings": 0
            }
            st.session_state.result = None
        
        # Progress
        progress_placeholder = st.empty()
        
        # Show workflow progress steps with real-time updates
        if st.session_state.result is None or (st.session_state.result.get('__interrupt__') and not st.session_state.result.get('approved_stories')):
            st.markdown("---")
            st.markdown("### 📋 Workflow Status")
            
            # Compact progress indicators
            progress_steps = [
                ("🗜️", "Compress"),
                ("🔍", "Classify"),
                ("💼", "Business"),
                ("📊", "Analyze"),
                ("🎯", "Epic"),
                ("📝", "Stories"),
                ("✅", "Validate"),
                ("👤", "Review")
            ]
            
            # Determine current step based on state
            current_step_idx = 0
            if st.session_state.result:
                state = st.session_state.result
                if state.get('compressed_requirements'):
                    current_step_idx = max(current_step_idx, 1)
                if state.get('requirement_type'):
                    current_step_idx = max(current_step_idx, 2)
                if state.get('business_context') is not None:
                    current_step_idx = max(current_step_idx, 3)
                if state.get('analyzed_requirements'):
                    current_step_idx = max(current_step_idx, 4)
                if state.get('epic_info') is not None:
                    current_step_idx = max(current_step_idx, 5)
                if state.get('pending_review_stories') or state.get('approved_stories'):
                    current_step_idx = max(current_step_idx, 6)
                if len(state.get('pending_review_stories', [])) > 0 or len(state.get('approved_stories', {})) > 0:
                    current_step_idx = max(current_step_idx, 7)
            
            # Display compact progress
            cols = st.columns(len(progress_steps))
            for idx, (col, (icon, label)) in enumerate(zip(cols, progress_steps)):
                with col:
                    if idx < current_step_idx:
                        st.markdown(f"<div style='text-align: center;'><div style='font-size: 24px;'>✅</div><div style='font-size: 11px; color: green;'>{label}</div></div>", unsafe_allow_html=True)
                    elif idx == current_step_idx:
                        st.markdown(f"<div style='text-align: center;'><div style='font-size: 24px;'>🔄</div><div style='font-size: 11px; color: blue; font-weight: bold;'>{label}</div></div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div style='text-align: center;'><div style='font-size: 24px; opacity: 0.3;'>{icon}</div><div style='font-size: 11px; color: gray;'>{label}</div></div>", unsafe_allow_html=True)
            
            st.markdown("---")
        
        # Execute workflow with live updates
        if st.session_state.result is None:
            # Create status display container
            status_container = st.container()
            
            with status_container:
                st.markdown("### 🔄 AI Processing Workflow")
                
                # Progress tracking
                progress_bar = st.progress(0)
                status_placeholder = st.empty()
                details_placeholder = st.empty()
                
                # Workflow steps with descriptions
                workflow_steps = [
                    {
                        "step": "Compressing Requirements",
                        "icon": "🗜️",
                        "description": "Using advanced context engineering to reduce token usage by 60-70%",
                        "progress": 10
                    },
                    {
                        "step": "Classifying Requirement",
                        "icon": "🔍",
                        "description": "AI determines requirement type, priority, and complexity",
                        "progress": 25
                    },
                    {
                        "step": "Extracting Business Context",
                        "icon": "💼",
                        "description": "Identifies target users and business value",
                        "progress": 40
                    },
                    {
                        "step": "Analyzing Requirements",
                        "icon": "📊",
                        "description": "Breaks down technical stack and dependencies",
                        "progress": 55
                    },
                    {
                        "step": "Generating Epic",
                        "icon": "🎯",
                        "description": "Creates high-level epic for the feature",
                        "progress": 70
                    },
                    {
                        "step": "Generating User Stories",
                        "icon": "📝",
                        "description": "Creating user stories following INVEST principles",
                        "progress": 85
                    },
                    {
                        "step": "Validating Stories",
                        "icon": "✅",
                        "description": "Quality check on generated stories",
                        "progress": 95
                    },
                    {
                        "step": "Ready for Review",
                        "icon": "👤",
                        "description": "Preparing stories for human review",
                        "progress": 100
                    }
                ]
                
                # Store in session state for async updates
                st.session_state.workflow_steps = workflow_steps
                st.session_state.current_step_index = 0
                
            # Execute workflow with simulated progress updates
            import time
            import threading
            
            def update_progress():
                """Background thread to update progress"""
                for idx, step_info in enumerate(st.session_state.workflow_steps):
                    st.session_state.current_step_index = idx
                    time.sleep(1.5)  # Simulate processing time
            
            # Start background progress thread
            progress_thread = threading.Thread(target=update_progress, daemon=True)
            progress_thread.start()
            
            # Execute the actual workflow
            with st.spinner("Processing..."):
                # Show live updates
                for idx, step_info in enumerate(workflow_steps):
                    progress_bar.progress(step_info["progress"])
                    
                    status_placeholder.markdown(f"""
                    <div style='padding: 20px; background-color: #f0f8ff; border-left: 5px solid #4CAF50; border-radius: 5px; margin: 10px 0;'>
                        <h3 style='margin: 0; color: #2c3e50;'>{step_info['icon']} {step_info['step']}</h3>
                        <p style='margin: 5px 0 0 0; color: #555;'>{step_info['description']}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Show detailed info for specific steps
                    if idx == 1:  # Classification
                        details_placeholder.info("🔍 Analyzing: Requirement type, Priority level, Complexity score...")
                    elif idx == 2:  # Business Context
                        details_placeholder.info("💼 Extracting: Target users, Business goals, Success metrics...")
                    elif idx == 3:  # Analysis
                        details_placeholder.info("📊 Identifying: Technical stack, Dependencies, Constraints...")
                    elif idx == 5:  # Stories
                        details_placeholder.info("📝 Generating: User stories with acceptance criteria...")
                    
                    time.sleep(1.2)  # Delay between steps for visual effect
                
                # Clear details after processing
                details_placeholder.empty()
                
                # Now actually invoke the workflow
                st.session_state.result = st.session_state.app.invoke(
                    st.session_state.initial_state,
                    config=st.session_state.config
                )
                
                # Show completion
                status_placeholder.success("✅ AI Processing Complete! Ready for human review.")
                progress_bar.progress(100)
                time.sleep(1)
                
                # Display classification results
                if st.session_state.result:
                    state = st.session_state.result
                    
                    st.markdown("---")
                    st.markdown("### 📊 AI Analysis Results")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        req_type = state.get('requirement_type', 'Unknown')
                        st.metric("Requirement Type", req_type, 
                                 delta="Classified" if req_type != 'Unknown' else None,
                                 delta_color="normal")
                    
                    with col2:
                        priority = state.get('priority', 'Unknown')
                        priority_color = {"High": "🔴", "Medium": "🟡", "Low": "🟢", "Urgent": "🔴"}.get(priority, "⚪")
                        st.metric("Priority", f"{priority_color} {priority}")
                    
                    with col3:
                        complexity = state.get('complexity', 'Unknown')
                        st.metric("Complexity", complexity,
                                 delta={"S": "Small", "M": "Medium", "L": "Large", "XL": "X-Large"}.get(complexity, ""),
                                 delta_color="normal")
                    
                    with col4:
                        story_count = len(state.get('pending_review_stories', []))
                        st.metric("Stories Generated", story_count,
                                 delta=f"{story_count} stories" if story_count > 0 else None,
                                 delta_color="normal")
                    
                    # Show key insights
                    if state.get('compressed_requirements'):
                        compressed = state['compressed_requirements']
                        
                        with st.expander("🔍 View AI Insights", expanded=True):
                            st.markdown("**Summary:**")
                            st.info(compressed.get('summary', 'N/A'))
                            
                            col_a, col_b = st.columns(2)
                            
                            with col_a:
                                st.markdown("**Key Features:**")
                                features = compressed.get('key_features', [])
                                if features:
                                    for feat in features[:5]:
                                        st.markdown(f"• {feat}")
                                else:
                                    st.text("No features identified")
                            
                            with col_b:
                                st.markdown("**User Roles:**")
                                roles = compressed.get('user_roles', [])
                                if roles:
                                    for role in roles:
                                        st.markdown(f"• {role}")
                                else:
                                    st.text("No roles identified")
                            
                            if state.get('dependencies'):
                                st.markdown("**Dependencies:**")
                                st.markdown(", ".join(state['dependencies']))
                    
                    st.markdown("---")
                    st.info("👇 Scroll down to review generated user stories")
                    time.sleep(2)
        
        # Handle interrupts - ENHANCED REVIEW UI
        while st.session_state.result.get('__interrupt__'):
            interrupt_info = st.session_state.result['__interrupt__'][0]
            payload = interrupt_info.value
            
            if payload.get("type") == "review_story":
                story = payload["story"]
                current_state = st.session_state.result
                
                total = len(current_state['approved_stories']) + len(current_state['pending_review_stories']) + 1
                current = len(current_state['approved_stories']) + 1
                
                # Review Statistics
                stat_col1, stat_col2, stat_col3 = st.columns(3)
                
                with stat_col1:
                    st.metric("✅ Approved", len(current_state.get('approved_stories', {})))
                
                with stat_col2:
                    st.metric("⏳ Pending", len(current_state.get('pending_review_stories', [])) + 1)
                
                with stat_col3:
                    progress_pct = (len(current_state['approved_stories']) / total) * 100
                    st.metric("📊 Progress", f"{progress_pct:.0f}%")
                
                st.markdown("---")
                
                # Progress indicator
                progress_pct = (current - 1) / total
                st.progress(progress_pct)
                st.markdown(f"### 📋 Story Review: {current} of {total}")
                
                # Keyboard shortcuts help
                with st.expander("⌨️ Quick Actions Guide", expanded=False):
                    st.markdown("""
                    - **✅ Approve** - Accept the story as-is and move to next
                    - **❌ Reject** - Skip this story and move to next
                    - **💬 Give Feedback** - Let AI regenerate based on your feedback
                    - **✏️ Edit Manually** - Edit fields directly in the UI
                    """)
                
                # Story card with better visual design
                st.markdown(f"""
                <div style='background-color: #f8f9fa; padding: 20px; border-radius: 10px; border-left: 4px solid #4CAF50; margin-bottom: 20px;'>
                    <h4 style='margin-top: 0; color: #2c3e50;'>{story.get('id')}: {story.get('title')}</h4>
                </div>
                """, unsafe_allow_html=True)
                
                # Two-column layout for story details
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.markdown("#### User Story")
                    st.info(story.get('user_story'))
                    
                    st.markdown("#### Description")
                    st.write(story.get('description', 'No description provided'))
                    
                    st.markdown("#### Acceptance Criteria")
                    for idx, ac in enumerate(story.get('acceptance_criteria', []), 1):
                        st.markdown(f"{idx}. {ac}")
                
                with col2:
                    st.markdown("#### Story Details")
                    st.metric("Priority", story.get('priority'), help="Story priority level")
                    st.metric("Complexity", story.get('complexity'), help="Estimated complexity")
                    st.metric("Type", story.get('story_type'))
                    
                    if story.get('tags'):
                        st.markdown("**Tags:**")
                        st.write(", ".join(story.get('tags', [])))
                
                st.markdown("---")
                
                # Check if we're in feedback or edit mode
                if st.session_state.get('feedback_mode'):
                    st.markdown("### 💬 Provide Feedback")
                    st.info("Describe what changes you'd like to see in this story. The AI will regenerate it based on your feedback.")
                    
                    feedback_text = st.text_area(
                        "Your feedback:",
                        placeholder="Example: Make the acceptance criteria more specific, add security requirements, simplify the user story...",
                        height=150,
                        key="feedback_textarea"
                    )
                    
                    feedback_col1, feedback_col2 = st.columns([1, 4])
                    
                    with feedback_col1:
                        if st.button("🚀 Regenerate", type="primary", disabled=not feedback_text.strip(), use_container_width=True):
                            st.session_state.pending_feedback = feedback_text
                            del st.session_state.feedback_mode
                            st.session_state.result = st.session_state.app.invoke(
                                Command(resume='f'),
                                config=st.session_state.config
                            )
                            st.rerun()
                    
                    with feedback_col2:
                        if st.button("❌ Cancel", use_container_width=True):
                            del st.session_state.feedback_mode
                            st.rerun()
                
                elif st.session_state.get('edit_mode'):
                    st.markdown("### ✏️ Edit Story")
                    st.warning("⚠️ Edit the fields below. All changes will be applied to this story.")
                    
                    # Use form for better UX
                    with st.form("edit_story_form"):
                        edited = {}
                        edited['id'] = story.get('id')
                        
                        # Title
                        edited['title'] = st.text_input(
                            "Story Title",
                            value=story.get('title'),
                            help="Short, descriptive title for the story"
                        )
                        
                        # User Story
                        edited['user_story'] = st.text_area(
                            "User Story (As a... I want... So that...)",
                            value=story.get('user_story'),
                            height=100,
                            help="Follow the standard user story format"
                        )
                        
                        # Description
                        edited['description'] = st.text_area(
                            "Description",
                            value=story.get('description', ''),
                            height=150,
                            help="Detailed description of the story"
                        )
                        
                        # Acceptance Criteria
                        st.markdown("**Acceptance Criteria** (one per line)")
                        ac_text = st.text_area(
                            "Acceptance Criteria",
                            value='\n'.join(story.get('acceptance_criteria', [])),
                            height=200,
                            help="Enter each acceptance criterion on a new line"
                        )
                        edited['acceptance_criteria'] = [ac.strip() for ac in ac_text.split('\n') if ac.strip()]
                        
                        # Read-only fields
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.text_input("Priority", value=story.get('priority'), disabled=True)
                        with col2:
                            st.text_input("Complexity", value=story.get('complexity'), disabled=True)
                        with col3:
                            st.text_input("Type", value=story.get('story_type'), disabled=True)
                        
                        # Preserve other fields
                        edited['priority'] = story.get('priority')
                        edited['complexity'] = story.get('complexity')
                        edited['story_type'] = story.get('story_type')
                        edited['tags'] = story.get('tags', [])
                        
                        # Form actions
                        submit_col1, submit_col2 = st.columns([1, 4])
                        
                        with submit_col1:
                            submitted = st.form_submit_button("💾 Save Changes", type="primary", use_container_width=True)
                        
                        with submit_col2:
                            cancelled = st.form_submit_button("❌ Cancel", use_container_width=True)
                        
                        if submitted:
                            # Validate required fields
                            if not edited['title'] or not edited['user_story'] or not edited['acceptance_criteria']:
                                st.error("❌ Title, User Story, and at least one Acceptance Criterion are required!")
                            else:
                                del st.session_state.edit_mode
                                st.session_state.result = st.session_state.app.invoke(
                                    Command(resume=edited),
                                    config=st.session_state.config
                                )
                                st.rerun()
                        
                        if cancelled:
                            del st.session_state.edit_mode
                            st.rerun()
                
                else:
                    # Action buttons in a more prominent layout
                    st.markdown("#### Choose an action:")
                    
                    action_col1, action_col2, action_col3, action_col4 = st.columns(4)
                    
                    with action_col1:
                        if st.button("✅ Approve", type="primary", use_container_width=True, key="approve_btn"):
                            st.session_state.result = st.session_state.app.invoke(
                                Command(resume='y'),
                                config=st.session_state.config
                            )
                            st.rerun()
                    
                    with action_col2:
                        if st.button("❌ Reject", use_container_width=True, key="reject_btn"):
                            st.session_state.result = st.session_state.app.invoke(
                                Command(resume='n'),
                                config=st.session_state.config
                            )
                            st.rerun()
                    
                    with action_col3:
                        if st.button("💬 Give Feedback", use_container_width=True, key="feedback_btn"):
                            st.session_state.feedback_mode = True
                            st.rerun()
                    
                    with action_col4:
                        if st.button("✏️ Edit Manually", use_container_width=True, key="edit_btn"):
                            st.session_state.edit_mode = True
                            st.rerun()
                
                break
            
            elif payload.get("type") == "get_feedback":
                # Check if we have pending feedback from the previous step
                if "pending_feedback" in st.session_state:
                    feedback = st.session_state.pending_feedback
                    del st.session_state.pending_feedback
                    
                    with st.spinner("🔄 AI is regenerating the story based on your feedback..."):
                        st.session_state.result = st.session_state.app.invoke(
                            Command(resume=feedback),
                            config=st.session_state.config
                        )
                    st.rerun()
                else:
                    # Fallback to text area input (shouldn't happen with new flow)
                    st.markdown("### 💬 Provide Feedback")
                    feedback = st.text_area(
                        "Enter your feedback:",
                        placeholder="Describe what you'd like changed...",
                        height=150,
                        key="feedback_input_fallback"
                    )
                    
                    if st.button("Submit Feedback", type="primary"):
                        with st.spinner("🔄 AI is regenerating the story..."):
                            st.session_state.result = st.session_state.app.invoke(
                                Command(resume=feedback),
                                config=st.session_state.config
                            )
                        st.rerun()
                break
            
            elif payload.get("type") == "edit_story":
                # This shouldn't be reached with new flow, but keep as fallback
                story = payload.get("story")
                
                if "pending_edited_story" in st.session_state:
                    edited_story = st.session_state.pending_edited_story
                    del st.session_state.pending_edited_story
                    
                    st.session_state.result = st.session_state.app.invoke(
                        Command(resume=edited_story),
                        config=st.session_state.config
                    )
                    st.rerun()
                break
        
        # Workflow complete
        if not st.session_state.result.get('__interrupt__'):
            # Show ticket generation progress
            if "tickets_generated" not in st.session_state:
                st.info("🎫 Generating JIRA tickets...")
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                final_state = st.session_state.result
                
                # Calculate total items
                total_items = 0
                if final_state.get("epic_info"):
                    total_items += 1
                total_items += len(final_state.get("approved_stories", {}))
                for tasks in final_state.get("generated_tasks", {}).values():
                    total_items += len(tasks)
                
                if total_items > 0:
                    current = 0
                    
                    # Get created tickets info
                    created_tickets = final_state.get("created_jira_tickets", {})
                    
                    # Epic
                    if created_tickets.get("epic"):
                        current += 1
                        progress_bar.progress(current / total_items)
                        status_text.text(f"✅ Created Epic: {created_tickets['epic']}")
                        import time
                        time.sleep(0.5)
                    elif final_state.get("epic_info"):
                        current += 1
                        progress_bar.progress(current / total_items)
                        status_text.text(f"⚠️ Epic creation skipped/failed")
                        import time
                        time.sleep(0.5)
                    
                    # Stories and Tasks
                    for story_id in final_state.get("approved_stories", {}):
                        story_jira_key = created_tickets.get("stories", {}).get(story_id)
                        
                        if story_jira_key:
                            current += 1
                            progress_bar.progress(current / total_items)
                            status_text.text(f"✅ Created Story: {story_jira_key} ({story_id})")
                            import time
                            time.sleep(0.3)
                            
                            # Tasks for this story
                            story_tasks = created_tickets.get("tasks", {}).get(story_id, [])
                            for task_info in story_tasks:
                                current += 1
                                progress_bar.progress(current / total_items)
                                status_text.text(f"✅ Created Task: {task_info['jira_key']} ({task_info['task_id']})")
                                import time
                                time.sleep(0.2)
                        else:
                            current += 1
                            progress_bar.progress(current / total_items)
                            status_text.text(f"⚠️ Story creation failed: {story_id}")
                            import time
                            time.sleep(0.3)
                    
                    progress_bar.progress(1.0)
                    
                    # Check if there were any errors
                    if final_state.get("errors"):
                        status_text.text("⚠️ Tickets created with some errors - see Summary tab")
                    else:
                        status_text.text("✅ All tickets created successfully!")
                    
                    import time
                    time.sleep(1)
                else:
                    status_text.text("ℹ️ No tickets to create")
                
                st.session_state.tickets_generated = True
                st.session_state.workflow_state = final_state
                st.rerun()
            
            st.success("✅ Workflow Complete!")
            
            final_state = st.session_state.workflow_state
            
            # Display results
            tab1, tab2, tab3, tab4 = st.tabs(["📊 Summary", "📋 Stories", "🔧 Tasks", "📄 Output"])
            
            with tab1:
                col1, col2, col3 = st.columns(3)
                col1.metric("Requirement Type", final_state.get('requirement_type', 'N/A'))
                col2.metric("Priority", final_state.get('priority', 'N/A'))
                col3.metric("Complexity", final_state.get('complexity', 'N/A'))
                
                st.markdown("---")
                
                # JIRA Tickets Summary
                st.subheader("🎫 JIRA Tickets Created")
                
                created_tickets = final_state.get("created_jira_tickets", {})
                
                ticket_col1, ticket_col2, ticket_col3 = st.columns(3)
                
                epic_count = 1 if created_tickets.get("epic") else 0
                story_count = len(created_tickets.get("stories", {}))
                task_count = sum(len(tasks) for tasks in created_tickets.get("tasks", {}).values())
                
                ticket_col1.metric("Epic", epic_count, help="Epic ticket created")
                ticket_col2.metric("Stories", story_count, help="User story tickets created")
                ticket_col3.metric("Tasks", task_count, help="Task tickets created")
                
                # Show clickable links to created tickets
                if created_tickets.get("epic"):
                    epic_key = created_tickets["epic"]
                    epic_url = f"{JIRA_URL}browse/{epic_key}"
                    st.info(f"🎯 **Epic:** [{epic_key}]({epic_url})")
                
                if created_tickets.get("stories"):
                    st.markdown("**📋 Created Stories:**")
                    for story_id, jira_key in created_tickets["stories"].items():
                        story_url = f"{JIRA_URL}browse/{jira_key}"
                        story_title = final_state.get("approved_stories", {}).get(story_id, {}).get("title", story_id)
                        st.markdown(f"- [{jira_key}]({story_url}): {story_title}")
                
                if final_state.get("errors"):
                    st.warning("⚠️ Some errors occurred:")
                    with st.expander("View Errors", expanded=False):
                        for error in final_state["errors"]:
                            st.text(f"• {error}")
                
                st.markdown("---")
                
                if final_state.get('epic_info'):
                    st.subheader("🎯 Epic Details")
                    st.markdown(f"**Name:** {final_state['epic_info'].get('epic_name')}")
                    st.markdown(f"**Description:** {final_state['epic_info'].get('epic_description')}")
                    
                    if final_state['epic_info'].get('acceptance_criteria'):
                        st.markdown("**Acceptance Criteria:**")
                        for ac in final_state['epic_info'].get('acceptance_criteria', []):
                            st.markdown(f"- {ac}")
            
            with tab2:
                st.subheader("📋 Approved User Stories")
                for story_id, story in final_state.get('approved_stories', {}).items():
                    with st.expander(f"{story_id}: {story.get('title')}"):
                        st.markdown(f"**User Story:** {story.get('user_story')}")
                        st.markdown(f"**Description:** {story.get('description')}")
                        st.markdown("**Acceptance Criteria:**")
                        for ac in story.get('acceptance_criteria', []):
                            st.markdown(f"- {ac}")
            
            with tab3:
                st.subheader("🔧 Generated Tasks")
                for story_id, tasks in final_state.get('generated_tasks', {}).items():
                    st.markdown(f"**Story: {story_id}**")
                    for task in tasks:
                        with st.expander(f"{task.get('task_id')}: {task.get('title')}"):
                            st.markdown(f"**Category:** {task.get('category')}")
                            st.markdown(f"**Description:** {task.get('description')}")
                            st.markdown(f"**Estimated Hours:** {task.get('estimated_hours')}")
            
            with tab4:
                st.subheader("📄 JSON Output")
                output_data = {
                    "requirement_classification": {
                        "type": final_state.get("requirement_type"),
                        "priority": final_state.get("priority"),
                        "complexity": final_state.get("complexity"),
                    },
                    "epic": final_state.get("epic_info"),
                    "user_stories": list(final_state.get("approved_stories", {}).values()),
                    "tasks": final_state.get("generated_tasks", {}),
                    "created_jira_tickets": final_state.get("created_jira_tickets", {})
                }
                st.json(output_data)
                
                st.download_button(
                    "⬇️ Download JSON",
                    data=json.dumps(output_data, indent=2),
                    file_name="sdlc_output.json",
                    mime="application/json"
                )
            
            if st.button("🔄 Start New Workflow"):
                # Clear all session state
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

if __name__ == "__main__":
    main()