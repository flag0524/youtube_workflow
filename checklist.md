# Flow 영상 생성 단계 추가 체크리스트

- [x] 1. playwright 설치, 전용 Chrome 프로필 경로 확정 (`.flow_profile/`, .gitignore 등록)
- [x] 2. 사용자 1회 수동 로그인 → Flow UI 실제 구조 확인 (셀렉터, 9:16 설정, 다운로드 경로)
- [x] 3. `steps/flow.py` — 세그먼트별 프롬프트 생성 → Flow 클립 생성 → mp4 다운로드
- [x] 4. Flow 클립을 나레이션 길이에 맞춰 자르고 이어붙이도록 `render.py` 수정 (Flow 오디오는 제거)
- [x] 5. `daily.py` 에 flow 단계 추가, 실패 시 정적 배경 폴백
- [x] 6. 일일 클립 상한(`config.yaml: flow.max_clips_per_day`)과 소모량 로그
- [x] 7. 테스트: 프롬프트 생성·폴백 분기·클립 길이 계산 (Flow 접속 없이 도는 단위 테스트)
- [ ] 8. 실제 1회 end-to-end (업로드 제외) — 생성 크레딧 소모라 사용자 승인 대기. dry-run 이 Flow 를 호출하지 않는 것은 단위 테스트로 확인 완료
- [x] 9. 전체 pytest 통과 확인 후 커밋 (95 통과, 1 실패는 fontTools DLL 차단으로 변경 전에도 동일)

# 모션 자막(Remotion) 체크리스트
- [x] M1. remotion/ 프로젝트 생성, npm install, 투명 오버레이(webm) 렌더 확인
- [x] M2. Captions 컴포지션: 훅·마지막 자막은 pop, 나머지는 짧은 페이드, 키워드만 색 강조
- [x] M3. steps/motion.py — props 생성(순수 함수) + Jev 키워드 선택(실패 시 최장 단어) + remotion 렌더(실패 시 빈 결과)
- [x] M4. render.py — 오버레이가 있으면 ASS 대신 overlay, 없으면 기존 ASS 폴백
- [x] M5. daily.py 에 motion 단계 추가, 단위 테스트, 전체 pytest
- [x] M6. 실제 렌더로 프레임 확인 후 커밋
