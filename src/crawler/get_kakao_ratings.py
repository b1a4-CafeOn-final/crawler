# Python으로 kakao_rating 자동 수집 후 -> 주기적 업데이트를 위해 cron 또는 배치 작업 등록 (예: 주 1회)
from dotenv import load_dotenv
# from bs4 import BeautifulSoup # HTML 파서를 가져옴. 응답으로 받은 웹페이지 소스에서 원하는 태그를 쉽게 찾게 해줘요(HTML parser)
import requests, pymysql, os, time, random  # requests(HTTP요청 보냄), pymysql(MySQL 연결), os(환경변수 읽기), time(대기), random(랜덤 딜레이 만들 때 사용)
from tqdm import tqdm # 진행률 표시바를 콘솔에 예쁘게 보여줌. 대량 작업할 때 진행 상황을 눈으로 확인 가능 (progress bar)
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# .env 로드
load_dotenv(".env.local") # .env.local 파일을 읽어 환경변수를 메모리에 올림

# DB 연결
conn = pymysql.connect(
  host=os.getenv("DB_URL"),
  user=os.getenv("DB_USER"),
  password=os.getenv("DB_PW"),
  db='cafeOn',
  charset='utf8mb4'
)
cursor = conn.cursor()  # SQL 실행용 커서를 만듬. 이 커서로 SELECT/UPDATE 등을 날림 (DB cursor)

# Selenium 헤드리스 세팅
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--lang=ko-KR")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

cursor.execute("SELECT cafe_id, name, kakao_url FROM cafes WHERE kakao_url IS NOT NULL")
cafes = cursor.fetchall() # kakao_url이 있는 카페들의 (id, name, url)을 전부 가져와 리스트로 받음. (fetch all rows)

# 메인 루프
for cafe_id, name, url in tqdm(cafes, desc="카카오별점 수집 중"): # 각 카페를 돌면서 처리 (tqdm이 진행률 표시를 붙여줌) (iterate with pregress bar)
  try:
    driver.get(url) # 각 카페 URL을 실제 브라우저로 열고,
    time.sleep(random.uniform(1.5, 2.5))  # JS 렌더링 시간을 랜덤(1.5~2.5s)으로 대기 -> 과도한 요청을 피하고, DOM 생성될 시간을 줌

    # 별점 요소 찾기 (렌더링 완료될 때까지 최대 8초 기다림)
    try:
      wait = WebDriverWait(driver, 8) # 최대 8초 대기
      elem = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "span.starred_grade span.num_star"))) # CSS셀렉터로 별점 숫자 들어있는 노드를 찾음
    except:
      elem = None # 못찾으면 None(페이지 구조가 달라졌거나 별점이 없을 때 대비)

    """
    res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})  # 카카오맵 상세페이지로 HTTP GET 요청을 보냄. User-Agent를 브라우저처럼 설정해 봇 차단을 피하고 정상 HTML을 받기 위함 (send HTTP request with browser UA)
    if res.status_code != 200:  # 응답코드가 200(정상)이 아니면 이 카페는 건너뜀 (skip on non-200)
      continue

    soup = BeautifulSoup(res.text, "html.parser") # 응답의 HTML 텍스트를 파싱해 soup 객체 생성. 이후 CSS선택자로 태그를 찾음 (parse HTML)
    rating_elem = soup.select_one("span.starred_grade span.num_star") or soup.select_one("em.num_rate")  # 평점 숫자가 들어있는 태그를 CSS선택자로 하나 선택. (select rating element)
    """

    # 별점 값 파싱 -> float
    rating = None # 평점 기본값을 없음(None)으로 시작 (init default)
    if elem: # 평점 태그가 있으면
      txt = elem.text.strip() # elem에서 텍스트 추출
      if txt:
        rating = float(txt) # float 변환으로 별점을 파싱

    # DB 업데이트 + 커밋
    cursor.execute(
      "UPDATE cafes SET kakao_rating=%s WHERE cafe_id=%s",  # 파라미터바인딩(%s)을 사용해 SQL 인젝션 예방 (parameterized UPDATED)
      (rating, cafe_id) # 방금 얻은 (kakao_)rating을 해당 카페 행에 업데이트
    )
    conn.commit() # 트랜잭션을 커밋해서 실제 DB에 반영 (commit transaction)

    print(f"✅ [{name}] ({cafe_id}): 카카오맵 후기 {rating}점")
    time.sleep(random.uniform(0.8, 1.3)) # 필수!! 0.8~1.3초 랜덤 대기로 요청 간격을 띄움. 과도한 연속 요청으로 차단 방지(anti-ban) (throttle requests)

  except Exception as e:  # 위 블록에서 어떤 오류가 나도
    print(f"❌ {url}: {e}") # 에러 출력만 하고,
    time.sleep(2) # 필수!! 2초 쉬었다가 다음 카페로 넘어감. 전체 작업이 끊기지 않게 하는 내결함성(fault tolerance) (error handling + backoff)

driver.quit()
conn.close()  # 모든 작업이 끝난 후 DB연결을 정리. 리소스 누수를 막음 (close DB connection)
