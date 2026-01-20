from flask import Blueprint

ai_bp = Blueprint(
    'ai_safety',
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/safety/static'  # 정적 파일 URL 경로 명시
)
from . import routes
