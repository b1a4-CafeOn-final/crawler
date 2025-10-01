# 1. 필요한 라이브러리 불러오기
import os                       # 운영체제 관련 기능 (환경변수 불러오기 등)
import requests                 # 웹 요청 라이브러리
from dotenv import load_dotenv  # .env 파일을 읽어주는 라이브러리

# 2. .env 파일에서 환경변수 로드
load_dotenv() # 실행하면 현재 폴더의 .env 내용을 불러옴

# 3. 카카오 API 키 불러오기
KAKAO_KEY =  os.getenv("KAKAO_REST_API_KEY")
print(".env에서 불러온 KAKAO_REST_API_KEY: ", KAKAO_KEY)
if not KAKAO_KEY:
  raise SystemExit("❌ KAKAO_REST_API_KEY 가 .env에 없습니다.")

# API 요청 준비
keywordUrl = "https://dapi.kakao.com/v2/local/search/keyword.json"
categoryUrl = "https://dapi.kakao.com/v2/local/search/category.json"
headers = {"Authorization": f"KakaoAK {KAKAO_KEY}"}

# DB(cafes) - 카페이름(name), 카페주소(address), 위도(String), 경도(String), phone(String), 오픈시간(open_hours), 평균별점(avg_rating), 생성일시(TIMESTAMP)
""" 5. 테스트: '시흥5동 카페' 검색하기
요청) 쿼리 파라미터
- query(String) : 검색을 원하는 질의어 (필수)
- analyze_type(String) : 검색 결과 제공 방식, 아래 중 하나 (기본값: similar)
  ㄴsimilar: 입력한 건물명과 일부만 매칭될 경우에도 확장된 검색 결과 제공, 미지정 시 similar가 적용됨
  ㄴexact: 주소의 정확한 건물명이 입력된 주소패턴일 경우에 한해, 입력한 건물명과 정확히 일치하는 검색 결과 제공
- page(Integer) : 결과 페이지 번호 (최소:1, 최대:45, 기본값:1)
- size(Integer) : 한 페이지에 보여질 문서의 개수 (최소:1, 최대:30, 기본값:10)"""
params = {
  "query": "카페",
  "x": 126.91023773649, # 금천구 우리집 경위도로 설정함
  "y": 37.4519704409382,
  # "radius": 1000,       # 반경: 1000m(1km)
  "page": 45,
  "size": 15,
  "sort": "distance"
}

""" # 6. 응답 확인
응답) 본문
- meta(Meta) : 응답 관련 정보
    ㄴtotal_count(Integer) : 검색어에 검색된 문서 수
    ㄴpageable_count(Integer) : total_count 중 노출 가능 문서 수
    ㄴis_end(Boolean) : 현재 페이지가 마지막 페이지인지 여부. 값이 false면 다음 요청 시 page값을 증가시켜 다음 페이지 요청 가능
- documents(Document []) : 응답 결과
    ㄴplace_name(String) : 장소명, 업체명
    ㄴcategory_name(String) : 카테고리 이름
    ㄴcategory_group_name(String) : 중요 카테고리만 그룹핑한 카테고리 그룹명
    ㄴphone(String) : 전화번호 (XXX-XXXX-XXXX 형태)
    ㄴaddress_name(String) : 전체 지번 주소 or 전체 도로명 주소, 입력에 따라 결정됨
    ㄴaddress_type(String) : address_name의 값이 타입(Type), 아래 중 하나
                            ㄴREGION(지명) / ROAD(도로명) / REGION_ADDR(지번 주소) / ROAD_ADDR(도로명 주소)
    ㄴx(String) : X 좌표값, 경위도인 경우 경도(longitude)
    ㄴy(String) : Y 좌표값, 경위도인 경우 위도(latitude)
    ㄴaddress(Address) : 지번 주소 상세 정보
    ㄴroad_address(RoadAddress) : 도로명 주소 상세 정보
    ㄴplace_url(String) : 장소 상세페이지 URL
    ㄴdistance(String) : 중심좌표까지의 거리(단 x,y 파라미터를 준 경우에만 존재) / 단위 meter"""
    
# 페이지 반복 호출
page = 1
all_results = []

while True:
  params["page"] = page
  response = requests.get(keywordUrl, headers=headers, params=params)
  
  if response.status_code != 200:
    print("❌ 요청 실패:", response.status_code, response.text)
    break
    
  print("✅ 카페 검색 성공!")
  data = response.json()
  docs = data.get("documents", [])
  
  # 데이터 누적
  for doc in docs:
    name = doc.get("place_name")
    addr = doc.get("road_address_name") or doc.get("address_name")
    phone = doc.get("phone")
    distance = doc.get("distance")
    all_results.append((name, addr, phone, distance))
    print(f"[{page}] {name} | {addr} | {phone} | 거리: {distance}m")
    
  # 마지막 페이지 여부 확인
  if data["meta"].get("is_end"):
    print("✅ 모든 페이지 조회 완료")
    break
  
  page +=1
  
print(f"\n총 {len(all_results)}개 카페 수집 완료!")