import json
import asyncio
import requests
from playwright.async_api import async_playwright

COOKIE_FILE = "cookies.json"
TARGET_URL = "https://www.hairinjob.com/cms/s01.php"


async def collect_cookies_with_playwright():
    """옵션 1: Playwright로 브라우저를 열어 쿠키를 수집하고 저장합니다."""
    print(f"\n[옵션 1] Playwright로 {TARGET_URL} 접속 중...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        print(f"브라우저가 열렸습니다. 페이지 로딩 중...")
        await page.goto(TARGET_URL)

        # 페이지 로딩 대기
        await page.wait_for_load_state("networkidle")

        # 쿠키 추출
        cookies = await context.cookies()

        # 쿠키를 JSON 파일로 저장
        with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)

        print(f"\n✓ 쿠키가 '{COOKIE_FILE}' 파일에 저장되었습니다.")
        print(f"✓ 총 {len(cookies)}개의 쿠키가 수집되었습니다.")

        # 사용자가 확인할 수 있도록 대기
        print("\n브라우저를 닫으려면 Enter 키를 누르세요...")
        input()

        await browser.close()


def fetch_with_saved_cookies():
    """옵션 2: 저장된 쿠키를 사용하여 requests로 페이지를 가져옵니다."""
    print(f"\n[옵션 2] 저장된 쿠키로 {TARGET_URL} 요청 중...")

    # 쿠키 파일 확인
    try:
        with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
    except FileNotFoundError:
        print(f"\n✗ 오류: '{COOKIE_FILE}' 파일이 없습니다.")
        print("먼저 옵션 1을 실행하여 쿠키를 수집하세요.")
        return

    # Playwright 쿠키 형식을 requests 형식으로 변환
    cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}

    # User-Agent 및 헤더 설정 (실제 브라우저처럼 보이도록)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }

    # requests로 페이지 가져오기
    try:
        response = requests.get(TARGET_URL, cookies=cookie_dict, headers=headers)
        response.raise_for_status()

        # 인코딩을 euc-kr로 설정
        response.encoding = 'euc-kr'

        print(f"\n✓ 페이지를 성공적으로 가져왔습니다.")
        print(f"✓ 응답 크기: {len(response.text)} 문자")
        print(f"\n{'='*80}")
        print("페이지 내용:")
        print('='*80)
        print(response.text)
        print('='*80)

    except requests.exceptions.RequestException as e:
        print(f"\n✗ 오류 발생: {e}")


def main():
    """메인 메뉴를 표시하고 사용자 입력을 처리합니다."""
    print("\n" + "="*80)
    print("HairinJob 스크래퍼")
    print("="*80)
    print("\n선택하세요:")
    print("  1. Playwright로 쿠키 수집 및 저장")
    print("  2. 저장된 쿠키로 페이지 요청")
    print("="*80)

    choice = input("\n선택 (1 또는 2): ").strip()

    if choice == "1":
        asyncio.run(collect_cookies_with_playwright())
    elif choice == "2":
        fetch_with_saved_cookies()
    else:
        print("\n✗ 잘못된 입력입니다. 1 또는 2를 입력하세요.")


if __name__ == "__main__":
    main()
