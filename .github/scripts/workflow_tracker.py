import os
import re
from datetime import datetime
import pytz
from github import Github, GithubException
import logging
from typing import Dict, List, Tuple, Optional
from github.Repository import Repository
from github.Issue import Issue
import time

class WorkflowLogger:
    def __init__(self):
        self.logger = logging.getLogger('workflow_tracker')
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('=== %(message)s ===')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def section(self, title: str, message: str = '') -> None:
        self.logger.info(f"{title}")
        if message:
            print(f"{message}")
    
    def commit(self, action: str, sha: str, message: str, extra: str = '') -> None:
        print(f"{action}: [{sha[:7]}] {message}{' - ' + extra if extra else ''}")
    
    def todo(self, status: str, text: str) -> None:
        print(f"{status}: {text}")
    
    def debug(self, message: str) -> None:
        print(f"DEBUG: {message}")
        
    def error(self, message: str) -> None:
        print(f"ERROR: {message}")

logger = WorkflowLogger()

COMMIT_TYPES = {
    'feat': {'emoji': '✨', 'label': 'feature', 'description': 'New Feature'},
    'fix': {'emoji': '🐛', 'label': 'bug', 'description': 'Bug Fix'},
    'refactor': {'emoji': '♻️', 'label': 'refactor', 'description': 'Code Refactoring'},
    'docs': {'emoji': '📝', 'label': 'documentation', 'description': 'Documentation Update'},
    'test': {'emoji': '✅', 'label': 'test', 'description': 'Test Update'},
    'chore': {'emoji': '🔧', 'label': 'chore', 'description': 'Build/Config Update'},
    'style': {'emoji': '💄', 'label': 'style', 'description': 'Code Style Update'},
    'perf': {'emoji': '⚡️', 'label': 'performance', 'description': 'Performance Improvement'},
}

def is_merge_commit_message(message):
    return message.startswith('Merge')

class CommitMessage:
    def __init__(self, type_: str, title: str, body: str = '', todo: str = '', footer: str = ''):
        self.type = type_
        self.title = title
        self.body = body
        self.todo = todo
        self.footer = footer
        self.type_info = COMMIT_TYPES.get(type_.lower(), {'emoji': '🔍', 'label': 'other', 'description': 'Other'})

    @classmethod
    def parse(cls, message: str) -> Optional['CommitMessage']:
        sections = {'title': '', 'body': '', 'todo': '', 'footer': ''}
        current_section = 'title'

        message_lines = message.split('\n')
        if not message_lines:
            return None
            
        sections['title'] = message_lines[0].strip()
        
        for line in message_lines[1:]:
            line = line.strip()
            if not line:
                continue

            if line.lower() in ['[body]', '[todo]', '[footer]']:
                current_section = line.strip('[]').lower()
                continue
            
            if current_section in sections:
                if sections[current_section]:
                    sections[current_section] += '\n'
                sections[current_section] += line

        title_match = re.match(r'\[(.*?)\]\s*(.*)', sections['title'])
        if not title_match:
            return None

        return cls(
            type_=title_match.group(1),
            title=title_match.group(2),
            body=sections['body'],
            todo=sections['todo'],
            footer=sections['footer']
        )

def parse_commit_message(message: str) -> Optional[Dict]:
    commit = CommitMessage.parse(message)
    if not commit:
        return None

    return {
        'type': commit.type,
        'type_info': commit.type_info,
        'title': commit.title,
        'body': commit.body,
        'todo': commit.todo,
        'footer': commit.footer
    }

class CategoryManager:
    def __init__(self):
        self._categories = {}
        self._current = 'General'
        self.add_category('General')
    
    def add_category(self, category):
        if not category:
            return self._categories['General']
            
        category = category.strip()
        if category not in self._categories:
            self._categories[category] = []
        return category
    
    def add_todo(self, category, todo_item):
        category = self.add_category(category)
        if todo_item not in self._categories[category]:
            self._categories[category].append(todo_item)
    
    def get_todos(self, category=None):
        if category:
            return self._categories.get(category, [])
        return self._categories
    
    def set_current(self, category):
        self._current = self.add_category(category)
    
    @property
    def current(self):
        return self._current

    @property
    def categories(self):
        return list(self._categories.keys())

def retry_api_call(func, max_retries=3, delay=5):
    for attempt in range(max_retries):
        try:
            return func()
        except GithubException as e:
            if e.status == 503 and attempt < max_retries - 1:
                print(f"\n[재시도] GitHub API 호출 실패 (시도 {attempt + 1}/{max_retries})")
                print(f"오류 메시지: {str(e)}")
                print(f"{delay}초 후 재시도합니다...")
                time.sleep(delay)
                continue
            raise
    return None

class CommitSectionBuilder:
    def __init__(self, repo, timezone):
        self.repo = repo
        self.tz = pytz.timezone(timezone)
        self.current_date = datetime.now(self.tz).strftime('%Y-%m-%d')
    
    def _format_body(self, body: str) -> str:
        """커밋 본문을 포맷팅합니다."""
        if not body:
            return '> No additional details provided.'
            
        body_lines = []
        for line in body.strip().split('\n'):
            line = line.strip()
            if line:
                if line.startswith('-'):
                    line = line[1:].strip()
                body_lines.append(f"> • {line}")
        
        return '\n'.join(body_lines)
    
    def _get_related_issues(self, message: str, commit_data: dict) -> list:
        """관련된 이슈 참조를 찾습니다."""
        issue_numbers = set(re.findall(r'#(\d+)', message))
        related_issues = []
        
        dsr_issues = retry_api_call(lambda: list(self.repo.get_issues(state='open', labels=[os.environ.get('ISSUE_LABEL', 'dsr')])))
        current_dsr = next((issue for issue in dsr_issues if f"Daily Development Log ({self.current_date})" in issue.title), None)
        
        if current_dsr:
            issue_numbers.add(str(current_dsr.number))
        
        for issue_num in issue_numbers:
            try:
                issue = retry_api_call(lambda: self.repo.get_issue(int(issue_num)))
                if issue:
                    if current_dsr and str(issue.number) == str(current_dsr.number):
                        issue.create_comment(f"커밋이 추가되었습니다: {commit_data['title']}")
                    else:
                        issue.create_comment(f"Referenced in commit {commit_data['title']}")
                    related_issues.append(f"Related to #{issue_num}")
            except Exception as e:
                logger.debug(f"Failed to add comment to issue #{issue_num}: {str(e)}")
                continue
        
        return related_issues
    
    def create_section(self, commit_data: dict, branch: str, commit_sha: str, author: str, time_string: str) -> str:
        """커밋 섹션을 생성합니다."""
        logger.debug(f"Creating commit section for {commit_sha[:7]}")
        
        body = self._format_body(commit_data.get('body', ''))
        full_message = f"{commit_data['title']}\n{commit_data.get('body', '')}\n{commit_data.get('footer', '')}"
        related_issues = self._get_related_issues(full_message, commit_data)
        
        if related_issues:
            body += "\n> \n> Related Issues:\n> " + "\n> ".join(related_issues)
        
        return f'''> <details>
> <summary>💫 {time_string} - {commit_data['title'].strip()}</summary>
>
> Type: {commit_data['type']} ({commit_data['type_info']['description']})
> Commit: {commit_sha[:7]}
> Author: {author}
>
{body}
> </details>'''

class CommitProcessor:
    def __init__(self, repo, timezone):
        self.repo = repo
        self.timezone = timezone
        self.tz = pytz.timezone(timezone)
        self.today = datetime.now(self.tz).date()
        self.commit_history = {}  # (메시지, 작성자, 시간) -> (브랜치, 커밋)
        self.section_builder = CommitSectionBuilder(repo, timezone)
    
    def get_commit_key(self, commit):
        """커밋의 고유 키를 생성합니다."""
        return (
            commit.commit.message.strip(),
            commit.commit.author.name,
            commit.commit.author.date.strftime('%H:%M:%S')
        )
    
    def process_commit(self, commit, branch_name):
        """단일 커밋을 처리하고 유효성을 반환합니다."""
        if is_merge_commit_message(commit.commit.message):
            logger.debug(f"머지 커밋 무시: [{commit.sha[:7]}]")
            return False
            
        commit_key = self.get_commit_key(commit)
        if commit_key in self.commit_history:
            original_branch, _ = self.commit_history[commit_key]
            logger.debug(f"중복 커밋 무시: [{commit.sha[:7]}] - 원본 브랜치: {original_branch}")
            return False
            
        self.commit_history[commit_key] = (branch_name, commit)
        logger.debug(f"커밋 추가: [{commit.sha[:7]}] in {branch_name}")
        return True

    def get_todays_commits(self):
        """오늘의 모든 브랜치 커밋을 가져옵니다."""
        logger.section("Getting Today's Commits from All Branches")
        branches_commits = {}
        
        try:
            for branch in self.repo.get_branches():
                branch_name = branch.name
                logger.debug(f"\n브랜치 확인 중: {branch_name}")
                
                try:
                    commits = self.repo.get_commits(sha=branch.commit.sha)
                    branch_commits = []
                    
                    for commit in commits:
                        commit_date = commit.commit.author.date.replace(tzinfo=pytz.UTC).astimezone(self.tz).date()
                        
                        if commit_date == self.today:
                            if self.process_commit(commit, branch_name):
                                branch_commits.append(commit)
                        elif commit_date < self.today:
                            break
                    
                    if branch_commits:
                        branches_commits[branch_name] = branch_commits
                        logger.debug(f"{branch_name}: {len(branch_commits)}개의 커밋 발견")
                    
                except Exception as e:
                    logger.error(f"{branch_name} 브랜치 처리 중 오류 발생: {str(e)}")
                    continue
            
            return branches_commits
            
        except Exception as e:
            logger.error(f"브랜치 목록 가져오기 실패: {str(e)}")
            return {}

    def create_branch_sections(self, branches_commits, existing_content=None):
        """브랜치별 섹션을 생성합니다."""
        branches_content = existing_content.get('branches', {}) if existing_content else {}
        result = []
        
        for branch_name, commits in branches_commits.items():
            logger.debug(f"\n{branch_name} 브랜치 섹션 생성 중...")
            branch_sections = []
            
            for commit in commits:
                commit_data = parse_commit_message(commit.commit.message)
                if not commit_data:
                    continue
                
                commit_time = commit.commit.author.date.replace(tzinfo=pytz.UTC).astimezone(self.tz)
                commit_time_string = commit_time.strftime('%H:%M:%S')
                
                section = self.section_builder.create_section(
                    commit_data,
                    branch_name,
                    commit.sha,
                    commit.commit.author.name,
                    commit_time_string
                )
                branch_sections.append(section)
            
            if branch_sections:
                branch_content = '\n\n'.join(branch_sections)
                if branch_name in branches_content:
                    branch_content = branch_content + "\n\n" + branches_content[branch_name]
                
                # 브랜치별 섹션을 details로 감싸기
                branch_section = f'''<details>
<summary><h3 style="display: inline;">✨ {branch_name}</h3></summary>

{branch_content}
</details>'''
                result.append(branch_section)
                logger.debug(f"브랜치 '{branch_name}' 섹션 생성됨")
        
        return result

def find_active_dsr_issue(repo: Repository, date_string: str, issue_title: str) -> Optional[Issue]:
    logger.section("Searching for Active DSR Issue")
    
    dsr_issues = repo.get_issues(state='open', labels=['DSR'])

    for issue in dsr_issues:
        logger.debug(f"Checking issue #{issue.number}: {issue.title}")
        if issue.title == issue_title:
            logger.debug(f"Found today's DSR issue: #{issue.number}")
            return issue
    
    logger.debug("No active DSR issue found for today")
    return None

class TodoProcessor:
    def __init__(self, repo, issue_number=None):
        self.repo = repo
        self.issue_number = issue_number
        self.todos = []
        self.current_category = 'General'
    
    @staticmethod
    def is_issue_todo(todo_text: str) -> bool:
        """TODO 항목이 이슈 생성이 필요한지 확인합니다."""
        return todo_text.strip().startswith('(issue)')
    
    @staticmethod
    def convert_to_checkbox_list(text: str) -> str:
        """텍스트를 체크박스 목록으로 변환합니다."""
        if not text:
            return ''
        
        lines = []
        for line in text.strip().split('\n'):
            line = line.strip()
            if line:
                if line.startswith('@'):
                    lines.append(line)
                elif line.startswith(('-', '*')):
                    lines.append(f"- [ ] {line[1:].strip()}")
                else:
                    lines.append(f"- [ ] {line}")
        
        return '\n'.join(lines)
    
    @staticmethod
    def merge_todos(existing_todos: List[Tuple[bool, str]], new_todos: List[Tuple[bool, str]]) -> List[Tuple[bool, str]]:
        """기존 TODO와 새로운 TODO를 병합합니다."""
        todo_dict = {text: checked for checked, text in existing_todos}
        
        for checked, text in new_todos:
            if text not in todo_dict:
                todo_dict[text] = checked
        
        return [(todo_dict[text], text) for text in todo_dict]
    
    def process_todo_message(self, todo_text):
        """커밋 메시지의 TODO 섹션을 처리합니다."""
        if not todo_text:
            return []
        
        todo_lines = []
        for line in todo_text.strip().split('\n'):
            line = line.strip()
            if line:
                if line.startswith('@'):
                    self.current_category = line[1:].strip()
                    todo_lines.append((False, line))
                elif line.startswith(('-', '*')):
                    if '(issue)' in line:
                        text = line[1:].strip()  # '-' 제거
                        todo_lines.append((False, text))
                    else:
                        todo_lines.append((False, line[1:].strip()))
                else:
                    todo_lines.append((False, line))
        
        return todo_lines
    
    def process_existing_todos(self, existing_todos):
        """기존 TODO 항목들을 처리합니다."""
        if not existing_todos:
            return []
            
        processed = []
        for checked, text in existing_todos:
            if text.startswith('@'):
                self.current_category = text[1:].strip()
            processed.append((checked, text))
        return processed
    
    def create_issue_from_todo(self, todo_text):
        """TODO 항목으로부터 새 이슈를 생성합니다."""
        if not self.is_issue_todo(todo_text):
            return None
            
        title = todo_text.replace('(issue)', '', 1).strip()
        issue_title = f"[{self.current_category}] {title}"
        
        try:
            new_issue = self.repo.create_issue(
                title=issue_title,
                body=self._create_issue_body(title),
                labels=['todo-generated', f'category:{self.current_category}']
            )
            
            if self.issue_number:
                parent_issue = self.repo.get_issue(self.issue_number)
                parent_issue.create_comment(f"Created issue #{new_issue.number} from todo item")
                
            return new_issue
        except Exception as e:
            logger.error(f"Failed to create issue for todo: {title}")
            logger.error(f"Error: {str(e)}")
            return None
    
    def _create_issue_body(self, title):
        """이슈 본문을 생성합니다."""
        return f"""## 📌 Task Description
{title}

## 🏷 Category
{self.current_category}

## 🔗 References
- Created from Daily Log: #{self.issue_number}"""

    def process_todos(self, commit_data=None, existing_todos=None, is_new_day=False):
        """TODO 항목들을 처리합니다."""
        all_todos = []
        created_issues = []
        
        if existing_todos:
            if is_new_day:
                all_todos.extend([(checked, text) for checked, text in existing_todos 
                                if not checked or text.startswith('@')])
            else:
                all_todos.extend(self.process_existing_todos(existing_todos))
        
        if commit_data and commit_data.get('todo'):
            new_todos = self.process_todo_message(commit_data['todo'])
            all_todos = self.merge_todos(all_todos, new_todos)
        
        processed_todos = []
        for checked, text in all_todos:
            if text.startswith('@'):
                self.current_category = text[1:].strip()
                processed_todos.append((checked, text))
            elif self.is_issue_todo(text):
                new_issue = self.create_issue_from_todo(text)
                if new_issue:
                    created_issues.append(new_issue)
                    processed_todos.append((checked, f"#{new_issue.number}"))
            else:
                processed_todos.append((checked, text))
        
        return processed_todos, created_issues

    def create_todo_section(self, todos: List[Tuple[bool, str]]) -> str:
        """TODO 섹션을 생성합니다."""
        if not todos:
            return ''
            
        sections = {}
        category_order = []
        current_category = 'General'
        
        for checked, text in todos:
            if text.startswith('@'):
                current_category = text[1:].strip()
                if current_category not in category_order:
                    category_order.append(current_category)
                continue
                
            if current_category not in sections:
                sections[current_category] = []
            sections[current_category].append((checked, text))
        
        if not category_order:
            category_order.append('General')
        
        result = []
        for category in category_order:
            if category not in sections:
                continue
                
            items = sections[category]
            completed = sum(1 for checked, _ in items if checked)
            section = f'''<details>
<summary><h3 style="display: inline;">📑 {category} ({completed}/{len(items)})</h3></summary>

{'\n'.join(f"- [{'x' if checked else ' '}] {text}" for checked, text in items)}

⚫
</details>'''
            result.append(section)
        
        return '\n\n'.join(result)

def parse_existing_issue(body: str) -> dict:
    """이슈 본문을 파싱하여 TODO 항목과 카테고리를 추출합니다."""
    todos = []
    current_category = 'General'
    in_todo_section = False
    
    if not body:
        return {'todos': todos}
    
    for line in body.split('\n'):
        if '## 📝 Todo' in line:
            in_todo_section = True
        elif in_todo_section and line.strip() and line.startswith('##'):
            in_todo_section = False
        elif in_todo_section and line.strip():
            if '<summary><h3' in line:  # 카테고리 헤더 찾기
                category_match = re.search(r'📑\s*(.*?)\s*\(', line)
                if category_match:
                    current_category = category_match.group(1).strip()
                    todos.append((False, f"@{current_category}"))
            elif line.startswith('- ['):
                checked = 'x' in line[3]
                text = line[6:].strip()
                if text.startswith('#'):  # 이슈 참조인 경우
                    todos.append((checked, text))
                else:  # 일반 TODO 항목
                    todos.append((checked, text))
    
    return {'todos': todos}

def get_previous_dsr_todos(repo: Repository, current_date: str) -> List[Tuple[bool, str]]:
    """이전 일자의 미완료 TODO 항목을 가져오고 이슈를 닫습니다."""
    todos = []
    dsr_issues = repo.get_issues(state='open', labels=['DSR'])
    
    # 날짜순으로 정렬 (최신순)
    sorted_issues = sorted(
        [issue for issue in dsr_issues if "Development Status Report" in issue.title],
        key=lambda x: x.created_at,
        reverse=True
    )
    
    for issue in sorted_issues:
        if current_date in issue.title:  # 현재 날짜의 이슈는 건너뜀
            continue
            
        # 이전 이슈의 TODO 항목을 파싱
        previous_content = parse_existing_issue(issue.body)
        if previous_content and 'todos' in previous_content:
            # 미완료 항목과 카테고리만 가져옴
            for checked, text in previous_content['todos']:
                if text.startswith('@') or not checked:  # 카테고리이거나 미완료 항목
                    todos.append((checked, text))
            
            # 이전 이슈 닫기
            issue.edit(state='closed')
            logger.debug(f"이전 DSR 이슈 #{issue.number} 닫힘")
            
            break  # 가장 최근 이슈만 처리
    
    return todos

def main():
    github_token = os.environ.get('PAT') or os.environ['GITHUB_TOKEN']
    g = Github(github_token)
    repository = os.environ['GITHUB_REPOSITORY']
    repo = g.get_repo(repository)
    
    try:
        test_commit = repo.get_commits()[0]
        logger.debug(f"Repository access test - latest commit: {test_commit.sha[:7]}")
    except Exception as e:
        logger.error(f"Repository access error: {str(e)}")
    
    timezone = os.environ.get('TIMEZONE', 'Asia/Seoul')
    issue_prefix = os.environ.get('ISSUE_PREFIX', '📅')
    branch = os.environ['GITHUB_REF'].replace('refs/heads/', '')
    
    logger.debug(f"Current branch: {branch}")
    logger.debug(f"GITHUB_REF: {os.environ['GITHUB_REF']}")
    
    tz = pytz.timezone(timezone)
    now = datetime.now(tz)
    date_string = now.strftime('%Y-%m-%d')
    
    repo_name = repository.split('/')[-1]
    if repo_name.startswith('.'):
        repo_name = repo_name[1:]

    issue_title = f"{issue_prefix} Development Status Report ({date_string})"
    if repo_name:
        issue_title += f" - {repo_name}"
    
    logger.section("Issue Title Format")
    logger.debug(f"Using title format: {issue_title}")

    # 커밋 처리
    commit_processor = CommitProcessor(repo, timezone)
    branches_commits = commit_processor.get_todays_commits()
    
    if not branches_commits:
        logger.debug("오늘 커밋된 내용이 없습니다")
        return

    today_issue = find_active_dsr_issue(repo, date_string, issue_title)
    
    # TODO 처리
    todo_processor = TodoProcessor(repo, today_issue.number if today_issue else None)
    
    # 이전 일자의 미완료 TODO 가져오기
    previous_todos = get_previous_dsr_todos(repo, date_string)
    
    # 기존 내용과 이전 TODO 병합
    existing_content = {'todos': previous_todos}
    if today_issue:
        today_content = parse_existing_issue(today_issue.body)
        # TodoProcessor의 merge_todos 메서드 사용
        existing_content['todos'] = todo_processor.merge_todos(previous_todos, today_content.get('todos', []))
    
    # 브랜치 섹션 생성
    branches_content = commit_processor.create_branch_sections(branches_commits, existing_content)
    
    # 현재 커밋의 TODO 처리
    current_commit = repo.get_commit(os.environ['GITHUB_SHA'])
    commit_data = parse_commit_message(current_commit.commit.message)
    
    processed_todos, created_issues = todo_processor.process_todos(
        commit_data=commit_data,
        existing_todos=existing_content.get('todos', []),
        is_new_day=datetime.now(pytz.timezone(timezone)).strftime('%Y-%m-%d') != date_string
    )
    
    if created_issues:
        logger.section("Created new issues from todos")
        for issue in created_issues:
            print(f"#{issue.number}: {issue.title}")
    
    logger.section("Final Result")
    print(f"Total TODOs: {len(processed_todos)} items")
    
    # 이슈 본문 생성
    body = f'''# {issue_title}

<div align="center">

## 📊 Branch Summary

</div>

{"\n\n".join(branches_content)}

<div align="center">

## 📝 Todo

{todo_processor.create_todo_section(processed_todos)}'''

    # 이슈 업데이트 또는 생성
    if today_issue:
        today_issue.edit(body=body)
        logger.debug(f"이슈 #{today_issue.number} 업데이트됨")
    else:
        new_issue = repo.create_issue(
            title=issue_title,
            body=body,
            labels=[os.environ.get('ISSUE_LABEL', 'dsr'), f"branch:{branch}"]
        )
        print(f"Created new issue #{new_issue.number}")

if __name__ == '__main__':
    main()