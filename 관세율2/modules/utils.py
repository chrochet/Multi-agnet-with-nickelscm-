# modules/utils.py
from pathlib import Path

def get_project_root():
    """
    프로젝트 루트 경로 반환
    app.py·data·modules 등을 모두 자동 인식하게 해줌
    """
    return Path(__file__).resolve().parents[1]
