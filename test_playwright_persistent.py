"""
Playwright 영구 브라우저 컨텍스트 테스트
사용자 데이터(쿠키, 로컬스토리지 등)를 보존하고 재사용
브라우저 데이터는 일주일마다 자동으로 초기화됨
"""
import asyncio
import os
import shutil
import time
from playwright.async_api import async_playwright

BROWSER_DATA_DIR = "browser-data"  # 브라우저 데이터 영구 저장 폴더
TIMESTAMP_FILE = os.path.join(BROWSER_DATA_DIR, ".last_reset")
RESET_INTERVAL = 7 * 24 * 60 * 60  # 7일 (초 단위)
TARGET_URL = "https://www.hairinjob.com/"


def should_reset_browser_data():
    """브라우저 데이터를 초기화해야 하는지 확인"""
    if not os.path.exists(BROWSER_DATA_DIR):
        return False  # 폴더가 없으면 초기화 불필요

    if not os.path.exists(TIMESTAMP_FILE):
        # 타임스탬프 파일이 없으면 지금 생성하고 초기화 안함
        with open(TIMESTAMP_FILE, 'w') as f:
            f.write(str(time.time()))
        return False

    # 마지막 초기화 시간 확인
    with open(TIMESTAMP_FILE, 'r') as f:
        last_reset = float(f.read().strip())

    elapsed = time.time() - last_reset
    return elapsed > RESET_INTERVAL


def reset_browser_data():
    """브라우저 데이터 초기화"""
    if os.path.exists(BROWSER_DATA_DIR):
        print(f"브라우저 데이터 초기화 중... (일주일 경과)")
        shutil.rmtree(BROWSER_DATA_DIR)
        print("✓ 브라우저 데이터 삭제 완료")

    # 새 타임스탬프 기록
    os.makedirs(BROWSER_DATA_DIR, exist_ok=True)
    with open(TIMESTAMP_FILE, 'w') as f:
        f.write(str(time.time()))


async def open_persistent_browser():
    """영구 브라우저 컨텍스트로 hairinjob.com 열기"""
    # 일주일 경과 확인 및 초기화
    if should_reset_browser_data():
        reset_browser_data()
    else:
        # 타임스탬프 파일이 없으면 생성 (첫 실행)
        if not os.path.exists(TIMESTAMP_FILE):
            os.makedirs(BROWSER_DATA_DIR, exist_ok=True)
            with open(TIMESTAMP_FILE, 'w') as f:
                f.write(str(time.time()))

    print(f"브라우저 데이터 디렉토리: {BROWSER_DATA_DIR}")

    # 마지막 초기화로부터 경과 시간 표시
    if os.path.exists(TIMESTAMP_FILE):
        with open(TIMESTAMP_FILE, 'r') as f:
            last_reset = float(f.read().strip())
        elapsed_days = (time.time() - last_reset) / (24 * 60 * 60)
        print(f"마지막 초기화로부터 {elapsed_days:.1f}일 경과 (7일마다 자동 초기화)")

    print("영구 브라우저 컨텍스트 실행 중...")
    print("(이전 세션의 쿠키와 로그인 정보가 자동으로 유지됩니다)")

    async with async_playwright() as p:
        # 영구 컨텍스트로 브라우저 실행
        context = await p.chromium.launch_persistent_context(
            BROWSER_DATA_DIR,
            headless=False,  # 브라우저 창을 보이게
            args=[
                '--disable-blink-features=AutomationControlled',  # 자동화 감지 우회
            ],
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

        # 페이지 생성
        page = context.pages[0] if context.pages else await context.new_page()

        print(f"\n{TARGET_URL} 이동 중...")
        await page.goto(TARGET_URL, wait_until='networkidle')
        print("✓ 페이지 로드 완료")

        # 새로고침
        print("\n페이지 새로고침 중...")
        await page.reload(wait_until='networkidle')
        print("✓ 새로고침 완료")

        # 4초 대기
        print("페이지 안정화 대기 중... (4초)")
        await asyncio.sleep(4)

        # 로그인 상태 확인
        print("\n로그인 상태 확인 중...")
        page_content = await page.content()

        LOGIN_URL = "https://www.hairinjob.com/cms/user/login.php"
        LOGOUT_URL = "https://www.hairinjob.com/member/login_ok.php?del=1"

        is_logged_in = False
        if LOGOUT_URL in page_content:
            is_logged_in = True
            print("✅ 로그인 상태: 로그인됨")
        elif LOGIN_URL in page_content:
            is_logged_in = False
            print("❌ 로그인 상태: 로그인 안됨")
        else:
            print("⚠️  로그인 상태: 확인 불가 (페이지 구조 변경 가능성)")

        # 로그인 안되어 있으면 로그인 페이지로 이동
        if not is_logged_in:
            print("\n로그인 페이지로 이동 중...")
            await page.goto(LOGIN_URL, wait_until='networkidle')
            print(f"✓ 로그인 페이지 로드 완료: {LOGIN_URL}")

            # 자동 로그인 시도
            print("\n자동 로그인 진행 중...")
            try:
                # 아이디 입력
                await page.fill('input[name="mb_id"]', '01028721278')
                print("✓ 아이디 입력 완료")

                # 비밀번호 입력
                await page.fill('input[name="mb_password"]', '235194')
                print("✓ 비밀번호 입력 완료")

                # 10초 대기
                print("10초 대기 중...")
                await asyncio.sleep(10)
                print("✓ 대기 완료")

                print("\n안내: 로그인 버튼을 확인하거나 자동 로그인이 완료되었는지 확인하세요.")
                print("다음 실행부터는 자동으로 로그인 상태가 유지됩니다.")

            except Exception as e:
                print(f"⚠️  자동 로그인 오류: {e}")
                print("수동으로 로그인해주세요.")

        print("\n브라우저가 열려 있습니다.")
        print("사이트를 자유롭게 탐색하거나 로그인하세요.")
        print("종료하려면 이 터미널에서 Ctrl+C를 누르세요.")
        print("(다음 실행 시 현재 상태가 그대로 유지됩니다)")

        # 사용자가 종료할 때까지 대기
        try:
            await asyncio.sleep(3600)  # 1시간 대기 (또는 수동 종료)
        except KeyboardInterrupt:
            print("\n\n브라우저 종료 중...")

        await context.close()
        print("✓ 브라우저 데이터 저장 완료")


if __name__ == "__main__":
    asyncio.run(open_persistent_browser())
