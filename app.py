from flask import Flask, render_template, request, jsonify, send_file
from datetime import datetime, timedelta
import sqlite3
import json
import os
from io import BytesIO
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import matplotlib.dates as mdates
import base64
import shutil

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here-change-in-production'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# 设置matplotlib中文显示
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect('piano_practice.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """初始化数据库"""
    conn = get_db()
    cursor = conn.cursor()
    
    # 创建练习记录表
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
    
    # 创建设置表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # 初始化默认设置
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

# 初始化数据库
init_db()

# ==================== 页面路由 ====================

@app.route('/')
def index():
    """主页面"""
    return render_template('index.html')

# ==================== API路由 ====================

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """获取所有设置"""
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

@app.route('/api/settings/<key>', methods=['PUT'])
def update_setting(key):
    """更新设置"""
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    value = json.dumps(data['value'], ensure_ascii=False) if isinstance(data['value'], list) else data['value']
    cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/sessions', methods=['GET'])
def get_sessions():
    """获取练习记录"""
    days = request.args.get('days', 7, type=int)
    collection = request.args.get('collection', '')
    
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
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

@app.route('/api/sessions', methods=['POST'])
def create_session():
    """创建练习记录"""
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

@app.route('/api/sessions/<int:session_id>', methods=['PUT'])
def update_session(session_id):
    """更新练习记录"""
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

@app.route('/api/sessions/<int:session_id>', methods=['DELETE'])
def delete_session(session_id):
    """删除练习记录"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM practice_sessions WHERE id = ?', (session_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/stats/today', methods=['GET'])
def get_today_stats():
    """获取今日统计"""
    today = datetime.now().strftime('%Y-%m-%d')
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT COUNT(*), SUM(duration), AVG(pause_count)
        FROM practice_sessions
        WHERE date = ?
    ''', (today,))
    
    result = cursor.fetchone()
    conn.close()
    
    return jsonify({
        'count': result[0] or 0,
        'duration': result[1] or 0,
        'avg_pause': round(result[2] or 0, 1)
    })

@app.route('/api/stats/period', methods=['GET'])
def get_period_stats():
    """获取周期统计"""
    days = request.args.get('days', 30, type=int)
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    conn = get_db()
    cursor = conn.cursor()
    
    # 总统计
    cursor.execute('''
        SELECT SUM(duration), COUNT(*), AVG(pause_count)
        FROM practice_sessions
        WHERE date >= ?
    ''', (start_date,))
    total_stats = cursor.fetchone()
    
    # 连续打卡
    cursor.execute('SELECT DISTINCT date FROM practice_sessions ORDER BY date DESC')
    dates = [row[0] for row in cursor.fetchall()]
    consecutive = 0
    today = datetime.now().date()
    for i in range(len(dates)):
        date = datetime.strptime(dates[i], '%Y-%m-%d').date()
        expected_date = today - timedelta(days=i)
        if date != expected_date:
            break
        consecutive += 1
    
    conn.close()
    
    return jsonify({
        'total_duration': total_stats[0] or 0,
        'total_count': total_stats[1] or 0,
        'avg_pause': round(total_stats[2] or 0, 1),
        'consecutive_days': consecutive
    })

@app.route('/api/charts/<chart_type>', methods=['GET'])
def get_chart(chart_type):
    """生成图表"""
    days = request.args.get('days', 30, type=int)
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    conn = get_db()
    cursor = conn.cursor()
    
    fig = Figure(figsize=(10, 6), dpi=80)
    fig.patch.set_facecolor('#1e1e1e')
    ax = fig.add_subplot(111)
    ax.set_facecolor('#1e1e1e')
    
    if chart_type == 'duration_trend':
        # 练习时长趋势
        cursor.execute('''
            SELECT date, SUM(duration) 
            FROM practice_sessions 
            WHERE date >= ?
            GROUP BY date
            ORDER BY date
        ''', (start_date,))
        
        data = cursor.fetchall()
        if data:
            dates = [datetime.strptime(row[0], '%Y-%m-%d') for row in data]
            durations = [row[1] / 60 for row in data]
            
            ax.plot(dates, durations, marker='o', linewidth=2, color='#1f77b4')
            ax.fill_between(dates, durations, alpha=0.3, color='#1f77b4')
            ax.set_title('练习时长趋势', color='white', fontsize=14)
            ax.set_xlabel('日期', color='white')
            ax.set_ylabel('分钟', color='white')
            ax.grid(True, alpha=0.2, color='white')
            ax.tick_params(colors='white')
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
            fig.autofmt_xdate()
    
    elif chart_type == 'type_distribution':
        # 练习类型分布
        cursor.execute('''
            SELECT practice_type, COUNT(*) 
            FROM practice_sessions 
            WHERE date >= ?
            GROUP BY practice_type
        ''', (start_date,))
        
        data = cursor.fetchall()
        if data:
            labels = [row[0] for row in data]
            sizes = [row[1] for row in data]
            colors = ['#ff9999', '#66b3ff', '#99ff99', '#ffcc99', '#ff99cc']
            
            ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90,
                   colors=colors, textprops={'color': 'white'})
            ax.set_title('练习类型分布', color='white', fontsize=14)
    
    conn.close()
    
    # 转换为base64
    buf = BytesIO()
    fig.savefig(buf, format='png', facecolor='#1e1e1e', edgecolor='none', bbox_inches='tight')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    
    return jsonify({'image': f'data:image/png;base64,{img_base64}'})

@app.route('/api/export', methods=['GET'])
def export_data():
    """导出数据"""
    return send_file('piano_practice.db', as_attachment=True,
                    download_name=f'piano_practice_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db')

@app.route('/api/import', methods=['POST'])
def import_data():
    """导入数据"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '没有上传文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': '文件名为空'}), 400
    
    if not file.filename.endswith('.db'):
        return jsonify({'success': False, 'error': '只支持.db文件'}), 400
    
    try:
        # 备份当前数据库
        backup_filename = f'piano_practice_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
        shutil.copy2('piano_practice.db', backup_filename)
        
        # 保存上传的文件
        temp_path = 'temp_upload.db'
        file.save(temp_path)
        
        # 验证是否是有效的数据库文件
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
            os.remove(temp_path)
            return jsonify({'success': False, 'error': f'无效的数据库文件: {str(e)}'}), 400
        
        # 替换当前数据库
        os.replace(temp_path, 'piano_practice.db')
        
        return jsonify({
            'success': True, 
            'message': f'数据导入成功！原数据已备份到: {backup_filename}'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
