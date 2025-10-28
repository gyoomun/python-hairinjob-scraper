#!/usr/bin/env python3
"""
HTML 뷰어 생성 스크립트
all_jobs.json 파일을 읽어서 viewer.html에 데이터를 삽입하여
최종 HTML 파일을 생성합니다.
"""
import json
import sys
import os

def generate_viewer(json_file_path, output_file='hairinjob_viewer.html'):
    """JSON 데이터를 포함한 HTML 뷰어 파일을 생성합니다."""

    # JSON 파일 읽기
    print(f"JSON 파일 읽는 중: {json_file_path}")
    with open(json_file_path, 'r', encoding='utf-8') as f:
        jobs_data = json.load(f)

    print(f"✓ {len(jobs_data)}개의 채용 공고 로드 완료")

    # HTML 템플릿 읽기 (같은 폴더 내)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(script_dir, 'viewer.html')
    print(f"HTML 템플릿 읽는 중: {template_path}")
    with open(template_path, 'r', encoding='utf-8') as f:
        html_template = f.read()

    # JSON 데이터를 JavaScript 형식으로 변환
    json_string = json.dumps(jobs_data, ensure_ascii=False, indent=2)

    # HTML에 데이터 삽입
    final_html = html_template.replace('__JSON_DATA__', json_string)

    # 최종 HTML 파일 저장
    print(f"최종 HTML 파일 생성 중: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(final_html)

    file_size = os.path.getsize(output_file) / 1024 / 1024  # MB
    print(f"\n✓ 완료!")
    print(f"  파일: {output_file}")
    print(f"  크기: {file_size:.2f} MB")
    print(f"  채용공고: {len(jobs_data)}개")
    print(f"\n브라우저에서 '{output_file}' 파일을 열어보세요!")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("사용법: python viewer/generate_viewer.py <all_jobs.json 경로> [출력파일명]")
        print("\n예시:")
        print("  python viewer/generate_viewer.py scraping-result/20251024-194532/all_jobs.json")
        print("  python viewer/generate_viewer.py scraping-result/20251024-194532/all_jobs.json output.html")
        sys.exit(1)

    json_path = sys.argv[1]

    if not os.path.exists(json_path):
        print(f"✗ 오류: '{json_path}' 파일을 찾을 수 없습니다.")
        sys.exit(1)

    # 출력 파일 기본값은 viewer/ 폴더 내에 생성
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_output = os.path.join(script_dir, 'hairinjob_viewer.html')
    output = sys.argv[2] if len(sys.argv) > 2 else default_output

    generate_viewer(json_path, output)
