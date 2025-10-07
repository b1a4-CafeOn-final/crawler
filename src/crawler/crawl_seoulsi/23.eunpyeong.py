import requests
import os
import time
from dotenv import load_dotenv
from crawler.db import insert_cafe

# 🌐 환경변수 불러오기
load_dotenv()
KAKAO_KEY = os.getenv("KAKAO_REST_API_KEY")
headers = {"Authorization": f"KakaoAK {KAKAO_KEY}"}

# 🧭 카페 검색 함수 (자동 재시도 + timeout + SSL 대응)
def search_cafes(x, y, radius=1000, max_retries=3):
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
    for page in range(1, 46):  # 카카오 API 최대 45페이지
        params["page"] = page
        attempt = 0
        while attempt < max_retries:
            try:
                res = requests.get(url, headers=headers, params=params, timeout=5)
                res.raise_for_status()
                docs = res.json().get("documents", [])
                if not docs:
                    break
                results.extend(docs)
                time.sleep(0.25)  # 요청 간 간격 (rate limit 방지)
                break

            except (requests.exceptions.SSLError,
                    requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout) as e:
                attempt += 1
                print(f"⚠️ 네트워크 오류 (page={page}, 재시도 {attempt}/{max_retries}): {e}")
                time.sleep(1.5)
                if attempt == max_retries:
                    print(f"❌ 최대 재시도 초과 → page {page} 스킵")
            except requests.exceptions.RequestException as e:
                print(f"⚠️ 기타 요청 오류 (page={page}): {e}")
                break
    return results


# 🗺️ 은평구 대략 범위 (불광·연신내·응암·구파발·수색 포함)
xmin, xmax = 126.90, 126.96   # 경도 (longitude)
ymin, ymax = 37.57, 37.64     # 위도 (latitude)
step = 0.005  # 약 500m 간격

coords = []
x = xmin
while x <= xmax:
    y = ymin
    while y <= ymax:
        coords.append((x, y))
        y += step
    x += step

print(f"📍 은평구 전체 크롤링 시작 (총 {len(coords)}개 좌표)")

# === 재시작 인덱스 설정 ===
START_INDEX = 1  # 처음부터 실행 시 1 / 중단 후 재시작 시 변경

# 좌표별 크롤링
for idx, (x, y) in enumerate(coords[START_INDEX-1:], start=START_INDEX):
    print(f"\n=== 좌표 {idx}/{len(coords)} (x={x}, y={y}) ===")
    cafes = search_cafes(x, y, 1000)

    if not cafes:
        print("⚠️ 결과 없음 or 요청 실패 → 다음 좌표로 이동")
        continue

    for c in cafes:
        address = c.get("road_address_name") or c.get("address_name")
        if not address or "은평구" not in address:
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

print("\n✅ 은평구 카페 수집 완료 & DB 저장 완료")