import requests
import argparse
import json
import os
from collections import defaultdict, deque

parser = argparse.ArgumentParser(description='Export Grafana folders and dashboards to Terraform')
parser.add_argument('--url', type=str, required=True, help='Grafana instance URL')
parser.add_argument('--api-key', type=str, required=True, help='Admin API key')
parser.add_argument('--folder-names', type=str, nargs='+', help='List of folder names to include')
parser.add_argument('--skip-resources', type=str, help='Comma-delimited list of dashboard resource names to skip in Terraform (e.g., d_cardinality_management,d_cardinality_management_metrics_detail)')
parser.add_argument('--timeout', type=int, default=300, help='Timeout in seconds for API requests (default: 300)')
args = parser.parse_args()

headers = {'Authorization': f'Bearer {args.api_key}'}

def get_all_folders():
    """Fetch specified folders and all their nested subfolders"""
    all_folders = []
    processed_uids = set()
    
    def fetch_folder_and_children(uid):
        if uid in processed_uids:
            return
        
        processed_uids.add(uid)
        url = f"{args.url.rstrip('/')}/api/folders/{uid}"
        try:
            response = requests.get(url, headers=headers, timeout=args.timeout)
            response.raise_for_status()
            folder = response.json()
            
            # Skip GrafanaCloud folder
            if folder['title'] == 'GrafanaCloud':
                print(f"Skipping GrafanaCloud folder")
                return
            
            all_folders.append({
                'uid': folder['uid'],
                'title': folder['title'],
                'parent_uid': folder.get('parentUid')
            })
            
            # Get all subfolders
            subfolders_url = f"{args.url.rstrip('/')}/api/folders"
            params = {'parentUid': uid}
            subfolders_response = requests.get(subfolders_url, headers=headers, params=params, timeout=args.timeout)
            subfolders_response.raise_for_status()
            
            # Recursively process each subfolder
            for subfolder in subfolders_response.json():
                fetch_folder_and_children(subfolder['uid'])
                
        except requests.exceptions.HTTPError as e:
            print(f"Error fetching folder {uid}: {e.response.text}")
        except requests.exceptions.Timeout:
            print(f"Timeout fetching folder {uid}")
    
    # First get all folders to find the ones we want
    url = f"{args.url.rstrip('/')}/api/folders"
    try:
        response = requests.get(url, headers=headers, timeout=args.timeout)
        response.raise_for_status()
        all_folders_response = response.json()
        
        if not all_folders_response:
            print("No folders found in the Grafana instance")
            return all_folders
            
        # Create a map of folder names to their data
        folder_map = {folder['title']: folder for folder in all_folders_response}
        
        if not args.folder_names:
            print("No folder names specified. Processing all folders...")
            for folder in all_folders_response:
                fetch_folder_and_children(folder['uid'])
        else:
            # Get the folders we want by name and process their hierarchies
            for name in args.folder_names:
                if name in folder_map:
                    folder = folder_map[name]
                    fetch_folder_and_children(folder['uid'])
                else:
                    print(f"Warning: Folder '{name}' not found")
    
    except requests.exceptions.HTTPError as e:
        print(f"Error fetching folders: {e.response.text}")
        return all_folders
    except requests.exceptions.Timeout:
        print("Timeout fetching folders")
        return all_folders
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return all_folders
    
    return all_folders

def get_all_dashboards():
    """Fetch all dashboards from Grafana"""
    all_dashboards = []
    
    # Get all dashboards
    url = f"{args.url.rstrip('/')}/api/search"
    params = {
        'type': 'dash-db',
        'limit': 1000
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=args.timeout)
        response.raise_for_status()
        
        for dashboard in response.json():
            # Get the full dashboard JSON
            dashboard_url = f"{args.url.rstrip('/')}/api/dashboards/uid/{dashboard['uid']}"
            dashboard_response = requests.get(dashboard_url, headers=headers, timeout=args.timeout)
            dashboard_response.raise_for_status()
            dashboard_data = dashboard_response.json()
            
            # Get dashboard JSON and make it editable
            dashboard_json = dashboard_data['dashboard']
            dashboard_json['editable'] = True
            
            # Remove version, id, and gnetId fields to avoid conflicts
            if 'version' in dashboard_json:
                del dashboard_json['version']
            if 'id' in dashboard_json:
                del dashboard_json['id']
            if 'gnetId' in dashboard_json:
                del dashboard_json['gnetId']
            
            all_dashboards.append({
                'uid': dashboard['uid'],
                'title': dashboard['title'],
                'folder_uid': dashboard.get('folderUid'),
                'json': dashboard_json
            })
            
    except requests.exceptions.HTTPError as e:
        print(f"Error fetching dashboards: {e.response.text}")
    except requests.exceptions.Timeout:
        print("Timeout fetching dashboards")
    
    return all_dashboards

def generate_terraform(folders, dashboards):
    """Generate Terraform config for folders and dashboards"""
    tf_config = ""
    skip_resources = set(resource.strip() for resource in (args.skip_resources or '').split(',')) if args.skip_resources else set()
    
    # Create dashboards directory if it doesn't exist
    os.makedirs('dashboards', exist_ok=True)
    
    # Generate folder resources
    for folder in sorted(folders, key=lambda x: x['uid']):
        folder_id = folder['uid'].replace('-', '_')
        tf_config += f"""resource "grafana_folder" "{folder_id}" {{
  title = "{folder['title']}"
  uid   = "{folder['uid']}"
"""
        
        if folder['parent_uid']:
            parent_id = folder['parent_uid'].replace('-', '_')
            tf_config += f'  parent_folder_uid = "{folder["parent_uid"]}"\n'
            tf_config += f'  depends_on = [grafana_folder.{parent_id}]\n'
        
        tf_config += "}\n\n"
    
    # Generate dashboard resources
    for dashboard in dashboards:
        # Use the dashboard's UID as the filename
        dashboard_file = f"dashboards/{dashboard['uid']}.json"
        dashboard_id = f"d_{dashboard['uid']}"
        
        # Skip specified dashboard resources
        if dashboard_id in skip_resources:
            print(f"Skipping dashboard resource: {dashboard_id}")
            continue
            
        folder_id = dashboard['folder_uid'].replace('-', '_')
        
        # Save dashboard JSON to file
        with open(dashboard_file, 'w') as f:
            json.dump(dashboard['json'], f, indent=2)
        
        tf_config += f"""resource "grafana_dashboard" "{dashboard_id}" {{
  folder = grafana_folder.{folder_id}.uid
  config_json = jsonencode(jsondecode(file("{dashboard_file}")))
  overwrite = true
  depends_on = [grafana_folder.{folder_id}]
}}

"""
    
    return tf_config

if __name__ == '__main__':
    try:
        # Get all folders
        folders = get_all_folders()
        print(f"Found {len(folders)} folders")
        
        # Get all dashboards
        all_dashboards = get_all_dashboards()
        
        # Filter dashboards to only those in target folders
        target_folder_uids = {folder['uid'] for folder in folders}
        target_dashboards = [
            dashboard for dashboard in all_dashboards
            if dashboard['folder_uid'] in target_folder_uids
        ]
        print(f"Found {len(target_dashboards)} dashboards in target folders")
        
        # Generate Terraform config
        tf_output = generate_terraform(folders, target_dashboards)
        
        # Write to file
        with open('grafana.tf', 'w') as f:
            f.write(tf_output)
            
        print(f"Generated Terraform config with {len(folders)} folders and {len(target_dashboards)} dashboards")
        print(f"Dashboard JSON files are stored in the 'dashboards' directory")
        
    except requests.exceptions.HTTPError as e:
        print(f"API Error: {e.response.text}")
    except requests.exceptions.Timeout:
        print("Timeout error occurred") 