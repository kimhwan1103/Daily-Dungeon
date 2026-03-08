"""
============================================================
 2. AI 검증 파이프라인 (Gemini API 연동)
============================================================
 퀘스트 작업 증명(Proof of Work)을 AI가 검증하는 핵심 모듈

 프롬프트는 prompts/verify_prompt.json에서 외부 관리
 → 코드 수정 없이 JSON만 편집하여 검증 기준/톤/모델 변경 가능

 흐름:
 1. JSON에서 프롬프트 템플릿 로딩
 2. 유저 증명 데이터를 템플릿에 삽입
 3. Gemini API 비동기 호출 (구조화된 출력 강제)
 4. 응답을 VerifyResult로 파싱
============================================================
"""

import json
import base64
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types

from ..config import settings
from ..models.schemas import VerifyResult

# ============================================================
#  프롬프트 JSON 로딩
# ============================================================
#  prompts/verify_prompt.json을 읽어 딕셔너리로 캐싱
#  서버 기동 시 1회만 로드 (파일 변경 시 서버 재시작 필요)
#
#  JSON 구조:
#    system_prompt      - 시스템 프롬프트 (NPC 역할 + 검증 기준)
#    user_template      - 유저 메시지 뼈대 ({quest_title}, {proof_body})
#    proof_text_section  - 텍스트 증명이 있을 때 삽입되는 블록
#    proof_image_section - 이미지 증명이 있을 때 삽입되는 블록
#    no_proof_section    - 증명이 아예 없을 때 삽입되는 블록
#    model              - 사용할 Gemini 모델 이름
#    temperature        - 생성 온도 (0.0~2.0)

PROMPTS_PATH = Path(__file__).parent.parent / "prompts" / "verify_prompt.json"

def _load_prompts() -> dict:
    """프롬프트 JSON 파일 로딩"""
    with open(PROMPTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

_prompts: dict = _load_prompts()


def reload_prompts():
    """
    프롬프트 핫 리로드 (런타임 중 JSON 변경 반영)
    관리자 API나 디버그용으로 호출 가능
    """
    global _prompts
    _prompts = _load_prompts()


# ============================================================
#  Gemini 클라이언트
# ============================================================

_client: Optional[genai.Client] = None

def _get_client() -> genai.Client:
    """Gemini API 클라이언트 싱글톤 (lazy init)"""
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


# ============================================================
#  유저 메시지 조립
# ============================================================

def _build_user_message(
    quest_title: str,
    proof_text: Optional[str],
    proof_image_base64: Optional[str],
) -> str:
    """
    프롬프트 JSON 템플릿에 실제 데이터를 삽입하여 유저 메시지 생성

    조립 순서:
    1. proof_body 구성 (텍스트/이미지/없음 섹션 조합)
    2. user_template에 quest_title + proof_body 삽입
    """
    proof_body = ""

    if proof_text:
        proof_body += _prompts["proof_text_section"].format(proof_text=proof_text)

    if proof_image_base64:
        proof_body += _prompts["proof_image_section"]

    if not proof_text and not proof_image_base64:
        proof_body += _prompts["no_proof_section"]

    return _prompts["user_template"].format(
        quest_title=quest_title,
        proof_body=proof_body,
    )


# ============================================================
#  메인 검증 함수
# ============================================================

async def verify_quest_proof(
    quest_title: str,
    proof_text: Optional[str] = None,
    proof_image_base64: Optional[str] = None,
) -> VerifyResult:
    """
    퀘스트 증명을 Gemini AI로 검증

    Args:
        quest_title: 검증 대상 퀘스트 제목
        proof_text: 텍스트 증명 (코드 스니펫, 작업 요약 등)
        proof_image_base64: 이미지 증명 (base64 인코딩)

    Returns:
        VerifyResult: 통과 여부 + 확신도 + NPC 피드백
    """
    client = _get_client()

    # 유저 메시지 조립 (JSON 템플릿 기반)
    user_message = _build_user_message(quest_title, proof_text, proof_image_base64)

    # 요청 컨텐츠 구성 (이미지가 있으면 멀티모달)
    contents = [user_message]

    if proof_image_base64:
        # base64 헤더(data:image/...;base64,) 제거 후 디코딩
        raw = proof_image_base64
        if "," in raw:
            raw = raw.split(",", 1)[1]
        image_bytes = base64.b64decode(raw)

        contents = [
            types.Part.from_text(text=user_message),
            types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
        ]

    try:
        # Gemini API 호출 (JSON 구조화 출력 강제)
        response = client.models.generate_content(
            model=_prompts["model"],
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=_prompts["system_prompt"],
                response_mime_type="application/json",
                temperature=_prompts["temperature"],
            ),
        )

        result_data = json.loads(response.text)
        return VerifyResult(
            is_passed=result_data.get("is_passed", False),
            confidence_score=min(1.0, max(0.0, result_data.get("confidence_score", 0.5))),
            npc_feedback=result_data.get("npc_feedback", "검증 결과를 확인할 수 없습니다."),
        )

    except Exception as e:
        # API 오류 시 안전하게 실패 처리
        return VerifyResult(
            is_passed=False,
            confidence_score=0.0,
            npc_feedback=f"검증 중 문제가 발생했습니다. 다시 시도해주세요. (오류: {str(e)[:100]})",
        )
