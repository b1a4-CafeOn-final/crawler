import requests
import os
import time
from dotenv import load_dotenv
from crawler.db import insert_cafe

load_dotenv()
KAKAO_KEY = os.getenv("KAKAO_REST_API_KEY")
headers = {"Authorization": f"KakaoAK {KAKAO_KEY}"}

# 카페 검색 함수 (카카오맵 API)
def search_cafes(x, y, radius=1000):
    url = "https://dapi.kakao.com/v2/local/search/category.json"
    params = {
        "category_group_code": "CE7",  # 카페
        "x": x,
        "y": y,
        "radius": radius,
        "size": 15,
        "page": 1
    }
    results = []
    for page in range(1, 46):  # API 최대 45페이지
        params["page"] = page
        try:
            res = requests.get(url, headers=headers, params=params, timeout=5)
            res.raise_for_status()  # HTTP 오류 발생 시 예외 발생
            docs = res.json().get("documents", [])
            if not docs:
                break
            results.extend(docs)
            time.sleep(0.2)  # 200ms 대기 - 과도한 요청 방지
        except requests.exceptions.RequestException as e:
            print(f"⚠️ 요청 실패 (page={page}): {e}")
            continue
    return results


# 강남구 대략 범위 (bounding box)
xmin, xmax = 127.02, 127.10   # 경도 범위
ymin, ymax = 37.45, 37.55     # 위도 범위

# 격자 간격 (0.005도 ≈ 약 500m)
step = 0.005

coords = []
x = xmin
while x <= xmax:
    y = ymin
    while y <= ymax:
        coords.append((x, y))
        y += step
    x += step

print(f"📍 강남구 전체 크롤링 시작 (총 {len(coords)}개 좌표)")

# === 여기서부터 시작할 좌표 지정 (마지막 터미널 오류 좌표부터) ===
START_INDEX = 113   # <- 중간부터 이어서 실행 (1-based index)

# 좌표별 크롤링
for idx, (x, y) in enumerate(coords[START_INDEX-1:], start=START_INDEX):
    print(f"\n=== 좌표 {idx}/{len(coords)} (x={x}, y={y}) ===")
    cafes = search_cafes(x, y, 1000)

    for c in cafes:
        address = c.get("road_address_name") or c.get("address_name")
        if not address or "강남구" not in address:  # 강남구만 저장
            continue

        data = {
            "kakao_id": c.get("id"),
            "name": c.get("place_name"),
            "address": address,
            "latitude": float(c.get("y")),
            "longitude": float(c.get("x")),
            "phone": c.get("phone"),
            "open_hours": None,
            "avg_rating": None,
            "kakao_url": c.get("place_url"),
            "source": "KAKAO"
        }

        # 콘솔 출력
        print(f"[{data['name']}] {data['address']} ({data['latitude']}, {data['longitude']})")

        try:
            # DB 저장
            insert_cafe(data)
        except Exception as e:
            print(f"⚠️ DB 저장 실패: {e}")
            continue

print("\n✅ 강남구 카페 수집 완료 & DB 저장 완료")