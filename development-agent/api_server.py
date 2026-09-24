"""
FastAPI Server for Developer Agent V2.0
Complete implementation with validation agent workflow
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
import os
from dotenv import load_dotenv
import uuid

from agent_workflow import create_agent, AgentState

load_dotenv()

app = FastAPI(title="Developer Agent V2.0 API")

active_workflows: Dict[str, Dict[str, Any]] = {}
agent = None


class StartWorkflowRequest(BaseModel):
    jira_ticket_id: str
    repo_path: str
    developer_id: Optional[str] = "unknown_developer"


class ApprovalRequest(BaseModel):
    workflow_id: str
    action: str  # "approve", "reject", "continue", "feedback"
    feedback: Optional[str] = ""


class WorkflowStatusResponse(BaseModel):
    workflow_id: str
    current_stage: str
    jira_content: Optional[Dict[str, Any]] = None
    identified_files: Optional[List[str]] = None
    file_analysis: Optional[str] = None
    modifications: Optional[Dict[str, str]] = None
    validation_report: Optional[Dict[str, Any]] = None
    pr_url: Optional[str] = None
    messages: List[str]
    error_message: Optional[str] = None
    iteration_count: int = 0


@app.on_event("startup")
async def startup_event():
    """Initialize the agent on startup"""
    global agent
    
    service_account_path = "gen-lang-client-0375456222-003d04a91a5d.json"
    project_id = "dg-assistant-451309"
    
    if not os.path.exists(service_account_path):
        print(f"WARNING: Service account file not found: {service_account_path}")
    
    agent = create_agent(service_account_path, project_id)
    print("✅ Developer Agent V2.0 initialized successfully")
    print("✅ Server running on http://localhost:8000")


@app.get("/")
async def root():
    """Serve the frontend"""
    return FileResponse("static/index.html")


@app.get("/favicon.ico")
async def favicon():
    """Serve favicon"""
    favicon_path = "static/favicon.svg"
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path, media_type="image/svg+xml")
    else:
        from fastapi.responses import Response
        return Response(status_code=204)


@app.post("/api/workflow/start")
async def start_workflow(request: StartWorkflowRequest) -> Dict[str, Any]:
    """Start a new workflow for a Jira ticket"""
    try:
        workflow_id = str(uuid.uuid4())
        
        initial_state: AgentState = {
            "jira_ticket_id": request.jira_ticket_id,
            "jira_content": {},
            "repo_path": request.repo_path,
            "developer_id": request.developer_id,
            "identified_files": [],
            "file_vector_ids": {},
            "file_analysis": "",
            "modifications": {},
            "validation_report": {},
            "approval_status": "",
            "modification_feedback": "",
            "pr_url": None,
            "current_stage": "initialized",
            "error_message": None,
            "messages": [],
            "iteration_count": 0
        }
        
        config = {"configurable": {"thread_id": workflow_id}}
        
        active_workflows[workflow_id] = {
            "state": initial_state,
            "config": config
        }
        
        print(f"[Workflow {workflow_id[:8]}] Started for ticket: {request.jira_ticket_id}")
        
        # Start the workflow
        asyncio.create_task(run_workflow_step(workflow_id))
        
        return {
            "workflow_id": workflow_id,
            "status": "started",
            "current_stage": "initialized"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start workflow: {str(e)}")


@app.post("/api/workflow/approve")
async def approve_workflow(request: ApprovalRequest) -> Dict[str, Any]:
    """Handle workflow approvals and actions"""
    if request.workflow_id not in active_workflows:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    workflow = active_workflows[request.workflow_id]
    state = workflow["state"]
    current_stage = state.get("current_stage", "unknown")
    
    print(f"🎯 [API] Current workflow stage: {current_stage}")
    print(f"🎯 [API] Action requested: {request.action}")
    
    # Handle file rejection immediately without continuing workflow
    if current_stage == "awaiting_file_approval" and request.action == "reject":
        print(f"🎯 [API] Files rejected - stopping workflow immediately")
        state["current_stage"] = "cancelled"
        state["approval_status"] = "rejected"
        state["messages"].append("❌ Workflow cancelled - files rejected by user")
        
        # DON'T start the workflow step - just return
        return {
            "status": "cancelled",
            "message": "Workflow cancelled by user",
            "current_stage": "cancelled"
        }
    
    # Handle other approval cases
    if current_stage == "awaiting_file_approval":
        if request.action == "approve" or request.action == "continue":
            state["approval_status"] = "approved"
            state["messages"].append("✅ Files approved. Starting direct modification...")
            print(f"🎯 [API] Files approved - proceeding to modification")
            
    elif current_stage == "awaiting_validation_approval":
        if request.action == "approve":
            state["approval_status"] = "approved"
            state["messages"].append("✅ Validation approved. Creating pull request...")
            print(f"🎯 [API] Validation approved - creating PR")
            
        elif request.action == "feedback":
            state["approval_status"] = "feedback"
            state["modification_feedback"] = request.feedback or ""
            state["messages"].append(f"💬 Human feedback received. Applying changes...")
            print(f"🎯 [API] Human feedback provided - applying changes")
    
    # Update workflow state
    workflow["state"] = state
    
    # Only continue workflow if not cancelled
    if state.get("current_stage") != "cancelled":
        print(f"🎯 [API] Starting workflow step continuation...")
        asyncio.create_task(run_workflow_step(request.workflow_id))
    
    return {
        "status": "success",
        "message": f"Action '{request.action}' processed",
        "current_stage": state.get("current_stage")
    }


@app.get("/api/workflow/{workflow_id}/status")
async def get_workflow_status(workflow_id: str) -> WorkflowStatusResponse:
    """Get current workflow status"""
    if workflow_id not in active_workflows:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    state = active_workflows[workflow_id]["state"]
    
    return WorkflowStatusResponse(
        workflow_id=workflow_id,
        current_stage=state.get("current_stage", "unknown"),
        jira_content=state.get("jira_content"),
        identified_files=state.get("identified_files"),
        file_analysis=state.get("file_analysis"),
        modifications=state.get("modifications"),
        validation_report=state.get("validation_report"),
        pr_url=state.get("pr_url"),
        messages=state.get("messages", []),
        error_message=state.get("error_message"),
        iteration_count=state.get("iteration_count", 0)
    )


async def run_workflow_step(workflow_id: str):
    """Run the next step of the workflow"""
    try:
        if workflow_id not in active_workflows:
            return
        
        workflow = active_workflows[workflow_id]
        config = workflow["config"]
        current_stage = workflow["state"].get("current_stage", "initialized")
        
        print(f"[Workflow {workflow_id[:8]}] Running from stage: {current_stage}")
        
        # For LangGraph with interrupts:
        # - Pass state for initialization
        # - Pass None to continue from checkpoint after interrupt
        if current_stage == "initialized":
            input_state = workflow["state"]
        else:
            # CRITICAL: Update the checkpoint state with our local changes BEFORE continuing
            try:
                # Get current checkpoint
                snapshot = agent.app.get_state(config)
                if snapshot and snapshot.values:
                    # Update checkpoint with our approval status
                    updated_state = snapshot.values.copy()
                    updated_state.update(workflow["state"])  # This includes approval_status
                    
                    # Force update the checkpoint with our state
                    agent.app.update_state(config, updated_state)
                    
                    workflow["state"] = updated_state
                    print(f"[Workflow {workflow_id[:8]}] ✅ Checkpoint updated with approval_status: '{updated_state.get('approval_status', '')}'")
                else:
                    print(f"[Workflow {workflow_id[:8]}] No checkpoint found, using local state")
            except Exception as e:
                print(f"[Workflow {workflow_id[:8]}] Could not update checkpoint state: {e}")
            
            # Pass None to continue from updated checkpoint
            input_state = None
        
        current_state = None
        step_count = 0
        
        for state in agent.app.stream(input_state, config, stream_mode="values"):
            current_state = state
            step_count += 1
            
            # Ensure approval_status is preserved during execution
            if workflow["state"].get("approval_status"):
                state["approval_status"] = workflow["state"]["approval_status"]
            
            # Ensure modification_feedback is preserved
            if workflow["state"].get("modification_feedback"):
                state["modification_feedback"] = workflow["state"]["modification_feedback"]
            
            workflow["state"] = state
            print(f"[Workflow {workflow_id[:8]}] Stage update ({step_count}): {state.get('current_stage')}")
            
            # If we reach an error state, break
            if state.get('current_stage') == 'error':
                print(f"[Workflow {workflow_id[:8]}] Error detected: {state.get('error_message')}")
                break
                
            # Break after reasonable number of steps to prevent infinite loops
            if step_count > 10:
                print(f"[Workflow {workflow_id[:8]}] Maximum steps reached, stopping execution")
                break
        
        if current_state:
            workflow["state"] = current_state
            final_stage = current_state.get('current_stage')
            print(f"[Workflow {workflow_id[:8]}] Final stage: {final_stage}")
            
            # Log success/completion
            if final_stage == "completed":
                print(f"[Workflow {workflow_id[:8]}] ✅ Workflow completed successfully")
                pr_url = current_state.get('pr_url')
                if pr_url:
                    print(f"[Workflow {workflow_id[:8]}] ✅ PR created: {pr_url}")
            elif final_stage == "awaiting_file_approval":
                print(f"[Workflow {workflow_id[:8]}] ⏸ Waiting for file approval")
            elif final_stage == "awaiting_validation_approval":
                print(f"[Workflow {workflow_id[:8]}] ⏸ Waiting for validation approval")
            
    except Exception as e:
        error_msg = str(e)
        print(f"[Workflow {workflow_id[:8]}] Error: {error_msg}")
        import traceback
        traceback.print_exc()
        
        if workflow_id in active_workflows:
            active_workflows[workflow_id]["state"]["error_message"] = error_msg
            active_workflows[workflow_id]["state"]["current_stage"] = "error"
            active_workflows[workflow_id]["state"]["messages"].append(f"❌ Error: {error_msg}")


@app.delete("/api/workflow/{workflow_id}")
async def delete_workflow(workflow_id: str) -> Dict[str, Any]:
    """Delete a workflow and free up resources"""
    if workflow_id in active_workflows:
        del active_workflows[workflow_id]
        return {"status": "success", "message": "Workflow deleted"}
    else:
        raise HTTPException(status_code=404, detail="Workflow not found")


@app.get("/api/config/test")
async def test_config() -> Dict[str, Any]:
    """Test configuration status"""
    config_status = {
        "jira": {
            "base_url": bool(os.getenv("JIRA_BASE_URL")),
            "email": bool(os.getenv("JIRA_EMAIL")),
            "token": bool(os.getenv("JIRA_API_TOKEN"))
        },
        "github": {
            "token": bool(os.getenv("GITHUB_TOKEN")),
            "repo_url": bool(os.getenv("GITHUB_REPO_URL")),
            "base_branch": bool(os.getenv("GITHUB_BASE_BRANCH"))
        },
        "qdrant": {
            "url": bool(os.getenv("QDRANT_URL")),
            "api_key": bool(os.getenv("QDRANT_API_KEY")),
            "collection": bool(os.getenv("QDRANT_COLLECTION_NAME"))
        }
    }
    
    all_configured = all([
        all(config_status["jira"].values()),
        all(config_status["github"].values()),
        all(config_status["qdrant"].values())
    ])
    
    return {
        "status": "configured" if all_configured else "incomplete",
        "details": config_status
    }


# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)