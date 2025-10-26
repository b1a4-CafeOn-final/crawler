from dotenv import load_dotenv
from selenium import webdriver  # selenium : 브라우저 자동조작 (실제 크롬 창 띄워서 웹페이지 클릭/스크롤/텍스트 추출 등 가능) pip install selenium
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By # By : HTML요소를 찾을 때 사용하는 기준 (CSS_SELECTOR, XPATH 등)
from sqlalchemy import create_engine, text  # SQLAlchemy : 파이썬 <-> MySQL 연결을 쉽게 해주는 ORM/DB 라이브러리 pip install SQLAlchemy pymysql
import time, random, os, re # 파이썬 표준 모듈. 대기 시간(sleep), 랜덤 시간 설정할 때 사용
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# 1. DB 연결 (SQLAlchemy)
load_dotenv()  # .env 파일에서 환경변수 불러오기
DB_URL = os.getenv("DB_URL")
DB_USER = os.getenv("DB_USER")
DB_PW = os.getenv("DB_PW")

DB_CONN_URL = f"mysql+pymysql://{DB_USER}:{DB_PW}@{DB_URL}:3306/cafeOn?charset=utf8mb4"
engine = create_engine(DB_CONN_URL) # engine은 이후 쿼리를 실행할 때 쓰임 (engine.connect(), engine.begin() 등)

# 2. 크롤링 준비 (Selenium + ChromeDriver로 실제 브라우저 렌더링)
# Selenium 설정
chrome_options = Options()
chrome_options.add_argument("--headless")  # 실제 창을 띄우지 않고, 백그라운드에서 실행
chrome_options.add_argument("--no-sandbox") # 리눅스 환경에서 충돌 방지용
chrome_options.add_argument("--disable-dev-shm-usage") # /dev/shm 사용 안함
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)   # 실제 크롬 브라우저를 자동조작할 수 있는 드라이버 객체 생성 -> 이후 driver.get(url)로 웹페이지를 열 수 있음

# 3. 운영시간 추출 로직 구현 (페이지 내에서 '영업시간' 또는 '운영시간'을 포함하는 element를 찾아서 텍스트만 뽑기)
# 3-1. DB에서 open_hours 비어있는 카페 목록 가져오기
# ※ 기존에는 open_hours가 비어있는 데이터만 불러왔지만, 지금은 전체를 다시 갱신하기 위해 조건을 제거함
with engine.connect() as conn:
    cafes = conn.execute(text("SELECT cafe_id, kakao_url, name FROM cafes LIMIT 15000")).fetchall()    # 전체 카페 데이터 대상으로 크롤링 수행

wait = WebDriverWait(driver, 8) # 최대 8초 대기 (페이지 로딩 및 요소 탐색 시)

def clean_open_hours(raw: str) -> str:
    """카카오맵 영업시간 텍스트에서 불필요한 문구 제거 및 정규화"""
    if not raw:
        return "정보없음"
    
    # 1) 불필요한 키워드 제거
    raw = re.sub(r"(영업\s*중|영업\s*마감|곧\s*영업\s*마감|내일\s*\d{1,2}:\d{2}\s*오픈|수정제안|요기요\s*제공)", "", raw)
    
    # 2) 날짜 패턴 제거 (예: (10/10), (10/12) 등)
    raw = re.sub(r"\(\d{1,2}/\d{1,2}\)", "", raw)
    
    # 3) 불필요한 공백 / 줄바꿈 정리
    raw = re.sub(r"\s+", " ", raw).strip()
    
    # 4) 라스트오더, 브레이크타임, 공휴일 등 보조정보는 유지 (핵심은 시간만)
    return raw

def extract_weekly_schedule(raw: str) -> str:
    """정규표현식으로 '요일 + 시간' 패턴만 남기고, 월~일 순서로 정렬"""
    if not raw or raw == "정보없음":
        return raw

    # (요일)(시작시간)(종료시간) 그룹으로 추출
    matches = re.findall(r"(월|화|수|목|금|토|일)[^\d]*(\d{1,2}:\d{2})\s*[~\-]\s*(\d{1,2}:\d{2})", raw)

    if not matches:
        return raw  # 혹시 매칭 실패 시 원본 반환

    # 요일 순서 기준
    order = {"월": 1, "화": 2, "수": 3, "목": 4, "금": 5, "토": 6, "일": 7}

    results = []
    for day, start, end in matches:
        results.append((order.get(day, 99), f"{day} {start} ~ {end}"))

    # 중복 제거 + 요일순 정렬
    unique = list(dict.fromkeys(results))
    unique.sort(key=lambda x: x[0])

    # 정렬된 문자열로 반환
    return "\n".join([item[1] for item in unique])

def extract_open_hours(driver):
    """ 카카오맵 카페 상세페이지에서 운영시간 텍스트를 추출하는 함수 """
    try:
        # 접혀있을 경우, '더보기' 버튼 클릭
        btns = driver.find_elements(By.CSS_SELECTOR, 'button[aria-controls="foldDetail2"], button.btn_fold2')
        if btns:
            try:
                btns[0].click()
            except:
                driver.execute_script("arguments[0].click();", btns[0])  # 자바스크립트로 클릭 시도
                time.sleep(0.5) # 클릭 후 잠시 대기
                
        selectors = [
            "#foldDetail2 .info_operation",
            "#foldDetail2 .detail_info",
            ".location_present",
            ".txt_operation"
        ]
        
        texts = []
        for sel in selectors:
            elems = driver.find_elements(By.CSS_SELECTOR, sel)
            for e in elems:
                txt = e.get_attribute("textContent") or e.text
                if txt and len(txt.strip()) > 4: # 너무 짧은 텍스트는 제외
                    texts.append(txt.strip())
            
            if texts:
                break  # 유효한 텍스트를 찾았으면 더 이상 탐색하지 않음
            
        if not texts:
            return None
            
        # 여러 줄 정리
        raw = sorted(texts, key=len, reverse=True)[0]  # 가장 긴 텍스트 선택
        raw = raw.replace("영업정보 전체보기", "").strip()
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        return "\n".join(lines)
    
    except Exception as e:
        print("extract_open_hours() 오류:", e)
        return None

# 3-2. 가져온 카페들 하나씩 반복문 돌려, 각 URL에서 운영시간 가져오기
for cafe_id, kakao_url, name in cafes:
    try:
        driver.get(kakao_url)   # 3-3. 크롬으로 실제 페이지 열기
        time.sleep(random.uniform(2, 4))  # 사람이 클릭하는 것처럼 잠깐 대기 (랜덤 2~4초)
        
        # 3-4. 새로운 함수 호출
        open_hours = extract_open_hours(driver) or "정보없음"
        open_hours = clean_open_hours(open_hours)
        open_hours = extract_weekly_schedule(open_hours)  # ✅ 요일+시간 형태로 정제
        
        # 3-5. DB 업데이트
        with engine.begin() as conn:    # 트랜잭션 단위로 DB 연결 시작 (자동 commit/rollback)
            conn.execute(
                text("UPDATE cafes SET open_hours = :open_hours WHERE cafe_id = :cafe_id"),   # 파라미터 바인딩 방식으로 SQL Injection 방지
                {"open_hours": open_hours, "cafe_id": cafe_id},  # cafe_id별로 3-5에서 추출한 open_hours 텍스트값으로 컬럼 업데이트
            )
            
        print(f"✅ [{name}] ({cafe_id}) -> {open_hours}")    # 콘솔에 성공 로그 출력

    # 3-7.예외처리 + 로그 저장 (운영시간 없는 경우 "정보없음" 처리)
    except Exception as e:
        print(f"❌ {cafe_id} 오류: {e}")
        continue    # 크롤링 중 에러가 나도 전체 코드 멈추지 않고 다음 카페로 넘어감

driver.quit() # 브라우저 종료 (작업이 끝나면 Chrome 프로세스를 안전하게 닫음)