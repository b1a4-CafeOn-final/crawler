# get_reviewsSummary_missing_only.py
# ------------------------------------------------------------
# ✅ reviewsSummary가 NULL인 카페만 다시 요약
# ✅ 진행률(%) + ETA(예상 완료 시간)
# ✅ 네이버 Local로 상호/주소 정규화 → 블로그 다단계 쿼리
# ✅ 블로그 없으면 중립 요약으로 폴백(재시도 악순환 방지)
# ✅ MySQL 끊김 자동복구 / OpenRouter 무료 모델 사용
# ------------------------------------------------------------

from dotenv import load_dotenv
import requests, pymysql, time, os, json, sys, html, re
from datetime import timedelta

# ① 환경변수
load_dotenv()
client_id = os.getenv("NAVER_API_CLIENT_ID")
client_secret = os.getenv("NAVER_API_SECRET_KEY")
openrouter_key = os.getenv("OPENROUTER_API_KEY")    # OpenRouter API 키의 크레딧이 모두 소진되었거나, 다른 계정/조직 키를 잘못 사용 중 에러

DB_CONFIG = {
    "host": os.getenv("DB_URL"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PW"),
    "database": "cafeOn",
    "charset": "utf8mb4",
    "autocommit": False
}

# ② DB 연결
def get_connection():
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        return conn, cursor
    except Exception as e:
        print(f"❌ DB 연결 실패: {e}")
        sys.exit(1)

conn, cursor = get_connection()

# ③ 요약 (OpenRouter 크레딧소진 ->무료 HuggingFace API 사용)
# + OpenRouter + HuggingFace fallback, 자동 전환
# ③ 요약 (OpenRouter 선시도 → HuggingFace 다중 모델 순환, 503 로딩 대기 포함)
def summarize_text(text: str) -> str:
    import time
    import math

    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    HF_API_KEY = os.getenv("HUGGINGFACE_TOKEN")

    OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

    # 무료/무승인으로 잘 돌아가는 서버리스 후보들을 우선순위대로 나열
    HF_MODELS = [
    "upstage/solar-1-mini-chat",     # ✅ 가장 자연스럽고 빠름 (추천 1순위)
    "upstage/solar-1-mini",          # ✅ fallback: mini-chat이 과부하일 때
    "upstage/solar-1-7b",            # ✅ 품질 좋지만 약간 느림
    ]

    # 원래 프롬프트 유지
    base_prompt = (
        "너는 한국어 카페 리뷰를 자연스럽고 부드럽게 요약하는 한국어 전용 요약봇이야. "
        "반드시 한국어로만 대답하고, 영어 문장은 절대 포함하지 마. "
        "출력은 한 문단으로 완전한 문장으로 끝나야 해. "
        "리뷰의 분위기와 핵심만 전달하되, 주소, 전화번호, 영업시간, 이벤트 등 불필요한 정보는 빼고 "
        "방문자가 느낀 전반적인 인상과 분위기, 추천 포인트를 중심으로 자연스럽게 요약해.\n\n"
        f"다음 내용을 한 문단의 자연스러운 한국어 요약으로 작성해줘:\n{text[:2000]}"
    )

    # 1) OpenRouter 먼저 시도 (크레딧 있으면 빠르고 품질 좋음)
    if openrouter_key:
        try:
            headers = {
                "Authorization": f"Bearer {openrouter_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "meta-llama/llama-3-8b-instruct",
                "messages": [{"role": "system", "content": base_prompt}],
                "temperature": 0.4,
                "max_tokens": 400,
                "stop": ["\n\n", "요약:"]
            }
            r = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=60)
            if r.status_code == 402:
                raise Exception("OpenRouter 크레딧 만료 (402)")
            r.raise_for_status()
            data = r.json()
            if data.get("choices"):
                out = data["choices"][0]["message"]["content"].strip()
                if not out.endswith(("다.", "요.", "음.")):
                    out += "입니다."
                return out
        except Exception as e:
            print(f"⚠️ OpenRouter 실패 → HuggingFace로 전환 ({e})")

    # 2) Hugging Face 서버리스로 폴백 (다중 모델 순환 + 503 로딩 대기)
    if not HF_API_KEY:
        return "요약 실패: HF_API_KEY/HUGGINGFACE_TOKEN 없음 (환경변수 설정 필요)"

    def call_hf_model(model_id: str) -> str:
        url = f"https://router.huggingface.co/hf-inference/{model_id}"
        headers = {"Authorization": f"Bearer {HF_API_KEY}"}
        payload = {
            "inputs": base_prompt,
            "parameters": {
                "max_new_tokens": 350,
                "temperature": 0.4,
                "do_sample": False
            }
        }
        # 503(loading) 대기 & 재시도: 최대 6회, 지수백오프
        for attempt in range(6):
            resp = requests.post(url, headers=headers, json=payload, timeout=120)
            if resp.status_code == 503:
                # 모델 로딩 중 → 대기 후 재시도
                wait = min(5 * (2 ** attempt), 40)
                print(f"⏳ HF {model_id} 로딩중(503) → {wait}s 대기 후 재시도...")
                time.sleep(wait)
                continue
            if resp.status_code in (404, 403):
                # 서버리스 미지원/권한문제 → 다음 모델로
                raise FileNotFoundError(f"HF {model_id} 미지원 또는 접근불가 ({resp.status_code})")
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list) and data and "generated_text" in data[0]:
                return data[0]["generated_text"].strip()
            # 일부 엔진은 문자열이나 다른 키로 반환할 수 있음
            if isinstance(data, dict):
                if "generated_text" in data:
                    return data["generated_text"].strip()
                if "error" in data:
                    raise RuntimeError(f"HF {model_id} 오류: {data['error']}")
            return str(data)

        raise TimeoutError(f"HF {model_id} 로딩 재시도 초과")

    last_err = None
    for mid in HF_MODELS:
        try:
            out = call_hf_model(mid)
            if not out.endswith(("다.", "요.", "음.")):
                out += "입니다."
            return out
        except FileNotFoundError as e:
            # 404/403 → 다음 후보로
            print(f"↪️ {mid} 건너뜀: {e}")
            last_err = e
            continue
        except Exception as e:
            # 기타 오류는 로그만 남기고 다음 후보
            print(f"↪️ {mid} 실패: {e}")
            last_err = e
            continue

    return f"요약 실패: 모든 HF 후보 실패 ({last_err})"





# ④ 유틸: HTML/태그 정리
TAG_RE = re.compile(r"<[^>]+>")
def clean_text(s: str) -> str:
    # 네이버 응답의 <b>강조</b>, &nbsp; 등 제거
    s = html.unescape(s or "")
    s = TAG_RE.sub("", s)
    s = s.replace("\n", " ").replace("\r", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s

# ⑤ 네이버 Local: 상호 정규화
def naver_local_normalize(name: str):
    # 상호를 네이버가 인식하는 정규명/주소로 보정
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    params = {"query": name, "display": 3}
    try:
        r = requests.get("https://openapi.naver.com/v1/search/local.json", headers=headers, params=params, timeout=20)
        if r.status_code == 200:
            items = r.json().get("items", [])
            if items:
                # 최상단 결과 사용
                it = items[0]
                title = clean_text(it.get("title"))
                address = clean_text(it.get("address"))      # 지번
                road_addr = clean_text(it.get("roadAddress")) # 도로명
                return title or name, road_addr or address
    except Exception:
        pass
    return name, None

# ⑥ 네이버 블로그: 다단계 쿼리 전략
def get_blog_snippets(name: str, gu_or_dong: str | None):
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }

    # 쿼리 후보들: 적중률 높은 순으로 시도
    queries = []
    norm_name, norm_addr = naver_local_normalize(name)

    # 행정동/구 추출 보정
    if not gu_or_dong and norm_addr:
        # 예: "서울 강남구 논현로 88" → "강남구"를 힌트로
        m = re.search(r"(?:서울|경기|인천|부산|대구|대전|광주|울산|세종)?\s*([가-힣]+구)\s*([가-힣0-9]+동)?", norm_addr)
        if m:
            gu_or_dong = m.group(1)

    base_names = [norm_name] if norm_name != name else [name, norm_name]
    base_names = list(dict.fromkeys([clean_text(n) for n in base_names if n]))  # 중복 제거

    for bn in base_names:
        if gu_or_dong:
            queries.append(f"{bn} {gu_or_dong} 후기")
        queries.append(f"{bn} 후기")
        queries.append(f"{bn} 리뷰")
        queries.append(f"{bn} 카페 후기")
        queries.append(f"{bn}")  # 마지막 완화

    snippets = []
    for q in queries:
        params = {"query": q, "display": 5, "sort": "sim"}
        try:
            res = requests.get("https://openapi.naver.com/v1/search/blog.json", headers=headers, params=params, timeout=20)
            if res.status_code == 200:
                items = res.json().get("items", [])
                if items:
                    for it in items:
                        desc = clean_text(it.get("description", ""))
                        if desc:
                            snippets.append(desc)
                    # 한 쿼리에서 충분히 모였으면 종료
                    if len(snippets) >= 5:
                        break
            else:
                # API 오류는 다음 후보로 진행
                continue
        except Exception:
            continue

        # 다음 쿼리로 계속 시도
        if len(snippets) >= 3:
            break

    return snippets[:5]

# ⑦ 아직 요약 안 된 카페만
cursor.execute("SELECT cafe_id, name, address FROM cafes WHERE reviewsSummary IS NULL;")
cafes = cursor.fetchall()
total = len(cafes)
print(f"📊 아직 요약되지 않은 카페: {total}개 (NULL only)")

# ⑧ 메인 루프
start_time = time.time()
for idx, (cafe_id, name, address) in enumerate(cafes, start=1):
    try:
        conn.ping(reconnect=True)

        # 구/동 힌트 추출
        gu_hint = None
        if address:
            m = re.search(r"([가-힣]+구)|([가-힣0-9]+동)", address)
            if m:
                gu_hint = m.group(1) or m.group(2)

        snippets = get_blog_snippets(name, gu_hint)

        if not snippets:
            # 🔸 폴백: 리뷰 부족 중립 요약으로 채움(재시도 악순환 방지)
            summary = f"해당 매장에 대한 최근 블로그 리뷰가 매우 적거나 확인되지 않았습니다. 방문 환경과 메뉴는 시기에 따라 달라질 수 있으니 최신 정보를 확인해 보시길 권합니다."
            sql = "UPDATE cafes SET reviewsSummary = %s WHERE cafe_id = %s"
            cursor.execute(sql, (summary, cafe_id))
            conn.commit()

            elapsed = time.time() - start_time
            avg_time = elapsed / idx
            remaining = (total - idx) * avg_time
            eta = timedelta(seconds=int(remaining))
            percent = round(idx / total * 100, 2)

            print(f"➖ [{idx}/{total}] ({percent}%) [{name}] 블로그 거의 없음 → 중립 요약 저장 ⏱ ETA {eta}")
            # 과부하 완화
            time.sleep(2)
            continue

        text = " ".join(snippets)
        summary = summarize_text(text)

        sql = "UPDATE cafes SET reviewsSummary = %s WHERE cafe_id = %s"
        cursor.execute(sql, (summary, cafe_id))
        conn.commit()

        elapsed = time.time() - start_time
        avg_time = elapsed / idx
        remaining = (total - idx) * avg_time
        eta = timedelta(seconds=int(remaining))
        percent = round(idx / total * 100, 2)

        if "요약 실패" in summary:
            print(f"⚠️ [{idx}/{total}] ({percent}%) [{name}] 요약 실패 → {summary} ⏱ ETA {eta}")
        else:
            print(f"✅ [{idx}/{total}] ({percent}%) [{name}] 요약 완료 → {summary[:60]}... ⏱ ETA {eta}")

        time.sleep(5)  # API 과부하 방지

    except pymysql.err.OperationalError as e:
        print(f"⚠️ DB 연결 끊김 감지 → 재연결 중... ({e})")
        time.sleep(3)
        conn, cursor = get_connection()
        continue

    except Exception as e:
        print(f"❌ [{idx}/{total}] [{name}] 오류 발생: {e}")
        try:
            conn.rollback()
        except:
            pass
        continue

conn.close()
print("🎉 누락된 카페 요약 저장 완료!")