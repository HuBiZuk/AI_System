import logging
from flask import Flask, request
from safety import ai_bp

# 특정 경로 로그를 무시하는 필터
class NoHealthChecksFilter(logging.Filter):
    def filter(self, record):
        # record.getMessage()는 "GET /get_logs HTTP/1.1" 200 - 와 같은 문자열
        return '/get_logs' not in record.getMessage()

# Flask(Werkzeug) 로거에 필터 적용
log = logging.getLogger('werkzeug')
log.addFilter(NoHealthChecksFilter())

app = Flask(__name__)

# safety 폴더의 블루프린트 등록
app.register_blueprint(ai_bp)

if __name__ == '__main__':
    # 디버그 모드로 실행 (코드 수정 시 자동 재시작)
    app.run(debug=True, port=5000)
