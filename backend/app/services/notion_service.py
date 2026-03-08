"""
============================================================
 1. 노션 API 연동 서비스
============================================================
 노션 데이터베이스를 SSOT(Single Source of Truth)로 사용
 - 오늘의 할 일 조회: 날짜가 오늘이거나 미완료인 태스크 쿼리
 - 퀘스트 완료 처리: 노션 페이지의 체크박스 프로퍼티를 true로 변경

 노션 데이터베이스 필수 프로퍼티:
   - Name (title): 퀘스트 제목
   - Category (select): dev / study / life / work / etc
   - Difficuity (select): easy / medium / hard / legendary
   - Done (checkbox): 완료 여부
   - Date (date): 마감일
============================================================
"""

import httpx
from datetime import date
from typing import Optional

from ..config import settings
from ..models.schemas import QuestDTO, QuestCategory, QuestDifficulty

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

    노션 API 응답은 매우 복잡한 중첩 구조이므로
    _parse_notion_page()에서 위젯에 필요한 필드만 추출
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
            quests.append(quest)

    return quests


def _parse_notion_page(page: dict) -> Optional[QuestDTO]:
    """
    노션 페이지 JSON → QuestDTO 변환

    노션 API 응답 구조 예시:
    {
      "id": "page-id-xxx",
      "properties": {
        "Name": { "title": [{ "plain_text": "..." }] },
        "Category": { "select": { "name": "dev" } },
        "Difficuity": { "select": { "name": "hard" } },
        "Done": { "checkbox": true },
        "Date": { "date": { "start": "2024-01-01" } }
      }
    }

    이 복잡한 구조에서 필요한 값만 안전하게 추출
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

        return QuestDTO(
            id=page["id"],
            name=name,
            category=QuestCategory(category),
            difficulty=QuestDifficulty(difficulty),
            xp=DIFFICULTY_XP.get(difficulty, 30),
            completed=done,
            due_date=due_date,
        )
    except (KeyError, IndexError):
        return None


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
