import json
import asyncio
import requests
import os
import re
import sys
import argparse
import random
from datetime import datetime
from bs4 import BeautifulSoup, SoupStrainer
from playwright.async_api import async_playwright
from storage.factory import create_storage

COOKIE_DIR = "cookies"
COOKIE_FILE = os.path.join(COOKIE_DIR, "cookies.json")
TARGET_URL = "https://www.hairinjob.com/cms/s01.php"
RESULT_DIR = "scraping-result"


async def collect_cookies_with_playwright():
    """옵션 1: Playwright로 브라우저를 열어 쿠키를 수집하고 저장합니다."""
    import glob

    print(f"\n[옵션 1] 쿠키 세트 10개 수집")

    # cookies 폴더 생성
    if not os.path.exists(COOKIE_DIR):
        os.makedirs(COOKIE_DIR)
        print(f"✓ '{COOKIE_DIR}' 폴더 생성")

    # 기존 쿠키 파일 모두 삭제
    existing_cookies = glob.glob(os.path.join(COOKIE_DIR, "cookies_*.json"))
    if existing_cookies:
        print(f"\n기존 쿠키 파일 {len(existing_cookies)}개 삭제 중...")
        for cookie_file in existing_cookies:
            os.remove(cookie_file)
        print(f"✓ 기존 쿠키 파일 삭제 완료")

    async with async_playwright() as p:
        for i in range(1, 11):
            print(f"\n[{i}/10] 쿠키 세트 {i} 수집 중...")

            # 새로운 브라우저 컨텍스트 (독립적인 세션)
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()

            print(f"  브라우저가 열렸습니다. 페이지 로딩 중...")
            await page.goto(TARGET_URL)

            # 페이지 로딩 대기
            await page.wait_for_load_state("networkidle")

            # 쿠키 추출
            cookies = await context.cookies()

            # PHPSESSID 찾기
            phpsessid = next((c['value'] for c in cookies if c['name'] == 'PHPSESSID'), 'N/A')

            # 파일명: cookies/cookies_1.json, cookies/cookies_2.json, ...
            cookie_file = os.path.join(COOKIE_DIR, f"cookies_{i}.json")
            with open(cookie_file, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, indent=2, ensure_ascii=False)

            print(f"✓ {cookie_file} 저장 완료 (PHPSESSID: {phpsessid[:15]}...)")

            await browser.close()

            # 다음 세션 수집 전 대기 (서버 부하 고려)
            if i < 10:
                import random
                import time
                delay = random.uniform(2, 5)
                print(f"  다음 세션까지 {delay:.1f}초 대기...")
                time.sleep(delay)

        print(f"\n{'='*80}")
        print("✓ 총 10개의 쿠키 세트 수집 완료!")
        print('='*80)


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


def get_last_page_number(html_content):
    """HTML에서 마지막 페이지 번호를 자동으로 감지합니다."""
    soup = BeautifulSoup(html_content, 'lxml')

    # nav_l.gif 이미지를 찾음 (마지막 페이지로 이동하는 버튼)
    nav_img = soup.find('img', src='/images/newhair/nav_l.gif')

    if nav_img and nav_img.parent.name == 'a':
        href = nav_img.parent.get('href', '')
        # page=숫자 패턴 매칭
        match = re.search(r'page=(\d+)', href)
        if match:
            return int(match.group(1))

    return None


def fetch_phone_from_detail(idx, cookie_dict):
    """상세 페이지에서 핸드폰 번호를 추출합니다. (경량화 버전)"""
    detail_url = f"https://www.hairinjob.com/cms/s01_v.php?idx={idx}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html',  # 최적화: 이미지/CSS/JS 제외
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Referer': 'https://www.hairinjob.com/cms/s01.php',
        'Upgrade-Insecure-Requests': '1'
    }

    try:
        response = requests.get(detail_url, cookies=cookie_dict, headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = 'euc-kr'

        # 최적화: SoupStrainer로 template_content div만 파싱 (span과 div 모두 포함)
        only_content = SoupStrainer('div', id='template_content')
        soup = BeautifulSoup(response.text, 'lxml', parse_only=only_content)

        # "상세내용" 라벨을 가진 bottom_textbox 찾기
        all_textboxes = soup.find_all('div', class_='bottom_textbox')
        for textbox in all_textboxes:
            prev_sibling = textbox.find_previous_sibling()
            if prev_sibling and '상세내용' in prev_sibling.get_text(strip=True):
                detail_content = textbox.get_text(strip=True)

                # 핸드폰 번호 추출 (010만 허용)
                phone_pattern = r'010[-.\s]?\d{3,4}[-.\s]?\d{4}'
                phone_numbers = re.findall(phone_pattern, detail_content)

                if phone_numbers:
                    # 첫 번째 번호 반환 (중복 가능성 있으므로)
                    return phone_numbers[0]
                break

        return None

    except Exception as e:
        # 에러 발생 시 None 반환 (계속 진행)
        print(f"  ⚠ idx={idx} 상세페이지 오류: {e}")
        return None


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


def scrape_with_cookie(cookie_idx, cookie_file, start_page, end_page, storage, num_cookies):
    """특정 쿠키로 할당된 페이지 범위를 스크래핑합니다."""
    import random
    import time

    print(f"\n{'='*80}")
    print(f"[쿠키 세트 {cookie_idx}/{num_cookies}] {os.path.basename(cookie_file)}")
    print(f"페이지 범위: {start_page}~{end_page} ({end_page - start_page + 1}페이지)")
    print('='*80)

    # 쿠키 로드
    with open(cookie_file, 'r', encoding='utf-8') as f:
        cookies = json.load(f)
    cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}

    jobs_collected = []

    # 페이지별 스크래핑
    total_pages_in_range = end_page - start_page + 1
    for page_num in range(start_page, end_page + 1):
        current_page_index = page_num - start_page + 1
        progress = (current_page_index / total_pages_in_range) * 100

        print(f"\n  [{cookie_idx}] [{current_page_index}/{total_pages_in_range}] 페이지 {page_num} 스크래핑 중... ({progress:.1f}%)")

        # URL 구성
        if page_num == 1:
            url = TARGET_URL
            referer = TARGET_URL
        else:
            url = f"{TARGET_URL}?page={page_num}"
            referer = f"{TARGET_URL}?page={page_num - 1}"

        # User-Agent 및 헤더 설정
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': referer,
            'Upgrade-Insecure-Requests': '1'
        }

        # 페이지 요청
        try:
            response = requests.get(url, cookies=cookie_dict, headers=headers)
            response.raise_for_status()
            response.encoding = 'euc-kr'

            # HTML 파싱
            job_listings = parse_job_listings(response.text)
            print(f"  [{cookie_idx}] ✓ {len(job_listings)}개 항목 파싱 완료")

            # # 각 항목의 상세페이지에서 핸드폰 번호 추출
            # print(f"  [{cookie_idx}] 상세페이지에서 핸드폰 번호 수집 중...")
            # for i, job in enumerate(job_listings, 1):
            #     idx = job.get('idx')
            #     if idx:
            #         phone = fetch_phone_from_detail(idx, cookie_dict)
            #         if phone:
            #             job['phone'] = phone
            #
            #         # 상세 요청 간 짧은 딜레이 (0.5~1초)
            #         if i < len(job_listings):
            #             time.sleep(random.uniform(0.5, 1))
            #
            # print(f"  [{cookie_idx}] ✓ 핸드폰 번호 수집 완료")

            # Storage를 통한 저장
            storage.save_jobs(job_listings, page_num, cookie_idx)
            print(f"  [{cookie_idx}] ✓ 저장 완료")

            # 전체 목록에 추가
            jobs_collected.extend(job_listings)

            # 마지막 페이지가 아니면 랜덤 딜레이
            if page_num < end_page:
                delay = random.uniform(1, 3)
                print(f"  [{cookie_idx}] 딜레이: {delay:.1f}초...")
                time.sleep(delay)

        except requests.exceptions.RequestException as e:
            print(f"\n  [{cookie_idx}] ✗ 오류 발생: {e}")
            print(f"  [{cookie_idx}] 쿠키 세트 {cookie_idx}의 나머지 페이지를 건너뜁니다.")
            break  # 이 쿠키의 나머지 페이지 스킵

    print(f"\n[쿠키 세트 {cookie_idx}] 완료! 총 {len(jobs_collected)}개 항목 수집")
    return jobs_collected


def fetch_multiple_pages(storage_type='json', skip_pages=False):
    """옵션 3: 저장된 쿠키를 사용하여 여러 페이지를 스크래핑합니다."""
    import random
    import time
    import glob
    from concurrent.futures import ThreadPoolExecutor, as_completed

    print(f"\n[옵션 3] 다중 페이지 스크래핑 (병렬 처리)")
    print(f"저장 방식: {storage_type}")
    if skip_pages:
        print(f"모드: 페이지 스크래핑 건너뛰기 (상세페이지만)")

    # 쿠키 파일 개수 확인
    cookie_files = sorted(glob.glob(os.path.join(COOKIE_DIR, "cookies_*.json")))
    num_cookies = len(cookie_files)

    if num_cookies == 0:
        print(f"\n✗ 오류: 쿠키 파일이 없습니다.")
        print("먼저 옵션 1을 실행하여 쿠키를 수집하세요.")
        return

    print(f"✓ {num_cookies}개의 쿠키 세트 발견")

    # skip_pages가 True면 페이지 스크래핑 건너뛰고 바로 상세페이지로
    if skip_pages:
        print("\n페이지 스크래핑을 건너뛰고 상세페이지 스크래핑을 시작합니다...")

        # Storage 생성 (상세페이지에서 사용)
        storage = create_storage(storage_type, result_dir=RESULT_DIR)

        # 빈 all_jobs로 상세페이지 스크래핑 시작 (DB나 이전 결과에서 가져올 수 있음)
        all_jobs = []

        # 상세페이지 스크래핑 함수 호출
        scrape_detail_pages(all_jobs, cookie_files, storage)

        storage.close()
        return

    # 첫 번째 쿠키로 마지막 페이지 감지
    with open(cookie_files[0], 'r', encoding='utf-8') as f:
        cookies = json.load(f)
    cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}

    # User-Agent 및 헤더 설정
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }

    # 첫 페이지를 먼저 요청하여 마지막 페이지 번호 감지
    print(f"\n마지막 페이지 번호 감지 중...")
    try:
        response = requests.get(TARGET_URL, cookies=cookie_dict, headers=headers)
        response.raise_for_status()
        response.encoding = 'euc-kr'

        last_page = get_last_page_number(response.text)

        if last_page is None:
            print(f"\n✗ 오류: 마지막 페이지 번호를 감지할 수 없습니다.")
            print("HTML 구조가 변경되었을 수 있습니다.")
            print("프로그램을 종료합니다.")
            return

        print(f"✓ 마지막 페이지 감지 완료: {last_page}페이지")

    except requests.exceptions.RequestException as e:
        print(f"\n✗ 오류 발생: {e}")
        print("프로그램을 종료합니다.")
        return

    # 페이지 범위 분할
    pages_per_cookie = last_page // num_cookies
    remainder = last_page % num_cookies

    ranges = []
    start = 1
    for i in range(num_cookies):
        extra = 1 if i < remainder else 0
        end = start + pages_per_cookie - 1 + extra
        ranges.append((start, end))
        start = end + 1

    print(f"\n페이지 분할:")
    for i, (s, e) in enumerate(ranges, 1):
        print(f"  쿠키 세트 {i}: 페이지 {s}~{e} ({e-s+1}페이지)")

    # Storage 생성
    storage = create_storage(storage_type, result_dir=RESULT_DIR)
    session_id = storage.start_session(last_page, num_cookies)

    all_jobs = []

    # 시작 시간 기록
    start_time = time.time()

    # 병렬 처리로 각 쿠키 세트 동시 실행
    print(f"\n병렬 처리 시작 ({num_cookies}개 쿠키 세트 동시 실행)...")

    try:
        with ThreadPoolExecutor(max_workers=num_cookies) as executor:
            # 모든 쿠키 세트에 대한 작업 제출
            futures = {}
            for cookie_idx, (start_page, end_page) in enumerate(ranges, 1):
                cookie_file = cookie_files[cookie_idx - 1]
                future = executor.submit(
                    scrape_with_cookie,
                    cookie_idx,
                    cookie_file,
                    start_page,
                    end_page,
                    storage,
                    num_cookies
                )
                futures[future] = cookie_idx

            # 완료된 작업 결과 수집
            for future in as_completed(futures):
                cookie_idx = futures[future]
                try:
                    jobs = future.result()
                    all_jobs.extend(jobs)
                    print(f"\n✓ 쿠키 세트 {cookie_idx} 결과 수집 완료")
                except Exception as e:
                    print(f"\n✗ 쿠키 세트 {cookie_idx} 오류: {e}")
    finally:
        # Storage 세션 완료 및 리소스 정리
        total_jobs = len(all_jobs)
        storage.complete_session(session_id, total_jobs, 0, 0)
        storage.close()

    # 종료 시간 기록 및 소요 시간 계산
    end_time = time.time()
    elapsed_time = end_time - start_time
    elapsed_minutes = int(elapsed_time // 60)
    elapsed_seconds = int(elapsed_time % 60)

    # 모든 페이지 완료 요약
    print(f"\n{'='*80}")
    print("모든 페이지 스크래핑 완료!")
    print(f"총 {len(all_jobs)}개 항목 수집")
    print(f"소요 시간: {elapsed_minutes}분 {elapsed_seconds}초")
    print('='*80)

    # 상세페이지 스크래핑 시작
    scrape_detail_pages(all_jobs, cookie_files, storage)


def scrape_detail_pages(all_jobs, cookie_files, storage):
    """
    모든 채용공고의 상세페이지를 스크래핑합니다.
    Playwright 영구 브라우저를 사용하여 로그인 상태 유지

    Args:
        all_jobs: 수집된 모든 채용공고 리스트
        cookie_files: 쿠키 파일 경로 리스트
        storage: Storage 객체 (json/db/both)
    """
    print(f"\n{'='*80}")
    print("상세페이지 스크래핑 시작")
    print(f"대상: {len(all_jobs)}개 채용공고")
    print('='*80)

    # Playwright 영구 브라우저로 로그인 세션 시작
    print("\nPlaywright 영구 브라우저 시작 중...")
    import asyncio
    asyncio.run(start_playwright_detail_scraping(all_jobs, storage))

    print(f"\n{'='*80}")
    print("상세페이지 스크래핑 완료")
    print('='*80)


async def start_playwright_detail_scraping(all_jobs, storage):
    """Playwright로 영구 브라우저 세션을 시작하고 로그인 후 상세페이지 스크래핑"""
    import os
    import shutil
    import time
    from playwright.async_api import async_playwright

    BROWSER_DATA_DIR = "browser-data"
    TIMESTAMP_FILE = os.path.join(BROWSER_DATA_DIR, ".last_reset")
    RESET_INTERVAL = 7 * 24 * 60 * 60  # 7일
    TARGET_URL = "https://www.hairinjob.com/"
    LOGIN_URL = "https://www.hairinjob.com/cms/user/login.php"
    LOGOUT_URL = "https://www.hairinjob.com/member/login_ok.php?del=1"

    # 브라우저 데이터 초기화 확인
    if os.path.exists(TIMESTAMP_FILE):
        with open(TIMESTAMP_FILE, 'r') as f:
            last_reset = float(f.read().strip())
        if time.time() - last_reset > RESET_INTERVAL:
            print("브라우저 데이터 초기화 중... (일주일 경과)")
            shutil.rmtree(BROWSER_DATA_DIR)
            print("✓ 브라우저 데이터 삭제 완료")

    # 타임스탬프 생성
    os.makedirs(BROWSER_DATA_DIR, exist_ok=True)
    if not os.path.exists(TIMESTAMP_FILE):
        with open(TIMESTAMP_FILE, 'w') as f:
            f.write(str(time.time()))

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            BROWSER_DATA_DIR,
            headless=False,
            args=['--disable-blink-features=AutomationControlled'],
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )

        page = context.pages[0] if context.pages else await context.new_page()

        # 페이지 로드 및 로그인 확인
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

        is_logged_in = LOGOUT_URL in page_content

        if is_logged_in:
            print("✅ 로그인 상태: 로그인됨")
        else:
            print("❌ 로그인 상태: 로그인 안됨")
            print("\n로그인 페이지로 이동 중...")
            await page.goto(LOGIN_URL, wait_until='networkidle')
            print(f"✓ 로그인 페이지 로드 완료")

            # 자동 로그인
            print("\n자동 로그인 진행 중...")
            try:
                # 아이디 입력 (input name="userid" 중 첫번째)
                await page.locator('input[name="userid"]').first.fill('01028721278')
                print("✓ 아이디 입력 완료")

                # 비밀번호 입력 (input name="pwd" 중 첫번째)
                await page.locator('input[name="pwd"]').first.fill('235194')
                print("✓ 비밀번호 입력 완료")

                # 3초 대기
                print("로그인 버튼 클릭 전 대기 중... (3초)")
                await asyncio.sleep(3)

                # 로그인 버튼 클릭 (button class="btn_login" 중 첫번째)
                await page.locator('button.btn_login').first.click()
                print("✓ 로그인 버튼 클릭 완료")

                # 마이페이지 도착 대기
                print("마이페이지 로드 대기 중...")
                await page.wait_for_url('https://www.hairinjob.com/cms/p/mypage.php', timeout=30000)
                print("✓ 마이페이지 도착 완료")

            except Exception as e:
                print(f"⚠️  자동 로그인 오류: {e}")

        print("\n✓ 로그인 세션 준비 완료")

        # 로그인된 브라우저에서 쿠키 추출
        print("\n쿠키 추출 중...")
        cookies = await context.cookies()

        # requests 라이브러리에서 사용할 수 있는 형식으로 변환
        cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
        print(f"✓ 쿠키 추출 완료 (총 {len(cookie_dict)}개)")

        # DB에서 상세페이지 URL 조회
        print("\nDB에서 상세페이지 URL 조회 중...")
        from db.database import get_db_connection
        from db.queries import get_all_detail_urls

        with get_db_connection() as conn:
            detail_jobs = get_all_detail_urls(conn)
            print(f"✓ 상세페이지 URL 조회 완료 (총 {len(detail_jobs)}개)")

        # 상세페이지 스크래핑 준비 완료
        print("\n✅ 상세페이지 스크래핑 준비 완료")
        print(f"   - 로그인 쿠키: {len(cookie_dict)}개")
        print(f"   - 스크래핑 대상: {len(detail_jobs)}개 채용공고")

        # 브라우저 종료 (requests로 처리)
        await context.close()
        print("\n✓ 브라우저 세션 종료")

        # 첫 10개만 테스트 스크래핑
        test_jobs = detail_jobs[:10]
        print(f"\n테스트 스크래핑 시작: 첫 {len(test_jobs)}개 채용공고")

        # requests 헤더 설정
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://www.hairinjob.com/cms/s01.php',
            'Upgrade-Insecure-Requests': '1'
        }

        # 상세페이지 스크래핑
        for idx, job in enumerate(test_jobs, 1):
            job_idx = job['idx']
            detail_url = job['detail_url']
            company_name = job['company_name']
            title = job['title']

            # detail_url에 host가 없으면 추가
            if detail_url and not detail_url.startswith('http'):
                detail_url = f"https://www.hairinjob.com{detail_url}"

            print(f"\n[{idx}/{len(test_jobs)}] {company_name} - {title}")
            print(f"  URL: {detail_url}")

            try:
                # 페이지 요청
                response = requests.get(detail_url, cookies=cookie_dict, headers=headers, timeout=10)
                response.raise_for_status()
                response.encoding = 'euc-kr'

                # HTML 파싱
                soup = BeautifulSoup(response.text, 'lxml')

                # 헤더 정보 추출 (업체주소, 전화번호, 채용담당자, 담당자연락처)
                company_address = None
                company_phone = None
                recruiter_name = None
                recruiter_contact = None

                found_fields = set()
                left_items = soup.find_all('li', class_='left')

                for left_li in left_items:
                    # 4개 모두 찾았으면 조기 종료
                    if len(found_fields) >= 4:
                        break

                    label = left_li.get_text(strip=True)

                    # 이미 찾은 필드는 스킵
                    if label in found_fields:
                        continue

                    right_li = left_li.find_next_sibling('li', class_='right')
                    if not right_li:
                        continue

                    if label == '업체주소':
                        company_address = right_li.get_text(strip=True)
                        found_fields.add('업체주소')

                    elif label == '전화번호':
                        span = right_li.find('span')
                        if span:
                            company_phone = span.get_text(strip=True)
                            found_fields.add('전화번호')

                    elif label == '채용담당자':
                        span = right_li.find('span')
                        if span:
                            recruiter_name = span.get_text(strip=True)
                            found_fields.add('채용담당자')

                    elif label == '담당자연락처':
                        text = right_li.get_text(strip=True)
                        if text:
                            parts = text.split()
                            if parts:
                                recruiter_contact = parts[0]
                                found_fields.add('담당자연락처')

                print(f"  헤더 정보: 업체주소={bool(company_address)}, 전화번호={bool(company_phone)}, "
                      f"담당자={bool(recruiter_name)}, 담당자연락처={bool(recruiter_contact)}")

                # "상세내용" 라벨을 가진 bottom_textbox 찾기 (상세요강 속 핸드폰)
                detail_content = None
                phone = None

                for textbox in soup.find_all('div', class_='bottom_textbox'):
                    prev_sibling = textbox.find_previous_sibling()
                    if prev_sibling and '상세내용' in prev_sibling.get_text(strip=True):
                        detail_content = textbox.get_text(strip=True)
                        break

                if detail_content:
                    # 핸드폰 번호 추출 (010만 허용)
                    phone_pattern = r'010[-.\s]?\d{3,4}[-.\s]?\d{4}'
                    phone_numbers = re.findall(phone_pattern, detail_content)

                    if phone_numbers:
                        # 중복 제거 및 첫 번째 번호 사용
                        unique_phones = list(set(phone_numbers))
                        phone = unique_phones[0]
                        print(f"  ✓ 상세요강 전화번호: {phone}")
                    else:
                        print(f"  - 상세요강 전화번호 없음")
                else:
                    print(f"  - 상세내용 섹션 없음")

                # DB 업데이트 (헤더 정보 + 상세요강 전화번호)
                from db.database import get_db_connection
                from db.queries import batch_insert_jobs

                with get_db_connection() as conn:
                    job_data = {
                        'idx': job_idx,
                        'company_name': company_name,
                        'title': title,
                        'detail_url': detail_url,
                        'phone': phone,
                        'company_address': company_address,
                        'company_phone': company_phone,
                        'recruiter_name': recruiter_name,
                        'recruiter_contact': recruiter_contact,
                        'positions': '',
                        'location': '',
                        'salary': '',
                        'gender': '',
                        'deadline': '',
                        'grade': '',
                        'priority_badge': '',
                        'special_badges': []
                    }
                    batch_insert_jobs(conn, [job_data], page_num=0, cookie_idx=0, session_id=job.get('session_id'))
                    conn.commit()
                    print(f"  ✓ DB 업데이트 완료")

                # 요청 간 랜덤 딜레이 (0.3~1.0초)
                delay = random.uniform(0.3, 1.0)
                print(f"  ⏱️  {delay:.2f}초 대기 중...")
                await asyncio.sleep(delay)

            except Exception as e:
                print(f"  ✗ 오류: {e}")
                continue

        print(f"\n✅ 테스트 스크래핑 완료 ({len(test_jobs)}개 처리)")


def fetch_detail_page():
    """옵션 4: 상세 페이지를 가져와서 콘솔에 출력합니다."""
    print(f"\n[옵션 4] 상세 페이지 스크래핑")

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

    # 테스트 URL
    detail_url = "https://www.hairinjob.com/cms/s01_v.php?idx=101200"

    # User-Agent 및 헤더 설정
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Referer': 'https://www.hairinjob.com/cms/s01.php',
        'Upgrade-Insecure-Requests': '1'
    }

    # 페이지 요청
    try:
        print(f"\n{detail_url} 요청 중...")
        response = requests.get(detail_url, cookies=cookie_dict, headers=headers)
        response.raise_for_status()

        # 인코딩을 euc-kr로 설정
        response.encoding = 'euc-kr'

        print(f"\n✓ 페이지를 성공적으로 가져왔습니다.")
        print(f"✓ 응답 크기: {len(response.text)} 문자")

        # HTML 파싱
        soup = BeautifulSoup(response.text, 'lxml')

        # "상세내용" 라벨을 가진 bottom_textbox 찾기
        detail_content = None
        for textbox in soup.find_all('div', class_='bottom_textbox'):
            prev_sibling = textbox.find_previous_sibling()
            if prev_sibling and '상세내용' in prev_sibling.get_text(strip=True):
                detail_content = textbox.get_text(strip=True)
                break

        if detail_content:
            print(f"\n{'='*80}")
            print("상세내용 (상세요강):")
            print('='*80)
            print(detail_content)
            print('='*80)

            # 핸드폰 번호 추출 (010만 허용)
            phone_pattern = r'010[-.\s]?\d{3,4}[-.\s]?\d{4}'
            phone_numbers = re.findall(phone_pattern, detail_content)

            if phone_numbers:
                # 중복 제거
                unique_phones = list(set(phone_numbers))
                print(f"\n✓ 찾은 핸드폰 번호: {unique_phones}")
            else:
                print(f"\n✗ 핸드폰 번호를 찾을 수 없습니다.")

        else:
            print(f"\n✗ 상세내용을 찾을 수 없습니다.")

    except requests.exceptions.RequestException as e:
        print(f"\n✗ 오류 발생: {e}")


def main():
    """메인 함수: 커맨드라인 인자를 파싱하여 모드를 실행합니다."""
    parser = argparse.ArgumentParser(
        description='HairinJob 스크래퍼 - 채용 정보 수집 도구',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python main.py --mode collect-cookies    # 쿠키 수집
  python main.py --mode test-page          # 1페이지 테스트
  python main.py --mode scrape-all         # 전체 페이지 스크래핑
  python main.py --mode test-detail        # 상세 페이지 테스트
        """
    )

    parser.add_argument(
        '--mode',
        type=str,
        required=True,
        choices=['collect-cookies', 'test-page', 'scrape-all', 'test-detail'],
        help='실행 모드 선택 (필수)'
    )

    parser.add_argument(
        '--storage',
        type=str,
        choices=['json', 'db', 'both'],
        help='저장 방식 선택 (scrape-all 모드 전용, 필수)'
    )

    parser.add_argument(
        '--skip-pages',
        action='store_true',
        help='페이지 스크래핑 건너뛰기 (scrape-all 모드 전용, 상세페이지만 스크래핑)'
    )

    # 인자가 없으면 커스텀 메시지만 표시
    if len(sys.argv) == 1:
        print("\n" + "="*80)
        print("❌ 오류: --mode 파라미터가 필요합니다!")
        print("="*80)
        print("\n사용 예시:")
        print("  python main.py --mode collect-cookies                    # 쿠키 수집")
        print("  python main.py --mode test-page                          # 1페이지 테스트")
        print("  python main.py --mode scrape-all --storage json          # 전체 스크래핑 (JSON)")
        print("  python main.py --mode scrape-all --storage db            # 전체 스크래핑 (DB)")
        print("  python main.py --mode scrape-all --storage both          # 전체 스크래핑 (JSON+DB)")
        print("  python main.py --mode test-detail                        # 상세 페이지 테스트")
        print("")
        sys.exit(1)

    args = parser.parse_args()

    # scrape-all 모드일 때 --storage 필수 체크
    if args.mode == 'scrape-all' and not args.storage:
        print("\n" + "="*80)
        print("❌ 오류: --mode scrape-all 실행 시 --storage 파라미터가 필요합니다!")
        print("="*80)
        print("\n사용 예시:")
        print("  python main.py --mode scrape-all --storage json          # JSON 저장")
        print("  python main.py --mode scrape-all --storage db            # DB 저장")
        print("  python main.py --mode scrape-all --storage both          # JSON+DB 저장")
        print("")
        sys.exit(1)

    print("\n" + "="*80)
    print("HairinJob 스크래퍼")
    print("="*80)

    # 모드에 따라 실행
    if args.mode == 'collect-cookies':
        print("\n[모드: 쿠키 수집] Playwright로 쿠키 수집 및 저장")
        asyncio.run(collect_cookies_with_playwright())

    elif args.mode == 'test-page':
        print("\n[모드: 페이지 테스트] 저장된 쿠키로 1페이지 요청")
        fetch_with_saved_cookies()

    elif args.mode == 'scrape-all':
        print("\n[모드: 전체 스크래핑] 저장된 쿠키로 다중 페이지 스크래핑")
        print(f"[저장 방식: {args.storage}]")
        if args.skip_pages:
            print("[옵션: 페이지 스크래핑 건너뛰기]")
        fetch_multiple_pages(storage_type=args.storage, skip_pages=args.skip_pages)

    elif args.mode == 'test-detail':
        print("\n[모드: 상세 페이지 테스트] 상세 페이지 스크래핑 (idx=101200)")
        fetch_detail_page()


if __name__ == "__main__":
    main()
