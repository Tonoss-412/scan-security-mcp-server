import requests
import csv
import time
import os
import base64

def get_readme_content(owner, repo, token=None):
    url = f"https://api.github.com/repos/{owner}/{repo}/readme"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        content = resp.json().get("content", "")
        encoding = resp.json().get("encoding", "base64")
        if encoding == "base64":
            try:
                return base64.b64decode(content).decode("utf-8", errors="ignore")
            except Exception:
                return ""
        else:
            return content
    return ""

def search_and_filter_mcp_servers(search_terms, output_file, token=None, sort_by="stars", order="asc", max_results=1000):
    query = " OR ".join([f'"{term}" in:readme' for term in search_terms])
    query = f"({query}) language:Python"
    print(f"Search query: {query}")

    base_url = "https://api.github.com/search/repositories"
    params = {
        "q": query,
        "sort": sort_by,
        "order": order,
        "per_page": 100
    }
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers['Authorization'] = f'token {token}'

    repos = []
    page = 1
    seen_repo_urls = set()
    found_count = 0

    while True:
        params["page"] = page
        response = requests.get(base_url, params=params, headers=headers)
        if response.status_code != 200:
            print(f"Error: {response.status_code}")
            try:
                print(response.json())
            except Exception:
                print(response.text)
            break

        items = response.json().get('items', [])
        if not items:
            break

        for repo in items:
            repo_url = repo['html_url']
            if repo_url in seen_repo_urls:
                continue
            owner = repo['owner']['login']
            repo_name = repo['name']
            readme = get_readme_content(owner, repo_name, token)
            readme_lower = readme.lower()
            # Chỉ lấy repo có chứa đúng cụm từ cần tìm
            if any(term.lower() in readme_lower for term in search_terms):
                repos.append({
                    'repository_name': repo_name,
                    'repository_url': repo_url,
                    'description': repo.get('description', ''),
                    'stars': repo.get('stargazers_count', 0),
                    'created_at': repo.get('created_at', ''),
                    'updated_at': repo.get('updated_at', ''),
                })
                seen_repo_urls.add(repo_url)
                found_count += 1
                print(f"Found: {repo_name} ({repo_url})")
            time.sleep(0.2)  # tránh bị rate limit

            if found_count >= max_results:
                break

        print(f"Page {page} done, total found: {found_count}")
        if found_count >= max_results or len(items) < 100:
            break
        page += 1
        time.sleep(0.5)

    # Ghi file CSV, chỉ chứa repo duy nhất (theo url)
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['repository_name', 'repository_url']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for repo in repos:
            writer.writerow(repo)
    print(f"Results saved to {output_file}")

if __name__ == "__main__":
    github_token = "github_token"
    search_terms = ["mcp server", "Model Context Protocol server"]
    output_file = "mcp_servers.csv"
    search_and_filter_mcp_servers(
        search_terms,
        output_file,
        token=github_token,
        sort_by="stars",
        order="asc",
        max_results=1000
    )
