import cv2
import numpy as np
import math
import time
from datetime import datetime

class SafetyDetector:
    def __init__(self):
        # 설정값 초기화
        self.zones = []
        self.expand_ratio = 0.0
        self.canvas_size = None 
        
        # 감지 설정
        self.conf = 0.5
        self.height_limit = 0
        self.elbow_angle = 0
        self.reach_enabled = False
        self.fall_enabled = False
        
        # 화면 표시 설정
        self.draw_objects = True 
        self.draw_zones = True # [추가] 구역 그리기 (기본값: 켜짐)
        self.show_only_alert = False 
        
        # 로그 관리
        self.logs = [] 
        self.last_log_time = 0 

    def update_config(self, conf, height_limit, elbow_angle, reach_enabled, fall_enabled):
        self.conf = float(conf)
        self.height_limit = int(height_limit)
        self.elbow_angle = int(elbow_angle)
        self.reach_enabled = bool(reach_enabled)
        self.fall_enabled = bool(fall_enabled)

    # [수정] 화면 표시 설정 업데이트
    def update_display_config(self, draw_objects, draw_zones, show_only_alert):
        self.draw_objects = bool(draw_objects)
        self.draw_zones = bool(draw_zones)
        self.show_only_alert = bool(show_only_alert)

    def update_zones(self, zones, expand_ratio, canvas_size):
        self.zones = zones
        self.expand_ratio = float(expand_ratio)
        self.canvas_size = canvas_size

    def calculate_angle(self, a, b, c):
        radians = np.arctan2(c[1]-b[1], c[0]-b[0]) - np.arctan2(a[1]-b[1], a[0]-b[0])
        angle = np.abs(radians*180.0/np.pi)
        if angle > 180.0: angle = 360 - angle
        return angle

    def get_expanded_zone(self, pts, ratio):
        if ratio <= 0: return None
        cx = np.mean(pts[:, 0])
        cy = np.mean(pts[:, 1])
        expanded_pts = []
        for p in pts:
            nx = cx + (p[0] - cx) * (1 + ratio)
            ny = cy + (p[1] - cy) * (1 + ratio)
            expanded_pts.append([nx, ny])
        return np.array(expanded_pts, np.int32).reshape((-1, 1, 2))

    def add_log(self, level, message):
        current_time = time.time()
        if current_time - self.last_log_time < 1.0:
            return

        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = {
            'time': timestamp,
            'level': level, 
            'message': message
        }
        self.logs.insert(0, log_entry) 
        if len(self.logs) > 50: 
            self.logs.pop()
        
        self.last_log_time = current_time

    def get_logs(self):
        return self.logs

    def process_frame(self, frame, result):
        if result.keypoints is None:
            return frame

        scale_x = 1.0
        scale_y = 1.0
        if self.canvas_size:
            h, w = frame.shape[:2]
            scale_x = w / self.canvas_size[0]
            scale_y = h / self.canvas_size[1]

        processed_zones = []
        for zone in self.zones:
            red_pts = []
            for p in zone['points']:
                red_pts.append([int(p['x'] * scale_x), int(p['y'] * scale_y)])
            red_pts = np.array(red_pts, np.int32).reshape((-1, 1, 2))
            
            yellow_pts = self.get_expanded_zone(red_pts.reshape(-1, 2), self.expand_ratio)
            
            processed_zones.append({
                'type': zone.get('type', 'touch'),
                'red_pts': red_pts,
                'yellow_pts': yellow_pts
            })

        boxes = result.boxes
        keypoints = result.keypoints.data

        # 1. 감지 로직 수행
        is_alert = False
        draw_list = [] 

        for i, kpts in enumerate(keypoints):
            kpts = kpts.cpu().numpy()
            
            # (1) 쓰러짐 감지
            is_fall = False
            if self.fall_enabled and boxes is not None and len(boxes) > i:
                box = boxes[i].xyxy[0].cpu().numpy()
                w = box[2] - box[0]
                h = box[3] - box[1]
                if w > h * 1.2:
                    is_fall = True
                    is_alert = True
                    self.add_log('danger', "쓰러짐 감지 (Fall Detected)")
                    draw_list.append({'type': 'fall', 'box': box})

            # (2) 팔 뻗음 판단
            shoulders_y = [kpts[i][1] for i in [5, 6] if kpts[i][2] >= 0.1]
            hips_y = [kpts[i][1] for i in [11, 12] if kpts[i][2] >= 0.1]

            height_pass = False
            limit_y = 0
            center_x = 0
            width = 0
            
            if shoulders_y and hips_y:
                avg_shoulder_y = sum(shoulders_y) / len(shoulders_y)
                avg_hip_y = sum(hips_y) / len(hips_y)
                torso_len = avg_hip_y - avg_shoulder_y
                limit_y = avg_hip_y - (torso_len * (self.height_limit / 100.0))
                center_x = int((kpts[5][0] + kpts[6][0] + kpts[11][0] + kpts[12][0]) / 4)
                width = int(torso_len * 0.8)

                if (kpts[9][2] >= self.conf and kpts[9][1] < limit_y) or \
                   (kpts[10][2] >= self.conf and kpts[10][1] < limit_y):
                    height_pass = True
                
                # 기준선 정보 저장
                if self.height_limit > 0:
                    draw_list.append({'type': 'line', 'p1': (center_x - width, int(limit_y)), 'p2': (center_x + width, int(limit_y))})

            angle_pass = False
            # 각도 정보 저장
            if kpts[5][2] >= 0.1 and kpts[7][2] >= 0.1 and kpts[9][2] >= 0.1:
                angle = self.calculate_angle(kpts[5][:2], kpts[7][:2], kpts[9][:2])
                draw_list.append({'type': 'text', 'msg': f"{int(angle)}", 'pos': (int(kpts[7][0]), int(kpts[7][1]) - 10)})
                if angle >= self.elbow_angle: angle_pass = True
            
            if kpts[6][2] >= 0.1 and kpts[8][2] >= 0.1 and kpts[10][2] >= 0.1:
                angle = self.calculate_angle(kpts[6][:2], kpts[8][:2], kpts[10][:2])
                draw_list.append({'type': 'text', 'msg': f"{int(angle)}", 'pos': (int(kpts[8][0]), int(kpts[8][1]) - 10)})
                if angle >= self.elbow_angle: angle_pass = True

            is_reaching = True
            if self.reach_enabled:
                cond_h = height_pass if self.height_limit > 0 else True
                cond_a = angle_pass if self.elbow_angle > 0 else True
                if not (cond_h and cond_a):
                    is_reaching = False

            # (3) 구역 침범 검사
            for zone in processed_zones:
                check_points = []
                if zone['type'] == 'touch':
                    if kpts[9][2] >= self.conf: check_points.append(kpts[9][:2])
                    if kpts[10][2] >= self.conf: check_points.append(kpts[10][:2])
                else:
                    for kp in kpts:
                        if kp[2] >= self.conf: check_points.append(kp[:2])

                if not is_reaching:
                    continue

                red_intrusion = False
                yellow_intrusion = False

                for kp in check_points:
                    pt = (int(kp[0]), int(kp[1]))
                    if cv2.pointPolygonTest(zone['red_pts'], pt, False) >= 0:
                        red_intrusion = True
                        break 
                    if zone['yellow_pts'] is not None:
                        if cv2.pointPolygonTest(zone['yellow_pts'], pt, False) >= 0:
                            yellow_intrusion = True

                if red_intrusion:
                    is_alert = True
                    msg = "DANGER: TOUCH!" if zone['type'] == 'touch' else "DANGER: INTRUSION!"
                    self.add_log('danger', f"Zone 침범 감지 ({msg})")
                    draw_list.append({'type': 'zone_alert', 'zone': zone, 'level': 'danger', 'msg': msg})
                elif yellow_intrusion:
                    is_alert = True
                    self.add_log('warning', "접근 경고 (Approaching)")
                    draw_list.append({'type': 'zone_alert', 'zone': zone, 'level': 'warning', 'msg': "WARNING: APPROACHING"})


        # 2. 그리기 결정 로직 (수정됨)
        should_draw = True
        
        # '감지 시에만 표시'가 켜져 있고, 감지된 게 없으면 -> 안 그림
        if self.show_only_alert and not is_alert:
            should_draw = False

        if should_draw:
            # YOLO 기본 그림 (스켈레톤/박스) 그리기
            # draw_objects가 켜져 있을 때만 그림 (위에서 이미 걸러졌지만 명시적으로)
            if self.draw_objects:
                frame = result.plot(img=frame)

            # 구역 선 그리기 (draw_zones가 켜져 있을 때만)
            if self.draw_zones:
                for zone in processed_zones:
                    cv2.polylines(frame, [zone['red_pts']], True, (0, 0, 255), 2)
                    if zone['yellow_pts'] is not None:
                        cv2.polylines(frame, [zone['yellow_pts']], True, (0, 255, 255), 2)

            # 추가 정보 그리기 (draw_objects가 켜져 있을 때만)
            if self.draw_objects:
                for item in draw_list:
                    if item['type'] == 'fall':
                        cv2.rectangle(frame, (int(item['box'][0]), int(item['box'][1])), (int(item['box'][2]), int(item['box'][3])), (0, 0, 255), 3)
                        cv2.putText(frame, "DANGER: FALL DETECTED!", (int(item['box'][0]), int(item['box'][1]) - 10), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
                    elif item['type'] == 'line':
                        cv2.line(frame, item['p1'], item['p2'], (0, 255, 255), 2)
                    elif item['type'] == 'text':
                        cv2.putText(frame, item['msg'], item['pos'], cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    elif item['type'] == 'zone_alert':
                        # 경고 시 구역 덧칠 및 메시지
                        color = (0, 0, 255) if item['level'] == 'danger' else (0, 255, 255)
                        thick = 5 if item['level'] == 'danger' else 4
                        pts = item['zone']['red_pts'] if item['level'] == 'danger' else item['zone']['yellow_pts']
                        
                        # 경고 시에는 구역 선을 굵게 덧칠 (draw_zones가 꺼져 있어도 경고는 보여야 함)
                        cv2.polylines(frame, [pts], True, color, thick)
                        cv2.putText(frame, item['msg'], (50, 100 if item['level']=='danger' else 150), cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 2)

        return frame
