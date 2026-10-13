# Context Notes

## 2026-09-30 결정
- Flow 는 영상 생성 단계만 담당. 자막·TTS·ffmpeg 합성·YouTube 예약 업로드는 기존 파이프라인 유지.
- Flow 에 공식 API 가 없어 Playwright 브라우저 자동화. 전용 Chrome 프로필에 1회 수동 로그인 후 세션 재사용.
  (사유: 기존 Chrome 연결은 사용 중인 브라우저를 건드릴 위험이 있음)
- 세그먼트당 클립 1개. 클립은 약 8초이므로 나레이션 세그먼트가 8초를 넘으면 초과분 처리 방식은 실측 후 결정.
- Flow 실패/크레딧 소진 시 기존 정적 그라데이션 배경으로 폴백해 그날 업로드는 유지.
- 구독 플랜 미확인 → 일일 상한 4클립으로 시작, 소모량을 로그로 남겨 조정.
- 리스크: Flow UI 변경 시 셀렉터 깨짐, 자동화가 Flow 약관상 회색지대일 수 있음. AI 생성물이라 YouTube 합성 콘텐츠 고지는 이미 upload.py 에 있음.

## 2026-09-30 Flow UI 실측 (로그인 완료, 세션은 .flow_profile/ 에 저장됨)
- 로그인은 flow_login.py 로 창을 띄워 수동 로그인. 창을 닫아야 세션이 저장된다. 세션 확인 결과 정상.
- 새 프로젝트: flow.google.com 홈에서 "새 프로젝트" 클릭 → /project/<uuid>.
- 하단 입력창의 모델 칩(예: "Nano Banana 2 Lite") 클릭 → 설정 팝업.
  - 탭: 이미지 / 동영상. 비율: 16:9, 9:16 (동영상). 개수: x1~x4. 길이: 4·6·8·10초. 화질: 360p / 720p.
  - 영상 모델: Omni 1.1 Flash, Veo 3.1 Lite / Fast / Quality. 전부 오디오 지원(스피커 아이콘).
  - 팝업 하단에 "생성 시 N 크레딧이 사용됩니다" 표시. Omni 1.1 Flash·360p·8초·x2 = 12크레딧.
- 기본값은 이미지 모드 x2. 동영상 전환 시 개수도 x2 로 남아 있어 x1 로 명시해야 크레딧 낭비가 없다.
- 홈 배너: Google AI 구독자는 매일 50 Flow 크레딧 추가 지급.

## 2026-09-30 Flow 생성·다운로드 실측 (테스트 클립 1개 생성, 12크레딧 소모)
- 설정 순서: 칩("동영상 ·"로 시작하는 문구 또는 모델명) 클릭 → 동영상 → 9:16 → 720p → 8초 → x1 → Esc.
  설정은 프로젝트를 다시 열어도 유지되므로 매번 x1 등을 명시적으로 다시 눌러야 한다.
- 입력창은 ProseMirror. placeholder 텍스트가 아니라 `.prosemirror-editor` 를 클릭해 타이핑한다.
- 제출 버튼: `arrow_forward` 아이콘 텍스트.
- 생성 진행률은 본문에 "N%"로 표시되고, 완료되면 사라지며 그리드에 썸네일(`play_circle`)이 생긴다. 8초 720p 는 약 55초.
- 썸네일 클릭 → /project/<id>/edit/<clip-id> 편집 화면. 우상단 `download` 아이콘 → 메뉴에서 "원본 크기"(720p)는 무료, 1080p·4K 는 업그레이드 필요.
- `page.expect_download()` 로 파일 저장 가능. 결과: H.264 720x1280 24fps 8.000초, AAC 오디오 포함.
  → 렌더 단계에서 Flow 오디오는 제거하고 edge-tts 나레이션만 쓴다. 24fps 는 30fps 로 변환.
- 프로젝트 내 ffmpeg/bin/ffprobe.exe 는 이 환경에서 Permission denied. PATH 의 ffprobe/ffmpeg(WinGet 설치본)는 정상. render.py 도 PATH 를 쓴다.
- 시행착오: 셀렉터를 추측하면 두 번 실패했다. 화면/DOM 을 먼저 확인하고 짤 것.

## 2026-09-30 다운로드 방식 결정 (시행착오 기록)
- Playwright `expect_download` + `save_as`/`path()` 는 실패한다. 다운로드 이벤트 0.4초 뒤 **Chrome 이 통째로 종료**되기 때문(페이지·컨텍스트 모두 closed 이벤트). 가끔 종료 직전에 저장이 끝나 성공해서 재현이 들쭉날쭉했다.
- 응답 본문(`response.body()`)도 같은 이유로 비거나 실패.
- 채택: "원본 크기" 클릭 시 브라우저가 `flow-content.google/video/<id>?Expires=..&KeyName=..` 서명 URL 로 mp4 를 요청한다. 이 URL 만 response 이벤트로 잡고 `requests.get` 으로 직접 받는다. 3/3 성공, 파일 동일(2,008,445B).
- 그 여파로 클립마다 브라우저를 새로 띄운다: (1) 생성 세션 (2) 다운로드 세션. 생성과 다운로드를 분리해 다운로드만 무료로 재시도할 수 있게 했다(재생성 시 크레딧 낭비 방지).
- `wait_until="networkidle"` 은 Flow 가 계속 통신해 타임아웃이 난다 → `domcontentloaded` + 고정 대기.
- 설정 칩은 `aria-label="설정 트리거"`. Esc 직후 클릭은 무시되므로 열린 것을 확인하며 재클릭.
- 타일은 `alt="생성된 동영상 썸네일"` 이미지를 클릭한다(play_circle 아이콘은 이미지에 가려 클릭 불가).
- 크레딧 실측(Omni 1.1 Flash 720p x1): 4초=7, 8초=12. 길이를 맞춰 고르면 절약된다.

## 2026-09-30 크레딧 부족 확인
- 테스트 클립 1개(12크레딧) 생성 직후부터 제출 버튼이 주황 info 아이콘(aria-label="크레딧 부족 경고")으로 바뀌어 더 이상 생성 불가. 홈에 "Upgrade" 배너가 있어 무료 또는 소액 플랜으로 보임.
- 전체 실행(4세그먼트, 약 30크레딧)은 크레딧 문제로 진행하지 못함. 코드 결함이 아니다.
- 제출 전 이 아이콘을 검사해 "Flow 크레딧이 부족하다"로 즉시 폴백하도록 했다.

## 2026-10-11 모션 자막 결정
- shorts-reel-maker.skill 검토: 자막은 정적 ASS 번인, 모션 개념 없음. 클립은 Flow 가 아니라 외부 도구 전제. 스킬이 가리키는 read_calendar_slot.py·prepare_upload_kit.py·youtube_upload.py·xlsx 가 .skill 안에 없다(불완전 포팅). 인스타 절차는 우리 프로젝트(YouTube)와 무관.
- Jev(TypeSafe System One, jev-latest) 로 9/12·9/22 대본 12줄 판단: 강조효과 noul 0.30~0.87, 평균 약 0.7. 에너지는 훅 ~1.3·마지막 CTA 1~1.8, 나머지 ~0. '화려한 모션은 방해' noul 은 전 줄 ~0.8 로 변별력이 없었다(질문 문구에 '화려한'을 넣은 탓). 결론: 내용이 차분한 정보형이라 절제된 모션만 도움. 한계: Jev 는 텍스트 의미만 판단하고 시각 품질은 못 본다. 표본 12줄.
- 범위: 절제된 Remotion. 훅·마지막 자막 pop, 나머지 짧은 페이드, 키워드 색 강조. 개인 채널로 보고 Remotion 무료 라이선스(개인은 상업적 이용 포함 무료, 직원 4명 이상 영리 조직은 유료) 가정. 회사 명의면 재확인 필요.
- 구조: Remotion 이 투명 webm 오버레이를 렌더 → ffmpeg overlay. 실패하면 기존 ASS 자막으로 폴백.
- 키워드 선택은 Jev choice(후보=자막 단어), JEV_API_KEY 없거나 오류면 최장 단어.

## 2026-10-13 모션 자막 구현 결과
- After Effects: 이 PC 에 미설치(Adobe 폴더 없음), aerender 는 설치+유료 구독 필요 → 사용자가 AE 없이 Remotion 만 쓰기로 결정. Jev 는 텍스트 의미 판단 도구라 '기술적으로 가능한가'는 판단 대상이 아니다(설치·라이선스·렌더 성공 여부는 사실 확인으로 정함).
- Remotion 전용 브라우저(headless shell)는 spawn EFTYPE 으로 실행 불가(앱 제어 정책 추정). 설치된 Chrome 을 --browser-executable 로 지정해 해결. 사용자 승인 후 적용.
- 렌더: vp9 + yuva420p 투명 webm. ffmpeg 가 알파를 읽으려면 입력 앞에 `-c:v libvpx-vp9` 를 지정해야 한다.
- 폰트: remotion/public/font.ttf 로 복사해 FontFace 로 로드(gitignore, 윈도우 폰트 재배포 방지).
- 키워드는 Jev choice. '조사 포함'(예: "AI가") 단어가 선택될 수 있다. 개선 여지.
- 실패 시 overlay.webm 을 지우고 ASS 자막으로 폴백. 테스트 107개 통과(신규 motion 8 + render 3).
