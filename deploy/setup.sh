#!/bin/bash
# 거지세끼 맥미니 배포 스크립트
# 사용법: bash deploy/setup.sh

set -e

PROJECT_DIR="/Users/zzimong/geoji-sekki"
PLIST_NAME="com.zzimong.geojisekki.plist"

echo "🍚 거지세끼 배포 시작"

# 1. Python 가상환경 + 패키지 설치
echo "📦 Python 패키지 설치..."
cd "$PROJECT_DIR/backend"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Playwright 브라우저 설치 (올리브영/다이소용)
echo "🌐 Playwright Chromium 설치..."
playwright install chromium

# 3. Frontend 빌드
echo "🎨 프론트엔드 빌드..."
cd "$PROJECT_DIR/frontend"
npm install
npm run build

# 4. 디렉토리 확인
mkdir -p "$PROJECT_DIR/data" "$PROJECT_DIR/logs"

# 5. .env 파일 확인
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "⚠️  .env 파일이 없습니다. .env.example을 복사합니다."
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo "📝 .env 파일을 편집하세요: nano $PROJECT_DIR/.env"
fi

# 6. launchd 서비스 등록
echo "🚀 launchd 서비스 등록..."
cp "$PROJECT_DIR/deploy/$PLIST_NAME" ~/Library/LaunchAgents/
launchctl unload ~/Library/LaunchAgents/$PLIST_NAME 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/$PLIST_NAME

echo ""
echo "✅ 배포 완료!"
echo "  - API: http://localhost:8100/api/health"
echo "  - 도메인: https://geoji-sekki.zzimong.com"
echo ""
echo "📋 관리 명령어:"
echo "  launchctl stop com.zzimong.geojisekki    # 서비스 중지"
echo "  launchctl start com.zzimong.geojisekki   # 서비스 시작"
echo "  tail -f $PROJECT_DIR/logs/crawler.log     # 로그 확인"
