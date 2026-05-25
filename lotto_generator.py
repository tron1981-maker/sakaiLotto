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

# Supabase 타입 힌트
Client = None

# ─────────────────────────────────────────
# Supabase 연동 및 로또 통계 기능
# ─────────────────────────────────────────

def get_supabase_client():
    """Supabase 클라이언트를 초기화하여 반환합니다."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        print("  [알림] SUPABASE_URL 또는 SUPABASE_KEY 환경변수가 설정되지 않아 Supabase 연동을 건너뜁니다.")
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception as e:
        print(f"  [경고] Supabase 클라이언트 생성 실패: {e}", file=sys.stderr)
        return None


def check_previous_round_results(supabase, latest_draw: dict) -> Optional[str]:
    """직전 회차의 실제 당첨 결과와 이전 추천 번호를 매칭한 피드백 HTML을 생성합니다."""
    round_no = latest_draw["round"]
    actual_numbers = latest_draw["numbers"]
    actual_bonus = latest_draw["bonus"]
    
    try:
        response = supabase.table("lotto_recommendations").select("*").eq("round", round_no).order("game_index").execute()
        records = response.data
        if not records:
            print(f"  [알림] Supabase에 {round_no}회차 추천 번호 기록이 존재하지 않습니다.")
            return None
        
        results = []
        has_any_match = False
        
        for rec in records:
            rec_nums = rec["numbers"]
            game_idx = rec["game_index"]
            
            matched = sorted(list(set(rec_nums) & set(actual_numbers)))
            match_count = len(matched)
            bonus_matched = actual_bonus in rec_nums
            
            rank_str = ""
            is_win = False
            
            if match_count == 6:
                rank_str = "1등 당첨! 🎉"
                is_win = True
            elif match_count == 5 and bonus_matched:
                rank_str = "2등 당첨! 🎉"
                is_win = True
            elif match_count == 5:
                rank_str = "3등 당첨! 🥉"
                is_win = True
            elif match_count == 4:
                rank_str = "4등 당첨! 🏅"
                is_win = True
            elif match_count == 3:
                rank_str = "5등 당첨! 💸"
                is_win = True
                
            if match_count > 0:
                has_any_match = True
                
            results.append({
                "game_index": game_idx,
                "numbers": rec_nums,
                "matched": matched,
                "match_count": match_count,
                "bonus_matched": bonus_matched,
                "rank_str": rank_str,
                "is_win": is_win
            })
            
        if not has_any_match:
            print(f"  → {round_no}회차 추천 번호 중 일치하는 번호가 전혀 없습니다.")
            return None
            
        # 미려한 피드백 HTML 빌드
        html = f"""
<div style="background: #f8fafc; border: 1px solid #e2e8f0; border-left: 5px solid #3b82f6; padding: 20px; border-radius: 12px; margin-bottom: 30px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
    <h3 style="margin-top: 0; color: #1e3a8a; font-size: 1.25em; display: flex; align-items: center; gap: 8px;">
        <span>🎯 지난 제 {round_no}회 추천 번호 분석 결과</span>
    </h3>
    <p style="margin: 5px 0 15px 0; font-size: 0.95em; color: #64748b;">
        지난주 제안해 드린 분석 조합과 실제 당첨 번호(<strong>{', '.join(map(str, actual_numbers))} + 보너스 {actual_bonus}</strong>)를 대조한 결과입니다.
    </p>
    <div style="overflow-x: auto;">
        <table style="width: 100%; border-collapse: collapse; font-size: 0.9em; min-width: 400px;">
            <thead>
                <tr style="border-bottom: 2px solid #e2e8f0; text-align: left; color: #475569;">
                    <th style="padding: 8px 12px;">구분</th>
                    <th style="padding: 8px 12px;">추천 조합 번호</th>
                    <th style="padding: 8px 12px;">일치 개수</th>
                    <th style="padding: 8px 12px;">맞춘 번호</th>
                    <th style="padding: 8px 12px;">결과</th>
                </tr>
            </thead>
            <tbody>
"""
        for r in results:
            if r["match_count"] == 0:
                continue
            
            match_nums_str = ", ".join(map(str, r["matched"]))
            if r["bonus_matched"]:
                match_nums_str += f" (+보너스 {actual_bonus})"
                
            row_bg = "#f0f9ff" if r["is_win"] else "transparent"
            win_badge = f'<span style="background: #dbeafe; color: #1e40af; padding: 2px 8px; border-radius: 9999px; font-weight: bold; font-size: 0.85em;">{r["rank_str"]}</span>' if r["is_win"] else '<span style="color: #94a3b8;">-</span>'
            
            html += f"""
                <tr style="border-bottom: 1px solid #f1f5f9; background-color: {row_bg}; color: #334155;">
                    <td style="padding: 10px 12px; font-weight: bold;">조합 {r['game_index']}</td>
                    <td style="padding: 10px 12px; font-family: monospace; letter-spacing: 0.5px;">{', '.join(map(lambda x: f"{x:02d}" if isinstance(x, int) else str(x), r['numbers']))}</td>
                    <td style="padding: 10px 12px; font-weight: bold; color: #2563eb;">{r['match_count']}개 일치</td>
                    <td style="padding: 10px 12px; color: #dc2626; font-weight: 500;">{match_nums_str}</td>
                    <td style="padding: 10px 12px;">{win_badge}</td>
                </tr>
"""
        html += """
            </tbody>
        </table>
    </div>
</div>
"""
        return html
    except Exception as e:
        print(f"  [경고] 이전 회차 매칭 결과 분석 중 오류 발생: {e}", file=sys.stderr)
        return None


def save_recommendations_to_supabase(supabase, round_no: int, sets: list[list[int]]) -> None:
    """새로운 추천 번호 5세트를 Supabase에 업서트(저장)합니다."""
    try:
        data = []
        for idx, combo in enumerate(sets, 1):
            data.append({
                "round": round_no,
                "game_index": idx,
                "numbers": combo
            })
        supabase.table("lotto_recommendations").upsert(
            data,
            on_conflict="round,game_index"
        ).execute()
        print(f"  → Supabase에 제 {round_no}회 추천 번호 5세트 저장 성공!")
    except Exception as e:
        print(f"  [경고] Supabase 추천 번호 저장 실패: {e}", file=sys.stderr)


def analyze_combination_stats(combo: list[int]) -> dict:
    """단일 조합의 로또 통계 분석 정보를 반환합니다."""
    c_sum = sum(combo)
    odds = len([n for n in combo if n % 2 != 0])
    evens = 6 - odds
    lows = len([n for n in combo if n <= 22])
    highs = 6 - lows
    
    # 연속수 검사
    consecutive = []
    for i in range(len(combo) - 1):
        if combo[i+1] - combo[i] == 1:
            consecutive.append(f"{combo[i]}-{combo[i+1]}")
            
    return {
        "sum": c_sum,
        "odd_even": f"{odds}:{evens}",
        "high_low": f"{highs}:{lows}",
        "consecutive": ", ".join(consecutive) if consecutive else "없음"
    }


def get_frequency_stats(draws: list[dict]) -> dict:
    """최근 30회차 통계를 계산합니다 (최다/최소 출현, 번호대 분포)."""
    recent_30 = draws[-30:]
    freq_30 = Counter()
    for d in recent_30:
        freq_30.update(d["numbers"])
        
    # 전체 1~45 중 빈도
    all_freq = {n: freq_30.get(n, 0) for n in range(1, 46)}
    sorted_freq = sorted(all_freq.items(), key=lambda x: (-x[1], x[0]))
    
    # 핫 넘버 (상위 5)
    hot_numbers = [n for n, cnt in sorted_freq[:5]]
    # 콜드 넘버 (하위 5)
    cold_numbers = [n for n, cnt in sorted_freq[-5:]]
    
    # 번호대별 분포 카운트
    sections = {"1~10": 0, "11~20": 0, "21~30": 0, "31~40": 0, "41~45": 0}
    total_nums = 30 * 6
    for d in recent_30:
        for n in d["numbers"]:
            if 1 <= n <= 10:
                sections["1~10"] += 1
            elif 11 <= n <= 20:
                sections["11~20"] += 1
            elif 21 <= n <= 30:
                sections["21~30"] += 1
            elif 31 <= n <= 40:
                sections["31~40"] += 1
            elif 41 <= n <= 45:
                sections["41~45"] += 1
                
    section_pct = {k: f"{v / total_nums * 100:.1f}%" for k, v in sections.items()}
    
    return {
        "hot": hot_numbers,
        "cold": cold_numbers,
        "sections": section_pct
    }


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
    """CSV 파일에서 데이터를 로드합니다."""
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


def append_draw_to_csv(filepath: str, draw: dict) -> None:
    """새 회차 데이터를 CSV에 추가합니다."""
    import csv
    with open(filepath, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([draw["round"]] + draw["numbers"] + [draw["bonus"]])


def update_db(filepath: str) -> list[dict]:
    """CSV DB를 로드하고, API에서 최신 회차만 가져와 신규면 추가합니다."""
    draws = load_draws_from_csv(filepath)
    last_round = draws[-1]["round"]

    print(f"[1/3] DB 최신 회차: {last_round}회 - 신규 회차 확인 중...")
    new_count = 0
    for rno in range(last_round + 1, last_round + 10):
        draw = fetch_draw(rno)
        if draw is None:
            break
        append_draw_to_csv(filepath, draw)
        draws.append(draw)
        new_count += 1
        print(f"  → {rno}회차 추가")

    if new_count == 0:
        print(f"  → 신규 회차 없음 (현재 최신: {last_round}회)")
    else:
        print(f"  → {new_count}회차 추가 완료, 현재 최신: {draws[-1]['round']}회")

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


def build_post_content(analysis: dict, sets: list[list[int]], previous_feedback: Optional[str], draws: list[dict]) -> tuple[str, str]:
    """포스팅 제목과 HTML 본문을 생성합니다."""
    next_round = analysis["next_round"]
    title = f"[로또 분석] 제 {next_round}회 후나츠 사카이 로또 번호 추천 및 통계 종합"

    core_list  = ", ".join(map(str, sorted(analysis["core_group"])))
    cold_list  = ", ".join(map(str, sorted(analysis["cold_numbers"])))
    carry_list = ", ".join(map(str, sorted(analysis["last_numbers"])))

    # 생성된 5개 세트 각각의 통계 계산 및 HTML 로우 생성
    combos_html = ""
    for i, s in enumerate(sets, 1):
        stats = analyze_combination_stats(s)
        # 번호별 색상 스타일링 (로또 번호공 색상 대입)
        numbers_styled = []
        for n in s:
            if 1 <= n <= 10:
                bg, text = "#f59e0b", "#ffffff" # 노란색
            elif 11 <= n <= 20:
                bg, text = "#3b82f6", "#ffffff" # 파란색
            elif 21 <= n <= 30:
                bg, text = "#ef4444", "#ffffff" # 빨간색
            elif 31 <= n <= 40:
                bg, text = "#6b7280", "#ffffff" # 회색
            else:
                bg, text = "#10b981", "#ffffff" # 초록색
            numbers_styled.append(f'<span style="background: {bg}; color: {text}; display: inline-block; width: 30px; height: 30px; line-height: 30px; text-align: center; border-radius: 50%; font-weight: bold; margin-right: 5px; font-size: 0.9em;">{n}</span>')
            
        numbers_html = "".join(numbers_styled)
        
        combos_html += f"""
        <tr style="border-bottom: 1px solid #e2e8f0; color: #334155;">
            <td style="padding: 12px 10px; font-weight: bold; text-align: center;">조합 {i}</td>
            <td style="padding: 12px 10px; text-align: left;">{numbers_html}</td>
            <td style="padding: 12px 10px; text-align: center; font-weight: 500;">{stats['sum']}</td>
            <td style="padding: 12px 10px; text-align: center;">{stats['odd_even']}</td>
            <td style="padding: 12px 10px; text-align: center;">{stats['high_low']}</td>
            <td style="padding: 12px 10px; text-align: center; color: #475569; font-size: 0.85em;">{stats['consecutive']}</td>
        </tr>
"""

    # 최근 30회차 통계 정보 가져오기
    freq_stats = get_frequency_stats(draws)
    hot_str = ", ".join(map(str, freq_stats["hot"]))
    cold_str = ", ".join(map(str, freq_stats["cold"]))
    
    sections_html = ""
    for k, v in freq_stats["sections"].items():
        sections_html += f'<div style="flex: 1; min-width: 70px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; text-align: center;"><div style="font-size: 0.8em; color: #64748b; margin-bottom: 4px;">{k}</div><div style="font-size: 1em; font-weight: bold; color: #0f172a;">{v}</div></div>'

    # 이전 회차 피드백 추가
    feedback_section = previous_feedback if previous_feedback else ""

    body = f"""<div style="font-family: 'Noto Sans KR', -apple-system, BlinkMacSystemFont, sans-serif; max-width: 800px; margin: 0 auto; line-height: 1.8; color: #334155; padding: 10px;">

<!-- 메인 히어로 배너 -->
<div style="background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); color: #ffffff; padding: 30px 20px; border-radius: 16px; margin-bottom: 30px; text-align: center; box-shadow: 0 10px 15px -3px rgba(59, 130, 246, 0.3);">
    <h1 style="margin: 0; font-size: 1.8em; font-weight: 800; letter-spacing: -0.5px;">제 {next_round}회 로또 분석 & 황금 조합</h1>
    <p style="margin: 10px 0 0 0; font-size: 1em; opacity: 0.9;">후나츠 사카이 알고리즘 기반 통계 최적화 번호</p>
</div>

{feedback_section}

<!-- 1. 통계 최적화 예상 번호 5세트 -->
<div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 16px; padding: 24px; margin-bottom: 30px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
    <h2 style="margin-top: 0; border-bottom: 2px solid #3b82f6; padding-bottom: 8px; color: #1e3a8a; font-size: 1.4em;">🔮 제 {next_round}회 추천 조합 및 분석 통계</h2>
    <p style="font-size: 0.95em; color: #64748b; margin-top: 4px; margin-bottom: 16px;">사카이 규칙(이월수, 핵심군, 콜드수 비율 조정)에 의해 생성된 필터링 5세트와 주요 통계 지표입니다.</p>
    
    <div style="overflow-x: auto;">
        <table style="width: 100%; border-collapse: collapse; font-size: 0.9em; min-width: 550px;">
            <thead>
                <tr style="background-color: #f8fafc; border-bottom: 2px solid #e2e8f0; text-align: center; color: #475569; font-weight: bold;">
                    <th style="padding: 12px 10px; width: 10%;">구분</th>
                    <th style="padding: 12px 10px; width: 45%; text-align: left;">조합 번호</th>
                    <th style="padding: 12px 10px; width: 10%;">총합</th>
                    <th style="padding: 12px 10px; width: 11%;">홀:짝</th>
                    <th style="padding: 12px 10px; width: 11%;">고:저</th>
                    <th style="padding: 12px 10px; width: 13%;">연속수</th>
                </tr>
            </thead>
            <tbody>
                {combos_html}
            </tbody>
        </table>
    </div>
    
    <div style="margin-top: 15px; background-color: #f1f5f9; padding: 12px 15px; border-radius: 8px; font-size: 0.85em; color: #475569;">
        <strong>💡 로또 통계 상식:</strong>
        <ul style="margin: 5px 0 0 0; padding-left: 20px; line-height: 1.6;">
            <li><strong>총합 구간</strong>: 역대 당첨 번호의 약 70% 이상이 총합 100 ~ 170 사이에 집중됩니다.</li>
            <li><strong>홀짝 및 고저 비율</strong>: 3:3, 4:2, 2:4 비율이 전체 당첨 확률의 80% 이상을 차지합니다. (고: 23~45, 저: 1~22)</li>
        </ul>
    </div>
</div>

<!-- 2. 후나츠 사카이 필터링 기준 -->
<div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 16px; padding: 24px; margin-bottom: 30px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
    <h2 style="margin-top: 0; border-bottom: 2px solid #10b981; padding-bottom: 8px; color: #065f46; font-size: 1.4em;">🛠️ 후나츠 사카이 분석 필터 스탯</h2>
    
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 15px; margin-top: 15px;">
        <div style="border: 1px solid #e2e8f0; border-radius: 12px; padding: 15px; background: #f0f4ff; border-left: 4px solid #3b82f6;">
            <h4 style="margin: 0 0 8px 0; color: #1e3a8a; font-size: 0.95em;">🎯 Rule A · 핵심군 번호</h4>
            <div style="font-size: 0.85em; color: #475569; margin-bottom: 6px;">최근 30회차 중 4~6회 출현</div>
            <div style="font-size: 1em; font-weight: bold; color: #1d4ed8; word-break: break-all;">{core_list}</div>
        </div>
        <div style="border: 1px solid #e2e8f0; border-radius: 12px; padding: 15px; background: #fff4e0; border-left: 4px solid #f59e0b;">
            <h4 style="margin: 0 0 8px 0; color: #78350f; font-size: 0.95em;">❄️ Rule B · 콜드 넘버</h4>
            <div style="font-size: 0.85em; color: #475569; margin-bottom: 6px;">최근 3회차 미출현 (반등 기대)</div>
            <div style="font-size: 1em; font-weight: bold; color: #b45309; word-break: break-all;">{cold_list}</div>
        </div>
        <div style="border: 1px solid #e2e8f0; border-radius: 12px; padding: 15px; background: #f0fff4; border-left: 4px solid #10b981;">
            <h4 style="margin: 0 0 8px 0; color: #064e3b; font-size: 0.95em;">🔄 Rule C · 이월수 후보</h4>
            <div style="font-size: 0.85em; color: #475569; margin-bottom: 6px;">직전 {next_round - 1}회 당첨번호 (이월 1개 필수)</div>
            <div style="font-size: 1em; font-weight: bold; color: #047857; word-break: break-all;">{carry_list}</div>
        </div>
    </div>
</div>

<!-- 3. 트렌디한 로또 통계 분석 콘텐츠 -->
<div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 16px; padding: 24px; margin-bottom: 30px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
    <h2 style="margin-top: 0; border-bottom: 2px solid #8b5cf6; padding-bottom: 8px; color: #5b21b6; font-size: 1.4em;">📊 최근 30회 트렌드 로또 분석 통계</h2>
    <p style="font-size: 0.95em; color: #64748b; margin-top: 4px; margin-bottom: 16px;">과거 30회 동안의 빅데이터 흐름을 통해 보는 트렌드 통계 정보입니다.</p>
    
    <div style="margin-bottom: 20px;">
        <h4 style="margin: 0 0 10px 0; color: #1e293b; font-size: 1em;">🔥 HOT & COLD 넘버 분포</h4>
        <div style="display: flex; flex-direction: column; gap: 8px;">
            <div style="display: flex; align-items: center; background: #fef2f2; border: 1px solid #fee2e2; padding: 10px 15px; border-radius: 8px;">
                <span style="background: #ef4444; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold; margin-right: 12px;">HOT</span>
                <span style="font-size: 0.9em; font-weight: bold; color: #991b1b; letter-spacing: 1px;">최다 출현 번호 Top 5: {hot_str}</span>
            </div>
            <div style="display: flex; align-items: center; background: #f0f9ff; border: 1px solid #e0f2fe; padding: 10px 15px; border-radius: 8px;">
                <span style="background: #3b82f6; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold; margin-right: 12px;">COLD</span>
                <span style="font-size: 0.9em; font-weight: bold; color: #1e40af; letter-spacing: 1px;">최소 출현 번호 Top 5: {cold_str}</span>
            </div>
        </div>
    </div>
    
    <div>
        <h4 style="margin: 0 0 10px 0; color: #1e293b; font-size: 1em;">🔢 최근 30회차 구간별 출현 비율</h4>
        <div style="display: flex; flex-wrap: wrap; gap: 8px;">
            {sections_html}
        </div>
    </div>
</div>

<p style="margin-top: 30px; text-align: center; color: #64748b; font-size: 0.85em; border-top: 1px solid #e2e8f0; padding-top: 15px;">
    본 분석 자료는 통계적 확률 모형 및 후나츠 사카이 배합법을 기초로 생성되었습니다.<br/>
    로또는 재미로 즐겨주시기 바라며, 여러분에게 행운을 가져다주기를 진심으로 바랍니다. 🍀
</p>
</div>"""

    return title, body



def get_blogger_service(credentials_path: str):
    """
    Blogger API 서비스 객체를 반환합니다.

    인증 방식 A - OAuth 2.0 (권장):
      credentials_path 에 client_secret_*.json 파일 경로를 지정합니다.
      최초 실행 시 브라우저 인증 창이 열리며, 이후 token.json 에 토큰이 저장됩니다.

    인증 방식 B - Service Account:
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
                try:
                    credentials.refresh(Request())
                except Exception:
                    credentials = None  # refresh token 만료 → 재인증 필요
            if not credentials or not credentials.valid:
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
        print("\n[DRY-RUN] 포스팅 생략 - 실제 게시하려면 --dry-run 플래그를 제거하세요.")
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
    parser.add_argument("--csv", help="로컬 CSV DB 파일 경로 (기본값: lotto_data.csv)")
    parser.add_argument("--credentials", help="GCP 인증 JSON 파일 경로 (OAuth 또는 Service Account)")
    parser.add_argument("--dry-run", action="store_true", help="번호 생성만 하고 포스팅 생략")
    parser.add_argument("--output", help="결과를 저장할 JSON 파일 경로")
    parser.add_argument("--seed", type=int, help="난수 시드 (재현성 확보)")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    # ── 데이터 로드 (CSV DB 우선, 없으면 API 전체 수집)
    db_path = args.csv if args.csv else "lotto_data.csv"
    try:
        if os.path.exists(db_path):
            draws = update_db(db_path)
        else:
            print(f"[1/3] DB 없음 - API에서 30회차 전체 수집 후 DB 생성: {db_path}")
            draws = load_recent_draws(count=30)
            import csv as _csv
            with open(db_path, "w", newline="", encoding="utf-8") as f:
                w = _csv.writer(f)
                w.writerow(["round","n1","n2","n3","n4","n5","n6","bonus"])
                for d in draws:
                    w.writerow([d["round"]] + d["numbers"] + [d["bonus"]])
            print(f"  → DB 생성 완료: {db_path}")

        if len(draws) < 30:
            print(f"[오류] 데이터 부족: {len(draws)}회차", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"[오류] 데이터 수집 실패: {e}", file=sys.stderr)
        sys.exit(1)

    # ── 분석 및 번호 생성
    try:
        # Supabase 연동 처리
        supabase = get_supabase_client()
        previous_feedback = None
        if supabase:
            print("\n[Supabase] 이전 회차 추천 번호 당첨 결과 조회 중...")
            previous_feedback = check_previous_round_results(supabase, draws[-1])
            if previous_feedback:
                print("  → 지난 회차 추천 조합 중 적중 번호가 존재하여 포스팅에 포함합니다.")
            else:
                print("  → 지난 회차 적중 조합이 없거나 이전 추천 기록이 없습니다.")

        analysis = analyze(draws)
        sets = generate_five_sets(analysis)

        # 새로운 추천 조합 Supabase 저장
        if supabase:
            print(f"\n[Supabase] 제 {analysis['next_round']}회 추천 조합 저장 중...")
            save_recommendations_to_supabase(supabase, analysis["next_round"], sets)
    except Exception as e:
        print(f"[오류] 번호 생성 및 Supabase 연동 실패: {e}", file=sys.stderr)
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
            title, body = build_post_content(analysis, sets, previous_feedback, draws)
            post_to_blogger(title, body, args.credentials, dry_run=False)
        except Exception as e:
            print(f"[오류] 포스팅 실패: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        title, body = build_post_content(analysis, sets, previous_feedback, draws)
        print(f"\n[DRY-RUN] 제목: {title}")
        print("[DRY-RUN] 본문 미리보기 (첫 500자):")
        print(body[:500], "...")

    print("\n완료")



if __name__ == "__main__":
    main()
