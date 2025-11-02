import os, json, time, random, pymysql, requests, re
from datetime import datetime, timedelta
from difflib import get_close_matches
from dotenv import load_dotenv

# ==============================
# ① 기본 설정
# ==============================
load_dotenv(".env.local")
openrouter_key = os.getenv("OPENROUTER_API_KEY")

DB_CONFIG = {
    "host": os.getenv("DB_URL"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PW"),
    "database": "cafeOn",
    "charset": "utf8mb4"
}

# ✅ 오로지 이 리스트 안에서만 태그 선택 가능
CANDIDATE_TAGS = [
    # 분위기 / 무드
    "조용한","감성적인","프라이빗한","우중(비오는날)","따뜻한","햇살좋은","통창있는",
    "아늑한","빈티지한","모던한","조명어두운","음악좋은","루프탑","뷰좋은",
    "로맨틱한","잔잔한","차분한","고급스러운","깔끔한","포근한","힐링되는","분위기있는",
    "세련된","트렌디한","아트적인","인더스트리얼한","북유럽감성","미니멀한","내추럴한",

    # 이용 목적 / 활동
    "데이트하기좋은","혼자오기좋은","친구모임좋은","작업하기좋은","공부하기좋은",
    "책읽기좋은","휴식하기좋은","대화하기좋은","사진찍기좋은","힐링하기좋은",
    "산책중가기좋은","브런치하기좋은","디저트먹기좋은","커피맛좋은","카공하기좋은",
    "회의하기좋은","수다떨기좋은","멍때리기좋은","노트북하기좋은","생각정리하기좋은",

    # 공간 / 구조 / 좌석
    "의자편한","좌석넓은","좌식자리있는","바좌석있는","콘센트많은","층고높은",
    "테라스있는","야외좌석있는","창가자리좋은","단체석있는","소파자리있는",
    "1인석있는","룸있는","뷰자리좋은","통유리","오픈키친","테이블간격넓은","흡연공간있는",

    # 서비스 / 편의
    "주차편리","발렛가능","반려동물가능","가성비좋은","가격대높은","예약가능",
    "친절한","응대좋은","조명따뜻한","냉난방쾌적한","청결한","화장실깨끗한","분리수거잘된",
    "와이파이빠른","배달가능","포장가능","셀프서비스","잔잔한음악","프리오더가능","충전가능",

    # 메뉴 / 맛 / 퀄리티
    "디저트맛집","브런치맛집","커피맛집","케이크맛있는","음료다양한","빵맛있는",
    "수제디저트","라떼맛집","홍차맛있는","차종류다양한","식사메뉴있는","간식좋은",
    "건강한","비건가능","논커피메뉴많은","계절메뉴있는","한정메뉴있는","시그니처있음",

    # 분위기 상황 / 특수 테마
    "데이트코스","기념일분위기","사진스팟","야경좋은","조용한동네","핫플레이스",
    "감성사진","전시있는","플랜테리어","드라이플라워","빈티지소품","갤러리느낌",
    "목재인테리어","화이트톤","카페거리위치","주택개조","지하감성","옥상카페","숨은명소"
]



LOG_FILE = "tag_progress.json"
ERROR_LOG = "tag_errors.log"


# ==============================
# ② DB 연결
# ==============================
def get_conn():
    while True:
        try:
            return pymysql.connect(**DB_CONFIG)
        except Exception as e:
            print("❌ DB 연결 실패:", e)
            time.sleep(10)


# ==============================
# ③ AI 태그 추출
# ==============================
def extract_tags(summary: str):
    url = "https://openrouter.ai/api/v1/chat/completions"
    prompt = f"""
후기:
"{summary}"

아래의 100개 태그 중에서, 이 후기와 가장 관련 있는 3~6개의 태그를 골라주세요.
새로운 태그를 만들지 말고, 반드시 아래 목록 중에서만 선택하세요.
출력 형식은 쉼표로 구분된 태그명만 쓰세요. 예: 조용한, 프라이빗한, 감성적인

가능한 태그 목록:
{', '.join(CANDIDATE_TAGS)}
"""
    headers = {
        "Authorization": f"Bearer {openrouter_key.strip()}",
        "Content-Type": "application/json"
    }
#     payload = {
#     "model": "openrouter/sonoma-dusk-alpha",  # ✅ 정확한 전체 모델명
#     "messages": [{"role": "user", "content": prompt}],
#     "temperature": 0.05
# }
    payload = {
    "model": "mistralai/mixtral-8x7b",  # ✅ 현재 사용 가능한 모델
    "messages": [{"role": "user", "content": prompt}],
    "temperature": 0.05
}



    for attempt in range(3):
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=80)
            res.raise_for_status()
            text = res.json()["choices"][0]["message"]["content"].strip()
            text_clean = re.sub(r"[^가-힣,\s]", " ", text)

            matched = [tag for tag in CANDIDATE_TAGS if re.search(tag, text_clean)]
            matched = list(set(matched))
            return matched[:6]
        except Exception as e:
            print(f"⚠️ AI 요청 실패 ({attempt+1}/3):", e)
            time.sleep(5 * (attempt + 1))
    return []




    for attempt in range(3):
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=80)
            res.raise_for_status()
            text = res.json()["choices"][0]["message"]["content"].strip()
            text_clean = re.sub(r"[^가-힣,\s]", " ", text)

            # 🔹 핵심: CANDIDATE_TAGS 안의 단어만 허용
            matched = []
            for tag in CANDIDATE_TAGS:
                # 부분 일치 허용 (e.g. '뷰자리좋은' -> '뷰좋은')
                if re.search(tag.replace("(", r"\(").replace(")", r"\)"), text_clean):
                    matched.append(tag)

            # 중복 제거
            matched = list(set(matched))
            return matched[:6]  # 최대 6개까지만
        except Exception as e:
            print(f"⚠️ AI 요청 실패 ({attempt+1}/3):", e)
            time.sleep(5 * (attempt + 1))
    return []


# ==============================
# ④ 태그 삽입
# ==============================
def insert_cafe_tags(conn, cafe_id: int, tag_names: list[str]):
    cur = conn.cursor()
    for name in tag_names:
        cur.execute("SELECT tag_id FROM tags WHERE name=%s", (name,))
        row = cur.fetchone()
        if row:
            tag_id = row[0]
        else:
            cur.execute("INSERT INTO tags (name) VALUES (%s)", (name,))
            conn.commit()
            tag_id = cur.lastrowid
        cur.execute("INSERT IGNORE INTO cafe_tags (cafe_id, tag_id) VALUES (%s, %s)", (cafe_id, tag_id))
    conn.commit()


# ==============================
# ⑤ 진행 로그 로드/저장
# ==============================
def load_progress():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"done": []}

def save_progress(done_list):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump({"done": done_list}, f, ensure_ascii=False, indent=2)


# ==============================
# ⑥ 메인 루프
# ==============================
def main():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT cafe_id, name, reviews_summary FROM cafes WHERE reviews_summary IS NOT NULL")
    cafes = cur.fetchall()
    total = len(cafes)

    done = load_progress()["done"]
    start_time = datetime.now()

    for idx, (cafe_id, name, summary) in enumerate(cafes, start=1):
        if str(cafe_id) in done:
            continue

        progress = (len(done) / total) * 100
        elapsed = datetime.now() - start_time
        avg_time = elapsed / (len(done) + 1) if done else timedelta(seconds=3)
        eta = elapsed + avg_time * (total - len(done))
        eta_h, eta_m = int(eta.total_seconds() // 3600), int((eta.total_seconds() % 3600) // 60)

        print(f"\n🧠 [{idx}/{total}] {name} — 태그 추출 중... ({progress:.2f}% | ETA {eta_h}h {eta_m}m 남음)")

        tags = extract_tags(summary)
        if not tags:
            print(f"❌ 실패: {cafe_id} ({name})")
            with open(ERROR_LOG, "a", encoding="utf-8") as f:
                f.write(f"{cafe_id},{name}\n")
            continue

        print("  → 추출된 태그:", tags)
        insert_cafe_tags(conn, cafe_id, tags)
        done.append(str(cafe_id))
        save_progress(done)
        time.sleep(random.uniform(0.6, 1.2))

    conn.close()
    print("\n✅ 모든 카페 태그 매핑 완료!")


if __name__ == "__main__":
    main()
