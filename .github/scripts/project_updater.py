import os
import json
import logging
from github import Github
import requests
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_project_v2(github_token, org_name, project_number):
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    query = """
    query($org: String!, $number: Int!) {
        organization(login: $org) {
            projectV2(number: $number) {
                id
                title
                url
                fields(first: 20) {
                    nodes {
                        ... on ProjectV2SingleSelectField {
                            id
                            name
                            options {
                                id
                                name
                            }
                        }
                    }
                }
            }
        }
    }
    """
    
    variables = {
        "org": org_name,
        "number": project_number
    }
    
    try:
        response = requests.post(
            'https://api.github.com/graphql',
            json={'query': query, 'variables': variables},
            headers=headers
        )
        response.raise_for_status()
        result = response.json()
        
        if 'errors' in result:
            logger.error(f"GraphQL errors: {result['errors']}")
            return None
            
        return result['data']['organization']['projectV2']
    except Exception as e:
        logger.error(f"Error fetching project v2: {str(e)}")
        return None

def set_issue_status(github_token, project_id, item_id, status_field_id, status_option_id):
    """이슈의 상태 필드 설정"""
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    mutation = """
    mutation($project: ID!, $item: ID!, $field: ID!, $value: String!) {
        updateProjectV2ItemFieldValue(
            input: {
                projectId: $project
                itemId: $item
                fieldId: $field
                value: { singleSelectOptionId: $value }
            }
        ) {
            projectV2Item {
                id
            }
        }
    }
    """
    
    variables = {
        "project": project_id,
        "item": item_id,
        "field": status_field_id,
        "value": status_option_id
    }
    
    try:
        response = requests.post(
            'https://api.github.com/graphql',
            json={'query': mutation, 'variables': variables},
            headers=headers
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error setting issue status: {str(e)}")
        return None

def add_issue_to_project_v2(github_token, project_id, issue_node_id):
    """이슈를 프로젝트에 추가하고 상태를 설정"""
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    mutation = """
    mutation($project: ID!, $issue: ID!) {
        addProjectV2ItemById(input: {projectId: $project, contentId: $issue}) {
            item {
                id
            }
        }
    }
    """
    
    variables = {
        "project": project_id,
        "issue": issue_node_id
    }
    
    try:
        response = requests.post(
            'https://api.github.com/graphql',
            json={'query': mutation, 'variables': variables},
            headers=headers
        )
        response.raise_for_status()
        result = response.json()
        
        if result and 'errors' not in result:
            return result['data']['addProjectV2ItemById']['item']['id']
        return None
    except Exception as e:
        logger.error(f"Error adding issue to project: {str(e)}")
        return None

def extract_issue_numbers(text):
    """이슈 본문에서 체크박스 형식의 이슈 참조도 추출"""
    pattern = r'-\s*\[[ xX]\]\s*#(\d+)'
    matches = re.finditer(pattern, text)
    return [match.group(1) for match in matches]

def parse_existing_issue(body):
    """이슈 본문에서 체크박스 형식의 TODO 항목을 추출합니다."""
    todos = []
    for line in body.split('\n'):
        if line.startswith('- ['):
            checked = 'x' in line[0:5] or 'X' in line[0:5]
            text = line[5:].strip()
            todos.append((checked, text))
    return {'todos': todos}

def get_issue_node_id(github_token, repo_owner, repo_name, issue_number):
    """GraphQL을 사용하여 이슈의 node_id를 가져옵니다."""
    query = """
    query($owner: String!, $name: String!, $number: Int!) {
        repository(owner: $owner, name: $name) {
            issue(number: $number) {
                id
            }
        }
    }
    """
    
    variables = {
        "owner": repo_owner,
        "name": repo_name,
        "number": issue_number
    }
    
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    try:
        response = requests.post(
            'https://api.github.com/graphql',
            json={'query': query, 'variables': variables},
            headers=headers
        )
        response.raise_for_status()
        result = response.json()
        return result['data']['repository']['issue']['id']
    except Exception as e:
        logger.error(f"Error fetching node_id for issue #{issue_number}: {str(e)}")
        return None

def process_todo_items(repo, todos, github_token, project_id, existing_items):
    """이슈를 프로젝트 보드에 추가만 하고, 새 이슈를 생성하지 않습니다."""
    current_category = 'General'
    repo_owner, repo_name = os.environ["GITHUB_REPOSITORY"].split('/')
    
    for checked, text in todos:
        if text.startswith('@'):
            current_category = text[1:].strip()
            continue
            
        if text.startswith('#'):
            issue_number = int(text[1:])
            if issue_number in existing_items:
                logger.info(f"Issue #{issue_number} already in project, skipping")
                continue
                
            try:
                node_id = get_issue_node_id(github_token, repo_owner, repo_name, issue_number)
                if node_id:
                    add_issue_to_project_v2(github_token, project_id, node_id)
                    logger.info(f"Added issue #{issue_number} to project")
            except Exception as e:
                logger.error(f"Failed to add issue #{issue_number} to project: {str(e)}")

def get_project_items(github_token, project_id):
    """프로젝트의 현재 항목들을 가져옵니다."""
    query = """
    query($project: ID!) {
        node(id: $project) {
            ... on ProjectV2 {
                items(first: 100) {
                    nodes {
                        id
                        content {
                            ... on Issue {
                                id
                                number
                            }
                        }
                    }
                }
            }
        }
    }
    """
    
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    try:
        response = requests.post(
            'https://api.github.com/graphql',
            json={'query': query, 'variables': {"project": project_id}},
            headers=headers
        )
        response.raise_for_status()
        result = response.json()
        return {item['content']['number']: item['id'] 
                for item in result['data']['node']['items']['nodes'] 
                if item['content'] and 'number' in item['content']}
    except Exception as e:
        logger.error(f"Error fetching project items: {str(e)}")
        return {}

def update_project_board():
    try:
        github_token = os.environ.get("PAT") or os.environ["GITHUB_TOKEN"]
        g = Github(github_token)
        
        with open(os.environ["GITHUB_EVENT_PATH"]) as f:
            event = json.load(f)
        
        issue = event.get("issue", {})
        if not issue or "Development Status Report" not in issue.get("title", ""):
            logger.info("Not a DSR issue update, skipping")
            return
            
        repo = g.get_repo(os.environ["GITHUB_REPOSITORY"])
        repo_owner, repo_name = os.environ["GITHUB_REPOSITORY"].split('/')
        
        org_name = "KGAMeta8thTeam1"
        project_number = 2
        
        project = get_project_v2(github_token, org_name, project_number)
        if not project:
            logger.error("Could not find project v2")
            return
            
        existing_items = get_project_items(github_token, project['id'])
        logger.info(f"Found {len(existing_items)} existing items in project")
            
        status_field = None
        todo_option = None
        for field in project['fields']['nodes']:
            if field.get('name') == 'Status':
                status_field = field
                for option in field['options']:
                    if option['name'] == 'Todo':
                        todo_option = option
                        break
                break
        
        if not status_field or not todo_option:
            logger.error("Could not find Status field or Todo option")
            return
            
        issue_numbers = re.findall(r'#(\d+)', issue.get("body", ""))
        logger.info(f"Found {len(issue_numbers)} issue references in DSR")
        
        for issue_number in issue_numbers:
            try:
                issue_number = int(issue_number)
                if issue_number in existing_items:
                    logger.info(f"Issue #{issue_number} already in project, skipping")
                    continue
                    
                node_id = get_issue_node_id(github_token, repo_owner, repo_name, issue_number)
                if node_id:
                    item_id = add_issue_to_project_v2(github_token, project['id'], node_id)
                    if item_id:
                        set_issue_status(github_token, project['id'], item_id, status_field['id'], todo_option['id'])
                        logger.info(f"Added issue #{issue_number} to project with Todo status")
            except Exception as e:
                logger.error(f"Failed to process issue #{issue_number}: {str(e)}")
                
        todos = parse_existing_issue(issue.get("body", ""))['todos']
        process_todo_items(repo, todos, github_token, project['id'], existing_items)
        
    except Exception as e:
        logger.error(f"Failed to update project board: {str(e)}")
        raise

def handle_card_movement(card_event, columns, repo):
    logger.info(f"Processing card movement event: {card_event['id']}")
    if card_event["column_id"]:
        logger.debug(f"Card moved to column ID: {card_event['column_id']}")
        issue = get_issue_from_card(card_event, repo)
        if issue:
            logger.info(f"Updating status for issue #{issue.number}")
            update_issue_status(issue, card_event["column_id"], columns)
        else:
            logger.debug("No associated issue found for card")

def handle_issue_status(issue, columns):
    logger.info(f"Processing issue status: #{issue['number']}")
    if any(label["name"] == "done" for label in issue["labels"]):
        logger.info("Moving issue to Done column")
        move_to_column(issue, columns["Done"])
    elif any(label["name"] == "in-progress" for label in issue["labels"]):
        logger.info("Moving issue to In Progress column")
        move_to_column(issue, columns["In Progress"])
    else:
        logger.info("Moving issue to To Do column")
        move_to_column(issue, columns["To Do"])

def get_issue_from_card(card, repo):
    logger.debug(f"Extracting issue from card: {card['id']}")
    if "content_url" in card:
        issue_url = card["content_url"]
        issue_number = int(issue_url.split("/")[-1])
        logger.debug(f"Found issue #{issue_number}")
        return repo.get_issue(issue_number)
    logger.debug("No content URL found in card")
    return None

def move_to_column(issue, column):
    logger.info(f"Moving issue #{issue.number} to column: {column.name}")
    for card in column.get_cards():
        if card.content_url == issue.url:
            logger.debug("Issue already in target column")
            return
    column.create_card(content_id=issue.id, content_type="Issue")
    logger.info(f"Created new card for issue #{issue.number} in column {column.name}")

def update_issue_status(issue, column_id, columns):
    logger.info(f"Updating status for issue #{issue.number}")
    status_labels = {
        columns["To Do"].id: "todo",
        columns["In Progress"].id: "in-progress",
        columns["Done"].id: "done"
    }
    
    if column_id in status_labels:
        logger.debug(f"Updating labels for column ID: {column_id}")
        for label in issue.labels:
            if label.name in status_labels.values():
                logger.debug(f"Removing label: {label.name}")
                issue.remove_from_labels(label.name)
        
        new_label = status_labels[column_id]
        logger.debug(f"Adding new label: {new_label}")
        issue.add_to_labels(new_label)
    else:
        logger.warning(f"Unknown column ID: {column_id}")

if __name__ == "__main__":
    update_project_board() 