import json
import asyncio
import requests
import os
import re
import sys
import argparse
from datetime import datetime
from bs4 import BeautifulSoup, SoupStrainer
from playwright.async_api import async_playwright

COOKIE_DIR = "cookies"
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


def scrape_with_cookie(cookie_idx, cookie_file, start_page, end_page, work_dir, num_cookies):
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

    # 쿠키별 폴더 생성
    cookie_work_dir = os.path.join(work_dir, f"cookies_{cookie_idx}")
    os.makedirs(cookie_work_dir, exist_ok=True)

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

            # 페이지별 파일 저장 (쿠키별 폴더에)
            page_file = os.path.join(cookie_work_dir, f"page_{page_num:03d}.json")
            with open(page_file, 'w', encoding='utf-8') as f:
                json.dump(job_listings, f, indent=2, ensure_ascii=False)
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


def fetch_multiple_pages():
    """옵션 3: 저장된 쿠키를 사용하여 여러 페이지를 스크래핑합니다."""
    import random
    import time
    import glob
    from concurrent.futures import ThreadPoolExecutor, as_completed

    print(f"\n[옵션 3] 다중 페이지 스크래핑 (병렬 처리)")

    # 쿠키 파일 개수 확인
    cookie_files = sorted(glob.glob(os.path.join(COOKIE_DIR, "cookies_*.json")))
    num_cookies = len(cookie_files)

    if num_cookies == 0:
        print(f"\n✗ 오류: 쿠키 파일이 없습니다.")
        print("먼저 옵션 1을 실행하여 쿠키를 수집하세요.")
        return

    print(f"✓ {num_cookies}개의 쿠키 세트 발견")

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

    # 작업 폴더 생성 (타임스탬프 기반)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    work_dir = os.path.join(RESULT_DIR, timestamp)
    os.makedirs(work_dir, exist_ok=True)
    print(f"\n작업 폴더: {work_dir}")

    all_jobs = []

    # 시작 시간 기록
    start_time = time.time()

    all_jobs = []

    # 병렬 처리로 각 쿠키 세트 동시 실행
    print(f"\n병렬 처리 시작 ({num_cookies}개 쿠키 세트 동시 실행)...")

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
                work_dir,
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

    # 종료 시간 기록 및 소요 시간 계산
    end_time = time.time()
    elapsed_time = end_time - start_time
    elapsed_minutes = int(elapsed_time // 60)
    elapsed_seconds = int(elapsed_time % 60)

    # 모든 페이지 완료 후 통합 파일 생성
    print(f"\n{'='*80}")
    print("모든 페이지 스크래핑 완료!")
    print(f"총 {len(all_jobs)}개 항목 수집")
    print(f"소요 시간: {elapsed_minutes}분 {elapsed_seconds}초")

    all_jobs_file = os.path.join(work_dir, "all_jobs.json")
    with open(all_jobs_file, 'w', encoding='utf-8') as f:
        json.dump(all_jobs, f, indent=2, ensure_ascii=False)
    print(f"✓ 통합 파일 저장: {all_jobs_file}")
    print('='*80)


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

    # 인자가 없으면 커스텀 메시지만 표시
    if len(sys.argv) == 1:
        print("\n" + "="*80)
        print("❌ 오류: --mode 파라미터가 필요합니다!")
        print("="*80)
        print("\n사용 예시:")
        print("  python main.py --mode collect-cookies    # 쿠키 수집")
        print("  python main.py --mode test-page          # 1페이지 테스트")
        print("  python main.py --mode scrape-all         # 전체 페이지 스크래핑")
        print("  python main.py --mode test-detail        # 상세 페이지 테스트")
        print("")
        sys.exit(1)

    args = parser.parse_args()

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
        fetch_multiple_pages()

    elif args.mode == 'test-detail':
        print("\n[모드: 상세 페이지 테스트] 상세 페이지 스크래핑 (idx=101200)")
        fetch_detail_page()


if __name__ == "__main__":
    main()
