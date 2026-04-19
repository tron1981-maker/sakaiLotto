"""
후나츠 사카이 로또 번호 추출기 v0.1 + Blogger 자동 포스팅
"""

import os
import sys
import json
import random
import argparse
import time
from collections import Counter
from typing import Optional

import requests

# ─────────────────────────────────────────
# 1. 데이터 수집
# ─────────────────────────────────────────

LOTTO_API_URL = "https://www.dhlottery.co.kr/lt645/selectPstLt645Info.do?srchLtEpsd={}"


def fetch_latest_round_number() -> int:
    """이진 탐색으로 현재 최신 회차 번호를 탐색합니다."""
    lo, hi = 1000, 1300
    # hi 상한선 동적 확장
    while True:
        resp = requests.get(LOTTO_API_URL.format(hi), timeout=10)
        if resp.json()["data"]["list"]:
            hi += 100
        else:
            break

    while lo < hi:
        mid = (lo + hi + 1) // 2
        resp = requests.get(LOTTO_API_URL.format(mid), timeout=10)
        if resp.json()["data"]["list"]:
            lo = mid
        else:
            hi = mid - 1
    return lo


def fetch_draw(round_no: int) -> Optional[dict]:
    """단일 회차 데이터를 API에서 가져옵니다."""
    try:
        resp = requests.get(LOTTO_API_URL.format(round_no), timeout=10)
        resp.raise_for_status()
        items = resp.json()["data"]["list"]
        if not items:
            return None
        d = items[0]
        return {
            "round": d["ltEpsd"],
            "numbers": [
                d["tm1WnNo"], d["tm2WnNo"], d["tm3WnNo"],
                d["tm4WnNo"], d["tm5WnNo"], d["tm6WnNo"],
            ],
            "bonus": d["bnsWnNo"],
        }
    except Exception as e:
        print(f"  [경고] {round_no}회차 조회 실패: {e}", file=sys.stderr)
        return None


def load_recent_draws(count: int = 30) -> list[dict]:
    """최근 count 회차 데이터를 로드합니다."""
    print(f"[1/3] 최신 회차 탐색 중...")
    latest = fetch_latest_round_number()
    print(f"  → 최신 회차: {latest}회")

    draws = []
    for rno in range(latest, latest - count - 5, -1):
        if len(draws) >= count:
            break
        if rno < 1:
            break
        draw = fetch_draw(rno)
        if draw:
            draws.append(draw)
        time.sleep(0.05)  # API 부하 방지

    if len(draws) < count:
        raise ValueError(f"데이터 부족: {len(draws)}회차만 수집됨 (필요: {count}회차)")

    draws.sort(key=lambda d: d["round"])
    print(f"  → {draws[0]['round']}회 ~ {draws[-1]['round']}회 ({len(draws)}회차) 로드 완료")
    return draws


def load_draws_from_csv(filepath: str) -> list[dict]:
    """로컬 CSV 파일에서 데이터를 로드합니다.
    CSV 형식: round,n1,n2,n3,n4,n5,n6,bonus  (헤더 있음)
    """
    import csv
    draws = []
    with open(filepath, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            draws.append({
                "round": int(row["round"]),
                "numbers": [int(row[f"n{i}"]) for i in range(1, 7)],
                "bonus": int(row["bonus"]),
            })
    draws.sort(key=lambda d: d["round"])
    return draws


# ─────────────────────────────────────────
# 2. 후나츠 사카이 알고리즘
# ─────────────────────────────────────────

def analyze(draws: list[dict]) -> dict:
    """Rule A, B, C 분석 결과를 반환합니다."""
    recent_30 = draws[-30:]
    recent_3  = draws[-3:]

    # Rule A: 30회차 빈도 → 4~6회 출현 번호 = 핵심군
    freq_30 = Counter()
    for d in recent_30:
        freq_30.update(d["numbers"])
    core_group = {n for n, cnt in freq_30.items() if 4 <= cnt <= 6}

    # Rule B: 최근 3회차 미출현 번호 = 콜드 넘버
    appeared_3 = set()
    for d in recent_3:
        appeared_3.update(d["numbers"])
    cold_numbers = set(range(1, 46)) - appeared_3

    # Rule C: 직전 회차 당첨번호 (이월수 후보)
    last_numbers = set(draws[-1]["numbers"])
    next_round   = draws[-1]["round"] + 1

    print(f"\n[2/3] 후나츠 사카이 분석 결과")
    print(f"  ▶ Rule A - 핵심군(30회차 4~6번 출현): {sorted(core_group)}")
    print(f"  ▶ Rule B - 콜드 넘버(최근 3회차 미출현): {sorted(cold_numbers)}")
    print(f"  ▶ Rule C - 이월수 후보(직전 {draws[-1]['round']}회 당첨번호): {sorted(last_numbers)}")

    return {
        "core_group": core_group,
        "cold_numbers": cold_numbers,
        "last_numbers": last_numbers,
        "next_round": next_round,
        "freq_30": freq_30,
    }


def generate_combination(
    core_group: set,
    cold_numbers: set,
    last_numbers: set,
    all_numbers: set,
    max_attempts: int = 10000,
) -> list[int]:
    """Rule D에 따라 6개 번호 1세트를 생성합니다."""
    for _ in range(max_attempts):
        selected = set()

        # Rule C: 이월수 1개
        carry = random.choice(sorted(last_numbers))
        selected.add(carry)

        # Rule A: 핵심군에서 3~4개 (이월수 제외)
        available_core = sorted(core_group - selected)
        core_count = random.randint(3, 4)
        if len(available_core) < core_count:
            core_count = len(available_core)
        selected.update(random.sample(available_core, core_count))

        # Rule B: 콜드 넘버에서 1~2개
        available_cold = sorted(cold_numbers - selected)
        cold_count = random.randint(1, 2)
        if len(available_cold) < cold_count:
            cold_count = len(available_cold)
        selected.update(random.sample(available_cold, cold_count))

        # 부족분 랜덤 보충
        if len(selected) < 6:
            pool = sorted(all_numbers - selected)
            selected.update(random.sample(pool, 6 - len(selected)))

        if len(selected) == 6:
            return sorted(selected)

    raise RuntimeError("번호 생성 실패: 조건 충족 조합을 찾지 못했습니다.")


def generate_five_sets(analysis: dict) -> list[list[int]]:
    """서로 다른 5세트를 생성합니다."""
    all_numbers = set(range(1, 46))
    sets = []
    seen = set()

    attempts = 0
    while len(sets) < 5 and attempts < 50000:
        attempts += 1
        combo = generate_combination(
            analysis["core_group"],
            analysis["cold_numbers"],
            analysis["last_numbers"],
            all_numbers,
        )
        key = tuple(combo)
        if key not in seen:
            seen.add(key)
            sets.append(combo)

    if len(sets) < 5:
        raise RuntimeError(f"5세트 생성 실패: {len(sets)}세트만 생성됨")

    print(f"\n  ▶ Rule D - 생성된 5세트:")
    for i, s in enumerate(sets, 1):
        print(f"     조합{i}: {', '.join(map(str, s))}")

    return sets


# ─────────────────────────────────────────
# 3. Blogger 자동 포스팅
# ─────────────────────────────────────────

BLOG_ID = "1558338119441977086"


def build_post_content(analysis: dict, sets: list[list[int]]) -> tuple[str, str]:
    """포스팅 제목과 HTML 본문을 생성합니다."""
    next_round = analysis["next_round"]
    title = f"[후나츠 사카이] 제 {next_round}회 로또 예상 번호 분석 v0.1"

    core_list  = ", ".join(map(str, sorted(analysis["core_group"])))
    cold_list  = ", ".join(map(str, sorted(analysis["cold_numbers"])))
    carry_list = ", ".join(map(str, sorted(analysis["last_numbers"])))

    combos_html = "\n".join(
        f'  <li><strong>조합{i}</strong>: {", ".join(map(str, s))}</li>'
        for i, s in enumerate(sets, 1)
    )

    body = f"""<div style="font-family: 'Noto Sans KR', sans-serif; max-width: 700px; margin: 0 auto; line-height: 1.8;">

<h2>후나츠 사카이 분석 요약 — 제 {next_round}회</h2>

<h3>Rule A · 핵심군 (최근 30회차 4~6번 출현)</h3>
<p style="background:#f0f4ff;padding:10px;border-radius:6px;">{core_list}</p>

<h3>Rule B · 콜드 넘버 (최근 3회차 미출현)</h3>
<p style="background:#fff4e0;padding:10px;border-radius:6px;">{cold_list}</p>

<h3>Rule C · 이월수 후보 (직전 {next_round - 1}회 당첨번호)</h3>
<p style="background:#f0fff4;padding:10px;border-radius:6px;">{carry_list}</p>

<h3>Rule D · 생성 규칙</h3>
<ul>
  <li>이월수 1개 포함</li>
  <li>핵심군에서 3~4개 선택</li>
  <li>콜드 넘버에서 1~2개 선택</li>
  <li>부족분은 나머지에서 랜덤 보충 → 총 6개</li>
</ul>

<hr/>

<h2>🎱 제 {next_round}회 예상 번호 5세트</h2>
<ol>
{combos_html}
</ol>

<p style="margin-top:2em; color:#555;">
이 번호는 후나츠 사카이식 통계 분석을 통해 생성되었습니다. 행운을 빕니다. 🍀
</p>
</div>"""

    return title, body


def get_blogger_service(credentials_path: str):
    """
    Blogger API 서비스 객체를 반환합니다.

    인증 방식 A — OAuth 2.0 (권장):
      credentials_path 에 client_secret_*.json 파일 경로를 지정합니다.
      최초 실행 시 브라우저 인증 창이 열리며, 이후 token.json 에 토큰이 저장됩니다.

    인증 방식 B — Service Account:
      GCP 서비스 계정 JSON 키 파일 경로를 지정합니다.
      단, Blogger API는 개인 블로그 소유자의 계정 권한이 필요하므로
      서비스 계정을 블로그 관리자로 초대해야 합니다.
    """
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    import google.oauth2.service_account as sa

    SCOPES = ["https://www.googleapis.com/auth/blogger"]
    TOKEN_FILE = "token.json"

    # 서비스 계정 여부 판별
    with open(credentials_path) as f:
        cred_data = json.load(f)

    if cred_data.get("type") == "service_account":
        # 방식 B: Service Account
        credentials = sa.Credentials.from_service_account_file(
            credentials_path, scopes=SCOPES
        )
    else:
        # 방식 A: OAuth 2.0
        credentials = None
        if os.path.exists(TOKEN_FILE):
            credentials = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_path, SCOPES
                )
                # 포트 충돌 방지: 여러 포트 순서대로 시도
                for _port in [8080, 8090, 9090, 9191, 0]:
                    try:
                        credentials = flow.run_local_server(port=_port)
                        break
                    except OSError:
                        continue
                else:
                    raise RuntimeError("사용 가능한 OAuth 포트를 찾지 못했습니다.")
            with open(TOKEN_FILE, "w") as f:
                f.write(credentials.to_json())

    return build("blogger", "v3", credentials=credentials)


def post_to_blogger(title: str, body: str, credentials_path: str, dry_run: bool = False) -> Optional[str]:
    """Blogger에 포스트를 작성하고 URL을 반환합니다."""
    if dry_run:
        print("\n[DRY-RUN] 포스팅 생략 — 실제 게시하려면 --dry-run 플래그를 제거하세요.")
        return None

    print("\n[3/3] Blogger 포스팅 중...")
    service = get_blogger_service(credentials_path)

    post_body = {
        "kind": "blogger#post",
        "blog": {"id": BLOG_ID},
        "title": title,
        "content": body,
    }

    result = service.posts().insert(blogId=BLOG_ID, body=post_body, isDraft=False).execute()
    url = result.get("url", "")
    print(f"  → 포스팅 완료: {url}")
    return url


# ─────────────────────────────────────────
# 4. CLI 진입점
# ─────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="후나츠 사카이 로또 번호 생성기 v0.1",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # API로 데이터 수집 후 Blogger에 포스팅
  python lotto_generator.py --credentials client_secret.json

  # 로컬 CSV 파일 사용
  python lotto_generator.py --csv lotto_data.csv --credentials client_secret.json

  # 번호만 생성하고 포스팅하지 않음
  python lotto_generator.py --dry-run

  # 결과를 JSON 파일로 저장
  python lotto_generator.py --dry-run --output result.json
        """,
    )
    parser.add_argument("--csv", help="로컬 CSV 파일 경로 (미지정 시 API 사용)")
    parser.add_argument("--credentials", help="GCP 인증 JSON 파일 경로 (OAuth 또는 Service Account)")
    parser.add_argument("--dry-run", action="store_true", help="번호 생성만 하고 포스팅 생략")
    parser.add_argument("--output", help="결과를 저장할 JSON 파일 경로")
    parser.add_argument("--seed", type=int, help="난수 시드 (재현성 확보)")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    # ── 데이터 로드
    if args.csv:
        print(f"[1/3] CSV 파일 로드: {args.csv}")
        draws = load_draws_from_csv(args.csv)
        if len(draws) < 30:
            print(f"[오류] CSV 데이터가 30회차 미만입니다 ({len(draws)}회차).", file=sys.stderr)
            sys.exit(1)
        draws = draws[-30:]
        print(f"  → {draws[0]['round']}회 ~ {draws[-1]['round']}회 ({len(draws)}회차) 로드 완료")
    else:
        try:
            draws = load_recent_draws(count=30)
        except Exception as e:
            print(f"[오류] 데이터 수집 실패: {e}", file=sys.stderr)
            sys.exit(1)

    # ── 분석 및 번호 생성
    try:
        analysis = analyze(draws)
        sets = generate_five_sets(analysis)
    except Exception as e:
        print(f"[오류] 번호 생성 실패: {e}", file=sys.stderr)
        sys.exit(1)

    # ── 결과 저장
    if args.output:
        result = {
            "next_round": analysis["next_round"],
            "core_group": sorted(analysis["core_group"]),
            "cold_numbers": sorted(analysis["cold_numbers"]),
            "last_numbers": sorted(analysis["last_numbers"]),
            "combinations": sets,
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n  → 결과 저장: {args.output}")

    # ── 포스팅
    if not args.dry_run:
        if not args.credentials:
            print("[오류] --credentials 옵션으로 GCP 인증 파일을 지정해야 합니다.", file=sys.stderr)
            sys.exit(1)
        if not os.path.exists(args.credentials):
            print(f"[오류] 인증 파일을 찾을 수 없습니다: {args.credentials}", file=sys.stderr)
            sys.exit(1)
        try:
            title, body = build_post_content(analysis, sets)
            post_to_blogger(title, body, args.credentials, dry_run=False)
        except Exception as e:
            print(f"[오류] 포스팅 실패: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        title, body = build_post_content(analysis, sets)
        print(f"\n[DRY-RUN] 제목: {title}")
        print("[DRY-RUN] 본문 미리보기 (첫 500자):")
        print(body[:500], "...")

    print("\n완료")


if __name__ == "__main__":
    main()
