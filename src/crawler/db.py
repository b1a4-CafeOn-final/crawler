# DB 연결, insert/select 함수
# - create_engine : SQLAlchemy에서 DB 연결 객체를 만드는 함수
# - text : SQL문을 문자열 그대로 작성할 때 사용하는 래퍼(안전하게 파라미터 바인딩 가능)
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PW = os.getenv("DB_PW")

DB_URL = f"mysql+pymysql://{DB_USER}:{DB_PW}@localhost:3306/cafeOn"  # mysql+pymysql : MySQL을 PyMySQL드라이버로 연결
engine = create_engine(DB_URL, echo=True, future=True)
# ㄴecho=True : SQLAlchemy가 실행하는 SQL쿼리를 콘솔에 찍어줌 (디버깅 편함)
# ㄴfuture=True : 최신 SQLAlchemy API 스타일 사용

def insert_cafe(data):  # data : 딕셔너리 형태로 넘겨줄 예정(예: {"kakao_id: "123", "name": "스타벅스", ...})
  with engine.begin() as conn:  # => 이 안에서 SQL을 실행하면 자동으로 안전하게 커밋됨
    # conn(SQL실행할 연결 객체) / engine.begin()(DB트랜잭션을 시작) / with구문(블록이 끝나면 자동으로 commit/rollback 처리)
    sql = text("""
               INSERT INTO cafes (kakao_id, name, address, latitude, longitude, phone, open_hours, avg_rating, kakao_url, source)
               VALUES (:kakao_id, :name, :address, :latitude, :longitude, :phone, :open_hours, :avg_rating, :kakao_url, :source)
               ON DUPLICATE KEY UPDATE
                name=:name,
                address=:address,
                latitude=:latitude,
                longitude=:longitude,
                phone=:phone,
                open_hours=:open_hours,
                avg_rating=:avg_rating,
                kakao_url=:kakao_url,
                source=:source
    """)
    # :kakao_id, :name 등은 자리표시자(placeholder) = data 딕셔너리의 key랑 매칭됨
    # ON DUPLICATE KEY UPDATE: 테이블의 UNIQUE KEY(kakao_id)가 이미 DB에 있으면 새 값으로 갱신 -> 즉, 중복 방지 + 최신화 기능
    conn.execute(sql, data) # 두번째 인자 data를 넘겨주면, SQL문 안의 :kakao_id, :name 같은 placeholder에 값이 채워짐