import os
from github import Github
from datetime import datetime
import re
import json
import requests

TASK_CATEGORIES = {
    "기능 개발": {
        "emoji": "🔧",
        "name": "기능 개발",
        "description": "주요 기능 개발 태스크"
    },
    "UI/UX": {
        "emoji": "🎨",
        "name": "UI/UX",
        "description": "UI/UX 디자인 및 개선"
    },
    "QA/테스트": {
        "emoji": "🔍",
        "name": "QA/테스트",
        "description": "품질 보증 및 테스트"
    },
    "문서화": {
        "emoji": "📚",
        "name": "문서화",
        "description": "문서 작성 및 관리"
    },
    "유지보수": {
        "emoji": "🛠️",
        "name": "유지보수",
        "description": "버그 수정 및 유지보수"
    }
}

def find_report_issue(repo, project_name):
    report_title = f"[{project_name}] 프로젝트 진행보고서"
    open_issues = repo.get_issues(state='open')
    for issue in open_issues:
        if issue.title == report_title:
            return issue
    return None

def get_assignees_string(issue):
    return ', '.join([assignee.login for assignee in issue.assignees]) if issue.assignees else 'TBD'

def get_task_duration(task_issue):
    """태스크의 예상 소요 시간을 계산합니다."""
    print(f"\n=== 태스크 #{task_issue.number}의 예상 시간 추출 시작 ===")
    
    # 1. 기본 정보 섹션에서 예상 시간 찾기
    body_lines = task_issue.body.split('\n')
    for line in body_lines:
        line = line.strip()
        if '예상 시간:' in line or '예상시간:' in line:
            time_str = line.split(':', 1)[1].strip()
            print(f"기본 정보에서 예상 시간 발견: {time_str}")
            if time_str.endswith('d'):
                return time_str
            else:
                return f"{time_str}d"
    
    # 2. 제안일과 구현목표일로부터 계산
    proposal_date = None
    target_date = None
    
    for line in body_lines:
        line = line.strip()
        if '제안일:' in line:
            try:
                proposal_date = datetime.strptime(line.split(':', 1)[1].strip(), '%Y.%m.%d')
                print(f"제안일 발견: {proposal_date.date()}")
            except:
                continue
        elif '구현목표일:' in line:
            try:
                target_date = datetime.strptime(line.split(':', 1)[1].strip(), '%Y.%m.%d')
                print(f"구현목표일 발견: {target_date.date()}")
            except:
                continue
    
    if proposal_date and target_date:
        duration = (target_date - proposal_date).days
        print(f"날짜 차이로 계산된 예상 시간: {duration}d")
        return f"{duration}d"
    
    # 3. 기본값 반환
    print("예상 시간을 찾을 수 없어 기본값 사용: 1d")
    return "1d"

def parse_time_spent(todo_text):
    spent_match = re.search(r'\(spent:\s*(\d+)h\)', todo_text)
    if spent_match:
        return f"{spent_match.group(1)}h"
    return None

def update_task_status(repo, task_number, todo_text):
    """태스크 상태를 업데이트합니다."""
    # find report issue
    project_name = repo.name
    report_issue = find_report_issue(repo, project_name)
    if not report_issue:
        return
        
    spent_time = parse_time_spent(todo_text)
    if not spent_time:
        return
        
    body = report_issue.body
    task_pattern = rf"\|\s*\[TSK-{task_number}\].*?\|\s*([^\|]*?)\s*\|\s*([^\|]*?)\s*\|\s*([^\|]*?)\s*\|\s*-\s*\|\s*🟡\s*진행중\s*\|\s*-\s*\|"
    
    def replace_task(match):
        return match.group(0).replace("| - | 🟡 진행중 |", f"| {spent_time} | ✅ 완료 |")
    
    updated_body = re.sub(task_pattern, replace_task, body)
    if updated_body != body:
        report_issue.edit(body=updated_body)
        report_issue.create_comment(f"✅ TSK-{task_number} 태스크가 완료되었습니다. (소요 시간: {spent_time})")

def process_todo_completion(repo, todo_text):
    """완료된 TODO 항목을 처리합니다."""
    # extract TSK number
    task_match = re.search(r'\[TSK-(\d+)\]', todo_text)
    if not task_match:
        return
        
    task_number = task_match.group(1)
    update_task_status(repo, task_number, todo_text)

def create_task_entry(task_issue):
    """태스크 항목을 생성합니다."""
    assignees = get_assignees_string(task_issue)
    title_parts = task_issue.title.strip('[]').split('] ')
    task_name = title_parts[1]
    issue_url = task_issue.html_url
    expected_time = get_task_duration(task_issue)
    return f"| [TSK-{task_issue.number}]({issue_url}) | {task_name} | {assignees} | {expected_time} | - | 🟡 진행중 | - |"

def get_category_from_labels(issue_labels):
    """이슈의 라벨을 기반으로 카테고리를 결정합니다."""
    # 기존 시스템 카테고리들은 모두 "기능 개발"로 매핑
    system_categories = [
        "기본 노트 판정 시스템",
        "콤보 시스템",
        "점수 관리 시스템",
        "롱노트 시스템",
        "NoteEditorSystem"
    ]
    
    for label in issue_labels:
        if label.name.startswith("category:"):
            category_name = label.name.replace("category:", "").strip()
            if category_name in system_categories:
                return "기능 개발"
            elif category_name in TASK_CATEGORIES:
                return category_name
    return "기능 개발"  # 기본값도 기능 개발로 설정

def create_category_sections():
    """모든 카테고리 섹션을 생성합니다."""
    sections = []
    for category_key, category_info in TASK_CATEGORIES.items():
        section = f"""<details>
<summary><h3>{category_key}</h3></summary>

| 태스크 ID | 태스크명 | 담당자 | 예상 시간 | 실제 시간 | 진행 상태 | 우선순위 |
| --------- | -------- | ------ | --------- | --------- | --------- | -------- |

</details>"""
        sections.append(section)
    return "\n\n".join(sections)

def update_report_content(old_content, new_task_entry, category_key):
    """보고서 내용을 업데이트합니다."""
    print(f"\n=== 보고서 내용 업데이트 ===")
    print(f"카테고리: {category_key}")
    
    # find category section
    category_start = old_content.find(f"<h3>{category_key}</h3>")
    if category_start == -1:
        print("카테고리 섹션을 찾을 수 없습니다.")
        return old_content
    
    # find table for the category
    table_header = "| 태스크 ID | 태스크명 | 담당자 | 예상 시간 | 실제 시간 | 진행 상태 | 우선순위 |"
    header_pos = old_content.find(table_header, category_start)
    if header_pos == -1:
        print("테이블 헤더를 찾을 수 없습니다.")
        return old_content
    
    # find table end
    table_end = old_content.find("</details>", header_pos)
    if table_end == -1:
        print("테이블 끝을 찾을 수 없습니다.")
        return old_content
    
    # get current table content
    table_content = old_content[header_pos:table_end].strip()
    print("\n현재 테이블 내용:")
    print(table_content)
    
    # split table lines
    lines = table_content.split('\n')
    
    # check if new task item already exists
    task_number = re.search(r'TSK-(\d+)', new_task_entry).group(1)
    task_exists = False
    
    print(f"\n태스크 TSK-{task_number} 검사 중...")
    
    for i, line in enumerate(lines):
        if f"TSK-{task_number}" in line:
            print(f"기존 태스크 발견: {line}")
            task_exists = True
            lines[i] = new_task_entry  # update existing item
            break
    
    if not task_exists:
        print("새로운 태스크 추가")
        if len(lines) > 2:  # header and divider exist
            lines.append(new_task_entry)
        else:  # first item
            lines = [table_header, "| --------- | -------- | ------ | --------- | --------- | --------- | -------- |", new_task_entry]
    
    # create new table
    new_table = '\n'.join(lines)
    print("\nupdated table:")
    print(new_table)
    
    # return updated content
    updated_content = f"{old_content[:header_pos]}{new_table}\n\n{old_content[table_end:]}"
    return updated_content

def calculate_progress_stats(body):
    """보고서 내용에서 태스크 진행 상태를 계산합니다."""
    print("\n[진행 상태] 계산 시작")
    stats = {
        "완료": 0,
        "진행중": 0,
        "대기중": 0,
        "total": 0,
        "category_stats": {}
    }
    
    current_category = None
    
    # 모든 카테고리 통계 초기화
    for category in TASK_CATEGORIES.keys():
        stats["category_stats"][category] = {
            "완료": 0,
            "진행중": 0,
            "대기중": 0,
            "total": 0
        }
    
    for line in body.split('\n'):
        # 카테고리 헤더 확인
        if '<summary><h3>' in line:
            category_match = re.search(r'<h3>(.*?)</h3>', line)
            if category_match:
                current_category = category_match.group(1)
                continue
        
        # 태스크 행 확인
        if '| TSK-' in line or '|[TSK-' in line:
            if current_category:
                stats["total"] += 1
                stats["category_stats"][current_category]["total"] += 1
                
                if '✅ 완료' in line:
                    stats["완료"] += 1
                    stats["category_stats"][current_category]["완료"] += 1
                elif '🟡 진행중' in line:
                    stats["진행중"] += 1
                    stats["category_stats"][current_category]["진행중"] += 1
                else:
                    stats["대기중"] += 1
                    stats["category_stats"][current_category]["대기중"] += 1
    
    print(f"[진행 상태] 완료: {stats['완료']}, 진행중: {stats['진행중']}, 대기중: {stats['대기중']}, 총: {stats['total']}")
    return stats

def create_progress_section(stats):
    """진행 현황 섹션을 생성합니다."""
    if stats["total"] == 0:
        return """### 전체 진행률

아직 등록된 태스크가 없습니다.

```mermaid
pie title 태스크 진행 상태
    "대기중" : 100
```"""
    
    completed_percent = (stats["완료"] / stats["total"]) * 100
    in_progress_percent = (stats["진행중"] / stats["total"]) * 100
    waiting_percent = (stats["대기중"] / stats["total"]) * 100
    
    # 카테고리별 진행률 계산
    category_progress = []
    for category, cat_stats in stats["category_stats"].items():
        if cat_stats["total"] > 0:
            cat_completed = (cat_stats["완료"] / cat_stats["total"]) * 100
            category_progress.append(f"- {TASK_CATEGORIES[category]['emoji']} **{category}**: {cat_completed:.1f}% 완료 ({cat_stats['완료']}/{cat_stats['total']})")
    
    category_section = "\n".join(category_progress) if category_progress else "아직 카테고리별 진행률을 계산할 수 없습니다."
    
    return f"""### 전체 진행률

전체 진행 상태: {stats["완료"]}/{stats["total"]} 완료 ({completed_percent:.1f}%)

```mermaid
pie title 태스크 진행 상태
    "완료" : {completed_percent:.1f}
    "진행중" : {in_progress_percent:.1f}
    "대기중" : {waiting_percent:.1f}
```

### 카테고리별 진행률

{category_section}"""

def update_progress_section(body):
    """보고서의 진행 현황 섹션을 업데이트합니다."""
    print("\n=== 진행 현황 섹션 업데이트 ===")
    
    # calculate progress status
    stats = calculate_progress_stats(body)
    
    # create new progress section
    new_progress_section = create_progress_section(stats)
    
    # update progress section
    progress_start = body.find("### 전체 진행률")
    if progress_start == -1:
        print("진행 현황 섹션을 찾을 수 없습니다.")
        return body
        
    progress_end = body.find("## 📝 특이사항", progress_start)
    if progress_end == -1:
        print("다음 섹션을 찾을 수 없습니다.")
        return body
    
    return f"{body[:progress_start]}{new_progress_section}\n\n{body[progress_end:]}"

def create_report_body(project_name):
    """프로젝트 보고서 템플릿을 생성합니다."""
    # 카테고리 섹션 생성
    category_sections = create_category_sections()
    
    # 초기 진행 현황 섹션 생성
    initial_stats = {
        "완료": 0,
        "진행중": 0,
        "대기중": 0,
        "total": 0,
        "category_stats": {category: {"완료": 0, "진행중": 0, "대기중": 0, "total": 0} for category in TASK_CATEGORIES.keys()}
    }
    initial_progress = create_progress_section(initial_stats)
    
    return f"""<div align="center">

![header](https://capsule-render.vercel.app/api?type=transparent&color=39FF14&height=150&section=header&text=Project%20Report&fontSize=50&animation=fadeIn&fontColor=39FF14&desc=프로젝트%20진행%20보고서&descSize=25&descAlignY=75)

# 📊 프로젝트 진행 보고서

</div>

## 📌 기본 정보

**프로젝트명**: {project_name}  
**보고서 작성일**: {datetime.now().strftime('%Y-%m-%d')}  
**보고 기간**: {datetime.now().strftime('%Y-%m-%d')} ~ 진행중

## 📋 태스크 상세 내역

{category_sections}

## 📊 진행 현황 요약

{initial_progress}

## 📝 특이사항 및 리스크

| 구분 | 내용 | 대응 방안 |
| ---- | ---- | --------- |
| - | - | - |

## 📈 다음 단계 계획

1. 초기 설정 및 환경 구성
2. 세부 작업 항목 정의
3. 진행 상황 정기 업데이트

---
> 이 보고서는 자동으로 생성되었으며, 담당자가 지속적으로 업데이트할 예정입니다.
"""

def sanitize_project_name(name):
    """프로젝트 이름에서 특수문자를 제거하고 적절한 형식으로 변환합니다."""
    print(f"\n=== 프로젝트 이름 정리 ===")
    print(f"원본 이름: {name}")
    
    # remove . at the beginning
    while name.startswith('.'):
        name = name[1:]
    
    # convert special characters to spaces
    sanitized = re.sub(r'[^\w\s-]', ' ', name)
    
    # convert consecutive spaces to one and remove leading/trailing spaces
    sanitized = ' '.join(sanitized.split())
    
    print(f"변환된 이름: {sanitized}")
    return sanitized

def find_daily_log_issue(repo, project_name):
    """가장 최근의 Daily Log 이슈를 찾습니다."""
    project_name = sanitize_project_name(project_name) 
    print(f"\n=== 일일 로그 이슈 검색 ===")
    print(f"프로젝트명: {project_name}")
    
    # search for open issues with 'daily-log' label
    daily_issues = repo.get_issues(state='open', labels=['daily-log'])
    daily_list = list(daily_issues)
    print(f"검색된 일일 로그 이슈 수: {len(daily_list)}")
    
    for issue in daily_list:
        print(f"검토 중인 이슈: {issue.title}")
        # match with project name
        if f"- {project_name}" in issue.title:
            print(f"일일 로그 이슈를 찾았습니다: #{issue.number}")
            return issue
    
    print("일일 로그 이슈를 찾지 못했습니다.")
    return None

def create_task_todo(task_issue):
    """태스크 시작을 위한 TODO 항목을 생성합니다."""
    title_parts = task_issue.title.strip('[]').split('] ')
    task_name = title_parts[1]
    category_key = get_category_from_labels(task_issue.labels)
    
    print(f"\n=== TODO 항목 생성 ===")
    print(f"태스크명: {task_name}")
    print(f"카테고리: {category_key}")
    
    # create category header and task item
    todo_text = f"""@{TASK_CATEGORIES[category_key]['name']}
- [ ] #{task_issue.number}"""
    print(f"생성된 TODO 텍스트:\n{todo_text}")
    return todo_text

def parse_existing_issue(body):
    """이슈 본문을 파싱하여 기존 TODO 항목들을 추출합니다."""
    print(f"\n=== 이슈 본문 파싱 ===")
    todos = []
    in_todo_section = False
    
    for line in body.split('\n'):
        if '## 📝 Todo' in line:
            print("TODO 섹션 시작")
            in_todo_section = True
            continue
        elif in_todo_section and line.strip() and line.startswith('##'):
            print("TODO 섹션 종료")
            break
        elif in_todo_section and line.strip():
            if line.startswith('- [ ]'):
                todos.append((False, line[6:].strip()))
                print(f"미완료 TODO 추가: {line[6:].strip()}")
            elif line.startswith('- [x]'):
                todos.append((True, line[6:].strip()))
                print(f"완료된 TODO 추가: {line[6:].strip()}")
            elif line.startswith('@'):
                todos.append((None, line.strip()))
                print(f"카테고리 추가: {line.strip()}")
    
    print(f"총 {len(todos)}개의 TODO 항목을 찾았습니다.")
    return {
        'todos': todos
    }

def merge_todos(existing_todos, new_todos):
    """기존 TODO 항목과 새로운 TODO 항목을 병합합니다."""
    print(f"\n=== TODO 항목 병합 ===")
    print(f"기존 TODO 항목 수: {len(existing_todos)}")
    print(f"새로운 TODO 항목 수: {len(new_todos)}")
    
    all_todos = existing_todos.copy()
    
    # add new TODO items
    for completed, text in new_todos:
        if text.startswith('@'):
            # category header is added without duplication
            if text not in [t[1] for t in all_todos]:
                all_todos.append((None, text))
                print(f"새로운 카테고리 추가: {text}")
        else:
            # general TODO items are added after checking for duplicates
            if text not in [t[1] for t in all_todos]:
                all_todos.append((completed, text))
                print(f"새로운 TODO 항목 추가: {text}")
            else:
                print(f"중복된 TODO 항목 무시: {text}")
    
    print(f"병합 후 총 TODO 항목 수: {len(all_todos)}")
    return all_todos

def create_todo_section(todos):
    """TODO 섹션을 생성합니다."""
    print(f"\n=== TODO 섹션 생성 ===")
    
    # group todos by category
    categories = {}
    current_category = "General"
    uncategorized_todos = []
    
    for completed, text in todos:
        print(f"처리 중인 항목: {text}")
        if completed is None and text.startswith('@'):
            current_category = text[1:]  # @ 제거
            print(f"새 카테고리 시작: {current_category}")
            continue
            
        # item is already in checkbox format
        if text.startswith('- [ ]') or text.startswith('- [x]'):
            text = text.replace('- [ ]', '').replace('- [x]', '').strip()
            
        if current_category not in categories:
            categories[current_category] = []
            
        categories[current_category].append((completed, text))
        print(f"'{current_category}' 카테고리에 항목 추가: {text}")
    
    # create category sections
    sections = []
    for category, category_todos in categories.items():
        if not category_todos:  # skip empty category
            continue
            
        completed_count = sum(1 for completed, _ in category_todos if completed)
        total_count = len(category_todos)
        
        section = f"""<details>
<summary><h3 style="display: inline;">📑 {category} ({completed_count}/{total_count})</h3></summary>

"""
        # add TODO items
        for completed, text in category_todos:
            checkbox = '[x]' if completed else '[ ]'
            if text.startswith('#'):  # task reference
                section += f"- {checkbox} {text}\n"
            else:
                section += f"- {checkbox} {text}\n"
        
        section += "\n⚫\n</details>\n"
        sections.append(section)
    
    result = '\n'.join(sections)
    print(f"\n생성된 TODO 섹션:\n{result}")
    return result

def process_approval(issue, repo):
    """이슈의 라벨에 따라 승인 처리를 수행합니다."""
    print(f"\n=== 승인 처리 시작 ===")
    print(f"이슈 번호: #{issue.number}")
    print(f"이슈 제목: {issue.title}")
    
    labels = [label.name for label in issue.labels]
    print(f"이슈 라벨: {labels}")
    
    # extract project name and task name from title
    title_parts = issue.title.strip('[]').split('] ')
    project_name = repo.name  # use repository name as project name
    print(f"프로젝트명: {project_name}")
    
    if '✅ 승인완료' in labels:
        print("\n승인완료 처리 시작")
        # determine task category
        category_key = get_category_from_labels(issue.labels)
        print(f"태스크 카테고리: {category_key}")
        
        report_issue = find_report_issue(repo, project_name)
        
        if report_issue:
            print(f"\n보고서 이슈 발견: #{report_issue.number}")
            task_entry = create_task_entry(issue)
            print(f"생성된 태스크 항목:\n{task_entry}")
            
            updated_body = update_report_content(report_issue.body, task_entry, category_key)
            
            updated_body = update_progress_section(updated_body)
            
            report_issue.edit(body=updated_body)
            report_issue.create_comment(f"✅ 태스크 #{issue.number}이 {category_key} 카테고리에 추가되었습니다.")
            print("보고서 업데이트 완료")
            
            print("\n=== Daily Log 처리 시작 ===")
            daily_issue = find_daily_log_issue(repo, project_name)
            if daily_issue:
                print(f"\n일일 로그 이슈 발견: #{daily_issue.number}")
                # create TODO item
                todo_text = create_task_todo(issue)
                print(f"생성된 TODO 항목:\n{todo_text}")
                
                # parse current issue body
                existing_content = parse_existing_issue(daily_issue.body)
                print(f"기존 TODO 항목 수: {len(existing_content['todos'])}")
                
                # add new TODO items
                new_todos = [(False, line) for line in todo_text.split('\n')]
                all_todos = merge_todos(existing_content['todos'], new_todos)
                
                # update TODO section
                todo_section = create_todo_section(all_todos)
                
                # update issue body
                print("\n이슈 본문 업데이트 시작")
                if '## 📝 Todo' in daily_issue.body:
                    body_parts = daily_issue.body.split('## 📝 Todo')
                    updated_body = f"{body_parts[0]}## 📝 Todo\n\n{todo_section}"
                    if len(body_parts) > 1 and '##' in body_parts[1]:
                        next_section = body_parts[1].split('##', 1)[1]
                        updated_body += f"\n\n##{next_section}"
                else:
                    # add Todo section if it doesn't exist
                    updated_body = f"{daily_issue.body}\n\n## 📝 Todo\n\n{todo_section}"
                
                daily_issue.edit(body=updated_body)
                daily_issue.create_comment(f"새로운 태스크가 추가되었습니다:\n\n{todo_text}")
                print("일일 로그 업데이트 완료")
            else:
                print(f"오늘자 Daily Log 이슈를 찾을 수 없습니다: {datetime.now().strftime('%Y-%m-%d')}")
        else:
            # create new report issue
            report_body = create_report_body(project_name)
            report_issue = repo.create_issue(
                title=f"[{project_name}] 프로젝트 진행보고서",
                body=report_body,
                labels=['📊 진행중']
            )
            # add first task
            task_entry = create_task_entry(issue)
            updated_body = update_report_content(report_body, task_entry, category_key)
            report_issue.edit(body=updated_body)
        
        # add approval message only
        issue.create_comment("✅ 태스크가 승인되어 보고서에 추가되었습니다.")
        
    elif '❌ 반려' in labels:
        issue.create_comment("❌ 태스크가 반려되었습니다. 수정 후 다시 제출해주세요.")
        
    elif '⏸️ 보류' in labels:
        issue.create_comment("⏸️ 태스크가 보류되었습니다. 추가 논의가 필요합니다.")

def extract_main_tasks(body):
    """태스크 보고서에서 메인 태스크 목록을 추출합니다."""
    main_tasks = {}
    current_category = None
    
    for line in body.split('\n'):
        if '<summary><h3>' in line:
            category_match = re.search(r'<h3>(.*?)</h3>', line)
            if category_match:
                current_category = category_match.group(1)
        elif '| [TSK-' in line and current_category:
            # [TSK-XX] 형식의 태스크 참조 추출
            task_match = re.search(r'\|\s*\[TSK-(\d+)\]', line)
            if task_match:
                task_id = task_match.group(1)
                task_reference = f'[TSK-{task_id}]'
                
                # 태스크명 추출 (두 번째 | 와 세 번째 | 사이의 내용)
                task_parts = line.split('|')
                if len(task_parts) >= 3:
                    task_name = task_parts[2].strip()
                    main_tasks[task_reference] = {
                        'id': task_id,
                        'name': task_name,
                        'category': current_category,
                        'todos': [],
                        'completed': 0,
                        'total': 0
                    }
                    print(f"태스크 추출: {task_reference} - {task_name}")
    
    return main_tasks

def find_task_issue(repo, task_id):
    """태스크 ID로 해당 태스크 이슈를 찾습니다."""
    print(f"\n=== 태스크 TSK-{task_id} 검색 ===")
    
    try:
        issue = repo.get_issue(int(task_id))
        print(f"태스크 이슈 발견: #{issue.number} - {issue.title}")
        return issue
    except Exception as e:
        print(f"태스크 이슈 #{task_id} 검색 중 오류 발생: {str(e)}")
        return None

def map_todos_to_tasks(todos, main_tasks):
    """TODO 아이템들을 메인 태스크에 매핑합니다."""
    print("\n=== TODO 매핑 시작 ===")
    
    github_token = os.getenv('GITHUB_TOKEN')
    if not github_token:
        print("GitHub 토큰이 설정되지 않았습니다.")
        return
    
    github = Github(github_token)
    repo = github.get_repo(os.getenv('GITHUB_REPOSITORY'))
    
    # 태스크 매핑 생성 (태스크 이름을 키로 사용)
    task_mapping = {}
    for task_reference, task_info in main_tasks.items():
        task_issue = find_task_issue(repo, task_info['id'])
        if task_issue:
            expected_time = get_task_duration(task_issue)
            task_name = task_info['name']  # 태스크 이름 추출
            # main_tasks에 expected_time 추가
            main_tasks[task_reference]['expected_time'] = expected_time
            task_mapping[task_name] = {
                'id': task_info['id'],
                'name': task_name,
                'expected_time': expected_time,
                'task_issue': task_issue,
                'reference': task_reference
            }
            print(f"태스크 {task_reference} 매핑 완료 (예상 시간: {expected_time}, 태스크명: {task_name})")
    
    print(f"발견된 태스크: {list(task_mapping.keys())}")
    
    # TODO 항목 처리
    for checked, text in todos:
        if text.startswith('@'):
            continue
            
        if text.startswith('#'):
            try:
                issue_number = int(text.strip('#').split()[0])
                issue = repo.get_issue(issue_number)
                
                # 이슈의 카테고리 라벨 확인
                task_name = None
                for label in issue.labels:
                    if label.name.startswith('category:'):
                        task_name = label.name.replace('category:', '').strip()
                        break
                
                if task_name and task_name in task_mapping:
                    task_reference = task_mapping[task_name]['reference']
                    print(f"\n이슈 #{issue_number}가 태스크 {task_reference} ({task_name})에 속합니다.")
                    
                    # 이슈 상태 확인
                    is_completed = issue.state == 'closed'
                    
                    # 프로젝트 상태 확인
                    project_status = get_project_item_status(github_token, issue_number)
                    is_in_progress = project_status == 'In Progress' if project_status else False
                    
                    # 태스크 정보 업데이트
                    main_tasks[task_reference]['todos'].append({
                        'text': text,
                        'completed': is_completed,
                        'in_progress': is_in_progress,
                        'issue_number': issue_number,
                        'issue_state': issue.state,
                        'project_status': project_status
                    })
                    
                    main_tasks[task_reference]['total'] += 1
                    if is_completed:
                        main_tasks[task_reference]['completed'] += 1
                    elif is_in_progress:
                        main_tasks[task_reference]['in_progress'] = True
                    
                    status = "✅ 완료" if is_completed else "🟡 진행중" if is_in_progress else "⬜ 대기중"
                    print(f"{status} {text} (상태: {issue.state}, 프로젝트 상태: {project_status})")
                else:
                    print(f"\n이슈 #{issue_number}는 매칭되는 태스크를 찾을 수 없습니다: {task_name if task_name else '카테고리 없음'}")
                    
            except Exception as e:
                print(f"\n이슈 #{text.strip('#').split()[0]} 처리 중 오류 발생: {str(e)}")
                continue

def calculate_task_progress(main_tasks):
    """각 태스크의 진행률을 계산합니다."""
    for task_info in main_tasks.values():
        if task_info['total'] > 0:
            task_info['progress'] = (task_info['completed'] / task_info['total']) * 100
        else:
            task_info['progress'] = 0

def get_completed_tasks_by_date(github_token, repo_owner, repo_name):
    """GitHub Projects에서 완료된 작업들을 날짜별로 조회합니다."""
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    query = """
    query($owner: String!, $name: String!) {
        repository(owner: $owner, name: $name) {
            issues(first: 100, states: CLOSED) {
                nodes {
                    number
                    title
                    closedAt
                    labels(first: 10) {
                        nodes {
                            name
                        }
                    }
                    projectItems(first: 1) {
                        nodes {
                            status: fieldValueByName(name: "Status") {
                                ... on ProjectV2ItemFieldSingleSelectValue {
                                    name
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """
    
    try:
        response = requests.post(
            'https://api.github.com/graphql',
            json={'query': query, 'variables': {'owner': repo_owner, 'name': repo_name}},
            headers=headers
        )
        response.raise_for_status()
        result = response.json()
        
        completed_tasks = {}
        
        if 'data' in result and 'repository' in result['data']:
            issues = result['data']['repository']['issues']['nodes']
            for issue in issues:
                # 이슈가 Done 상태이거나 closed 상태인 경우
                is_done = False
                if issue['projectItems']['nodes']:
                    status = issue['projectItems']['nodes'][0].get('status', {})
                    is_done = status and status.get('name') == 'Done'
                
                if is_done and issue['closedAt']:
                    closed_date = issue['closedAt'][:10]  # YYYY-MM-DD
                    if closed_date not in completed_tasks:
                        completed_tasks[closed_date] = []
                    
                    # 카테고리 라벨 찾기
                    category = "기타"
                    for label in issue['labels']['nodes']:
                        if label['name'].startswith('category:'):
                            category = label['name'].replace('category:', '').strip()
                            break
                    
                    completed_tasks[closed_date].append({
                        'number': issue['number'],
                        'title': issue['title'],
                        'category': category
                    })
        
        return completed_tasks
    except Exception as e:
        print(f"완료된 작업 조회 중 오류 발생: {str(e)}")
        return {}

def create_completion_history_section(completed_tasks):
    """완료된 작업 히스토리 섹션을 생성합니다."""
    if not completed_tasks:
        return "### 📅 완료 작업 히스토리\n\n아직 완료된 작업이 없습니다."
    
    sections = ["### 📅 완료 작업 히스토리\n"]
    
    for date in sorted(completed_tasks.keys(), reverse=True):
        tasks = completed_tasks[date]
        section = f"\n#### {date}\n"
        
        # 카테고리별로 그룹화
        categorized = {}
        for task in tasks:
            if task['category'] not in categorized:
                categorized[task['category']] = []
            categorized[task['category']].append(task)
        
        # 카테고리별로 출력
        for category, category_tasks in categorized.items():
            emoji = TASK_CATEGORIES.get(category, {}).get('emoji', '📌')
            section += f"\n{emoji} **{category}**\n"
            for task in category_tasks:
                section += f"- #{task['number']} {task['title']}\n"
        
        sections.append(section)
    
    return '\n'.join(sections)

def update_task_progress_in_report(body, main_tasks):
    """보고서의 태스크 진행률을 업데이트합니다."""
    print("\n=== 태스크 진행률 업데이트 시작 ===")
    
    # GitHub 정보 가져오기
    github_token = os.getenv('GITHUB_TOKEN')
    repo_name = os.getenv('GITHUB_REPOSITORY')
    repo_owner, repo_name = repo_name.split('/')
    
    # 완료된 작업 히스토리 가져오기
    completed_tasks = get_completed_tasks_by_date(github_token, repo_owner, repo_name)
    completion_history = create_completion_history_section(completed_tasks)
    
    lines = body.split('\n')
    updated_lines = []
    current_category = None
    
    # 태스크 진행 상태 업데이트
    for line in body.split('\n'):
        if '<summary><h3>' in line:
            category_match = re.search(r'<h3>(.*?)</h3>', line)
            if category_match:
                current_category = category_match.group(1)
                updated_lines.append(line)
                print(f"\n현재 카테고리: {current_category}")
        elif '| [TSK-' in line or '|[TSK-' in line:
            original_line = line
            for task_name, task_info in main_tasks.items():
                task_id_pattern = f"TSK-{task_info['id']}"
                if task_id_pattern in line:
                    print(f"\n태스크 발견: {task_name} (TSK-{task_info['id']})")
                    print(f"진행률: {task_info['progress']:.1f}% ({task_info['completed']}/{task_info['total']})")
                    
                    # 진행 상태 컬럼 업데이트
                    columns = line.split('|')
                    if len(columns) >= 7:
                        # 예상 시간 업데이트 (4번째 컬럼)
                        columns[4] = f" {task_info['expected_time']} "
                        progress = f"{task_info['progress']:.1f}%"
                        status = "✅ 완료" if task_info['progress'] == 100 else f"🟡 진행중 ({progress})"
                        columns[6] = f" {status} "
                        line = '|'.join(columns)
                        print(f"업데이트된 라인: {line}")
                    break
            
            if line != original_line:
                print("라인이 업데이트되었습니다.")
            updated_lines.append(line)
        else:
            updated_lines.append(line)
    
    updated_body = '\n'.join(updated_lines)
    
    # 진행 현황 섹션 업데이트
    progress_start = updated_body.find("### 전체 진행률")
    if progress_start != -1:
        progress_end = updated_body.find("## 📝 특이사항", progress_start)
        if progress_end != -1:
            # 진행 현황 섹션 생성
            stats = calculate_progress_stats(updated_body)
            progress_section = create_progress_section(stats)
            updated_body = updated_body[:progress_start] + progress_section + "\n\n" + updated_body[progress_end:]
    
    print("\n=== 진행 현황 업데이트 완료 ===")
    return updated_body

def sync_all_issues(repo):
    """현재 열려있는 모든 이슈를 순회하여 프로젝트 보고서를 업데이트합니다."""
    print("\n=== 전체 이슈 동기화 시작 ===")
    
    # 프로젝트 이름 가져오기
    project_name = repo.name
    
    # 보고서 이슈 찾기
    report_issue = find_report_issue(repo, project_name)
    if not report_issue:
        print("보고서 이슈를 찾을 수 없습니다.")
        return
    
    # DSR 이슈 찾기
    dsr_issues = repo.get_issues(state='open', labels=['DSR'])
    latest_dsr = None
    for issue in dsr_issues:
        if issue.title.startswith('📅 Development Status Report'):
            latest_dsr = issue
            break
    
    if not latest_dsr:
        print("DSR 이슈를 찾을 수 없습니다.")
        return
    
    # 메인 태스크 추출
    main_tasks = extract_main_tasks(report_issue.body)
    print(f"\n메인 태스크 추출 완료: {len(main_tasks)}개 발견")
    
    # DSR의 TODO 아이템 파싱
    dsr_content = parse_existing_issue(latest_dsr.body)
    todos = dsr_content['todos']
    
    # TODO 아이템들을 메인 태스크에 매핑
    map_todos_to_tasks(todos, main_tasks)
    print("\nTODO 매핑 완료")
    
    # 진행률 계산
    calculate_task_progress(main_tasks)
    print("\n진행률 계산 완료")
    
    # 태스크 보고서 업데이트
    updated_body = update_task_progress_in_report(report_issue.body, main_tasks)
    
    # 진행 상황 요약 생성
    summary = "\n### 🔄 현재 진행 상황\n\n"
    for task_name, task_info in main_tasks.items():
        progress = f"{task_info['progress']:.1f}%"
        summary += f"• **{task_name}**: {progress} ({task_info['completed']}/{task_info['total']} 완료)\n"
    
    # 특이사항 섹션 찾기
    special_section_start = updated_body.find("## 📝 특이사항")
    if special_section_start != -1:
        # 진행 상황 요약을 특이사항 섹션 앞에 추가
        updated_body = updated_body[:special_section_start] + summary + "\n" + updated_body[special_section_start:]
    
    if updated_body != report_issue.body:
        report_issue.edit(body=updated_body)
        print("\n보고서 업데이트 완료")
    else:
        print("\n업데이트할 내용이 없습니다.")

def get_project_item_status(github_token, issue_number):
    """GitHub Projects v2에서 이슈의 상태를 확인합니다."""
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    query = """
    query($org: String!, $number: Int!) {
        organization(login: $org) {
            projectV2(number: $number) {
                items(first: 100) {
                    nodes {
                        content {
                            ... on Issue {
                                number
                            }
                        }
                        fieldValues(first: 8) {
                            nodes {
                                ... on ProjectV2ItemFieldSingleSelectValue {
                                    name
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """
    
    try:
        response = requests.post(
            'https://api.github.com/graphql',
            json={'query': query, 'variables': {
                'org': 'KGAMeta8thTeam1',
                'number': 2
            }},
            headers=headers
        )
        response.raise_for_status()
        result = response.json()
        
        if 'data' in result and 'organization' in result['data']:
            items = result['data']['organization']['projectV2']['items']['nodes']
            for item in items:
                if item['content'] and item['content'].get('number') == issue_number:
                    field_values = item['fieldValues']['nodes']
                    for value in field_values:
                        if value and value.get('name'):
                            return value['name']
        return None
    except Exception as e:
        print(f"프로젝트 상태 확인 중 오류 발생: {str(e)}")
        return None

def main():
    try:
        print("\n[시작] 태스크 처리 스크립트")
        
        # GitHub 클라이언트 초기화
        github_token = os.getenv('GITHUB_TOKEN')
        if not github_token:
            raise ValueError("GitHub 토큰이 설정되지 않았습니다.")
        github = Github(github_token)
        
        # 저장소 정보 가져오기
        repo_name = os.getenv('GITHUB_REPOSITORY')
        if not repo_name:
            raise ValueError("GitHub 저장소 정보를 찾을 수 없습니다.")
        repo = github.get_repo(repo_name)
        print(f"[정보] 저장소: {repo_name}")
        
        # 이벤트 정보 가져오기
        event_name = os.getenv('GITHUB_EVENT_NAME')
        event_path = os.getenv('GITHUB_EVENT_PATH')
        print(f"[정보] 이벤트: {event_name}")
        
        # 전체 이슈 동기화 실행
        sync_all_issues(repo)
        
        if event_path and os.path.exists(event_path):
            # 이벤트 데이터 처리
            with open(event_path, 'r', encoding='utf-8') as f:
                event_data = json.load(f)
                if 'issue' in event_data:
                    issue_number = event_data['issue']['number']
                    issue = repo.get_issue(issue_number)
                    labels = [label.name for label in issue.labels]
                    print(f"[처리] 이슈 #{issue_number}: {issue.title}")
                    
                    # 이벤트 타입에 따른 처리
                    if event_name in ['issues', 'issue_comment']:
                        if '✅ 승인완료' in labels:
                            print("[실행] 태스크 승인 처리")
                            process_approval(issue, repo)
                        elif '❌ 반려' in labels:
                            print("[실행] 태스크 반려 처리")
                            process_approval(issue, repo)
                        elif '⏸️ 보류' in labels:
                            print("[실행] 태스크 보류 처리")
                            process_approval(issue, repo)
                
    except Exception as e:
        print(f"\n[오류] {str(e)}")
        raise

if __name__ == '__main__':
    main() 