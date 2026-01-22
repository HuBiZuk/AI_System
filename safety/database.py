import pymysql
import os
from datetime import datetime, timedelta

# MySQL 연결 설정
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',      
    'password': '12345', 
    'database': 'AI_Project', 
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor 
}

def get_connection():
    try:
        return pymysql.connect(**DB_CONFIG)
    except pymysql.err.OperationalError as e:
        if e.args[0] == 1049: 
            print("데이터베이스가 없어서 생성합니다.")
            create_database()
            return pymysql.connect(**DB_CONFIG)
        else:
            raise e

def create_database():
    temp_config = DB_CONFIG.copy()
    del temp_config['database']
    conn = pymysql.connect(**temp_config)
    c = conn.cursor()
    c.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']}")
    conn.commit()
    conn.close()

def init_db():
    try:
        conn = get_connection()
        c = conn.cursor()
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INT NOT NULL AUTO_INCREMENT,
                timestamp VARCHAR(255) NOT NULL,
                level VARCHAR(50) NOT NULL,
                message TEXT NOT NULL,
                source VARCHAR(255),
                PRIMARY KEY (id)
            )
        ''')
        
        conn.commit()
        conn.close()
        print("MySQL DB 초기화 완료")
    except Exception as e:
        print(f"DB 초기화 오류: {e}")

def insert_log(level, message, source='unknown'):
    try:
        conn = get_connection()
        c = conn.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        c.execute("INSERT INTO logs (timestamp, level, message, source) VALUES (%s, %s, %s, %s)",
                  (timestamp, level, message, source))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB 저장 오류: {e}")

# [수정] 로그 조회 (필터링 추가)
def get_all_logs(limit=100, source_filter=None):
    try:
        conn = get_connection()
        c = conn.cursor()
        
        query = "SELECT * FROM logs"
        params = []
        
        if source_filter and source_filter != 'all':
            query += " WHERE source = %s"
            params.append(source_filter)
            
        query += " ORDER BY id DESC LIMIT %s"
        params.append(limit)
        
        c.execute(query, tuple(params))
        rows = c.fetchall()
        
        conn.close()
        return rows 
    except Exception as e:
        print(f"로그 조회 오류: {e}")
        return []

# [수정] 통계 조회 (필터링 추가)
def get_stats_by_date(days=7, source_filter=None):
    try:
        conn = get_connection()
        c = conn.cursor()
        
        # 날짜 필터 계산
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        query = '''
            SELECT SUBSTRING(timestamp, 1, 10) as date, count(*) as count
            FROM logs 
            WHERE level = 'danger' AND timestamp >= %s
        '''
        params = [start_date]
        
        if source_filter and source_filter != 'all':
            query += " AND source = %s"
            params.append(source_filter)
            
        query += " GROUP BY date ORDER BY date DESC"
        
        c.execute(query, tuple(params))
        rows = c.fetchall()
        conn.close()
        
        labels = []
        data = []
        for row in reversed(rows): 
            labels.append(row['date'])
            data.append(row['count'])
            
        return {'labels': labels, 'data': data}
    except Exception as e:
        print(f"통계 조회 오류: {e}")
        return {'labels': [], 'data': []}

# [추가] 소스별 통계 조회 (원형 차트용)
def get_stats_by_source(days=7):
    try:
        conn = get_connection()
        c = conn.cursor()
        
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        c.execute('''
            SELECT source, count(*) as count
            FROM logs 
            WHERE level = 'danger' AND timestamp >= %s
            GROUP BY source
            ORDER BY count DESC
        ''', (start_date,))
        rows = c.fetchall()
        conn.close()
        
        labels = []
        data = []
        for row in rows:
            labels.append(row['source'] if row['source'] else 'Unknown')
            data.append(row['count'])
            
        return {'labels': labels, 'data': data}
    except Exception as e:
        print(f"소스 통계 조회 오류: {e}")
        return {'labels': [], 'data': []}

def get_source_list():
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT DISTINCT source FROM logs ORDER BY source")
        rows = c.fetchall()
        conn.close()
        return [row['source'] for row in rows if row['source']]
    except Exception as e:
        return []
