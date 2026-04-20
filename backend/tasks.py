from flask import Blueprint, request, jsonify, session
from backend.database import get_db
from datetime import datetime

tasks_bp = Blueprint('tasks', __name__)

def require_auth():
    if 'user_id' not in session:
        return None
    return session['user_id']

@tasks_bp.route('/tasks', methods=['GET'])
def get_tasks():
    user_id = require_auth()
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    conn = get_db()
    tasks = conn.execute(
        'SELECT * FROM study_tasks WHERE user_id = ? ORDER BY due_date ASC',
        (user_id,)
    ).fetchall()
    conn.close()
    return jsonify([dict(t) for t in tasks])

@tasks_bp.route('/tasks', methods=['POST'])
def create_task():
    user_id = require_auth()
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.get_json()
    required = ['title', 'subject', 'difficulty', 'estimated_time', 'due_date']
    if not all(k in data for k in required):
        return jsonify({'error': 'Missing fields'}), 400

    conn = get_db()
    cursor = conn.execute(
        '''INSERT INTO study_tasks (user_id, title, subject, difficulty, estimated_time, due_date, priority)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (user_id, data['title'], data['subject'], data['difficulty'],
         data['estimated_time'], data['due_date'], data.get('priority', 3))
    )
    conn.commit()
    task = conn.execute('SELECT * FROM study_tasks WHERE id = ?', (cursor.lastrowid,)).fetchone()
    conn.close()
    return jsonify(dict(task)), 201

@tasks_bp.route('/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    user_id = require_auth()
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.get_json()
    conn = get_db()
    task = conn.execute('SELECT * FROM study_tasks WHERE id = ? AND user_id = ?', (task_id, user_id)).fetchone()
    if not task:
        conn.close()
        return jsonify({'error': 'Task not found'}), 404

    fields = ['title', 'subject', 'difficulty', 'estimated_time', 'due_date', 'status', 'priority']
    updates = {k: data[k] for k in fields if k in data}

    if updates.get('status') == 'completed' and task['status'] != 'completed':
        updates['completed_at'] = datetime.now().isoformat()

    set_clause = ', '.join(f'{k} = ?' for k in updates)
    values = list(updates.values()) + [task_id]
    conn.execute(f'UPDATE study_tasks SET {set_clause} WHERE id = ?', values)
    conn.commit()
    updated = conn.execute('SELECT * FROM study_tasks WHERE id = ?', (task_id,)).fetchone()
    conn.close()
    return jsonify(dict(updated))

@tasks_bp.route('/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    user_id = require_auth()
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    conn = get_db()
    result = conn.execute('DELETE FROM study_tasks WHERE id = ? AND user_id = ?', (task_id, user_id))
    conn.commit()
    conn.close()
    if result.rowcount == 0:
        return jsonify({'error': 'Task not found'}), 404
    return jsonify({'message': 'Deleted'})
