import requests
import os
from dotenv import load_dotenv
from crawler.db import insert_cafe

# 환경변수 불러오기
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
        res = requests.get(url, headers=headers, params=params).json()
        docs = res.get("documents", [])
        if not docs:
            break
        results.extend(docs)
    return results


# 🗺️ 송파구 대략 범위 (bounding box)
# (북쪽: 잠실·석촌호수 / 남쪽: 위례신도시 / 서쪽: 강남구 경계 / 동쪽: 강동구 경계)
xmin, xmax = 127.09, 127.17   # 경도 (longitude)
ymin, ymax = 37.48, 37.55     # 위도 (latitude)

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

print(f"📍 송파구 전체 크롤링 시작 (총 {len(coords)}개 좌표)")

# 좌표별 크롤링
for idx, (x, y) in enumerate(coords, start=1):
    print(f"\n=== 좌표 {idx}/{len(coords)} (x={x}, y={y}) ===")
    cafes = search_cafes(x, y, 1000)

    for c in cafes:
        address = c.get("road_address_name") or c.get("address_name")
        if not address or "송파구" not in address:  # 송파구만 저장
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

        print(f"[{data['name']}] {data['address']} ({data['latitude']}, {data['longitude']})")
        insert_cafe(data)

print("\n✅ 송파구 카페 수집 완료 & DB 저장 완료")