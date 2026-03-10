"""
============================================================
 1. 노션 API 연동 서비스
============================================================
 노션 데이터베이스를 SSOT(Single Source of Truth)로 사용
 - 오늘의 할 일 조회: 날짜가 오늘이거나 미완료인 태스크 쿼리
 - 퀘스트 완료 처리: 노션 페이지의 체크박스 프로퍼티를 true로 변경
 - 세부 퀘스트 조회: 페이지 내부 to_do 블록 읽기
 - 일일 퀘스트 리셋: Daily 태그 퀘스트의 Done 체크박스 초기화

 노션 데이터베이스 필수 프로퍼티:
   - Name (title): 퀘스트 제목
   - Category (select): dev / study / life / work / etc
   - Difficuity (select): easy / medium / hard / legendary
   - Done (checkbox): 완료 여부
   - Date (date): 마감일
   - Tags (multi_select): Daily 태그로 일일 반복 퀘스트 식별
============================================================
"""

import httpx
from datetime import date
from typing import Optional

from ..config import settings
from ..models.schemas import QuestDTO, QuestCategory, QuestDifficulty, SubQuestDTO

# 노션 API 기본 설정
NOTION_BASE_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

# 난이도별 XP 매핑
DIFFICULTY_XP = {
    "easy": 15,
    "medium": 30,
    "hard": 50,
    "legendary": 100,
}


def _get_headers() -> dict:
    """노션 API 인증 헤더 생성"""
    return {
        "Authorization": f"Bearer {settings.NOTION_API_KEY}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


async def fetch_today_quests() -> list[QuestDTO]:
    """
    오늘의 퀘스트를 노션 데이터베이스에서 조회

    쿼리 필터 조건:
    - 날짜가 오늘이거나 (Date = today)
    - 아직 완료되지 않은 것 (Done = false)

    각 퀘스트의 페이지 내부 to_do 블록도 함께 조회하여 세부 퀘스트로 포함
    """
    today_str = date.today().isoformat()

    # 노션 데이터베이스 쿼리 필터 (OR 조건)
    query_body = {
        "filter": {
            "or": [
                {
                    "property": "Date",
                    "date": {"equals": today_str},
                },
                {
                    "property": "Done",
                    "checkbox": {"equals": False},
                },
            ]
        },
        "sorts": [
            {"property": "Date", "direction": "ascending"},
        ],
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{NOTION_BASE_URL}/databases/{settings.NOTION_DATABASE_ID}/query",
            headers=_get_headers(),
            json=query_body,
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()

    # 노션 페이지 배열 → QuestDTO 배열로 변환
    quests = []
    for page in data.get("results", []):
        quest = _parse_notion_page(page)
        if quest:
            # 세부 퀘스트(to_do 블록) 조회
            sub_quests = await fetch_page_sub_quests(quest.id)
            quest.sub_quests = sub_quests
            quest.sub_total = len(sub_quests)
            quest.sub_done = sum(1 for sq in sub_quests if sq.checked)
            quests.append(quest)

    return quests


def _parse_notion_page(page: dict) -> Optional[QuestDTO]:
    """
    노션 페이지 JSON → QuestDTO 변환

    Tags 프로퍼티에 "Daily"가 포함되어 있으면 is_daily=True
    """
    try:
        props = page.get("properties", {})

        # 제목 추출 (title 타입은 배열 안에 plain_text)
        name_prop = props.get("Name", {}).get("title", [])
        name = name_prop[0]["plain_text"] if name_prop else "제목 없음"

        # 카테고리 (select 타입)
        cat_prop = props.get("Category", {}).get("select")
        category = cat_prop["name"] if cat_prop else "etc"
        # 유효하지 않은 카테고리는 etc로 대체
        if category not in [e.value for e in QuestCategory]:
            category = "etc"

        # 난이도 (select 타입)
        diff_prop = props.get("Difficuity", {}).get("select")
        difficulty = diff_prop["name"] if diff_prop else "medium"
        if difficulty not in [e.value for e in QuestDifficulty]:
            difficulty = "medium"

        # 완료 여부 (checkbox 타입)
        done = props.get("Done", {}).get("checkbox", False)

        # 마감일 (date 타입)
        date_prop = props.get("Date", {}).get("date")
        due_date = date_prop["start"] if date_prop else None

        # Daily 태그 감지 (multi_select 타입)
        tags_prop = props.get("Tags", {}).get("multi_select", [])
        tag_names = [t.get("name", "").lower() for t in tags_prop]
        is_daily = "daily" in tag_names

        return QuestDTO(
            id=page["id"],
            name=name,
            category=QuestCategory(category),
            difficulty=QuestDifficulty(difficulty),
            xp=DIFFICULTY_XP.get(difficulty, 30),
            completed=done,
            due_date=due_date,
            is_daily=is_daily,
        )
    except (KeyError, IndexError):
        return None


# ============================================================
#  세부 퀘스트 (Sub-quest) - 페이지 내부 to_do 블록
# ============================================================

async def fetch_page_sub_quests(page_id: str) -> list[SubQuestDTO]:
    """
    노션 페이지 내부의 to_do 블록들을 세부 퀘스트로 조회

    노션 Block API를 사용하여 페이지의 자식 블록 중
    type이 "to_do"인 것만 필터링하여 SubQuestDTO로 변환
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{NOTION_BASE_URL}/blocks/{page_id}/children",
            headers=_get_headers(),
            timeout=10.0,
        )
        if response.status_code != 200:
            return []
        data = response.json()

    sub_quests = []
    for block in data.get("results", []):
        if block.get("type") == "to_do":
            todo = block["to_do"]
            text_parts = todo.get("rich_text", [])
            text = "".join(t.get("plain_text", "") for t in text_parts)
            checked = todo.get("checked", False)
            sub_quests.append(SubQuestDTO(
                block_id=block["id"],
                text=text,
                checked=checked,
            ))

    return sub_quests


async def toggle_sub_quest(block_id: str, checked: bool) -> bool:
    """
    세부 퀘스트(to_do 블록)의 체크 상태를 토글

    노션 Block API의 PATCH를 사용하여 to_do.checked 값을 변경
    """
    update_body = {
        "to_do": {
            "checked": checked,
        }
    }

    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"{NOTION_BASE_URL}/blocks/{block_id}",
            headers=_get_headers(),
            json=update_body,
            timeout=10.0,
        )
        return response.status_code == 200


async def mark_quest_complete(page_id: str) -> bool:
    """
    노션 페이지의 Done 체크박스를 true로 업데이트

    AI 검증을 통과한 후 내부적으로 호출됨
    → 노션에서도 해당 태스크가 '완료' 상태로 동기화
    """
    update_body = {
        "properties": {
            "Done": {"checkbox": True},
        }
    }

    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"{NOTION_BASE_URL}/pages/{page_id}",
            headers=_get_headers(),
            json=update_body,
            timeout=10.0,
        )
        return response.status_code == 200


# ============================================================
#  일일 퀘스트 리셋 - 스케줄러에서 호출
# ============================================================

async def reset_daily_quests():
    """
    Daily 태그가 붙은 퀘스트의 Done 체크박스를 false로 리셋

    매일 자정에 APScheduler가 호출하여
    일일 반복 퀘스트를 다시 활성화시킴
    """
    # Daily 태그 필터로 퀘스트 조회
    query_body = {
        "filter": {
            "property": "Tags",
            "multi_select": {"contains": "Daily"},
        }
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{NOTION_BASE_URL}/databases/{settings.NOTION_DATABASE_ID}/query",
            headers=_get_headers(),
            json=query_body,
            timeout=10.0,
        )
        if response.status_code != 200:
            return

        data = response.json()
        pages = data.get("results", [])

        # 각 Daily 퀘스트의 Done을 false로 리셋
        for page in pages:
            page_id = page["id"]
            is_done = page.get("properties", {}).get("Done", {}).get("checkbox", False)
            if is_done:
                await client.patch(
                    f"{NOTION_BASE_URL}/pages/{page_id}",
                    headers=_get_headers(),
                    json={"properties": {"Done": {"checkbox": False}}},
                    timeout=10.0,
                )

            # 세부 퀘스트(to_do 블록)도 리셋
            blocks_resp = await client.get(
                f"{NOTION_BASE_URL}/blocks/{page_id}/children",
                headers=_get_headers(),
                timeout=10.0,
            )
            if blocks_resp.status_code == 200:
                for block in blocks_resp.json().get("results", []):
                    if block.get("type") == "to_do" and block["to_do"].get("checked"):
                        await client.patch(
                            f"{NOTION_BASE_URL}/blocks/{block['id']}",
                            headers=_get_headers(),
                            json={"to_do": {"checked": False}},
                            timeout=10.0,
                        )
