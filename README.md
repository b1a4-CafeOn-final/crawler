# crawler
카카오맵 REST API 크롤링으로 카페 데이터 수집

### 카테고리
대형마트, 편의점, 어린이집/유치원, 학교, 학원, 주차장, 주유소,충전소, 지하철역, 은행, 문화시설, 중개업소, 공공기관, 관광명소, 숙박, 음식점, 카페, 병원, 약국

## 키워드로 장소 검색
`질의어`에 매칭된 장소검색결과를 지정된 정렬기준에 따라 제공
`GET https://dapi.kakao.com/v2/local/search/keyword.${FORMAT}`
##### 요청) 쿼리 파라미터
- **query(String) : 검색을 원하는 질의어 (필수)**
- x(String) : 중심 좌표의 X 또는 경도(longitude) 값. 특정 지역을 중심으로 검색할 경우 radius와 함께 사용 가능
- y(String) : 중심 좌표의 Y 혹은 위도(latitude) 값. 특정 지역을 중심으로 검색할 경우 radius와 함께 사용 가능
  - radius(Integer) : 중심 좌표부터의 반경거리. 특정 지역을 중심으로 검색하려고 할 경우 중심좌표로 쓰일 x,y와 함께 사용
(단위: 미터(m), 최소: 0, 최대: 20000)
- page(Integer) : 결과 페이지 번호 (최소: 1, 최대: 45, 기본값: 1)
- size(Integer) : 한 페이지에 보여질 문서의 개수 (최소: 1, 최대: 15, 기본값: 15)
- sort(String) : 결과 정렬 순서
  - distance 정렬을 원할 때는 기준 좌표로 쓰일 x, y와 함께 사용
  - distance 또는 accuracy(기본값: accuracy)
###### 키워드로 검색 요청 예제
서울 강남구 삼성동 20km 반경에서 카카오프렌즈 매장 검색
```
curl -v -G get "https://dapi.kakao.com/v2/local/search/keyword.json? \
  y=37.514322572335935 \
  &x=127.06283102249932 \
  &radius=20000" \
  -H "Authorization: KakaoAK ${REST_API_KEY} \
  --date-urlencode "query=카카오프렌즈"
```
##### 응답) 본문-documents(Document[])
- place_name(String) : 장소명, 업체명
- category_name(String) : 카테고리 이름
- category_group_name(String) : 중요 카테고리만 그룹핑한 카테고리 그룹명
- phone(String) : 전화번호 (XXX-XXX-XXXX 형식)
- address_name(String) : 전체 지번 주소
- road_address_name(String) : 전체 도로명 주소
- x(String) : X 좌표값, longitude(경도)
- y(String) : Y 좌표값, latitude(위도)
- place_url(String) : 장소 상세페이지 URL
- distance(String) : 중심좌표까지의 거리(단 x,y 파라미터를 준 경우에만 존재)
  - 단위 meter
###### 키워드로 검색 응답 예제
```
HTTP/1.1 200 OK
Content-Type: application/json;charset=UTF-8
{
  "meta": {
    "same_name": {
      "region": [],
      "keyword": "카카오프렌즈",
      "selected_region": ""
    },
    "pageable_count": 14,
    "total_count": 14,
    "is_end": true
  },
  "documents": [
    {
      "place_name": "카카오프렌즈 코엑스점",
      "distance": "418",
      "place_url": "http://place.map.kakao.com/26338954",
      "category_name": "가정,생활 > 문구,사무용품 > 디자인문구 > 카카오프렌즈",
      "address_name": "서울 강남구 삼성동 159",
      "road_address_name": "서울 강남구 영동대로 513",
      "id": "26338954",
      "phone": "02-6002-1880",
      "category_group_code": "",
      "category_group_name": "",
      "x": "127.05902969025047",
      "y": "37.51207412593136"
    },
    ...
  ]
}
```


## 카테고리로 장소 검색
미리 정의된 `카테고리코드`에 해당하는 장소검색결과를 지정된 정렬 기준에 따라 제공
`GET https://dapi.kakao.com/v2/local/search/category.${FORMAT}`
##### 카테고리그룹코드
- CE7(카페)
- FD6(음식점)
- AT4(관광명소)
- MT1(대형마트)
- CT1(문화시설)

##### 요청) 쿼리 파라미터
- **category_group_code(CategoryGroupCode) : 카테고리 코드(필수)**
- x(String) : 중심 좌표의 X값 혹은 longitude. 특정 지역을 중심으로 검색하려고 할 경우 radius와 함께 사용 가능.
  - (x,y,radius) or rect 필수
- y(String) : 중심 좌표의 Y값 혹은 latitude. 특정 지역을 중심으로 검색하려고 할 경우 radius와 함께 사용 가능.
  - (x,y,radius) or rect 필수
  - radius(Integer) : 중심 좌표부터의 반경거리. 특정 지역을 중심으로 검색하려고 할 경우 중심좌표로 쓰일 x,y와 함께 사용
    - 단위 meter, 0~20000 사이의 값
  - rect(String) : 사각형 범위내에서 제한 검색을 위한 좌표
지도 화면 내 검색시 등 제한 검색에서 사용 가능.
    - 좌측 X 좌표, 좌측 Y 좌표, 우측 X 좌표, 우측 Y 좌표 형식
    - x, y, radius 또는 rect 필수
- page(Integer) : 결과 페이지 번호. 1~45 사이의 값 (기본값: 1)
- size(Integer) : 	한 페이지에 보여질 문서의 개수. 1~15 사이의 값 (기본값: 15)
- sort(String) : 결과 정렬 순서, distance 정렬을 원할 때는 기준좌표로 쓰일 x, y 파라미터 필요
  - distance 또는 accuracy (기본값: accuracy)
###### 카테고리로 검색 응답 예제
서울 강남구 삼성동 20km 반경에서 약국 검색
```
curl -v -G GET "https://dapi.kakao.com/v2/local/search/category.json? \
  category\_group\_code=PM9 \
  &radius=20000" \
  -H "Authorization: KakaoAK ${REST_API_KEY}"
```

##### 응답) 본문-documents(Document[])
- place_name(String) : 장소명, 업체명
- category_name(String) : 카테고리 이름
- category_group_name(String) : 중요 카테고리만 그룹핑한 카테고리 그룹명
- phone(String) : 전화번호 (XXX-XXX-XXXX 형식)
- address_name(String) : 전체 지번 주소
- road_address_name(String) : 전체 도로명 주소
- x(String) : X 좌표값, longitude(경도)
- y(String) : Y 좌표값, latitude(위도)
- place_url(String) : 장소 상세페이지 URL
- distance(String) : 중심좌표까지의 거리(단 x,y 파라미터를 준 경우에만 존재)
  - 단위 meter

###### 카테고리로 검색 응답 예제
```
HTTP/1.1 200 OK
Content-Type: application/json;charset=UTF-8
{
  "meta": {
    "same_name": null,
    "pageable_count": 11,
    "total_count": 11,
    "is_end": true
  },
  "documents": [
    {
      "place_name": "장생당약국",
      "distance": "",
      "place_url": "http://place.map.kakao.com/16618597",
      "category_name": "의료,건강 > 약국",
      "address_name": "서울 강남구 대치동 943-16",
      "road_address_name": "서울 강남구 테헤란로84길 17",
      "id": "16618597",
      "phone": "02-558-5476",
      "category_group_code": "PM9",
      "category_group_name": "약국",
      "x": "127.05897078335246",
      "y": "37.506051888130386"
    },
    ...
  ]
}
```

### REST API 레퍼런스 (공식문서)
> https://developers.kakao.com/docs/latest/ko/rest-api/reference