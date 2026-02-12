from flask import Flask, render_template, request, jsonify, send_file, session
from datetime import datetime, timedelta
import sqlite3
import json
import os
from io import BytesIO
import shutil
from functools import wraps
import pytz

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-very-secret-key-change-this-in-production-12345'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

PASSWORD = '7777'
TIMEZONE = pytz.timezone('Asia/Shanghai')

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'piano_practice.db')

def get_local_now():
    return datetime.now(TIMEZONE)

def get_local_today():
    return get_local_now().strftime('%Y-%m-%d')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS practice_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            start_time TEXT,
            end_time TEXT,
            duration INTEGER,
            collection TEXT,
            piece TEXT,
            section TEXT,
            bpm TEXT,
            practice_type TEXT,
            pause_count INTEGER DEFAULT 0,
            notes TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    default_settings = {
        'collections': '["车尔尼599", "哈农", "拜厄", "小奏鸣曲集"]',
        'pieces': '["No.1", "No.2", "No.3", "练习曲1", "练习曲2"]',
        'sections': '["第1-8小节", "第9-16小节", "第17-24小节", "第25-32小节", "全曲"]',
        'practice_types': '["基础练习", "练习曲", "乐曲演奏", "视奏训练", "乐理学习"]'
    }
    
    for key, value in default_settings.items():
        cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', 
                      (key, value))
    
    conn.commit()
    conn.close()

init_db()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return jsonify({'error': '需要登录', 'login_required': True}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        password = data.get('password', '')
        
        if password == PASSWORD:
            session['logged_in'] = True
            session.permanent = True
            return jsonify({'success': True, 'message': '登录成功！'})
        else:
            return jsonify({'success': False, 'message': '密码错误！'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('logged_in', None)
    return jsonify({'success': True, 'message': '已退出登录'})

@app.route('/api/check-login', methods=['GET'])
def check_login():
    return jsonify({'logged_in': session.get('logged_in', False)})

@app.route('/api/settings', methods=['GET'])
def get_settings():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT key, value FROM settings')
        settings = {}
        for row in cursor.fetchall():
            try:
                settings[row['key']] = json.loads(row['value'])
            except:
                settings[row['key']] = row['value']
        conn.close()
        return jsonify(settings)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/<key>', methods=['PUT'])
@login_required
def update_setting(key):
    try:
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        value = json.dumps(data['value'], ensure_ascii=False) if isinstance(data['value'], list) else data['value']
        cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/sessions', methods=['GET'])
def get_sessions():
    try:
        days = request.args.get('days', 7, type=int)
        collection = request.args.get('collection', '')
        
        start_date = (get_local_now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        conn = get_db()
        cursor = conn.cursor()
        
        if collection and collection != '全部':
            cursor.execute('''
                SELECT * FROM practice_sessions 
                WHERE date >= ? AND collection = ?
                ORDER BY date DESC, start_time DESC
            ''', (start_date, collection))
        else:
            cursor.execute('''
                SELECT * FROM practice_sessions 
                WHERE date >= ?
                ORDER BY date DESC, start_time DESC
            ''', (start_date,))
        
        sessions = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify(sessions)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/sessions', methods=['POST'])
@login_required
def create_session():
    try:
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO practice_sessions 
            (date, start_time, end_time, duration, collection, piece, section, bpm, 
             practice_type, pause_count, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (data['date'], data['start_time'], data['end_time'], data['duration'],
              data['collection'], data['piece'], data['section'], data['bpm'],
              data['practice_type'], data['pause_count'], data['notes']))
        
        conn.commit()
        session_id = cursor.lastrowid
        conn.close()
        return jsonify({'success': True, 'id': session_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/sessions/<int:session_id>', methods=['PUT'])
@login_required
def update_session(session_id):
    try:
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE practice_sessions 
            SET date=?, start_time=?, end_time=?, duration=?, collection=?, 
                piece=?, section=?, bpm=?, practice_type=?, pause_count=?, notes=?
            WHERE id=?
        ''', (data['date'], data['start_time'], data['end_time'], data['duration'],
              data['collection'], data['piece'], data['section'], data['bpm'],
              data['practice_type'], data['pause_count'], data['notes'], session_id))
        
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/sessions/<int:session_id>', methods=['DELETE'])
@login_required
def delete_session(session_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM practice_sessions WHERE id = ?', (session_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats/today', methods=['GET'])
def get_today_stats():
    try:
        today = get_local_today()
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*), SUM(duration), SUM(pause_count)
            FROM practice_sessions
            WHERE date = ?
        ''', (today,))
        
        result = cursor.fetchone()
        conn.close()
        
        return jsonify({
            'count': result[0] or 0,
            'duration': result[1] or 0,
            'total_pause': result[2] or 0
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats/period', methods=['GET'])
def get_period_stats():
    try:
        days = request.args.get('days', 30, type=int)
        start_date = (get_local_now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT SUM(duration), COUNT(*), AVG(pause_count)
            FROM practice_sessions
            WHERE date >= ?
        ''', (start_date,))
        total_stats = cursor.fetchone()
        
        prev_start = (get_local_now() - timedelta(days=days*2)).strftime('%Y-%m-%d')
        prev_end = (get_local_now() - timedelta(days=days+1)).strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT SUM(duration)
            FROM practice_sessions
            WHERE date >= ? AND date <= ?
        ''', (prev_start, prev_end))
        prev_duration = cursor.fetchone()[0] or 0
        
        current_duration = total_stats[0] or 0
        if prev_duration > 0:
            change_percent = ((current_duration - prev_duration) / prev_duration) * 100
        else:
            change_percent = 100 if current_duration > 0 else 0
        
        cursor.execute('SELECT DISTINCT date FROM practice_sessions ORDER BY date DESC')
        dates = [row[0] for row in cursor.fetchall()]
        consecutive = 0
        yesterday = (get_local_now() - timedelta(days=1)).date()
        
        for i in range(len(dates)):
            date = datetime.strptime(dates[i], '%Y-%m-%d').date()
            expected_date = yesterday - timedelta(days=i)
            if date != expected_date:
                break
            consecutive += 1
        
        conn.close()
        
        return jsonify({
            'total_duration': current_duration,
            'total_count': total_stats[1] or 0,
            'avg_pause': round(total_stats[2] or 0, 1),
            'consecutive_days': consecutive,
            'change_percent': round(change_percent, 1)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/heatmap-data', methods=['GET'])
def get_heatmap_data():
    """获取当前年份全年热力图数据"""
    try:
        # 获取当前年份的1月1日到12月31日
        current_year = get_local_now().year
        start_date = f'{current_year}-01-01'
        end_date = f'{current_year}-12-31'
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT date, SUM(duration) as total_duration
            FROM practice_sessions
            WHERE date >= ? AND date <= ?
            GROUP BY date
            ORDER BY date
        ''', (start_date, end_date))
        
        data = {}
        for row in cursor.fetchall():
            data[row[0]] = row[1] / 60
        
        conn.close()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/trend-data', methods=['GET'])
def get_trend_data():
    """获取趋势对比数据"""
    try:
        days = request.args.get('days', 30, type=int)
        
        conn = get_db()
        cursor = conn.cursor()
        
        current_start = (get_local_now() - timedelta(days=days)).strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT date, SUM(duration) as total_duration
            FROM practice_sessions
            WHERE date >= ?
            GROUP BY date
            ORDER BY date
        ''', (current_start,))
        current_data = {row[0]: row[1] / 60 for row in cursor.fetchall()}
        
        prev_start = (get_local_now() - timedelta(days=days*2)).strftime('%Y-%m-%d')
        prev_end = (get_local_now() - timedelta(days=days+1)).strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT date, SUM(duration) as total_duration
            FROM practice_sessions
            WHERE date >= ? AND date <= ?
            GROUP BY date
            ORDER BY date
        ''', (prev_start, prev_end))
        prev_data = {row[0]: row[1] / 60 for row in cursor.fetchall()}
        
        conn.close()
        
        return jsonify({
            'current': current_data,
            'previous': prev_data
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/export', methods=['GET'])
def export_data():
    try:
        if not os.path.exists(DB_PATH):
            return jsonify({'error': '数据库文件不存在'}), 404
        
        timestamp = get_local_now().strftime('%Y%m%d_%H%M%S')
        filename = f'piano_practice_backup_{timestamp}.db'
        
        return send_file(
            DB_PATH,
            mimetype='application/octet-stream',
            as_attachment=True,
            download_name=filename
        )
    except:
        try:
            with open(DB_PATH, 'rb') as f:
                db_data = f.read()
            
            memory_file = BytesIO(db_data)
            memory_file.seek(0)
            
            timestamp = get_local_now().strftime('%Y%m%d_%H%M%S')
            filename = f'piano_practice_backup_{timestamp}.db'
            
            return send_file(
                memory_file,
                mimetype='application/octet-stream',
                as_attachment=True,
                download_name=filename
            )
        except Exception as e:
            return jsonify({'error': str(e)}), 500

@app.route('/api/import', methods=['POST'])
@login_required
def import_data():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '没有上传文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': '文件名为空'}), 400
    
    if not file.filename.endswith('.db'):
        return jsonify({'success': False, 'error': '只支持.db文件'}), 400
    
    try:
        backup_filename = f'piano_practice_backup_{get_local_now().strftime("%Y%m%d_%H%M%S")}.db'
        backup_path = os.path.join(BASE_DIR, backup_filename)
        shutil.copy2(DB_PATH, backup_path)
        
        temp_path = os.path.join(BASE_DIR, 'temp_upload.db')
        file.save(temp_path)
        
        try:
            test_conn = sqlite3.connect(temp_path)
            test_cursor = test_conn.cursor()
            test_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in test_cursor.fetchall()]
            test_conn.close()
            
            if 'practice_sessions' not in tables or 'settings' not in tables:
                os.remove(temp_path)
                return jsonify({'success': False, 'error': '数据库文件格式不正确'}), 400
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return jsonify({'success': False, 'error': f'无效的数据库文件: {str(e)}'}), 400
        
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        os.rename(temp_path, DB_PATH)
        
        return jsonify({
            'success': True, 
            'message': f'数据导入成功！原数据已备份到: {backup_filename}'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
