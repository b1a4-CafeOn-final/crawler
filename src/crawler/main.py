# 1. 필요한 라이브러리 불러오기
import os                       # 운영체제 관련 기능 (환경변수 불러오기 등)
import requests                 # 웹 요청 라이브러리
from dotenv import load_dotenv  # .env 파일을 읽어주는 라이브러리

# 2. .env 파일에서 환경변수 로드
load_dotenv() # 실행하면 현재 폴더의 .env 내용을 불러옴

# 3. 카카오 API 키 불러오기
KAKAO_KEY =  os.getenv("KAKAO_REST_API_KEY")
if not KAKAO_KEY:
  raise SystemExit("❌ KAKAO_REST_API_KEY 가 .env에 없습니다.")

# API 요청 준비
url = "https://dapi.kakao.com/v2/local/search/keyword.json"
headers = {"Authorization": f"KakaoAK {KAKAO_KEY}"}

# 5. 테스트: '강남역 카페' 검색하기
params = {"query": "강남역 카페"}
response = requests.get(url, headers=headers, params=params)

# 6. 응답 확인
if response.status_code == 200:
  data = response.json()
  print("✅ 카페 검색 성공!")
  for doc in data["documents"]:
    print(doc["place_name"], doc["road_address_name"], doc["phone"])
else:
  print("❌ 요청 실패:", response.status_code, response.text)