import sqlite3
import csv
import os

DB_PATH = 'database.db'

def generate_csv_report():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database file '{DB_PATH}' not found.")
        return False

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Query to fetch detailed exam results
        query = '''
            SELECT 
                r.id as ResultID,
                s.name as StudentName,
                s.roll_no as RollNo,
                e.title as ExamTitle,
                r.score as Score,
                r.total_marks as TotalMarks,
                r.percentage as Percentage,
                r.grade as Grade,
                r.attempted_at as AttemptedAt
            FROM results r
            JOIN students s ON r.student_id = s.id
            JOIN exams e ON r.exam_id = e.id
            ORDER BY r.attempted_at DESC
        '''
        results = cursor.execute(query).fetchall()

        if not results:
            print("No exam results found in the database. Report will be empty.")
        
        filename = 'exam_results_report.csv'
        with open(filename, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Write Header
            writer.writerow(['Result ID', 'Student Name', 'Roll No', 'Exam Title', 
                             'Score', 'Total Marks', 'Percentage', 'Grade', 'Attempt Date'])
            
            # Write Rows
            for row in results:
                writer.writerow([
                    row['ResultID'], row['StudentName'], row['RollNo'], 
                    row['ExamTitle'], row['Score'], row['TotalMarks'], 
                    f"{row['Percentage']}%", row['Grade'], row['AttemptedAt']
                ])
                
        print(f"Success! Report generated successfully: {filename}")
        return True

    except sqlite3.Error as e:
        print(f"Database error occurred: {e}")
        return False
    except IOError as e:
        print(f"File write error occurred: {e}")
        return False
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == '__main__':
    print("Starting report generation...")
    generate_csv_report()
