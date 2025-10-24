import json
import asyncio
import requests
import os
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

COOKIE_FILE = "cookies.json"
TARGET_URL = "https://www.hairinjob.com/cms/s01.php"
RESULT_DIR = "scraping-result"


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


def parse_job_listings(html_content):
    """HTML에서 채용 공고 목록을 파싱하여 JSON 형태로 변환합니다."""
    soup = BeautifulSoup(html_content, 'lxml')
    job_listings = []

    # 모든 채용 항목 찾기
    job_rows = soup.find_all('tr', class_='line01')

    for row in job_rows:
        try:
            job_data = {}

            # idx 추출
            scrap_link = row.find('a', href=lambda x: x and 'scrap_check' in x)
            if scrap_link:
                idx = scrap_link['href'].split("'")[3]
                job_data['idx'] = idx

            # 회사명 추출
            company_span = row.find('span', class_='span0101')
            if company_span:
                company_text = company_span.get_text(strip=True)
                # '찜하기' 텍스트 제거
                company_name = company_text.replace('찜하기', '').strip()
                job_data['company_name'] = company_name

            # 공고 제목 추출
            title_links = row.find_all('a', title='상세채용정보보기')
            for link in title_links:
                if 's01_v.php' in link.get('href', ''):
                    # style 속성이 있고 텍스트가 있는 링크 찾기
                    if link.get('style') and link.get_text(strip=True):
                        job_data['title'] = link.get_text(strip=True)
                        job_data['detail_url'] = link['href']
                        break

            # 모집 직종 추출
            position_span = row.find('span', class_='span0301')
            if position_span:
                job_data['positions'] = position_span.get_text(strip=True)

            # 근무지역, 급여, 성별, 마감일 추출
            info_span = row.find('span', class_='span0302')
            if info_span:
                # <span class='pay'> 태그 내용을 먼저 추출
                pay_span = info_span.find('span', class_='pay')
                pay_text = pay_span.get_text(strip=True) if pay_span else ''

                # 전체 텍스트 가져오기
                info_text = info_span.get_text(strip=True)
                parts = info_text.split('　')

                if len(parts) >= 1:
                    job_data['location'] = parts[0].replace('#', '').strip()
                if len(parts) >= 2:
                    salary_part = parts[1].replace('#', '').strip()
                    # pay_text가 있으면 사용, 없으면 전체 사용
                    if pay_text:
                        job_data['salary'] = pay_text + salary_part.replace(pay_text, '')
                    else:
                        job_data['salary'] = salary_part
                if len(parts) >= 3:
                    job_data['gender'] = parts[2].replace('#', '').strip()
                if len(parts) >= 4:
                    job_data['deadline'] = parts[3].replace('#', '').strip()

            # 등급 추출 (VVIP, VIP 등)
            grade_span = row.find('span', class_=lambda x: x and 'css_' in x if x else False)
            if grade_span:
                job_data['grade'] = grade_span.get_text(strip=True)

            # 우선 배지 확인
            priority_badge = row.find('span', class_='icon_top')
            if priority_badge:
                job_data['priority_badge'] = priority_badge.get_text(strip=True)

            # 특수 배지 확인 (급구, 최고 등)
            special_badges = []
            for badge_class in ['icon_mini21', 'icon_mini23']:
                badge = row.find('span', class_=badge_class)
                if badge:
                    special_badges.append(badge.get_text(strip=True))
            if special_badges:
                job_data['special_badges'] = special_badges

            job_listings.append(job_data)

        except Exception as e:
            print(f"항목 파싱 중 오류: {e}")
            continue

    return job_listings


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

        # HTML 파싱
        print(f"\n파싱 중...")
        job_listings = parse_job_listings(response.text)
        print(f"✓ {len(job_listings)}개의 채용 공고를 파싱했습니다.")

        # 결과 디렉토리 생성
        if not os.path.exists(RESULT_DIR):
            os.makedirs(RESULT_DIR)
            print(f"✓ '{RESULT_DIR}' 디렉토리를 생성했습니다.")

        # 현재 날짜/시간으로 파일명 생성
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_file = os.path.join(RESULT_DIR, f"hairinjob_{timestamp}.json")

        # JSON 파일로 저장
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(job_listings, f, indent=2, ensure_ascii=False)

        print(f"\n✓ 결과를 '{output_file}' 파일에 저장했습니다.")

        # 결과 미리보기 (처음 3개)
        print(f"\n{'='*80}")
        print("결과 미리보기 (처음 3개):")
        print('='*80)
        for i, job in enumerate(job_listings[:3], 1):
            print(f"\n[{i}] {job.get('company_name', 'N/A')}")
            print(f"    제목: {job.get('title', 'N/A')}")
            print(f"    직종: {job.get('positions', 'N/A')}")
            print(f"    위치: {job.get('location', 'N/A')}")
            print(f"    급여: {job.get('salary', 'N/A')}")
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
