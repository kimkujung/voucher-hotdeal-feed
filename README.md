# 상품권핫딜 공개 피드 수집기

공식 루리웹 핫딜 RSS에서 상품권 관련 제목·원문 링크·게시 시각만 추출합니다.
30분 간격의 GitHub Actions 표준 Linux 실행기용이며 AI API와 Supabase 비밀키를 사용하지 않습니다.
본문·이미지·작성자·댓글을 게시하지 않습니다. 가격은 커뮤니티 게시가격이며 판매처 검증을 뜻하지 않습니다.

저장소에는 이 README, refresh_feed.py, .github/workflows/collect.yml과 자동 생성된 data/ruliweb.xml만 올립니다.
앱 전체 소스·로컬 설정·계정 정보·서버 키를 포함하지 않습니다.

공식 RSS 안내: https://bbs.ruliweb.com/etcs/board/10/read/31
원본 피드: https://bbs.ruliweb.com/market/board/1020/rss

한 번에 GET 한 번만 요청합니다. 로그인·쿠키·리다이렉트·차단 우회·자동 재시도는 하지 않습니다.
접근 거부나 오류 시 작업이 실패하고 기존 파일을 유지합니다.
소비자는 lastBuildDate가 2시간을 넘은 피드를 새 수집 성공으로 처리하지 않아야 합니다.
GitHub 예약 작업은 지연되거나 비활동으로 중단될 수 있어 실시간 전달을 보장하지 않습니다.
