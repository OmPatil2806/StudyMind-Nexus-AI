from flask import Blueprint, jsonify, session
from backend.database import get_db
from datetime import datetime, timedelta

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/stats', methods=['GET'])
def get_stats():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    user_id = session['user_id']
    conn = get_db()

    total = conn.execute('SELECT COUNT(*) as c FROM study_tasks WHERE user_id = ?', (user_id,)).fetchone()['c']
    completed = conn.execute(
        "SELECT COUNT(*) as c FROM study_tasks WHERE user_id = ? AND status = 'completed'", (user_id,)
    ).fetchone()['c']
    pending = total - completed

    productivity_score = round((completed / total * 100) if total > 0 else 0, 1)

    # Focus trend: last 7 days
    seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
    focus_logs = conn.execute(
        '''SELECT DATE(logged_at) as day, predicted_focus, COUNT(*) as count
           FROM focus_logs WHERE user_id = ? AND logged_at >= ?
           GROUP BY day, predicted_focus ORDER BY day''',
        (user_id, seven_days_ago)
    ).fetchall()

    focus_trend = {}
    for row in focus_logs:
        day = row['day']
        if day not in focus_trend:
            focus_trend[day] = {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
        focus_trend[day][row['predicted_focus']] = row['count']

    # Subject breakdown
    subjects = conn.execute(
        '''SELECT subject, COUNT(*) as total,
           SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as done
           FROM study_tasks WHERE user_id = ?
           GROUP BY subject''',
        (user_id,)
    ).fetchall()

    # Tasks completed per day (last 14 days)
    fourteen_days_ago = (datetime.now() - timedelta(days=14)).isoformat()
    daily_completions = conn.execute(
        '''SELECT DATE(completed_at) as day, COUNT(*) as count
           FROM study_tasks
           WHERE user_id = ? AND status = 'completed' AND completed_at >= ?
           GROUP BY day ORDER BY day''',
        (user_id, fourteen_days_ago)
    ).fetchall()

    # Avg difficulty of completed tasks
    avg_difficulty = conn.execute(
        "SELECT AVG(difficulty) as avg FROM study_tasks WHERE user_id = ? AND status = 'completed'",
        (user_id,)
    ).fetchone()['avg'] or 0

    conn.close()

    return jsonify({
        'total_tasks': total,
        'completed_tasks': completed,
        'pending_tasks': pending,
        'productivity_score': productivity_score,
        'avg_difficulty': round(avg_difficulty, 1),
        'focus_trend': focus_trend,
        'subject_breakdown': [dict(s) for s in subjects],
        'daily_completions': [dict(d) for d in daily_completions]
    })
