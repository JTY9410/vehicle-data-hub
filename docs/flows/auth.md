# 인증 흐름

1. 사용자: 브라우저에서 `/login`
2. route: `admin.login` — 사용자가 없으면 `/setup`으로 보낸다
3. 빈 DB: `POST /setup` → `User` 해시 저장 → `/login`
4. 로그인: 초안 비밀번호 거부 → 세션 재발급 → 대시보드
5. CLI: `ADMIN_USERNAME`/`ADMIN_PASSWORD`가 있을 때만 `flask seed-admin`
