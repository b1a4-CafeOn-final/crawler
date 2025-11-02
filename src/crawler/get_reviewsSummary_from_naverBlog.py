# get_reviewsSummary_from_naver.py
# ------------------------------------------------------------
# ✅ 네이버 블로그 리뷰를 수집하고 OpenRouter 무료 모델로 요약 후 DB에 저장
# ✅ MySQL 자동 재연결 (ConnectionResetError, server gone away 완벽 대응)
# ✅ 모든 카페 대상 반복 실행
# ------------------------------------------------------------

from dotenv import load_dotenv
import requests, pymysql, time, os, json, sys

# ① 환경변수 불러오기
load_dotenv(".env.local")
client_id = os.getenv("NAVER_API_CLIENT_ID")
client_secret = os.getenv("NAVER_API_SECRET_KEY")
openrouter_key = os.getenv("OPENROUTER_API_KEY")

DB_CONFIG = {
    "host": os.getenv("DB_URL"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PW"),
    "database": "cafeOn",
    "charset": "utf8mb4",
    "autocommit": False
}

# ② DB 연결 함수 (끊기면 자동 재연결)
def get_connection():
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        return conn, cursor
    except Exception as e:
        print(f"❌ DB 연결 실패: {e}")
        sys.exit(1)

conn, cursor = get_connection()

# ③ OpenRouter 요약 함수
def summarize_text(text):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {openrouter_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com",  # OpenRouter 선택적 헤더 (사용 통계용)
        "X-Title": "Cafe Review Summarizer"  # OpenRouter 선택적 헤더 (사용 통계용)
    }

    # 텍스트 길이 제한
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
        "max_tokens": 400,
        "stop": ["\n\n", "요약:"]
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=60)

        # OpenRouter 특정 에러 코드 처리
        if res.status_code == 402:
            return f"요약 실패: OpenRouter 크레딧 만료 (402)"
        elif res.status_code == 401:
            return f"요약 실패: OpenRouter API 키 인증 실패 (401)"
        elif res.status_code == 429:
            return f"요약 실패: OpenRouter 요청 제한 초과 (429)"

        res.raise_for_status()
        data = res.json()

        if "choices" in data and len(data["choices"]) > 0:
            summary = data["choices"][0]["message"]["content"].strip()
            if not summary.endswith(("다.", "요.", "음.")):
                summary += "입니다."
            return summary
        else:
            return f"요약 실패: OpenRouter 응답에 choices가 없음 - {json.dumps(data, ensure_ascii=False)}"
    except requests.exceptions.RequestException as e:
        return f"요약 실패: 네트워크 오류 - {e}"
    except json.JSONDecodeError as e:
        return f"요약 실패: 응답 파싱 오류 - {e}"
    except Exception as e:
        return f"요약 실패: {e}"

# ④ 네이버 블로그 리뷰 수집
def get_blog_snippets(query):
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    params = {"query": query + " 카페 리뷰", "display": 5, "sort": "sim"}
    try:
        res = requests.get("https://openapi.naver.com/v1/search/blog.json", headers=headers, params=params)
        if res.status_code == 200:
            items = res.json().get("items", [])
            return [i["description"] for i in items]
        else:
            print(f"⚠️ 네이버 API 응답 오류({res.status_code}) → {query}")
            return []
    except Exception as e:
        print(f"⚠️ 네이버 요청 실패({query}): {e}")
        return []

# ⑤ 전체 카페 불러오기
cursor.execute("SELECT cafe_id, name FROM cafes;")
cafes = cursor.fetchall()
print(f"📊 총 {len(cafes)}개 카페 요약 시작... (기존 데이터도 포함)")

# ⑥ 메인 루프
for idx, (cafe_id, name) in enumerate(cafes, start=1):
    try:
        # 🔸 연결 유지 확인
        conn.ping(reconnect=True)

        snippets = get_blog_snippets(name)
        if not snippets:
            print(f"⚠️ ({idx}/{len(cafes)}) [{name}] 관련 블로그 없음, 건너뜀")
            continue

        text = " ".join(snippets)
        summary = summarize_text(text)

        sql = "UPDATE cafes SET reviewsSummary = %s WHERE cafe_id = %s"
        cursor.execute(sql, (summary, cafe_id))
        conn.commit()

        if "요약 실패" in summary:
            print(f"⚠️ ({idx}/{len(cafes)}) [{name}] 요약 실패 → {summary}")
        else:
            print(f"✅ ({idx}/{len(cafes)}) [{name}] 요약 완료 → {summary[:60]}...")

        time.sleep(5)  # API 과부하 방지

    except pymysql.err.OperationalError as e:
        print(f"⚠️ DB 연결 끊김 감지 → 재연결 시도 중... ({e})")
        time.sleep(3)
        conn, cursor = get_connection()
        continue

    except Exception as e:
        print(f"❌ ({idx}/{len(cafes)}) [{name}] 처리 중 오류 발생: {e}")
        try:
            conn.rollback()
        except:
            pass
        continue

conn.close()
print("🎉 모든 카페 요약 저장 완료!")
