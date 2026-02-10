#!/usr/bin/env python3
import os
from agent import create_deployment_agent, DeploymentState, GCP_PROJECT_ID, GCP_REGION

def main():
    print("Cloud Deployment Agent - Fixed Version")
    
    repo_url = input("\nEnter GitHub repository URL: ").strip()
    if not repo_url:
        print("Repository URL is required")
        return
    
    branch = input("Enter branch name (default: main): ").strip() or "main"
    
    print(f"\nConfiguration:")
    print(f"  Repository: {repo_url}")
    print(f"  Branch: {branch}")
    print(f"  Project: {GCP_PROJECT_ID}")
    print(f"  Region: {GCP_REGION}")
    
    confirm = input("\nProceed with deployment? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("Deployment cancelled")
        return
    
    initial_state: DeploymentState = {
        'repo_url': repo_url,
        'branch': branch,
        'gcp_project_id': GCP_PROJECT_ID,
        'gcp_region': GCP_REGION,
        'repo_local_path': '',
        'repo_structure': '',
        'analysis': {},
        'backend_dockerfile_content': '',
        'backend_cloudbuild_content': '',
        'backend_url': '',
        'backend_deployed': False,
        'frontend_dockerfile_content': '',
        'frontend_cloudbuild_content': '',
        'frontend_url': '',
        'frontend_deployed': False,
        'messages': [],
        'errors': [],
        'current_step': 'init'
    }
    
    print("\nStarting deployment agent...")
    agent = create_deployment_agent()
    
    try:
        final_state = agent.invoke(initial_state)
        
        print("\nDEPLOYMENT COMPLETE")
        
        if final_state.get('backend_deployed'):
            print(f"\nBackend Service:")
            print(f"  URL: {final_state.get('backend_url')}")
        
        if final_state.get('frontend_deployed'):
            print(f"\nFrontend Service:")
            print(f"  URL: {final_state.get('frontend_url')}")
        
        if final_state.get('errors'):
            print(f"\nErrors:")
            for error in final_state['errors']:
                print(f"  {error}")
        
    except KeyboardInterrupt:
        print("\n\nDeployment interrupted")
    except Exception as e:
        print(f"\n\nDeployment failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()