import os
import json
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from datetime import datetime
import pytz

def format_task_message(issue_data, event_type):
    title = issue_data['title']
    url = issue_data['html_url']
    user = issue_data['user']['login']
    labels = [label['name'] for label in issue_data.get('labels', [])]
    
    if event_type == 'opened':
        header = "🎯 새로운 태스크가 생성되었습니다"
    elif event_type == 'labeled':
        if any(label.startswith('task:') for label in labels):
            header = "📋 새로운 태스크가 등록되었습니다"
        elif 'in-progress' in labels:
            header = "▶️ 태스크가 진행 중입니다"
        elif 'done' in labels:
            header = "✅ 태스크가 완료되었습니다"
        else:
            header = "🏷 태스크 상태가 업데이트되었습니다"
    else:
        header = "ℹ️ 태스크가 업데이트되었습니다"
    
    category = next((label[5:] for label in labels if label.startswith('task:')), "미분류")
    
    return {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": header
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*제목:*\n{title}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*담당자:*\n{user}"
                    }
                ]
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*카테고리:*\n{category}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*상태:*\n{'진행 중' if 'in-progress' in labels else '완료' if 'done' in labels else '대기 중'}"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"👉 <{url}|태스크 보러가기>"
                }
            },
            {
                "type": "divider"
            }
        ]
    }

def format_todo_message(issue_data, event_type):
    """Todo 관련 Slack 메시지 포맷팅"""
    title = issue_data['title']
    url = issue_data['html_url']
    user = issue_data['user']['login']
    body = issue_data.get('body', '')
    
    task_refs = [line for line in body.split('\n') if 'task:' in line.lower()]
    linked_tasks = [f"#{ref.split('#')[1].split()[0]}" for ref in task_refs if '#' in ref]
    
    if event_type == 'opened':
        header = "🎯 새로운 Todo가 생성되었습니다"
    elif event_type == 'labeled':
        header = "🔄 Todo 상태가 업데이트되었습니다"
    else:
        header = "ℹ️ Todo가 업데이트되었습니다"
    
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": header
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*제목:*\n{title}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*작성자:*\n{user}"
                }
            ]
        }
    ]
    
    if linked_tasks:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*연결된 태스크:*\n{', '.join(linked_tasks)}"
            }
        })
    
    blocks.extend([
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"👉 <{url}|Todo 보러가기>"
            }
        },
        {
            "type": "divider"
        }
    ])
    
    return {"blocks": blocks}

def format_daily_log_message(issue_data):
    """일일 개발 로그 Slack 메시지 포맷팅"""
    title = issue_data['title']
    url = issue_data['html_url']
    
    return {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "📅 새로운 일일 개발 로그가 생성되었습니다"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{title}*\n\n👉 <{url}|로그 보러가기>"
                }
            },
            {
                "type": "divider"
            }
        ]
    }

def format_commit_message(commit_data, repo_name):
    commit_msg = commit_data['message']
    commit_url = commit_data['url'].replace('api.github.com/repos', 'github.com')
    author = commit_data['author']['name']
    commit_id = commit_data['id'][:7]
    
    commit_title = commit_msg.split('\n')[0]
    
    return {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🔨 새로운 커밋이 푸시되었습니다"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*커밋:*\n{commit_title}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*작성자:*\n{author}"
                    }
                ]
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*저장소:*\n{repo_name}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*커밋 ID:*\n`{commit_id}`"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"👉 <{commit_url}|커밋 보러가기>"
                }
            },
            {
                "type": "divider"
            }
        ]
    }

def format_commit_todo_message(commit_data, repo_name):
    commit_msg = commit_data['message']
    commit_url = commit_data['url'].replace('api.github.com/repos', 'github.com')
    author = commit_data['author']['name']
    
    todo_section = ""
    lines = commit_msg.split('\n')
    is_todo = False
    current_category = None
    todo_items = []
    
    for line in lines:
        if line.strip() == '[todo]':
            is_todo = True
            continue
        if is_todo:
            if line.startswith('@'):
                current_category = line[1:].strip()
            elif line.startswith('-') and current_category:
                todo_items.append({
                    'category': current_category,
                    'item': line[1:].strip()
                })
    
    if not todo_items:
        return None
    
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "📝 커밋에서 새로운 TODO 항목이 추가되었습니다"
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*작성자:*\n{author}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*저장소:*\n{repo_name}"
                }
            ]
        }
    ]
    
    categories = {}
    for item in todo_items:
        if item['category'] not in categories:
            categories[item['category']] = []
        categories[item['category']].append(item['item'])
    
    for category, items in categories.items():
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{category}*\n" + "\n".join(f"• {item}" for item in items)
            }
        })
    
    blocks.extend([
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"👉 <{commit_url}|커밋 보러가기>"
            }
        },
        {
            "type": "divider"
        }
    ])
    
    return {"blocks": blocks}

def send_slack_notification(message):
    """Slack으로 메시지 전송"""
    client = WebClient(token=os.environ['SLACK_BOT_TOKEN'])
    channel_id = os.environ['SLACK_CHANNEL_ID']    
    try:
        response = client.chat_postMessage(
            channel=channel_id,
            blocks=message['blocks']
        )
        print(f"메시지 전송 성공: {response['ts']}")
    except SlackApiError as e:
        print(f"에러 발생: {e.response['error']}")

def main():
    event_path = os.environ['GITHUB_EVENT_PATH']
    event_name = os.environ['GITHUB_EVENT_NAME']
    
    with open(event_path, 'r', encoding='utf-8') as f:
        event_data = json.load(f)
    
    if event_name == 'push':
        latest_commit = event_data['commits'][-1] if event_data.get('commits') else None
        if latest_commit:
            repo_name = event_data['repository']['name']
            commit_message = format_commit_message(latest_commit, repo_name)
            send_slack_notification(commit_message)
            
            todo_message = format_commit_todo_message(latest_commit, repo_name)
            if todo_message:
                send_slack_notification(todo_message)
        else:
            return
    else:
        issue_data = event_data['issue']
        labels = [label['name'] for label in issue_data.get('labels', [])]
        
        if any(label.startswith('task:') for label in labels):
            message = format_task_message(issue_data, event_name)
        elif 'todo' in labels:
            message = format_todo_message(issue_data, event_name)
        elif '📅 Daily Development Log' in issue_data['title']:
            message = format_daily_log_message(issue_data)
        else:
            return
        
        send_slack_notification(message)

if __name__ == '__main__':
    main() 