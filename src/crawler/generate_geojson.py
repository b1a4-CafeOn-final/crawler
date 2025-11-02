import requests
import json
import os
from dotenv import load_dotenv
load_dotenv(".env.local")

# V-World API key
VWORLD_KEY = os.getenv("VWORLD_API_KEY")
print("VWORLD_KEY =", VWORLD_KEY);
if not VWORLD_KEY:
  raise RuntimeError("❌ VWORLD_API_KEY가 .env에 없습니다.")

# 서울시 25개 구
districts = [
   "강남구","강동구","강북구","강서구","관악구","광진구","구로구","금천구","노원구","도봉구",
    "동대문구","동작구","마포구","서대문구","서초구","성동구","성북구","송파구","양천구","영등포구",
    "용산구","은평구","종로구","중구","중랑구"
]

def get_district_geojson(district_name):
  """V-World API로 구 경계 geometry 가져오기"""
  url = "http://api.vworld.kr/req/data"
  params = {
    "key": VWORLD_KEY,
    "service": "data",
    "request": "GetFeature",
    "data": "LT_C_ADSIGG",  # 시군구 행정구역 레이어
    "attrFilter": f"sig_kor_nm:{district_name}",
    # "size": 1,
    # "page": 1,
    # "query": f"서울특별시 {district_name}",
    # "type": "district", # 행정구 단위
    "format": "geojson"
  }

  res = requests.get(url, params=params).json()

  try:
    # item = res["response"]["result"]["items"][0]
    # geom = item["geometry"] # 경계 geometry
    feature = res["features"][0]
    feature["properties"]["name"] = district_name
    return feature
    return {
      "type": "Feature",
      "properties": {"name": district_name},
      "geometry": geom
    }
  except Exception as e:
    print(f"❌ {district_name} 불러오기 실패: {e}, 응답: {res}")
    return None

def main():
  features = []
  for gu in districts:
    print(f"📍 {gu} 불러오는 중...")
    feature = get_district_geojson(gu)

    if feature:
      features.append(feature)

  geojson = {
    "type": "FeatureCollection",
    "features": features
  }

  with open("seoul_districts.geojson", "w", encoding="utf-8") as f:
    json.dump(geojson, f, ensure_ascii=False, indent=2)

  print("✅ seoul_districts.geojson 파일 생성 완료!")

if __name__ == "__main__":
  main()
