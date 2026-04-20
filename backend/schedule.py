from flask import Blueprint, request, jsonify, session
from ml.focus_predictor import predict_focus
from backend.database import get_db
from datetime import datetime, timedelta

schedule_bp = Blueprint('schedule', __name__)

# Hours considered good for study (morning and afternoon peaks)
STUDY_HOURS = [7, 8, 9, 10, 14, 15, 16, 17, 19, 20]

@schedule_bp.route('/generate-schedule', methods=['POST'])
def generate_schedule():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    user_id = session['user_id']
    conn = get_db()

    # Get pending tasks sorted by due date and priority
    tasks = conn.execute(
        '''SELECT * FROM study_tasks
           WHERE user_id = ? AND status = 'pending'
           ORDER BY due_date ASC, priority DESC''',
        (user_id,)
    ).fetchall()

    if not tasks:
        conn.close()
        return jsonify({'message': 'No pending tasks', 'schedule': []})

    # Clear existing schedule
    conn.execute('DELETE FROM schedule WHERE user_id = ?', (user_id,))

    today = datetime.now().date()
    schedule_entries = []

    for task in tasks:
        due = datetime.strptime(task['due_date'], '%Y-%m-%d').date()
        days_until_due = (due - today).days
        search_window = max(1, min(days_until_due, 7))

        best_slot = None
        best_confidence = -1

        for day_offset in range(search_window):
            target_date = today + timedelta(days=day_offset)
            for hour in STUDY_HOURS:
                result = predict_focus(hour, task['difficulty'], task['estimated_time'])
                if result['confidence'] > best_confidence:
                    best_confidence = result['confidence']
                    best_slot = {
                        'date': target_date.isoformat(),
                        'hour': hour,
                        'focus_level': result['focus_level'],
                        'confidence': result['confidence']
                    }
                    if result['focus_level'] == 'HIGH' and result['confidence'] > 0.8:
                        break
            if best_slot and best_slot['focus_level'] == 'HIGH':
                break

        if best_slot:
            reason = _build_reason(best_slot, days_until_due)
            cursor = conn.execute(
                '''INSERT INTO schedule (user_id, task_id, suggested_date, suggested_hour, focus_level, reason)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (user_id, task['id'], best_slot['date'], best_slot['hour'],
                 best_slot['focus_level'], reason)
            )
            schedule_entries.append({
                'id': cursor.lastrowid,
                'task_id': task['id'],
                'task_title': task['title'],
                'subject': task['subject'],
                'suggested_date': best_slot['date'],
                'suggested_hour': best_slot['hour'],
                'focus_level': best_slot['focus_level'],
                'confidence': round(best_slot['confidence'], 2),
                'reason': reason,
                'estimated_time': task['estimated_time']
            })

    conn.commit()
    conn.close()
    return jsonify({'schedule': schedule_entries})

@schedule_bp.route('/schedule', methods=['GET'])
def get_schedule():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    conn = get_db()
    rows = conn.execute(
        '''SELECT s.*, t.title as task_title, t.subject, t.estimated_time, t.difficulty
           FROM schedule s
           JOIN study_tasks t ON s.task_id = t.id
           WHERE s.user_id = ?
           ORDER BY s.suggested_date ASC, s.suggested_hour ASC''',
        (session['user_id'],)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

def _build_reason(slot, days_until_due):
    hour_label = f"{slot['hour']}:00"
    urgency = "urgent" if days_until_due <= 1 else "upcoming" if days_until_due <= 3 else "planned"
    return f"{slot['focus_level']} focus predicted at {hour_label} — {urgency} deadline"
