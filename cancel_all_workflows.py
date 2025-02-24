import requests
import time

# GitHub 설정
token = "YOUR_PAT_TOKEN"  # PAT 토큰으로 교체하세요
owner = "KGAMeta8thTeam1"
repo = "KGAMeta8th_ContractProject_DM"

headers = {
    "Authorization": f"token {token}",
    "Accept": "application/vnd.github.v3+json"
}

def cancel_all_runs():
    print("Starting mass cancellation...")
    page = 1
    total_cancelled = 0

    while True:
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs?status=queued,in_progress&per_page=100&page={page}"
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print(f"Error fetching runs: {response.status_code}")
            break
            
        data = response.json()
        runs = data.get("workflow_runs", [])
        
        if not runs:
            break
            
        for run in runs:
            cancel_url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run['id']}/cancel"
            requests.post(cancel_url, headers=headers)
            total_cancelled += 1
            if total_cancelled % 100 == 0:
                print(f"Cancelled {total_cancelled} workflows...")
            time.sleep(0.1)  # API 제한 방지
        
        page += 1
        time.sleep(1)  # API 제한 방지

    print(f"Total workflows cancelled: {total_cancelled}")

if __name__ == "__main__":
    cancel_all_runs() 