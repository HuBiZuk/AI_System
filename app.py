import logging
from flask import Flask, request
from safety import ai_bp
from safety import database # DB 모듈 임포트

# 특정 경로 로그를 무시하는 필터
class NoHealthChecksFilter(logging.Filter):
    def filter(self, record):
        return '/get_logs' not in record.getMessage()

# Flask(Werkzeug) 로거에 필터 적용
log = logging.getLogger('werkzeug')
log.addFilter(NoHealthChecksFilter())

app = Flask(__name__)

# safety 폴더의 블루프린트 등록
app.register_blueprint(ai_bp)

# [수정] 앱 시작 시 DB 초기화 (여기서 호출해야 확실함)
with app.app_context():
    try:
        database.init_db()
        print("DB 초기화 완료 (테이블 확인)")
    except Exception as e:
        print(f"DB 초기화 실패: {e}")

if __name__ == '__main__':
    # 디버그 모드로 실행 (코드 수정 시 자동 재시작)
    app.run(debug=True, port=5000)
