from dotenv import load_dotenv
import requests, pymysql, time, os, json

# ① 환경변수 불러오기
load_dotenv()
client_id = os.getenv("NAVER_API_CLIENT_ID")
client_secret = os.getenv("NAVER_API_SECRET_KEY")
hf_token = os.getenv("HUGGINGFACE_TOKEN")  # Hugging Face 토큰 추가

# ② DB 연결
conn = pymysql.connect(
    host=os.getenv("DB_URL"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PW"),
    database="cafeOn",
    charset="utf8mb4"
)
cursor = conn.cursor()

# ③ Hugging Face 요약 API 함수
def summarize_text(text):
    API_URL = "https://api-inference.huggingface.co/models/paust/pko-t5-small"
    headers = {"Authorization": f"Bearer {hf_token}"}
    text = text[:1000]
    payload = {"inputs": text, "parameters": {"max_length": 50, "min_length": 10}}

    for attempt in range(3):  # 최대 3회 재시도
        try:
            res = requests.post(API_URL, headers=headers, json=payload, timeout=60)
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, list) and "summary_text" in data[0]:
                    return data[0]["summary_text"]
                else:
                    return f"요약 실패: {data}"
            elif res.status_code == 503:
                print("⏳ 모델이 로딩 중... 30초 대기 후 재시도")
                time.sleep(30)
                continue
            elif res.status_code == 404:
                print("⚠️ 모델 응답 없음(404), 10초 후 재시도")
                time.sleep(10)
                continue
            else:
                return f"요약 실패 (HTTP {res.status_code})"
        except Exception as e:
            if attempt < 2:
                print(f"⚠️ 재시도 중... ({attempt+1}/3) → {e}")
                time.sleep(5)
            else:
                return f"요약 실패: {e}"

    return "요약 실패 (최대 재시도 초과)"


# ④ 네이버 블로그 크롤링
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

# ⑤ DB에서 아직 요약 안 된 카페 불러오기
cursor.execute("SELECT cafe_id, name FROM cafes WHERE reviewsSummary IS NULL;")
cafes = cursor.fetchall()
print(f"📊 총 {len(cafes)}개 카페 요약 시작...")

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

        time.sleep(5)  # 요청 간격 5초 (API 과부하 방지)
    except Exception as e:
        print(f"❌ [{name}] 오류 발생: {e}")
        conn.rollback()
        continue

conn.close()
print("🎉 모든 카페 요약 저장 완료!")