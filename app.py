from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
import sqlite3
import os
from functools import wraps
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'super_secret_exam_key'
DATABASE = 'database.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.execute('PRAGMA foreign_keys = ON')
    conn.row_factory = sqlite3.Row
    return conn

# Auth Decorator
def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please login to access this page.', 'warning')
                return redirect(url_for('index'))
            if role and session.get('role') != role:
                flash('Unauthorized access!', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login/<role>')
def login(role):
    if role not in ['admin', 'teacher', 'student']:
        return redirect(url_for('index'))
    return render_template('login.html', role=role)

@app.route('/login/<role>', methods=['POST'])
def login_post(role):
    username = request.form.get('username')
    password = request.form.get('password')
    
    db = get_db()
    table = 'admins' if role == 'admin' else ('teachers' if role == 'teacher' else 'students')
    user = db.execute(f'SELECT * FROM {table} WHERE username = ?', (username,)).fetchone()
    db.close()

    if user and check_password_hash(user['password'], password):
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = role
        session['name'] = user['name'] if role != 'admin' else 'Admin'
        flash(f'Welcome back, {session["name"]}!', 'success')
        return redirect(url_for('dashboard'))
    else:
        flash('Invalid username or password.', 'danger')
        return redirect(url_for('login', role=role))

@app.route('/dashboard')
@login_required()
def dashboard():
    role = session.get('role')
    if role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif role == 'teacher':
        return redirect(url_for('teacher_dashboard'))
    else:
        return redirect(url_for('student_dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('index'))

# --- Admin Routes ---
@app.route('/admin/dashboard')
@login_required('admin')
def admin_dashboard():
    db = get_db()
    stats = {
        'teachers': db.execute('SELECT COUNT(*) FROM teachers').fetchone()[0],
        'students': db.execute('SELECT COUNT(*) FROM students').fetchone()[0],
        'exams': db.execute('SELECT COUNT(*) FROM exams').fetchone()[0]
    }
    
    # Data for Chart: Grade distribution
    grade_data = db.execute('''
        SELECT grade, COUNT(*) as count FROM results GROUP BY grade
    ''').fetchall()
    
    chart_labels = [r['grade'] for r in grade_data]
    chart_values = [r['count'] for r in grade_data]
    
    recent_results = db.execute('''
        SELECT r.*, s.name as student_name, e.title as exam_title 
        FROM results r
        JOIN students s ON r.student_id = s.id
        JOIN exams e ON r.exam_id = e.id
        ORDER BY r.attempted_at DESC LIMIT 5
    ''').fetchall()
    db.close()
    return render_template('admin/dashboard.html', stats=stats, recent_results=recent_results, 
                           chart_labels=chart_labels, chart_values=chart_values)

@app.route('/admin/teachers')
@login_required('admin')
def manage_teachers():
    db = get_db()
    teachers = db.execute('SELECT * FROM teachers').fetchall()
    db.close()
    return render_template('admin/manage_teachers.html', teachers=teachers)

@app.route('/admin/add-teacher', methods=['GET', 'POST'])
@login_required('admin')
def add_teacher():
    if request.method == 'POST':
        name = request.form['name']
        username = request.form['username']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        db = get_db()
        try:
            db.execute('INSERT INTO teachers (name, username, password, email) VALUES (?, ?, ?, ?)', 
                       (name, username, password, email))
            db.commit()
            flash('Teacher added successfully!', 'success')
        except sqlite3.IntegrityError:
            flash('Username or Email already exists!', 'danger')
        finally:
            db.close()
        return redirect(url_for('manage_teachers'))
    return render_template('admin/add_teacher.html')

@app.route('/admin/edit-teacher/<int:id>', methods=['GET', 'POST'])
@login_required('admin')
def edit_teacher(id):
    db = get_db()
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        db.execute('UPDATE teachers SET name = ?, email = ? WHERE id = ?', (name, email, id))
        db.commit()
        db.close()
        flash('Teacher updated!', 'success')
        return redirect(url_for('manage_teachers'))
    
    teacher = db.execute('SELECT * FROM teachers WHERE id = ?', (id,)).fetchone()
    db.close()
    return render_template('admin/add_teacher.html', teacher=teacher)

@app.route('/admin/delete-teacher/<int:id>')
@login_required('admin')
def delete_teacher(id):
    db = get_db()
    db.execute('DELETE FROM teachers WHERE id = ?', (id,))
    db.commit()
    db.close()
    flash('Teacher removed successfully.', 'success')
    return redirect(url_for('manage_teachers'))

@app.route('/admin/students')
@login_required('admin')
def manage_students():
    db = get_db()
    students = db.execute('SELECT * FROM students').fetchall()
    db.close()
    return render_template('admin/manage_students.html', students=students)

@app.route('/admin/add-student', methods=['GET', 'POST'])
@login_required('admin')
def add_student():
    if request.method == 'POST':
        name = request.form['name']
        username = request.form['username']
        email = request.form['email']
        roll_no = request.form['roll_no']
        password = generate_password_hash(request.form['password'])
        db = get_db()
        try:
            db.execute('INSERT INTO students (name, username, password, email, roll_no) VALUES (?, ?, ?, ?, ?)', 
                       (name, username, password, email, roll_no))
            db.commit()
            flash('Student added successfully!', 'success')
        except sqlite3.IntegrityError:
            flash('Username/Email/Roll No already exists!', 'danger')
        finally:
            db.close()
        return redirect(url_for('manage_students'))
    return render_template('admin/add_student.html')

@app.route('/admin/edit-student/<int:id>', methods=['GET', 'POST'])
@login_required('admin')
def edit_student(id):
    db = get_db()
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        roll_no = request.form['roll_no']
        db.execute('UPDATE students SET name = ?, email = ?, roll_no = ? WHERE id = ?', (name, email, roll_no, id))
        db.commit()
        db.close()
        flash('Student updated!', 'success')
        return redirect(url_for('manage_students'))
        
    student = db.execute('SELECT * FROM students WHERE id = ?', (id,)).fetchone()
    db.close()
    return render_template('admin/add_student.html', student=student)

@app.route('/admin/delete-student/<int:id>')
@login_required('admin')
def delete_student(id):
    db = get_db()
    db.execute('DELETE FROM students WHERE id = ?', (id,))
    db.commit()
    db.close()
    flash('Student removed successfully.', 'success')
    return redirect(url_for('manage_students'))

# --- Teacher Routes ---
@app.route('/teacher/dashboard')
@login_required('teacher')
def teacher_dashboard():
    db = get_db()
    teacher_id = session['user_id']
    exams = db.execute('SELECT * FROM exams WHERE teacher_id = ?', (teacher_id,)).fetchall()
    
    # Calculate some quick stats for teacher
    exam_stats = []
    for exam in exams:
        count = db.execute('SELECT COUNT(*) FROM results WHERE exam_id = ?', (exam['id'],)).fetchone()[0]
        avg = db.execute('SELECT AVG(percentage) FROM results WHERE exam_id = ?', (exam['id'],)).fetchone()[0]
        exam_stats.append({
            'id': exam['id'],
            'title': exam['title'],
            'attempts': count,
            'avg_score': round(avg, 2) if avg else 0,
            'duration': exam['duration'],
            'marks': exam['total_marks']
        })
    
    db.close()
    return render_template('teacher/dashboard.html', exams=exam_stats)

@app.route('/teacher/create-exam', methods=['GET', 'POST'])
@login_required('teacher')
def create_exam():
    if request.method == 'POST':
        title = request.form['title']
        desc = request.form['description']
        marks = request.form['total_marks']
        duration = request.form['duration']
        teacher_id = session['user_id']
        
        db = get_db()
        cursor = db.cursor()
        cursor.execute('INSERT INTO exams (teacher_id, title, description, total_marks, duration) VALUES (?, ?, ?, ?, ?)',
                       (teacher_id, title, desc, marks, duration))
        exam_id = cursor.lastrowid
        db.commit()
        db.close()
        flash('Exam created! Now add some questions.', 'success')
        return redirect(url_for('manage_questions', exam_id=exam_id))
    return render_template('teacher/create_exam.html')

@app.route('/teacher/exam/<int:exam_id>/questions', methods=['GET', 'POST'])
@login_required('teacher')
def manage_questions(exam_id):
    db = get_db()
    exam = db.execute('SELECT * FROM exams WHERE id = ?', (exam_id,)).fetchone()
    
    if request.method == 'POST':
        q_text = request.form['question_text']
        opt_a = request.form['option_a']
        opt_b = request.form['option_b']
        opt_c = request.form['option_c']
        opt_d = request.form['option_d']
        correct = request.form['correct_option']
        q_marks = request.form['marks']
        
        db.execute('''INSERT INTO questions 
            (exam_id, question_text, option_a, option_b, option_c, option_d, correct_option, marks) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', 
            (exam_id, q_text, opt_a, opt_b, opt_c, opt_d, correct, q_marks))
        db.commit()
        db.close()
        flash('Question added!', 'success')
        return redirect(url_for('manage_questions', exam_id=exam_id))
        
    questions = db.execute('SELECT * FROM questions WHERE exam_id = ?', (exam_id,)).fetchall()
    db.close()
    return render_template('teacher/manage_questions.html', exam=exam, questions=questions)

@app.route('/teacher/delete-question/<int:q_id>/<int:exam_id>')
@login_required('teacher')
def delete_question(q_id, exam_id):
    db = get_db()
    db.execute('DELETE FROM questions WHERE id = ?', (q_id,))
    db.commit()
    db.close()
    flash('Question deleted.', 'info')
    return redirect(url_for('manage_questions', exam_id=exam_id))

@app.route('/teacher/exam-results/<int:exam_id>')
@login_required('teacher')
def view_exam_results(exam_id):
    db = get_db()
    exam = db.execute('SELECT * FROM exams WHERE id = ?', (exam_id,)).fetchone()
    results = db.execute('''
        SELECT r.*, s.name as student_name, s.roll_no 
        FROM results r 
        JOIN students s ON r.student_id = s.id 
        WHERE r.exam_id = ?
        ORDER BY r.score DESC
    ''', (exam_id,)).fetchall()
    
    # Analytics
    analytics_row = db.execute('''
        SELECT AVG(score), MAX(score), MIN(score), COUNT(*) 
        FROM results WHERE exam_id = ?
    ''', (exam_id,)).fetchone()
    
    # Grade distribution for chart
    grade_dist = db.execute('''
        SELECT grade, COUNT(*) as count FROM results WHERE exam_id = ? GROUP BY grade
    ''', (exam_id,)).fetchall()
    
    chart_labels = [r['grade'] for r in grade_dist]
    chart_values = [r['count'] for r in grade_dist]
    
    db.close()
    return render_template('teacher/view_results.html', exam=exam, results=results, 
                           analytics=analytics_row, chart_labels=chart_labels, chart_values=chart_values)

# --- Student Routes ---
@app.route('/student/dashboard')
@login_required('student')
def student_dashboard():
    db = get_db()
    student_id = session['user_id']
    
    # Get exams student has NOT taken yet
    available_exams = db.execute('''
        SELECT e.*, t.name as teacher_name 
        FROM exams e 
        JOIN teachers t ON e.teacher_id = t.id
        WHERE e.id NOT IN (SELECT exam_id FROM results WHERE student_id = ?)
    ''', (student_id,)).fetchall()
    
    # Get previous results
    results = db.execute('''
        SELECT r.*, e.title as exam_title 
        FROM results r 
        JOIN exams e ON r.exam_id = e.id 
        WHERE r.student_id = ?
        ORDER BY r.attempted_at DESC
    ''', (student_id,)).fetchall()
    
    db.close()
    return render_template('student/dashboard.html', available_exams=available_exams, results=results)

@app.route('/student/take-exam/<int:exam_id>')
@login_required('student')
def take_exam(exam_id):
    db = get_db()
    # Check if already taken
    existing = db.execute('SELECT id FROM results WHERE student_id = ? AND exam_id = ?', 
                          (session['user_id'], exam_id)).fetchone()
    if existing:
        flash('You have already attempted this exam.', 'warning')
        return redirect(url_for('student_dashboard'))
        
    exam = db.execute('SELECT * FROM exams WHERE id = ?', (exam_id,)).fetchone()
    questions = db.execute('SELECT * FROM questions WHERE exam_id = ?', (exam_id,)).fetchall()
    db.close()
    
    if not questions:
        flash('This exam is not ready yet (no questions added).', 'info')
        return redirect(url_for('student_dashboard'))
        
    return render_template('student/take_exam.html', exam=exam, questions=questions)

@app.route('/student/submit-exam/<int:exam_id>', methods=['POST'])
@login_required('student')
def submit_exam(exam_id):
    db = get_db()
    questions = db.execute('SELECT id, correct_option, marks FROM questions WHERE exam_id = ?', (exam_id,)).fetchall()
    
    score = 0
    total_marks = 0
    for q in questions:
        submitted_ans = request.form.get(f'q_{q["id"]}')
        if submitted_ans == q['correct_option']:
            score = score + int(q['marks'])
        total_marks = total_marks + int(q['marks'])
        
    percentage = (float(score) / float(total_marks) * 100) if total_marks > 0 else 0.0
    
    # Grade assignment
    if percentage >= 80: grade = 'A'
    elif percentage >= 60: grade = 'B'
    elif percentage >= 40: grade = 'C'
    else: grade = 'Fail'
    
    student_id = session['user_id']
    rounded_percentage = float(round(percentage, 2))
    db.execute('''INSERT INTO results (student_id, exam_id, score, total_marks, percentage, grade) 
                  VALUES (?, ?, ?, ?, ?, ?)''', 
               (student_id, exam_id, score, total_marks, rounded_percentage, grade))
    db.commit()
    db.close()
    
    flash(f'Exam submitted! You scored {score}/{total_marks} ({grade})', 'success')
    return redirect(url_for('student_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
