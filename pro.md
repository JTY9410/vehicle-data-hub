# 프로젝트 기술개발 정의서

Cursor와 후속 개발자용 · 2026-09-27 공통 기준을 이 저장소(Vehicle Data Hub)에 맞게 적용한다.  
작업 전에 이 문서와 실제 요구사항을 읽는다. 헌법은 참고이며 기술 스택을 자동으로 바꾸지 않는다.

## 1. 기술 스택과 책임

| 영역 | 이 저장소 | 원칙 |
|------|-----------|------|
| 서버 | Python 3.12, Flask 3.1, Jinja | `create_app` · Blueprint. route는 입출력, service는 업무 규칙 |
| DB | SQLAlchemy 2, Flask-Migrate | 로컬 SQLite, 운영 PostgreSQL/Supabase |
| 화면 | HTML5, CSS3, Vanilla JS, Bootstrap 5.3.8 + Tailwind(prefix `tw-`, preflight 끔) | 서버 렌더링 우선 |
| 배포 | Docker multi-stage, Compose | 비루트, 이미지에 비밀값 금지 |
| PWA | Manifest, Service Worker | 공개 정적 파일만 캐시. 로그인 후 설치 안내는 선택 |

한 업무 규칙은 한 service에만 둔다. `config.py`는 환경 설정 인터페이스, `.env`는 로컬용이다.

## 2. 구조

이 앱은 이미 `apps/routes/` · `apps/services/` 로 나뉘어 있다. 동작하는 허브를 `app/modules/` 로 옮기지 않는다. 이유는 `docs/adr/001-keep-apps-layout.md`.

단순 기능에 억지 계층을 만들지 않는다. 화면 흐름은 `docs/flows/`에 남긴다.

## 3. 데이터베이스

모델 수정 → `flask db migrate` → 스크립트 검토 → `flask db upgrade`.  
확인되지 않은 업무 테이블(AI 키, MFA, 감사 로그 등)은 요구사항이 오기 전에 만들지 않는다.

## 4. 브랜드·UI

- 로고 파일이 생기면 `static/brand/`에 두고 핫링크하지 않는다.
- 회사 표기는 `templates/base.html` 푸터 한곳. `position: fixed`로 본문을 가리지 않는다.
- Tailwind는 Bootstrap을 대체하지 않고 유틸리티만 더한다.

## 5. 보안·관리자

- 고정 관리자 계정·공통 비밀번호를 제품에 넣지 않는다.
- 최초 관리자는 `/setup` 또는 `ADMIN_USERNAME`/`ADMIN_PASSWORD` + `flask seed-admin`.
- 공유 초안 비밀번호는 시드·로그인에서 거부한다.
- 관리자 AI 연결·RAG·MFA는 이 허브의 별도 요구사항이 오기 전에 구현하지 않는다.

## 6. Cursor 완료 기준

1. `pro.md`와 기존 코드를 읽고 바꿀 화면·서비스를 정한다. 불명확한 정책은 임의 확정하지 않는다.
2. 기존 컴포넌트를 재사용하고 작게 구현한다.
3. pytest와 핵심 흐름을 검증한다.
4. README만으로 실행·설정·마이그레이션·테스트가 가능해야 한다.

## 7. Hub ↔ PM 경계

매물·엔카 코드 원천은 이 허브, 시세·기준가·MFA·AI·파트너 API는 WeCar PM이다.  
상세·금지·계약·체크리스트: [`docs/architecture-boundaries.md`](docs/architecture-boundaries.md).  
Cursor 복붙 프롬프트: [`docs/cursor-hub-tasks.md`](docs/cursor-hub-tasks.md).  
두 앱을 하나로 합치거나, 기준가 테이블을 Hub에 넣거나, PM이 크롤 API로 Hub를 우회하게 하지 않는다.
