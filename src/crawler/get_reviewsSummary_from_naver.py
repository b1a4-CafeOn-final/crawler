from dotenv import load_dotenv
import requests, pymysql, time, os, json

# ① 환경변수 불러오기
load_dotenv()
client_id = os.getenv("NAVER_API_CLIENT_ID")
client_secret = os.getenv("NAVER_API_SECRET_KEY")
openrouter_key = os.getenv("OPENROUTER_API_KEY")

# ② DB 연결
conn = pymysql.connect(
    host=os.getenv("DB_URL"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PW"),
    database="cafeOn",
    charset="utf8mb4"
)
cursor = conn.cursor()

# ③ OpenRouter 요약 함수
def summarize_text(text):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {openrouter_key}",
        "Content-Type": "application/json"
    }

    # 텍스트 길이 제한 (너무 길면 잘라내기)
    text = text[:2000]

    payload = {
        "model": "meta-llama/llama-3-8b-instruct",  # ✅ 무료 모델
        "messages": [
            {
                "role": "system",
                "content": (
                    "너는 한국어 카페 리뷰를 자연스럽고 부드럽게 요약하는 한국어 전용 요약봇이야. "
                    "반드시 한국어로만 대답하고, 영어 문장은 절대 포함하지 마. "
                    "출력은 한 문단으로 완전한 문장으로 끝나야 해. "
                    "리뷰의 분위기와 핵심만 전달하되, 주소, 전화번호 등 불필요한 정보는 빼고 요약해."
                )
            },
            {
                "role": "user",
                "content": f"다음 내용을 짧고 자연스러운 한국어로 한 문단 요약해줘:\n{text}"
            }
        ],
        "temperature": 0.4,
        "max_tokens": 400,  # ✅ 더 긴 요약 허용
        "stop": ["\n\n", "요약:"]
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=60)
        data = res.json()

        if "choices" in data and len(data["choices"]) > 0:
            summary = data["choices"][0]["message"]["content"].strip()
            if not summary.endswith(("다.", "요.", "음.")):
                summary += "입니다."
            return summary
        else:
            return f"요약 실패: {json.dumps(data, ensure_ascii=False)}"
    except Exception as e:
        return f"요약 실패: {e}"

# ④ 네이버 블로그 검색
def get_blog_snippets(query):
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    params = {"query": query + " 카페 리뷰", "display": 5, "sort": "sim"}
    res = requests.get("https://openapi.naver.com/v1/search/blog.json", headers=headers, params=params)
    if res.status_code == 200:
        items = res.json().get("items", [])
        return [i["description"] for i in items]
    return []

# ⑤ DB에서 전체 카페 불러오기 (✅ 이미 요약된 것도 다시 처리)
cursor.execute("SELECT cafe_id, name FROM cafes;")
cafes = cursor.fetchall()
print(f"📊 총 {len(cafes)}개 카페 요약 시작... (모두 다시 실행)")

# ⑥ 실행 루프
for cafe_id, name in cafes:
    try:
        snippets = get_blog_snippets(name)
        if not snippets:
            print(f"⚠️ [{name}] 관련 블로그 없음, 건너뜀")
            continue

        text = " ".join(snippets)
        summary = summarize_text(text)

        sql = "UPDATE cafes SET reviewsSummary = %s WHERE cafe_id = %s"
        cursor.execute(sql, (summary, cafe_id))
        conn.commit()

        if "요약 실패" in summary:
            print(f"⚠️ [{name}] 요약 실패 → {summary}")
        else:
            print(f"✅ [{name}] 요약 완료 → {summary}")

        time.sleep(5)  # 과부하 방지
    except Exception as e:
        print(f"❌ [{name}] 오류 발생: {e}")
        conn.rollback()
        continue

conn.close()
print("🎉 모든 카페 요약 저장 완료!")