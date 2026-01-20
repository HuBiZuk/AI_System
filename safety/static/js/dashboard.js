// 전역 변수
let drawMode = false;
let currentPoints = []; 
let zones = []; 
const canvas = document.getElementById('zoneCanvas');
const ctx = canvas ? canvas.getContext('2d') : null;

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', function() {
    loadVideoList();
    setupEventListeners();
    
    const img = document.getElementById('videoStream');
    if (img) {
        if (img.complete) {
            resizeCanvas();
        } else {
            img.onload = resizeCanvas;
        }
    }
    window.addEventListener('resize', resizeCanvas);
    
    // 로그 업데이트 시작 (1초 간격)
    setInterval(updateLogs, 1000);
});

function resizeCanvas() {
    if (!canvas) return;
    const img = document.getElementById('videoStream');
    if (!img) return;

    canvas.width = img.clientWidth;
    canvas.height = img.clientHeight;
    
    canvas.style.width = img.clientWidth + 'px';
    canvas.style.height = img.clientHeight + 'px';
    canvas.style.left = img.offsetLeft + 'px';
    canvas.style.top = img.offsetTop + 'px';

    console.log(`캔버스 리사이징: ${canvas.width}x${canvas.height}`);
    drawAllZones(); 
}

function loadVideoList() {
    fetch('/get_videos')
    .then(response => response.json())
    .then(data => {
        const select = document.getElementById('videoSelect');
        if (!select) return;
        
        while (select.options.length > 1) {
            select.remove(1);
        }

        data.videos.forEach(video => {
            const option = document.createElement('option');
            option.value = video;
            option.text = video;
            select.add(option);
        });
    });
}

function setupEventListeners() {
    const videoSelect = document.getElementById('videoSelect');
    if (videoSelect) {
        videoSelect.addEventListener('change', function() {
            const selectedVideo = this.value;
            if (selectedVideo) changeSource(selectedVideo, 'file');
        });
    }

    const modelSelect = document.getElementById('modelSelect');
    if (modelSelect) {
        modelSelect.addEventListener('change', function() {
            const selectedModel = this.value;
            fetch('/model_update', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ model: selectedModel }),
            })
            .then(response => response.json())
            .then(data => {
                if(data.status !== 'success') alert('모델 변경 실패: ' + data.message);
            });
        });
    }

    // [감지 설정] 슬라이더 이벤트
    const confSlider = document.getElementById('confSlider');
    if (confSlider) {
        confSlider.addEventListener('input', function() {
            const percent = Math.round(this.value * 100);
            document.getElementById('confVal').innerText = percent;
        });
        confSlider.addEventListener('change', saveDetectConfigToServer); 
    }

    const heightSlider = document.getElementById('heightSlider');
    if (heightSlider) {
        heightSlider.addEventListener('input', function() {
            document.getElementById('heightVal').innerText = this.value;
            saveDetectConfigToServer(); 
        });
    }

    const angleSlider = document.getElementById('angleSlider');
    if (angleSlider) {
        angleSlider.addEventListener('input', function() {
            document.getElementById('angleVal').innerText = this.value;
        });
        angleSlider.addEventListener('change', saveDetectConfigToServer);
    }
    
    const reachCheck = document.getElementById('reachCheck');
    if (reachCheck) {
        reachCheck.addEventListener('change', saveDetectConfigToServer);
    }

    const fallCheck = document.getElementById('fallCheck');
    if (fallCheck) {
        fallCheck.addEventListener('change', saveDetectConfigToServer);
    }

    // [화면 표시 설정] 스위치 이벤트 (실시간 저장)
    const drawObjectsCheck = document.getElementById('drawObjectsCheck');
    if (drawObjectsCheck) {
        drawObjectsCheck.addEventListener('change', saveDisplayConfigToServer);
    }
    const drawZonesCheck = document.getElementById('drawZonesCheck'); // 추가
    if (drawZonesCheck) {
        drawZonesCheck.addEventListener('change', saveDisplayConfigToServer);
    }
    const showOnlyAlertCheck = document.getElementById('showOnlyAlertCheck');
    if (showOnlyAlertCheck) {
        showOnlyAlertCheck.addEventListener('change', saveDisplayConfigToServer);
    }

    // [구역 설정] 확장 비율 슬라이더
    const expandSlider = document.getElementById('expandSlider');
    if (expandSlider) {
        expandSlider.addEventListener('input', function() {
            document.getElementById('expandVal').innerText = this.value;
            drawAllZones(); 
        });
    }

    // [구역 설정] 그리기 모드 스위치
    const drawSwitch = document.getElementById('drawModeSwitch');
    if (drawSwitch) {
        drawSwitch.addEventListener('change', function() {
            drawMode = this.checked;
            if (drawMode) {
                canvas.style.pointerEvents = 'auto';
                canvas.style.cursor = 'crosshair';
                resizeCanvas();
            } else {
                canvas.style.pointerEvents = 'none';
                canvas.style.cursor = 'default';
                currentPoints = [];
                drawAllZones();
            }
        });
    }

    if (canvas) {
        canvas.addEventListener('click', function(e) {
            if (!drawMode) return;

            const rect = canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            currentPoints.push({x: x, y: y});
            drawAllZones(); 

            if (currentPoints.length === 4) {
                const newZone = {
                    points: [...currentPoints],
                    type: 'touch', 
                    id: Date.now() 
                };
                zones.push(newZone);
                currentPoints = []; 
                
                console.log("새 구역 추가됨:", newZone);
                drawAllZones();
                updateZoneListUI(); 
            }
        });
    }
    
    // [설정 저장] 버튼 이벤트
    const saveZoneBtn = document.getElementById('saveZoneBtn');
    if (saveZoneBtn) {
        saveZoneBtn.addEventListener('click', saveZonesToServer);
    }

    // [감지 설정 저장] 버튼 이벤트
    const saveDetectBtn = document.getElementById('saveDetectBtn');
    if (saveDetectBtn) {
        saveDetectBtn.addEventListener('click', function() {
            saveDetectConfigToServer();
            alert('감지 설정이 저장되었습니다.');
        });
    }
}

function updateZoneListUI() {
    const listContainer = document.getElementById('zoneList');
    if (!listContainer) return;

    listContainer.innerHTML = ''; 

    if (zones.length === 0) {
        listContainer.innerHTML = '<div class="text-center text-muted py-3">설정된 구역이 없습니다.</div>';
        return;
    }

    zones.forEach((zone, index) => {
        const item = document.createElement('div');
        item.className = 'list-group-item d-flex justify-content-between align-items-center';
        
        const typeLabel = zone.type === 'touch' ? '접촉 금지 (손)' : '침입 금지 (전신)';
        const badgeClass = zone.type === 'touch' ? 'bg-warning text-dark' : 'bg-danger';
        
        item.innerHTML = `
            <div>
                <span class="fw-bold">Zone ${index + 1}</span>
                <span class="badge ${badgeClass} ms-2">${typeLabel}</span>
            </div>
            <div class="d-flex align-items-center">
                <div class="form-check form-switch me-3" title="침입 금지 모드 전환">
                    <input class="form-check-input" type="checkbox" id="zoneSwitch-${zone.id}" ${zone.type === 'intrusion' ? 'checked' : ''}>
                </div>
                <button class="btn btn-sm btn-outline-danger" onclick="deleteZone(${zone.id})">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;
        
        listContainer.appendChild(item);

        const switchInput = item.querySelector(`#zoneSwitch-${zone.id}`);
        switchInput.addEventListener('change', function() {
            zone.type = this.checked ? 'intrusion' : 'touch';
            updateZoneListUI(); 
        });
    });
}

window.deleteZone = function(id) {
    zones = zones.filter(z => z.id !== id);
    drawAllZones();
    updateZoneListUI();
}

function drawAllZones() {
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    zones.forEach(zone => {
        drawSingleZone(zone.points, true); 
    });

    if (currentPoints.length > 0) {
        drawSingleZone(currentPoints, false); 
    }
}

function drawSingleZone(pts, isFinished) {
    if (pts.length === 0) return;

    ctx.fillStyle = 'red';
    pts.forEach(p => {
        ctx.beginPath();
        ctx.arc(p.x, p.y, 5, 0, Math.PI * 2);
        ctx.fill();
    });

    if (pts.length > 1) {
        ctx.beginPath();
        ctx.moveTo(pts[0].x, pts[0].y);
        for (let i = 1; i < pts.length; i++) {
            ctx.lineTo(pts[i].x, pts[i].y);
        }
        
        if (isFinished && pts.length === 4) {
            ctx.closePath();
            ctx.strokeStyle = 'rgba(255, 0, 0, 0.8)';
            ctx.lineWidth = 3;
            ctx.stroke();
            
            ctx.fillStyle = 'rgba(255, 0, 0, 0.2)';
            ctx.fill();

            drawExpandedZone(pts);
        } else {
            ctx.strokeStyle = 'red';
            ctx.lineWidth = 2;
            ctx.stroke();
        }
    }
}

function drawExpandedZone(pts) {
    const expandSlider = document.getElementById('expandSlider');
    if (!expandSlider) return;

    const ratio = parseInt(expandSlider.value) / 100;
    if (ratio === 0) return;

    let cx = 0, cy = 0;
    pts.forEach(p => {
        cx += p.x;
        cy += p.y;
    });
    cx /= pts.length;
    cy /= pts.length;

    const expandedPoints = pts.map(p => {
        return {
            x: cx + (p.x - cx) * (1 + ratio),
            y: cy + (p.y - cy) * (1 + ratio)
        };
    });

    ctx.beginPath();
    ctx.moveTo(expandedPoints[0].x, expandedPoints[0].y);
    for (let i = 1; i < expandedPoints.length; i++) {
        ctx.lineTo(expandedPoints[i].x, expandedPoints[i].y);
    }
    ctx.closePath();
    
    ctx.setLineDash([5, 5]); 
    ctx.strokeStyle = 'rgba(255, 255, 0, 0.8)';
    ctx.lineWidth = 2;
    ctx.stroke();
    
    ctx.setLineDash([]); 
    ctx.fillStyle = 'rgba(255, 255, 0, 0.1)';
    ctx.fill();
}

// [백엔드 연동] 구역 정보 서버로 전송
function saveZonesToServer() {
    const expandSlider = document.getElementById('expandSlider');
    const ratio = expandSlider ? parseInt(expandSlider.value) / 100 : 0;
    
    const confSlider = document.getElementById('confSlider');
    const conf = confSlider ? parseFloat(confSlider.value) : 0.5;

    const data = {
        zones: zones, 
        expand_ratio: ratio,
        conf: conf, 
        canvas_width: canvas.width,
        canvas_height: canvas.height
    };

    console.log("구역 설정 전송:", data);

    fetch('/update_zones', { 
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data),
    })
    .then(response => response.json())
    .then(data => {
        if(data.status === 'success') alert('구역 설정이 저장되었습니다.');
        else alert('저장 실패: ' + data.message);
    })
    .catch(error => alert('서버 통신 오류'));
}

// [수정] 감지 설정 서버로 전송
function saveDetectConfigToServer() {
    const confSlider = document.getElementById('confSlider');
    const heightSlider = document.getElementById('heightSlider');
    const angleSlider = document.getElementById('angleSlider');
    const reachCheck = document.getElementById('reachCheck');
    const fallCheck = document.getElementById('fallCheck');

    const data = {
        conf: confSlider ? parseFloat(confSlider.value) : 0.5,
        height_limit: heightSlider ? parseInt(heightSlider.value) : 0,
        elbow_angle: angleSlider ? parseInt(angleSlider.value) : 0,
        reach_enabled: reachCheck ? reachCheck.checked : false,
        fall_enabled: fallCheck ? fallCheck.checked : false
    };

    fetch('/update_detect_config', { 
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data),
    })
    .then(response => response.json())
    .then(data => {
        
    })
    .catch(error => console.error('설정 전송 오류'));
}

// [추가] 화면 표시 설정 서버로 전송 (알림 없음)
function saveDisplayConfigToServer() {
    const drawObjectsCheck = document.getElementById('drawObjectsCheck');
    const drawZonesCheck = document.getElementById('drawZonesCheck'); // 추가
    const showOnlyAlertCheck = document.getElementById('showOnlyAlertCheck');

    const data = {
        draw_objects: drawObjectsCheck ? drawObjectsCheck.checked : true,
        draw_zones: drawZonesCheck ? drawZonesCheck.checked : true, // 추가
        show_only_alert: showOnlyAlertCheck ? showOnlyAlertCheck.checked : false
    };

    fetch('/update_display_config', { 
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data),
    })
    .then(response => response.json())
    .then(data => {
        // 성공 시 아무것도 안 함 (조용히 저장)
    })
    .catch(error => console.error('설정 전송 오류'));
}

window.changeSource = function(source, type) {
    fetch('/change_source', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ source: source, type: type }),
    })
    .then(response => response.json())
    .then(data => {
        if(data.status === 'success') {
            const img = document.getElementById('videoStream');
            if (img) {
                img.src = "/video_feed?" + new Date().getTime();
                img.onload = resizeCanvas;
            }
            
            if (data.config) {
                applyConfigToUI(data.config);
            }
        } else {
            alert('소스 변경 실패');
        }
    });
}

function applyConfigToUI(config) {
    if (!config) return;

    if (config.zones) {
        zones = config.zones;
        drawAllZones();
        updateZoneListUI();
    }

    if (config.expand_ratio !== undefined) {
        const expandSlider = document.getElementById('expandSlider');
        if (expandSlider) {
            expandSlider.value = config.expand_ratio * 100;
            document.getElementById('expandVal').innerText = expandSlider.value;
        }
    }

    if (config.conf !== undefined) {
        const confSlider = document.getElementById('confSlider');
        if (confSlider) {
            confSlider.value = config.conf;
            document.getElementById('confVal').innerText = Math.round(config.conf * 100);
        }
    }
    
    if (config.height_limit !== undefined) {
        const heightSlider = document.getElementById('heightSlider');
        if (heightSlider) {
            heightSlider.value = config.height_limit;
            document.getElementById('heightVal').innerText = config.height_limit;
        }
    }
    if (config.elbow_angle !== undefined) {
        const angleSlider = document.getElementById('angleSlider');
        if (angleSlider) {
            angleSlider.value = config.elbow_angle;
            document.getElementById('angleVal').innerText = config.elbow_angle;
        }
    }
    if (config.reach_enabled !== undefined) {
        const reachCheck = document.getElementById('reachCheck');
        if (reachCheck) reachCheck.checked = config.reach_enabled;
    }
    if (config.fall_enabled !== undefined) {
        const fallCheck = document.getElementById('fallCheck');
        if (fallCheck) fallCheck.checked = config.fall_enabled;
    }
    
    // [추가] 화면 표시 설정 복원
    if (config.draw_objects !== undefined) {
        const drawObjectsCheck = document.getElementById('drawObjectsCheck');
        if (drawObjectsCheck) drawObjectsCheck.checked = config.draw_objects;
    }
    if (config.draw_zones !== undefined) { // 추가
        const drawZonesCheck = document.getElementById('drawZonesCheck');
        if (drawZonesCheck) drawZonesCheck.checked = config.draw_zones;
    }
    if (config.show_only_alert !== undefined) {
        const showOnlyAlertCheck = document.getElementById('showOnlyAlertCheck');
        if (showOnlyAlertCheck) showOnlyAlertCheck.checked = config.show_only_alert;
    }
}

window.uploadVideo = function() {
    const fileInput = document.getElementById('videoUpload');
    const file = fileInput.files[0];
    if (!file) {
        alert("파일을 선택해주세요.");
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    fetch('/upload_video', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if(data.status === 'success') {
            alert('업로드 완료! 영상을 재생합니다.');
            loadVideoList();
            const select = document.getElementById('videoSelect');
            if (select) {
                setTimeout(() => { select.value = data.source; }, 500);
            }
            const img = document.getElementById('videoStream');
            if (img) {
                img.src = "/video_feed?" + new Date().getTime();
                img.onload = resizeCanvas;
            }
            
            zones = [];
            drawAllZones();
            updateZoneListUI();
        } else {
            alert('업로드 실패: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('업로드 중 오류 발생');
    });
}

// [추가] 로그 업데이트 함수
function updateLogs() {
    fetch('/get_logs')
    .then(response => response.json())
    .then(data => {
        const logContainer = document.querySelector('#monitor .list-group');
        if (!logContainer) return;

        // 기존 로그 유지하면서 새로운 로그가 있으면 업데이트
        // 여기서는 간단하게 전체를 다시 그림 (성능 최적화 필요 시 수정 가능)
        if (data.logs.length > 0) {
            logContainer.innerHTML = ''; // 초기화
            data.logs.forEach(log => {
                const item = document.createElement('div');
                let colorClass = 'list-group-item-light';
                if (log.level === 'danger') colorClass = 'list-group-item-danger';
                if (log.level === 'warning') colorClass = 'list-group-item-warning';
                
                item.className = `list-group-item ${colorClass}`;
                item.innerHTML = `<span class="fw-bold">[${log.time}]</span> ${log.message}`;
                logContainer.appendChild(item);
            });
        }
    });
}
