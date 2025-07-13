# ===================== recon full repo python (logic cũ, có sắp xếp theo số sao) =====================
import requests
import csv
import time
import os
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# Global variables for easy access during recursion
all_found_repos = []
seen_repo_urls = set()

def fetch_and_store_results(query, headers):
    """Paginates through all results for a 'safe' query (< 1000 results) and stores them."""
    page = 1
    while True:
        params = {
            "q": query,
            "sort": "created",
            "order": "asc",
            "per_page": 100,
            "page": page
        }
        
        response = requests.get("https://api.github.com/search/repositories", params=params, headers=headers)
        
        if response.status_code != 200:
            print(f"Error fetching page {page} for query '{query}'. Status: {response.status_code}")
            print(f"Response: {response.text}")
            break

        items = response.json().get('items', [])
        if not items:
            break # No more results

        for repo in items:
            repo_url = repo['html_url']
            if repo_url not in seen_repo_urls:
                all_found_repos.append({
                    'repository_name': repo['name'],
                    'repository_url': repo_url,
                    'description': repo.get('description', ''),
                    'stargazers_count': repo.get('stargazers_count', 0)
                })
                seen_repo_urls.add(repo_url)

        if len(items) < 100:
            break # Last page for this query
        
        page += 1
        time.sleep(0.5)

def process_time_chunk_recursively(start_date, end_date, base_query, headers):
    """
    Recursively searches a time chunk, splitting it in half if it likely contains more than 1000 results.
    """
    # Use ISO 8601 format for the query, which is robust.
    start_date_str = start_date.strftime('%Y-%m-%dT%H:%M:%SZ')
    end_date_str = end_date.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    # Base case: If the time window is less than a second, it cannot be split further.
    if start_date >= end_date:
        return

    time_chunk_query = f"{base_query} created:{start_date_str}..{end_date_str}"
    
    # Perform a "dry run" search to get the total count for this chunk.
    dry_run_params = {"q": time_chunk_query, "per_page": 1}
    response = requests.get("https://api.github.com/search/repositories", params=dry_run_params, headers=headers)

    if response.status_code != 200:
        print(f"Error during dry run for {start_date.date()}..{end_date.date()}. Status: {response.status_code}")
        print(f"Response: {response.text}")
        return

    data = response.json()
    total_count = data.get('total_count', 0)
    print(f"Checking {start_date.date()} to {end_date.date()}... Found {total_count} potential results.")
    
    # If total_count is 1000, it's ambiguous. We must split.
    if total_count >= 1000:
        print(f"--> Interval has too many results ({total_count}). Splitting.")
        mid_point = start_date + (end_date - start_date) / 2
        
        # Recursively process the two new, smaller chunks
        process_time_chunk_recursively(start_date, mid_point, base_query, headers)
        process_time_chunk_recursively(mid_point + timedelta(seconds=1), end_date, base_query, headers)
    elif total_count > 0:
        # This interval is "safe" to fetch completely.
        print(f"--> Interval is safe ({total_count} results). Fetching all pages.")
        fetch_and_store_results(time_chunk_query, headers)

def adaptive_search_main(search_terms, output_file, token=None):
    """Main function to orchestrate the adaptive, recursive search."""
    # Clear global lists to ensure the script is re-runnable
    all_found_repos.clear()
    seen_repo_urls.clear()

    # Define keywords to exclude to filter out documentation, examples, etc.
    exclusions = ["client", "example", "tutorial", "awesome"]
    exclusion_string = " ".join([f"NOT {word}" for word in exclusions])

    quoted_terms = ' OR '.join([f'"{term}"' for term in search_terms])
    base_query = f"({quoted_terms}) {exclusion_string} in:description language:Python"
    print(f"Base search query: {base_query}")

    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers['Authorization'] = f'token {token}'
    else:
        print("Warning: No GitHub token provided. You will likely hit the rate limit quickly.")

    # Iterate through initial large chunks (month by month)
    start_date = datetime(2024, 11, 1)
    end_of_search_period = datetime.now()
    
    current_month_start = start_date
    while current_month_start < end_of_search_period:
        current_month_end = current_month_start + relativedelta(months=1) - timedelta(seconds=1)
        
        if current_month_end > end_of_search_period:
            current_month_end = end_of_search_period
        
        print(f"\n--- Processing Top-Level Chunk: {current_month_start.date()} to {current_month_end.date()} ---")
        process_time_chunk_recursively(current_month_start, current_month_end, base_query, headers)
        
        current_month_start += relativedelta(months=1)

    # Sắp xếp theo số sao giảm dần trước khi ghi file
    all_found_repos.sort(key=lambda x: x.get('stargazers_count', 0), reverse=True)

    # Final step: write all collected results to the CSV file
    print(f"\nSearch complete. Total unique repositories found: {len(all_found_repos)}")
    print(f"Saving results to {output_file}...")
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['repository_name', 'repository_url', 'description', 'stargazers_count']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_found_repos)
    print("Done.")

    # Đọc lại file, sort lại theo số sao giảm dần, ghi đè lại file
    with open(output_file, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        rows = list(reader)
        rows.sort(key=lambda x: int(x.get('stargazers_count', 0)), reverse=True)
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['repository_name', 'repository_url', 'description', 'stargazers_count']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print("Sorted CSV by stargazers_count.")

if __name__ == "__main__":
    github_token = os.getenv("GITHUB_TOKEN")
    search_terms = ["mcp server", "Model Context Protocol server"]
    output_file = "mcp_servers.csv"
    
    adaptive_search_main(
        search_terms,
        output_file,
        token=github_token
    )
