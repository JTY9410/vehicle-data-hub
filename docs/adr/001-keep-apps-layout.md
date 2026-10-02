# ADR 001. 기존 apps 레이아웃 유지

공통 정의서는 `app/modules/<feature>`를 예시로 든다. 이 저장소는 이미 `apps/routes`와 `apps/services`로 크롤 수집·API·관리 화면이 동작한다.

전면 이동은 배포·테스트·Vercel 진입점(`api/index.py`)을 한꺼번에 깨뜨린다. 새 기능이 생길 때만 그 기능 폴더에 모은다.
