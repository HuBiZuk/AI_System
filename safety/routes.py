import os
import json
from flask import render_template, Response, request, jsonify, current_app
from werkzeug.utils import secure_filename
from . import ai_bp
from .model import AIModel

# 초기 모델 설정 (기본값: Nano)
current_model = 'yolov8n-pose.pt'

print("AI 시스템 초기화 중...")
ai_system = AIModel(current_model)
print("AI 시스템 초기화 완료")

# 경로 설정
BASE_DIR = os.path.abspath(os.path.dirname(__file__)) 
PROJECT_ROOT = os.path.dirname(BASE_DIR) 
UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, 'safety', 'static', 'uploads')
CONFIG_FILE = os.path.join(PROJECT_ROOT, 'safety', 'config.json') 

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# 설정 파일 로드 함수
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"설정 파일 로드 오류: {e}")
    return {}

# 설정 파일 저장 함수
def save_config(config):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"설정 파일 저장 오류: {e}")

# 업로드 폴더 경로 구하기
def get_upload_folder():
    folder = os.path.join(os.getcwd(), 'safety', 'static', 'uploads')
    if not os.path.exists(folder):
        os.makedirs(folder)
    return folder

# 메인페이지 /ai 주소
@ai_bp.route('/')
def dashboard():
    return render_template('dashboard.html')

# 모델 변경 요청 처리 (POST)
@ai_bp.route('/model_update', methods=['POST'])
def update_model():
    data = request.get_json()
    new_model = data.get('model')
    
    if new_model:
        print(f"모델 변경 요청 받음: {new_model}")
        try:
            ai_system.set_model(new_model)
            return jsonify({'status': 'success', 'model': new_model})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500
    return jsonify({'status': 'error', 'message': 'No model specified'}), 400

# 소스 변경 (웹캠/URL/파일)
@ai_bp.route('/change_source', methods=['POST'])
def change_source():
    data = request.get_json()
    source = data.get('source')
    type = data.get('type') 

    if source is not None:
        source_key = source 
        
        if type == 'file':
            upload_folder = get_upload_folder()
            filepath = os.path.join(upload_folder, source)
            
            if os.path.exists(filepath):
                ai_system.set_source(filepath, source_key) 
            else:
                return jsonify({'status': 'error', 'message': f'File not found: {filepath}'}), 404
        else:
            ai_system.set_source(source, 'webcam') 
            source_key = 'webcam'

        # 설정 불러오기
        config = load_config()
        source_config = config.get(source_key)
        
        if source_config:
            # 구역 설정 적용
            ai_system.set_zones(source_config.get('zones', []), 
                                source_config.get('expand_ratio', 0), 
                                source_config.get('canvas_size'))
            # 감지 설정 적용
            ai_system.set_detect_config(
                source_config.get('conf', 0.5),
                source_config.get('height_limit', 0),
                source_config.get('elbow_angle', 0),
                source_config.get('reach_enabled', False),
                source_config.get('fall_enabled', False)
            )
            # [수정] 화면 표시 설정 적용 (인자 3개)
            ai_system.detector.update_display_config(
                source_config.get('draw_objects', True),
                source_config.get('draw_zones', True), # 추가
                source_config.get('show_only_alert', False)
            )
            
            return jsonify({'status': 'success', 'source': source, 'config': source_config})
        else:
            # 초기화
            ai_system.set_zones([], 0)
            ai_system.set_detect_config(0.5, 0, 0, False, False)
            # [수정] 초기화 시에도 인자 3개 전달
            ai_system.detector.update_display_config(True, True, False)
            return jsonify({'status': 'success', 'source': source, 'config': None})

    return jsonify({'status': 'error', 'message': 'No source provided'}), 400

# 비디오 파일 업로드 및 소스 변경
@ai_bp.route('/upload_video', methods=['POST'])
def upload_video():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No selected file'}), 400
        
    if file:
        filename = secure_filename(file.filename)
        upload_folder = get_upload_folder()
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)
        
        ai_system.set_source(filepath, filename) 
        
        # 초기화
        ai_system.set_zones([], 0)
        ai_system.set_detect_config(0.5, 0, 0, False, False)
        ai_system.detector.update_display_config(True, True, False)
        
        return jsonify({'status': 'success', 'source': filename})

# 업로드된 비디오 목록 반환
@ai_bp.route('/get_videos')
def get_videos():
    videos = []
    upload_folder = get_upload_folder()
    
    if os.path.exists(upload_folder):
        for filename in os.listdir(upload_folder):
            if filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
                videos.append(filename)
    
    return jsonify({'videos': videos})

# 실시간 비디오 스트리밍 경로
@ai_bp.route('/video_feed')
def video_feed():
    return Response(ai_system.generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# 감지 신뢰도 변경 (단독 호출용, 필요시 유지)
@ai_bp.route('/update_conf', methods=['POST'])
def update_conf():
    data = request.get_json()
    conf = data.get('conf')
    if conf is not None:
        ai_system.set_conf(conf)
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error'}), 400

# 구역 설정 업데이트
@ai_bp.route('/update_zones', methods=['POST'])
def update_zones():
    data = request.get_json()
    zones = data.get('zones')
    expand_ratio = data.get('expand_ratio')
    
    canvas_width = data.get('canvas_width')
    canvas_height = data.get('canvas_height')
    canvas_size = (canvas_width, canvas_height) if canvas_width and canvas_height else None

    if zones is not None:
        try:
            ai_system.set_zones(zones, expand_ratio, canvas_size)
            
            # 설정 파일 저장
            config = load_config()
            source_key = ai_system.source_key
            if source_key not in config: config[source_key] = {}
            
            config[source_key]['zones'] = zones
            config[source_key]['expand_ratio'] = expand_ratio
            config[source_key]['canvas_size'] = canvas_size
            save_config(config)
            
            return jsonify({'status': 'success', 'message': 'Zones saved'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

    return jsonify({'status': 'error', 'message': 'No zones data'}), 400

# 감지 설정 업데이트
@ai_bp.route('/update_detect_config', methods=['POST'])
def update_detect_config():
    data = request.get_json()
    try:
        ai_system.set_detect_config(
            data.get('conf', 0.5),
            data.get('height_limit', 0),
            data.get('elbow_angle', 0),
            data.get('reach_enabled', False),
            data.get('fall_enabled', False)
        )
        
        # 설정 파일 저장
        config = load_config()
        source_key = ai_system.source_key
        if source_key not in config: config[source_key] = {}
        
        config[source_key]['conf'] = data.get('conf')
        config[source_key]['height_limit'] = data.get('height_limit')
        config[source_key]['elbow_angle'] = data.get('elbow_angle')
        config[source_key]['reach_enabled'] = data.get('reach_enabled')
        config[source_key]['fall_enabled'] = data.get('fall_enabled')
        save_config(config)
        
        return jsonify({'status': 'success', 'message': 'Detect config saved'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# [수정] 화면 표시 설정 업데이트 (인자 3개)
@ai_bp.route('/update_display_config', methods=['POST'])
def update_display_config():
    data = request.get_json()
    try:
        draw_objects = data.get('draw_objects', True)
        draw_zones = data.get('draw_zones', True) # 추가
        show_only_alert = data.get('show_only_alert', False)
        
        ai_system.detector.update_display_config(draw_objects, draw_zones, show_only_alert)
        
        config = load_config()
        source_key = ai_system.source_key
        if source_key not in config: config[source_key] = {}
        
        config[source_key]['draw_objects'] = draw_objects
        config[source_key]['draw_zones'] = draw_zones
        config[source_key]['show_only_alert'] = show_only_alert
        save_config(config)
        
        return jsonify({'status': 'success', 'message': 'Display config saved'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# 로그 가져오기 API
@ai_bp.route('/get_logs')
def get_logs():
    logs = ai_system.detector.get_logs()
    return jsonify({'logs': logs})
