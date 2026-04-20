import os
import sys
import json
import urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, send_from_directory, session, request, jsonify
from flask_cors import CORS
from backend.database import init_db
from backend.auth import auth_bp
from backend.tasks import tasks_bp
from backend.focus import focus_bp
from backend.schedule import schedule_bp
from backend.analytics import analytics_bp

app = Flask(__name__, static_folder='frontend', static_url_path='')
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production-xyz')
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True

CORS(app, supports_credentials=True)

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(focus_bp)
app.register_blueprint(schedule_bp)
app.register_blueprint(analytics_bp)

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

STUDY_SYSTEM_PROMPT = """You are StudyMind AI Tutor — an expert, friendly academic assistant embedded inside a study planner app. You help students with:
- Explaining concepts clearly across all subjects (Math, Science, History, Languages, etc.)
- Study strategies, memory techniques, and focus tips
- Breaking down complex topics step-by-step
- Creating study plans and schedules
- Exam preparation and practice questions
- Understanding and solving homework problems

Keep responses clear, structured, and encouraging. Use bullet points or numbered steps when helpful. Be concise but thorough. If asked about something unrelated to studying or learning, gently redirect back to academic topics."""

@app.route('/api/chat', methods=['POST'])
def chat():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.get_json()
    messages = data.get('messages', [])
    if not messages:
        return jsonify({'error': 'No messages provided'}), 400

    # Keep last 20 messages for context window
    messages = messages[-20:]

    if not ANTHROPIC_API_KEY:
        # Fallback: smart rule-based responses when no API key
        user_msg = messages[-1].get('content', '').lower()
        reply = get_fallback_response(user_msg)
        return jsonify({'reply': reply})

    try:
        payload = json.dumps({
            'model': 'claude-haiku-4-5-20251001',
            'max_tokens': 1024,
            'system': STUDY_SYSTEM_PROMPT,
            'messages': messages
        }).encode('utf-8')

        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages',
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01'
            },
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            reply = result['content'][0]['text']
            return jsonify({'reply': reply})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_fallback_response(msg):
    """Smart fallback when no API key is set."""
    if any(w in msg for w in ['focus', 'concentrate', 'distract']):
        return "Great question about focus! Here are proven techniques:\n\n• **Pomodoro Technique**: 25 min work + 5 min break\n• **Eliminate distractions**: Phone on silent, website blockers\n• **Single-tasking**: One task at a time\n• **Environment**: Clean desk, good lighting\n• **Body**: Stay hydrated, avoid heavy meals before studying\n\nThe app's Focus Predictor can tell you your best study hours!"
    if any(w in msg for w in ['study plan', 'schedule', 'organize']):
        return "Here's how to build an effective study plan:\n\n1. **List all subjects/tasks** — use the Planner tab\n2. **Prioritize by deadline and difficulty**\n3. **Use the Smart Scheduler** — it picks your peak focus hours\n4. **Block time daily** — consistency beats cramming\n5. **Review weekly** — adjust based on progress\n\nTip: Study hardest subjects during HIGH focus periods (usually 8–11am)!"
    if any(w in msg for w in ['exam', 'test', 'quiz']):
        return "Exam preparation tips:\n\n• **Spaced repetition**: Review material over multiple days\n• **Active recall**: Test yourself instead of re-reading\n• **Past papers**: Practice with real exam questions\n• **Teach it**: Explain concepts to someone else\n• **Sleep**: Don't sacrifice sleep before exams — memory consolidates during sleep\n• **Start early**: Begin revision 2 weeks before the exam"
    if any(w in msg for w in ['math', 'calculus', 'algebra', 'equation']):
        return "For Mathematics:\n\n• **Understand, don't memorize**: Focus on WHY formulas work\n• **Practice daily**: Math is a skill — 30 min/day beats 3 hours once a week\n• **Work examples step-by-step**: Write every step out\n• **Identify weak areas**: Use past mistakes as a guide\n• **Resources**: Khan Academy, Wolfram Alpha for checking work\n\nWhat specific math topic can I help you with?"
    if any(w in msg for w in ['memory', 'remember', 'memorize', 'forget']):
        return "Memory techniques that actually work:\n\n• **Spaced Repetition**: Review at increasing intervals (1 day → 3 days → 1 week)\n• **Mnemonics**: Create acronyms or stories\n• **Mind Maps**: Visual connections between concepts\n• **Chunking**: Group related info together\n• **Sleep**: Crucial for memory consolidation\n• **Retrieval Practice**: Test yourself — don't just re-read\n\nApps like Anki use spaced repetition automatically!"
    return "I'm your AI Study Tutor! I can help you with:\n\n• **Subject explanations** — Math, Science, History, Languages\n• **Study strategies** — focus, memory, time management\n• **Exam preparation** — tips and practice approaches\n• **Study planning** — how to organize your workload\n\n💡 **Tip**: Set your `ANTHROPIC_API_KEY` environment variable to unlock full AI-powered responses!\n\nWhat would you like help with today?"

@app.route('/')
def index():
    return send_from_directory('frontend', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('frontend', path)

if __name__ == '__main__':
    init_db()
    from ml.focus_predictor import _load_model
    _load_model()
    has_key = bool(ANTHROPIC_API_KEY)
    print("✓ Database initialized")
    print("✓ ML model loaded")
    print(f"{'✓' if has_key else '⚠'} Anthropic API key {'found' if has_key else 'not set — chatbot uses fallback responses'}")
    print("✓ Starting server at http://localhost:5000")
    app.run(debug=True, port=5000)
