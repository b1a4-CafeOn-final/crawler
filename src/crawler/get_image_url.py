from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from sqlalchemy import create_engine, text
from webdriver_manager.chrome import ChromeDriverManager
import time, random, os

# 1️⃣ DB 연결
load_dotenv(".env.local")
DB_URL = os.getenv("DB_URL")
DB_USER = os.getenv("DB_USER")
DB_PW = os.getenv("DB_PW")

DB_CONN_URL = f"mysql+pymysql://{DB_USER}:{DB_PW}@{DB_URL}:3306/cafeOn?charset=utf8mb4"
engine = create_engine(DB_CONN_URL)

# 2️⃣ Selenium 설정
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--window-size=1920x1080")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

# 3️⃣ photo_url 비어있는 카페 불러오기
with engine.connect() as conn:
    cafes = conn.execute(text("""
        SELECT cafe_id, kakao_url, name
        FROM cafes
        WHERE (photo_url IS NULL OR photo_url = '')
        AND kakao_url IS NOT NULL
        LIMIT 10000
    """)).fetchall()

total = len(cafes)
print(f"📊 총 {total}개 카페 크롤링 시작")

# 4️⃣ 이미지 추출 함수 (board_photo 전용 selector 추가)
def extract_photo_url(driver):
    selectors = [
        "div.board_photo a.link_photo img",  # ✅ 새로 확인된 구조
        "div.place_thumb img",
        "div.photo_area img",
        "div.bg_present img",
        "div.wrap_thumb img"
    ]

    for sel in selectors:
        try:
            elems = driver.find_elements(By.CSS_SELECTOR, sel)
            print(f"🔍 selector='{sel}' → {len(elems)}개 발견")
            for e in elems:
                src = e.get_attribute("src")
                if src and src.startswith("http"):
                    print(f"✅ 이미지 src 발견: {src[:90]}...")
                    return src
        except Exception as e:
            print(f"❌ selector '{sel}' 오류: {e}")
    return None

# 5️⃣ 메인 크롤링 루프
for idx, (cafe_id, kakao_url, name) in enumerate(cafes, 1):
    try:
        print(f"\n⏳ [{idx}/{total}] {name} ({cafe_id}) 접속 중...")
        driver.get(kakao_url)
        time.sleep(random.uniform(2.5, 4.5))  # 자연스러운 대기

        photo_url = extract_photo_url(driver)
        if not photo_url:
            print(f"⚠️ [{name}] 대표 이미지 없음 ({kakao_url})")
            continue

        with engine.begin() as conn:
            conn.execute(
                text("UPDATE cafes SET photo_url = :photo_url WHERE cafe_id = :cafe_id"),
                {"photo_url": photo_url, "cafe_id": cafe_id}
            )

        print(f"✅ [{name}] ({cafe_id}) 저장 완료 → {photo_url}")

        # 주기적 재시작 (메모리 안정성)
        if idx % 100 == 0:
            print("♻️ 100개 완료 → 드라이버 재시작 중...")
            driver.quit()
            time.sleep(3)
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    except Exception as e:
        print(f"❌ [{name}] ({cafe_id}) 오류: {e}")
        continue

driver.quit()
print("\n🎉 모든 크롤링 완료")
