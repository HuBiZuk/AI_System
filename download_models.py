from ultralytics import YOLO

# 다운로드할 모델 목록
models = [
    'yolov8n-pose.pt',  # Nano
    'yolov8s-pose.pt',  # Small
    'yolov8m-pose.pt',  # Medium
    'yolov8l-pose.pt',  # Large
    'yolov8x-pose.pt'   # Extra Large
]

print("모든 YOLOv8-pose 모델 다운로드를 시작합니다...")

for model_name in models:
    print(f"\n[{model_name}] 다운로드 및 로드 확인 중...")
    try:
        # 모델을 로드하면 자동으로 다운로드가 진행됩니다.
        model = YOLO(model_name)
        print(f"-> {model_name} 준비 완료!")
    except Exception as e:
        print(f"-> {model_name} 다운로드 실패: {e}")

print("\n모든 작업이 완료되었습니다.")
