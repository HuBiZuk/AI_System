import cv2
import torch
import time
from ultralytics import YOLO
from .detector import SafetyDetector

class AIModel:
    def __init__(self, model_path='yolov8n-pose.pt'): # 생성자
        # GPU 사용 가능 여부 확인 및 장치 설정
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"AI 모델 실행 장치: {self.device}")
        if self.device == 'cuda':
            print(f"GPU 정보: {torch.cuda.get_device_name(0)}")

        self.model_name = model_path
        self.set_model(model_path)
        self.source = 0  # 기본값: 웹캠 (0)
        self.source_key = 'webcam' # 설정 저장용 키
        
        # 성능 최적화 설정
        self.skip_frames = 3  # 3프레임마다 1번만 분석 (부하 감소)
        self.latest_result = None # 마지막 분석 결과 저장용
        
        # 감지기 인스턴스 생성 (알고리즘 분리)
        self.detector = SafetyDetector()

    def set_model(self, model_path):
        # 모델 교체 메서드
        print(f"AI 모델 교체중...({model_path})")
        self.model = YOLO(model_path)
        self.model_name = model_path
        self.latest_result = None
        print(f"AI 모델 교체 완료: {self.model_name}")

    def set_source(self, source, source_key='webcam'):
        # 소스 변경 (0, 파일경로, RTSP 주소 등)
        print(f"영상 소스 변경: {source} (Key: {source_key})")
        self.source = source
        self.source_key = source_key
        self.latest_result = None
        
        # 소스 변경 시 감지기 설정 초기화 (routes.py에서 다시 설정됨)
        self.detector.update_zones([], 0.0, None)
        self.detector.update_config(0.5, 0, 0, False, False) # fall_enabled 추가

    def set_conf(self, conf):
        # 단독 신뢰도 변경 (detector에도 반영)
        self.detector.conf = float(conf)

    def set_zones(self, zones, expand_ratio, canvas_size=None):
        # 구역 정보 업데이트
        self.detector.update_zones(zones, expand_ratio, canvas_size)
        print(f"구역 설정 업데이트 (Detector)")

    def set_detect_config(self, conf, height_limit, elbow_angle, reach_enabled, fall_enabled):
        # 감지 설정 업데이트
        self.detector.update_config(conf, height_limit, elbow_angle, reach_enabled, fall_enabled)
        print(f"감지 설정 업데이트 (Detector)")

    def generate_frames(self):  # 실시간 영상 프레임 만들기
        # 현재 설정된 소스로 카메라/비디오 열기
        src = self.source
        if isinstance(src, str) and src.isdigit():
            src = int(src)
            
        # 웹캠인 경우 DSHOW 백엔드 사용 (윈도우 호환성 향상)
        if isinstance(src, int):
            cap = cv2.VideoCapture(src, cv2.CAP_DSHOW)
        else:
            cap = cv2.VideoCapture(src)
        
        if not cap.isOpened():
            print(f"영상을 열 수 없습니다: {src}")
            return

        # 동영상 원본 FPS 확인 (속도 동기화용)
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        if not video_fps or video_fps <= 0:
            video_fps = 30 # 기본값
        
        frame_duration = 1.0 / video_fps # 1프레임당 걸려야 하는 시간

        prev_time = 0
        frame_count = 0

        while True:
            loop_start = time.time() # 루프 시작 시간 측정

            success, frame = cap.read()
            if not success:
                # 동영상 파일인 경우 무한 반복
                if isinstance(src, str) and not src.startswith('http') and not src.startswith('rtsp'):
                     cap.release()
                     cap = cv2.VideoCapture(src)
                     continue
                else:
                    # 스트림 종료 시 루프 중단
                    break
            
            frame_count += 1

            # [최적화] 지정된 간격마다 AI 분석 수행
            if frame_count % self.skip_frames == 0:
                try:
                    # 추론 시에는 설정된 conf 사용
                    results = self.model(frame, verbose=False, device=self.device, conf=self.detector.conf)
                    self.latest_result = results[0]
                except Exception:
                    pass
            
            # 결과 처리 및 그리기 (Detector 위임)
            if self.latest_result:
                try:
                    # [수정] model.py에서는 plot()을 호출하지 않음!
                    # 모든 그리기 권한을 detector.process_frame으로 넘김
                    frame = self.detector.process_frame(frame, self.latest_result)
                except Exception as e:
                    # print(f"처리 오류: {e}")
                    pass

            # FPS 계산 및 표시
            curr_time = time.time()
            time_diff = curr_time - prev_time
            fps = 1 / time_diff if prev_time > 0 and time_diff > 0.001 else 0
            prev_time = curr_time
            
            # 화면 좌측 상단에 FPS와 장치 정보 표시
            cv2.putText(frame, f"FPS: {fps:.1f} ({self.device})", (20, 40),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                continue

            frame_bytes = buffer.tobytes()   # 압축된 이미지 바이트를 바이트 형태로 변환
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            
            # [속도 제어] 동영상 파일인 경우 원본 속도에 맞게 대기
            if isinstance(src, str) and not src.startswith('http') and not src.startswith('rtsp'):
                elapsed = time.time() - loop_start
                delay = frame_duration - elapsed
                if delay > 0:
                    time.sleep(delay)
        
        cap.release()
