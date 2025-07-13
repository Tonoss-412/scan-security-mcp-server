import csv
import os
import re
import subprocess

CSV_PATH = 'recon_mcpserver/mcp_servers.csv'
CLONE_ROOT = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.join(CLONE_ROOT, 'repo')

def sanitize_dirname(name):
    # Chỉ giữ lại chữ cái, số, gạch dưới, gạch ngang. Thay các ký tự khác bằng _
    return re.sub(r'[^a-zA-Z0-9_-]', '_', name)

def main():
    if not os.path.exists(REPO_DIR):
        os.makedirs(REPO_DIR)
    with open(CSV_PATH, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            repo_name = row['repository_name']
            repo_url = row['repository_url']
            if not repo_name or not repo_url:
                continue
            safe_name = sanitize_dirname(repo_name)
            target_dir = os.path.join(REPO_DIR, safe_name)
            if os.path.exists(target_dir):
                print(f"[SKIP] {safe_name} (already exists)")
                continue
            print(f"[CLONE] {repo_url} -> repo/{safe_name}")
            try:
                subprocess.run([
                    'git', 'clone', '--depth', '1', repo_url, safe_name
                ], cwd=REPO_DIR, check=True)
            except Exception as e:
                print(f"[ERROR] Failed to clone {repo_url}: {e}")

if __name__ == '__main__':
    main() 
