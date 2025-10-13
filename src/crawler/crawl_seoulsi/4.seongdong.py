import requests
import os
import time
from dotenv import load_dotenv
from crawler.insert_cafes import insert_cafe

# 환경변수 불러오기
load_dotenv()
KAKAO_KEY = os.getenv("KAKAO_REST_API_KEY")
headers = {"Authorization": f"KakaoAK {KAKAO_KEY}"}

# 🧭 카페 검색 함수
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
            res.raise_for_status()
            docs = res.json().get("documents", [])
            if not docs:
                break
            results.extend(docs)
            time.sleep(0.2)  # rate limit 방지
        except requests.exceptions.SSLError as e:
            print(f"⚠️ SSL 오류 (page={page}): {e}")
            continue
        except requests.exceptions.Timeout:
            print(f"⚠️ Timeout (page={page}) - 넘어감")
            continue
        except requests.exceptions.RequestException as e:
            print(f"⚠️ 기타 요청 오류 (page={page}): {e}")
            continue

    return results


# 🗺️ 성동구 범위 (서울시 기준 대략)
xmin, xmax = 127.02, 127.07
ymin, ymax = 37.54, 37.57
step = 0.005

coords = []
x = xmin
while x <= xmax:
    y = ymin
    while y <= ymax:
        coords.append((x, y))
        y += step
    x += step

print(f"📍 성동구 전체 크롤링 시작 (총 {len(coords)}개 좌표)")

# === 재시작 인덱스 설정 ===
START_INDEX = 5  # ← 여기만 바꾸면 중간부터 이어서 실행 가능

# 좌표별 크롤링
for idx, (x, y) in enumerate(coords[START_INDEX-1:], start=START_INDEX):
    print(f"\n=== 좌표 {idx}/{len(coords)} (x={x}, y={y}) ===")
    cafes = search_cafes(x, y, 1000)

    for c in cafes:
        address = c.get("road_address_name") or c.get("address_name")
        if not address or "성동구" not in address:
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

        try:
            insert_cafe(data)
        except Exception as e:
            print(f"❌ DB 저장 오류: {e}")
            continue

print("\n✅ 성동구 카페 수집 완료 & DB 저장 완료")