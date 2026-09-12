import random
import requests
from datetime import datetime
from config import VIRAL_PILLARS_DEV

def fetch_trends():
    trends = []
    try:
        r = requests.get("https://hn.algolia.com/api/v1/search?query=AI&tags=story&hitsPerPage=5", timeout=5).json()
        for hit in r.get("hits", []):
            trends.append(hit["title"])
    except:
        pass
    trends += ["MCP Model Context Protocol", "Cursor AI", "n8n AI automation", "LangGraph", "Claude 4", "GPT-5", "Sora 2"]
    return list(set(trends))[:10]

DEV_TEMPLATES = [
    "{trend}로 10분 만에 {task} 자동화하는 법",
    "{trend} + n8n 조합, 이걸 아직도 수동으로 한다고?",
    "{trend} 에이전트가 내 일을 대신한 24시간",
    "{trend} vs {rival} - 코딩 대결 결과 충격",
    "개발자 90%가 모르는 {trend} vs {rival} 차이",
    "{trend} 버리고 {rival} 갈아탄 이유",
    "{trend} 200% 활용하는 프롬프트 1줄",
    "{trend} 이 설정 안 하면 50% 손해",
    "Cursor에서 {trend} 이렇게 쓰는 사람 1%입니다",
    "{trend}로 SaaS 3일 만에 만들고 $1,200 번 썰",
    "{trend}가 내 코드 다 지운 썰 - 복구 방법",
]

def generate_candidates(trends):
    rivals = {"GPT-5": "Claude 4", "Claude 4": "Cursor", "MCP": "LangChain", "Cursor": "Windsurf", "n8n": "Make", "LangGraph": "CrewAI", "MCP Model Context Protocol": "LangChain"}
    tasks = ["유튜브 쇼츠 업로드", "PR 리뷰", "버그 픽스", "문서화", "배포 파이프라인", "고객 CS 답변", "코드 리팩토링"]
    candidates = []
    for _ in range(20):
        trend = random.choice(trends)
        tmpl = random.choice(DEV_TEMPLATES)
        rival = rivals.get(trend, "Claude 4")
        task = random.choice(tasks)
        topic = tmpl.format(trend=trend, rival=rival, task=task)
        pillar = "automation" if "자동화" in topic or "MCP" in topic or "n8n" in topic else \
                 "comparison" if "vs" in topic else \
                 "tips" if "프롬프트" in topic or "설정" in topic or "%" in topic or "이렇게 쓰는" in topic else "money"
        base_score = 80 + random.randint(0,15)
        weight = VIRAL_PILLARS_DEV.get(pillar, 0.1)
        viral_score = int(base_score + weight*30)
        hooks = {
            "automation": f"이거 아직도 수동으로 한다고요? {trend}",
            "comparison": f"{trend} 이제 쓸모없습니다. {rival} 때문에",
            "tips": f"개발자 90%가 모르는 {trend} 치트키",
            "money": f"{trend}로 3일 만에 만든 SaaS",
            "shock": f"어제 밤 {trend}가 제 코드 다 날렸습니다",
        }
        candidates.append({
            "topic": topic,
            "pillar": pillar,
            "hook": hooks.get(pillar, topic),
            "trend": trend,
            "viral_score": min(99, viral_score),
            "date": datetime.now().strftime("%Y-%m-%d")
        })
    candidates.sort(key=lambda x: x["viral_score"], reverse=True)
    return candidates

def pick_today_topic(use_gpt=False):
    trends = fetch_trends()
    candidates = generate_candidates(trends)
    if use_gpt:
        try:
            from openai import OpenAI
            import os, json
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            prompt = f"너는 개발자 타겟 유튜브 쇼츠 바이럴 전문가야. 후보 중 조회수 폭발할 1개 골라줘. 트렌드: {trends}, 후보: {candidates[:10]}, JSON으로 {{pick_index: 0, reason: ''}}"
            res = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"user","content":prompt}])
            data = json.loads(res.choices[0].message.content)
            return candidates[data["pick_index"]]
        except Exception as e:
            print(f"GPT 리랭킹 실패, 로컬 스코어 사용: {e}")
    return candidates[0]

if __name__ == "__main__":
    top = pick_today_topic()
    print(top)
