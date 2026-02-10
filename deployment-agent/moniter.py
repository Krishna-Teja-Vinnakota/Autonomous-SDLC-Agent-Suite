"""
Real-time Cloud Build & Cloud Run Monitor
Watch your deployment progress live
"""

import subprocess
import sys
import time
import json
from datetime import datetime

def run_command(cmd):
    """Execute command and return output"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=True,
            timeout=10
        )
        return result.stdout, result.returncode
    except Exception as e:
        return f"Error: {e}", 1

def get_recent_builds(project_id, limit=5):
    """Get recent Cloud Build jobs"""
    cmd = f'gcloud builds list --limit={limit} --project={project_id} --format=json'
    output, code = run_command(cmd)
    
    if code == 0:
        try:
            return json.loads(output)
        except:
            return []
    return []

def get_build_status(project_id, build_id):
    """Get specific build status"""
    cmd = f'gcloud builds describe {build_id} --project={project_id} --format=json'
    output, code = run_command(cmd)
    
    if code == 0:
        try:
            return json.loads(output)
        except:
            return None
    return None

def get_build_logs(project_id, build_id, lines=20):
    """Get build logs"""
    cmd = f'gcloud builds log {build_id} --project={project_id}'
    output, code = run_command(cmd)
    
    if code == 0:
        # Return last N lines
        lines_list = output.strip().split('\n')
        return '\n'.join(lines_list[-lines:])
    return "No logs available"

def get_cloud_run_services(project_id, region):
    """Get Cloud Run services"""
    cmd = f'gcloud run services list --project={project_id} --region={region} --format=json'
    output, code = run_command(cmd)
    
    if code == 0:
        try:
            return json.loads(output)
        except:
            return []
    return []

def format_time(timestamp):
    """Format timestamp"""
    try:
        if isinstance(timestamp, str):
            # Parse ISO format
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return dt.strftime('%H:%M:%S')
        return str(timestamp)
    except:
        return timestamp

def monitor_builds(project_id, region='us-central1', refresh_interval=10):
    """Monitor builds in real-time"""
    
    print("="*70)
    print("   REAL-TIME DEPLOYMENT MONITOR")
    print("="*70)
    print(f"\n  Project: {project_id}")
    print(f"  Region: {region}")
    print(f"  Refresh: Every {refresh_interval} seconds")
    print(f"  Press Ctrl+C to exit\n")
    print("="*70)
    
    last_build_statuses = {}
    iteration = 0
    
    try:
        while True:
            iteration += 1
            current_time = datetime.now().strftime('%H:%M:%S')
            
            # Clear screen (works on most terminals)
            if iteration > 1:
                print("\n" + "="*70)
            
            print(f"\n⏰ Updated at: {current_time}")
            
            # Get recent builds
            print("\n RECENT CLOUD BUILDS:")
            print("-"*70)
            
            builds = get_recent_builds(project_id, limit=5)
            
            if builds:
                for i, build in enumerate(builds, 1):
                    build_id = build.get('id', 'unknown')[:8]
                    status = build.get('status', 'UNKNOWN')
                    create_time = build.get('createTime', '')
                    source = build.get('source', {})
                    
                    # Get repo name from source
                    repo_name = 'unknown'
                    if 'repoSource' in source:
                        repo_name = source['repoSource'].get('repoName', 'unknown')
                    elif 'storageSource' in source:
                        repo_name = 'GCS source'
                    
                    # Status emoji
                    status_emoji = {
                        'SUCCESS': '',
                        'WORKING': '⏳',
                        'QUEUED': '',
                        'FAILURE': '',
                        'TIMEOUT': '⏰',
                        'CANCELLED': ''
                    }.get(status, '')
                    
                    print(f"{i}. {status_emoji} {status:<10} | ID: {build_id} | {repo_name}")
                    
                    # Check if status changed
                    if build_id in last_build_statuses:
                        if last_build_statuses[build_id] != status:
                            print(f"    Status changed: {last_build_statuses[build_id]} → {status}")
                    
                    last_build_statuses[build_id] = status
                    
                    # Show logs for WORKING builds
                    if status == 'WORKING':
                        print(f"    Latest logs:")
                        logs = get_build_logs(project_id, build['id'], lines=3)
                        for line in logs.split('\n')[-3:]:
                            if line.strip():
                                print(f"      {line[:60]}")
            else:
                print("   No recent builds found")
            
            # Get Cloud Run services
            print("\n CLOUD RUN SERVICES:")
            print("-"*70)
            
            services = get_cloud_run_services(project_id, region)
            
            if services:
                for service in services:
                    name = service.get('metadata', {}).get('name', 'unknown')
                    status = service.get('status', {})
                    url = status.get('url', 'No URL yet')
                    
                    conditions = status.get('conditions', [])
                    ready = False
                    for condition in conditions:
                        if condition.get('type') == 'Ready':
                            ready = condition.get('status') == 'True'
                            break
                    
                    status_emoji = '' if ready else '⏳'
                    print(f"  {status_emoji} {name:<20} | {url}")
            else:
                print("   No services deployed yet")
            
            print("\n" + "-"*70)
            print(f"Next update in {refresh_interval} seconds... (Ctrl+C to exit)")
            
            time.sleep(refresh_interval)
            
    except KeyboardInterrupt:
        print("\n\n Monitoring stopped")
        print("="*70)

def main():
    """Main entry point"""
    
    # Get project ID
    project_id = None
    
    # Try to get from gcloud config
    output, code = run_command('gcloud config get-value project')
    if code == 0 and output.strip():
        project_id = output.strip()
    
    # Ask user if needed
    if not project_id or project_id == 'unset':
        project_id = input("Enter GCP Project ID: ").strip()
    
    if not project_id:
        print(" Project ID required")
        sys.exit(1)
    
    # Get region
    region = input("Enter region (default: us-central1): ").strip() or "us-central1"
    
    # Get refresh interval
    try:
        interval = int(input("Refresh interval in seconds (default: 10): ").strip() or "10")
    except:
        interval = 10
    
    # Start monitoring
    monitor_builds(project_id, region, interval)

if __name__ == "__main__":
    main()