import cv2
import numpy as np
import math
import time
from datetime import datetime
from . import database # DB 모듈 임포트

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
        self.draw_zones = True 
        self.show_only_alert = False 
        
        # 로그 관리
        self.logs = [] 
        self.last_log_time = 0 
        self.current_source = 'webcam' # 현재 영상 소스
        
        # 스켈레톤 연결 정보
        self.skeleton_links = [
            (5, 7), (7, 9),       # 왼팔
            (6, 8), (8, 10),      # 오른팔
            (5, 6),               # 어깨
            (5, 11), (6, 12),     # 몸통
            (11, 12),             # 골반
            (11, 13), (13, 15),   # 왼다리
            (12, 14), (14, 16)    # 오른다리
        ]
        # 스타일 설정
        self.kpt_color_normal = (0, 255, 0) 
        self.kpt_color_warning = (0, 255, 255) 
        self.kpt_color_danger = (0, 0, 255) 
        
        self.limb_color = (255, 50, 50) 
        
        self.box_color_normal = (0, 255, 0) 
        self.box_color_warning = (0, 255, 255) 
        self.box_color_danger = (0, 0, 255) 

    def update_config(self, conf, height_limit, elbow_angle, reach_enabled, fall_enabled):
        self.conf = float(conf)
        self.height_limit = int(height_limit)
        self.elbow_angle = int(elbow_angle)
        self.reach_enabled = bool(reach_enabled)
        self.fall_enabled = bool(fall_enabled)

    def update_display_config(self, draw_objects, draw_zones, show_only_alert):
        self.draw_objects = bool(draw_objects)
        self.draw_zones = bool(draw_zones)
        self.show_only_alert = bool(show_only_alert)

    def update_zones(self, zones, expand_ratio, canvas_size):
        self.zones = zones
        self.expand_ratio = float(expand_ratio)
        self.canvas_size = canvas_size
        
    # [추가] 소스 정보 업데이트
    def set_source(self, source):
        self.current_source = source

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
        
        # 메모리 로그 (화면 표시용)
        log_entry = {
            'time': timestamp,
            'level': level, 
            'message': message
        }
        self.logs.insert(0, log_entry) 
        if len(self.logs) > 50: 
            self.logs.pop()
        
        self.last_log_time = current_time
        
        # [추가] DB 저장
        database.insert_log(level, message, self.current_source)

    def get_logs(self):
        return self.logs

    # 스켈레톤 그리기
    def draw_skeleton(self, frame, kpts, kpts_status):
        for p1, p2 in self.skeleton_links:
            if kpts[p1][2] >= 0.5 and kpts[p2][2] >= 0.5:
                pt1 = (int(kpts[p1][0]), int(kpts[p1][1]))
                pt2 = (int(kpts[p2][0]), int(kpts[p2][1]))
                cv2.line(frame, pt1, pt2, self.limb_color, 2)
        
        for i, kp in enumerate(kpts):
            if kp[2] >= 0.5: 
                status = kpts_status[i] 
                
                color = self.kpt_color_normal
                radius = 4
                
                if status == 2: 
                    color = self.kpt_color_danger
                    radius = 8
                elif status == 1: 
                    color = self.kpt_color_warning
                    radius = 6
                
                cv2.circle(frame, (int(kp[0]), int(kp[1])), radius, color, -1)

    # 박스 그리기
    def draw_box(self, frame, box, color, label=None):
        cv2.rectangle(frame, (int(box[0]), int(box[1])), (int(box[2]), int(box[3])), color, 2)
        if label:
            cv2.putText(frame, label, (int(box[0]), int(box[1]) - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    # 최종 그리기 로직
    def draw_results(self, frame, result, processed_zones, people_draw_data, is_alert):
        should_draw = True
        if self.show_only_alert and not is_alert:
            should_draw = False
        if not self.draw_objects and not self.draw_zones: 
            should_draw = False

        if not should_draw:
            return frame

        if self.draw_zones or is_alert:
            for zone in processed_zones:
                cv2.polylines(frame, [zone['red_pts']], True, (0, 0, 255), 2)
                if zone['yellow_pts'] is not None:
                    cv2.polylines(frame, [zone['yellow_pts']], True, (0, 255, 255), 2)

        if self.draw_objects:
            for person in people_draw_data:
                if self.show_only_alert and not person['is_alert']:
                    continue
                
                box_color = self.box_color_normal
                if person['is_alert']:
                    is_danger = any(item['level'] == 'danger' for item in person['items'] if 'level' in item)
                    box_color = self.box_color_danger if is_danger else self.box_color_warning

                if person['box'] is not None:
                    self.draw_box(frame, person['box'], box_color)
                
                if person['kpts'] is not None:
                    self.draw_skeleton(frame, person['kpts'], person['kpts_status'])

                for item in person['items']:
                    if item['type'] == 'fall':
                        self.draw_box(frame, item['box'], box_color, label="DANGER: FALL DETECTED!")
                    elif item['type'] == 'line':
                        cv2.line(frame, item['p1'], item['p2'], (0, 255, 255), 2)
                    elif item['type'] == 'text':
                        cv2.putText(frame, item['msg'], item['pos'], cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    elif item['type'] == 'zone_alert':
                        color = (0, 0, 255) if item['level'] == 'danger' else (0, 255, 255)
                        thick = 5 if item['level'] == 'danger' else 4
                        pts = item['zone']['red_pts'] if item['level'] == 'danger' else item['zone']['yellow_pts']
                        
                        cv2.polylines(frame, [pts], True, color, thick)
                        cv2.putText(frame, item['msg'], (50, 100 if item['level']=='danger' else 150), cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 2)
        
        return frame

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

        is_alert = False
        people_draw_data = []

        for i, kpts in enumerate(keypoints):
            kpts_cpu = kpts.cpu().numpy()
            person_alert = False 
            person_draw_items = [] 
            kpts_status = [0] * 17 
            
            if self.fall_enabled and boxes is not None and len(boxes) > i:
                box = boxes[i].xyxy[0].cpu().numpy()
                w = box[2] - box[0]
                h = box[3] - box[1]
                if w > h * 1.2:
                    person_alert = True
                    is_alert = True
                    self.add_log('danger', "쓰러짐 감지 (Fall Detected)")
                    person_draw_items.append({'type': 'fall', 'box': box, 'level': 'danger'})

            shoulders_y = [kpts_cpu[i][1] for i in [5, 6] if kpts_cpu[i][2] >= 0.1]
            hips_y = [kpts_cpu[i][1] for i in [11, 12] if kpts_cpu[i][2] >= 0.1]

            height_pass = False
            limit_y = 0
            center_x = 0
            width = 0
            
            if shoulders_y and hips_y:
                avg_shoulder_y = sum(shoulders_y) / len(shoulders_y)
                avg_hip_y = sum(hips_y) / len(hips_y)
                torso_len = avg_hip_y - avg_shoulder_y
                limit_y = avg_hip_y - (torso_len * (self.height_limit / 100.0))
                center_x = int((kpts_cpu[5][0] + kpts_cpu[6][0] + kpts_cpu[11][0] + kpts_cpu[12][0]) / 4)
                width = int(torso_len * 0.8)

                if (kpts_cpu[9][2] >= self.conf and kpts_cpu[9][1] < limit_y) or \
                   (kpts_cpu[10][2] >= self.conf and kpts_cpu[10][1] < limit_y):
                    height_pass = True
                
                if self.height_limit > 0:
                    person_draw_items.append({'type': 'line', 'p1': (center_x - width, int(limit_y)), 'p2': (center_x + width, int(limit_y))})

            angle_pass = False
            if kpts_cpu[5][2] >= 0.1 and kpts_cpu[7][2] >= 0.1 and kpts_cpu[9][2] >= 0.1:
                angle = self.calculate_angle(kpts_cpu[5][:2], kpts_cpu[7][:2], kpts_cpu[9][:2])
                person_draw_items.append({'type': 'text', 'msg': f"{int(angle)}", 'pos': (int(kpts_cpu[7][0]), int(kpts_cpu[7][1]) - 10)})
                if angle >= self.elbow_angle: angle_pass = True
            
            if kpts_cpu[6][2] >= 0.1 and kpts_cpu[8][2] >= 0.1 and kpts_cpu[10][2] >= 0.1:
                angle = self.calculate_angle(kpts_cpu[6][:2], kpts_cpu[8][:2], kpts_cpu[10][:2])
                person_draw_items.append({'type': 'text', 'msg': f"{int(angle)}", 'pos': (int(kpts_cpu[8][0]), int(kpts_cpu[8][1]) - 10)})
                if angle >= self.elbow_angle: angle_pass = True

            is_reaching = True
            if self.reach_enabled:
                cond_h = height_pass if self.height_limit > 0 else True
                cond_a = angle_pass if self.elbow_angle > 0 else True
                if not (cond_h and cond_a):
                    is_reaching = False

            for zone in processed_zones:
                check_indices = []
                if zone['type'] == 'touch':
                    check_indices = [9, 10] 
                else:
                    check_indices = range(17) 

                if not is_reaching:
                    continue

                red_intrusion = False
                yellow_intrusion = False

                for idx in check_indices:
                    if kpts_cpu[idx][2] < self.conf: continue
                    
                    pt = (int(kpts_cpu[idx][0]), int(kpts_cpu[idx][1]))
                    
                    if cv2.pointPolygonTest(zone['red_pts'], pt, False) >= 0:
                        red_intrusion = True
                        kpts_status[idx] = max(kpts_status[idx], 2) 
                    
                    elif zone['yellow_pts'] is not None:
                        if cv2.pointPolygonTest(zone['yellow_pts'], pt, False) >= 0:
                            yellow_intrusion = True
                            kpts_status[idx] = max(kpts_status[idx], 1) 

                if red_intrusion:
                    person_alert = True
                    is_alert = True
                    msg = "DANGER: TOUCH!" if zone['type'] == 'touch' else "DANGER: INTRUSION!"
                    self.add_log('danger', f"Zone 침범 감지 ({msg})")
                    person_draw_items.append({'type': 'zone_alert', 'zone': zone, 'level': 'danger', 'msg': msg})
                elif yellow_intrusion:
                    person_alert = True
                    is_alert = True
                    self.add_log('warning', "접근 경고 (Approaching)")
                    person_draw_items.append({'type': 'zone_alert', 'zone': zone, 'level': 'warning', 'msg': "WARNING: APPROACHING"})
            
            people_draw_data.append({
                'is_alert': person_alert,
                'items': person_draw_items,
                'box': boxes[i].xyxy[0].cpu().numpy() if boxes is not None and len(boxes) > i else None,
                'kpts': kpts_cpu,
                'kpts_status': kpts_status
            })

        return self.draw_results(frame, result, processed_zones, people_draw_data, is_alert)
