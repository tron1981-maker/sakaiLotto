# 후나츠 사카이 로또 번호 추출기 v0.1 — 실행 가이드

## 1. 사전 준비 — Python 패키지 설치

```bash
pip install -r requirements.txt
```

---

## 2. GCP Blogger API 세팅

### Step 1. Google Cloud Console 접속
1. https://console.cloud.google.com 에서 새 프로젝트 생성 (또는 기존 프로젝트 사용)
2. 좌측 메뉴 → **API 및 서비스 > 라이브러리** → `Blogger API v3` 검색 → **사용 설정**

### Step 2-A. OAuth 2.0 클라이언트 자격 증명 (권장)

> 본인 구글 계정으로 직접 블로그를 운영하는 경우 이 방식을 사용합니다.

1. **API 및 서비스 > 사용자 인증 정보 > 사용자 인증 정보 만들기 > OAuth 클라이언트 ID**
2. 애플리케이션 유형: **데스크톱 앱**
3. 생성 후 **JSON 다운로드** → 파일 이름을 `client_secret.json`으로 저장 (프로젝트 폴더에 위치)
4. **OAuth 동의 화면** 설정:
   - 사용자 유형: **외부**
   - 앱 이름, 이메일 입력 후 저장
   - **테스트 사용자**에 본인 구글 계정 이메일 추가

### Step 2-B. 서비스 계정 (자동화 서버 환경용)

1. **API 및 서비스 > 사용자 인증 정보 > 사용자 인증 정보 만들기 > 서비스 계정**
2. 키 생성 → **JSON 형식** 다운로드 → `service_account.json`으로 저장
3. **Blogger 관리자 페이지**(https://www.blogger.com) → 설정 → 권한
   → 서비스 계정 이메일(`xxx@yyy.iam.gserviceaccount.com`)을 **작성자** 이상으로 추가

---

## 3. CLI 실행 방법

### 기본 실행 (API 데이터 수집 + Blogger 포스팅)
```bash
python lotto_generator.py --credentials client_secret.json
```
> 최초 실행 시 브라우저 OAuth 인증 창이 열립니다.  
> 인증 완료 후 `token.json`이 생성되며, 이후 실행부터는 자동 로그인됩니다.

### 번호 생성만 (포스팅 생략)
```bash
python lotto_generator.py --dry-run
```

### 로컬 CSV 파일 사용
```bash
python lotto_generator.py --csv lotto_data.csv --credentials client_secret.json
```

CSV 형식 예시 (`lotto_data.csv`):
```
round,n1,n2,n3,n4,n5,n6,bonus
1150,3,7,18,24,35,42,11
1151,1,9,22,31,40,44,5
...
```

### 결과를 JSON으로 저장
```bash
python lotto_generator.py --dry-run --output result.json
```

### 재현 가능한 결과 (동일 시드)
```bash
python lotto_generator.py --dry-run --seed 42
```

---

## 4. 파일 구조

```
프로젝트 폴더/
├── lotto_generator.py   # 메인 스크립트
├── requirements.txt     # 패키지 목록
├── GUIDE.md             # 이 파일
├── client_secret.json   # OAuth 인증 파일 (직접 다운로드)
└── token.json           # OAuth 토큰 캐시 (자동 생성)
```

---

## 5. 후나츠 사카이 알고리즘 요약

| Rule | 설명 |
|------|------|
| A | 최근 30회차에서 **4~6회** 출현 번호 → 핵심군 |
| B | 최근 3회차 **미출현** 번호 → 콜드 넘버 |
| C | 직전 회차 당첨번호 중 **1개** 이월수 포함 |
| D | 이월수 1개 + 핵심군 3~4개 + 콜드 넘버 1~2개 + 보충 = 6개 × 5세트 |

---

## 6. 자주 묻는 질문

**Q. `token.json`이 만료되면?**  
A. 삭제 후 재실행하면 다시 브라우저 인증이 진행됩니다.

**Q. `403 Forbidden` 오류가 발생한다면?**  
A. OAuth 동의 화면의 **테스트 사용자** 목록에 본인 계정이 있는지 확인하세요.

**Q. API 호출이 느리면?**  
A. `--csv` 옵션으로 미리 수집한 CSV 파일을 사용하면 빠릅니다.
