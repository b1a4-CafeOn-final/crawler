from transformers import pipeline
import requests, pymysql, time, os

# ① 네이버 API 인증 정보
client_id = os.getenv("NAVER_API_CLIENT_ID")
client_secret = os.getenv("NAVER_API_SECRET_KEY")

# ② MySQL 연결
conn = pymysql.connect(
    host=os.getenv("DB_URL"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PW"),
    database="cafeOn",
    charset="utf8mb4"
)
cursor = conn.cursor()

# ③ 요약 모델 로드 (한국어 모델)
print("📦 Hugging Face 요약 모델 로드 중...")
summarizer = pipeline(
    "summarization",
    model="KETI-AIR/ke-t5-base-korean-summarization",
    framework="onnx"  # torch 대신 onnxruntime 사용
)

# ④ 블로그 검색 API
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
cursor.execute("SELECT id, name FROM cafes WHERE reviewsSummary IS NULL;")
cafes = cursor.fetchall()
print(f"📊 총 {len(cafes)}개 카페 요약 시작...")

# ⑥ 각 카페 이름별 요약 생성
for cafe_id, name in cafes:
    try:
        snippets = get_blog_snippets(name)
        if not snippets:
            print(f"⚠️ [{name}] 관련 블로그 없음, 건너뜀")
            continue

        text = " ".join(snippets)
        summary = summarizer(text, max_length=50, min_length=10, do_sample=False)[0]["summary_text"]

        sql = "UPDATE cafes SET reviewsSummary = %s WHERE id = %s"
        cursor.execute(sql, (summary, cafe_id))
        conn.commit()
        print(f"✅ [{name}] 요약 완료 → {summary}")

        time.sleep(1.2)  # 1초에 1개씩 처리 (API 과부하 방지)
    except Exception as e:
        print(f"❌ [{name}] 오류 발생: {e}")
        conn.rollback()
        continue

conn.close()
print("🎉 모든 카페 요약 저장 완료!")