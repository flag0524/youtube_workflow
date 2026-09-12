import os
from openai import OpenAI

SYSTEM_PROMPT = """너는 개발자 타겟 유튜브 쇼츠(45초) 대본 작가다.
규칙:
1. 0-3초 훅은 무조건 공포/충격/돈/호기심으로 시작
2. 전체 5개 챕터: HOOK(3초) - 문제제기(7초) - 해결책1(10초) - 해결책2(15초) - CTA(10초)
3. 한국어로 작성, 개발자 용어(MCP, n8n, LangGraph, Cursor) 자연스럽게 사용
4. 문장은 짧게, 구어체, 1문장 15자 이내
5. 마지막은 저장 유도 CTA
6. JSON으로만 출력"""

def write_script(topic_dict):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    user_prompt = f"""
주제: {topic_dict['topic']}
트렌드: {topic_dict['trend']}
훅: {topic_dict['hook']}
필러: {topic_dict['pillar']}

45초 대본 JSON으로 만들어줘:
{{
  "title": "유튜브 제목 (클릭유도, 30자 이내)",
  "hook_text": "0-3초 화면 자막용",
  "narration": "전체 나레이션 45초 분량 약 130-150자",
  "scenes": [
    {{"time": "0-3s", "visual": "화면 설명", "subtitle": "큰 자막"}}
  ],
  "description": "유튜브 설명란 SEO용 5줄",
  "tags": ["태그 15개"]
}}
"""
    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        response_format={"type": "json_object"}
    )
    import json
    return json.loads(res.choices[0].message.content)
