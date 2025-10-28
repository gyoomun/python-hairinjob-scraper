#!/bin/bash
# HairinJob Scraper 실행 스크립트

# 가상환경 활성화
source venv/bin/activate

# 인자를 그대로 python에 전달
python main.py "$@"
