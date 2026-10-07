import os
import json
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

app = FastAPI(title="EPS TOPIK UBT Production System")

DB_NAME = "ubt_database.db"
VAULT_FOLDER = "exam_vault"
os.makedirs(VAULT_FOLDER, exist_ok=True)
os.makedirs("static/uploads", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ----------------- DATABASE UTILS -----------------
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS papers (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            status TEXT DEFAULT 'ACTIVE',
            mode TEXT DEFAULT 'EXAM',
            max_attempts INTEGER DEFAULT 1,
            created_at TEXT
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS students (
            card_no TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            nic TEXT,
            passcode TEXT NOT NULL,
            allowed_papers TEXT DEFAULT 'ALL',
            created_at TEXT
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_id TEXT,
            paper_title TEXT,
            card_no TEXT,
            student_name TEXT,
            score INTEGER,
            percentage TEXT,
            status TEXT,
            attempt_number INTEGER,
            submitted_at TEXT
        )
    ''')
    
    cur.execute('SELECT COUNT(*) FROM papers')
    if cur.fetchone()[0] == 0:
        cur.execute(
            'INSERT INTO papers (id, title, status, mode, max_attempts, created_at) VALUES (?, ?, ?, ?, ?, ?)',
            ('Paper_1', 'Free UBT - 01', 'ACTIVE', 'EXAM', 1, datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        save_default_paper('Paper_1', 'Free UBT - 01')

    conn.commit()
    conn.close()

def save_default_paper(paper_id: str, title: str):
    questions = []
    default_svg = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 450 350" fill="none"><path d="M140 230 C 140 200, 220 185, 235 220 C 235 235, 215 250, 160 250 Z" fill="%23d1d5db" stroke="%231f2937" stroke-width="4"/><path d="M225 210 L 305 105 L 290 95 L 210 200 Z" fill="%239ca3af" stroke="%231f2937" stroke-width="3.5"/><circle cx="280" cy="205" r="26" fill="%23ffffff" stroke="%239ca3af" stroke-width="2"/><ellipse cx="280" cy="235" rx="10" ry="3" fill="%23d1d5db"/><path d="M276 235 L 284 235 L 281 270 L 279 270 Z" fill="%23e5e7eb" stroke="%234b5563" stroke-width="2"/></svg>'
    for i in range(1, 41):
        is_reading = i <= 20
        questions.append({
            'id': i,
            'type': 'reading' if is_reading else 'listening',
            'instruction': '[1~4] 다음 그림을 보고 맞는 단어나 문장을 고르십시오.' if i <= 4 else ('[5~20] 다음 질문에 답하십시오.' if is_reading else '[21~40] 잘 듣고 내용과 관계있는 그림이나 대답을 고르십시오.'),
            'prompt': f"{i}. " + ('다음 내용에 맞는 것을 고르십시오.' if is_reading and i > 1 else ('잘 듣고 알맞은 대답을 고르십시오.' if not is_reading else '')),
            'passage': '한국 사람들은 밥과 국, 그리고 여러 가지 반찬을 함께 먹습니다.' if i == 5 else '',
            'image': default_svg if i == 1 else '',
            'audioScript': '여기는 어디입니까?' if not is_reading else '',
            'options': [
                {'text': '야구입니다.', 'image': '', 'audio': ''},
                {'text': '볼링입니다.', 'image': '', 'audio': ''},
                {'text': '탁구입니다.', 'image': '', 'audio': ''},
                {'text': '골프입니다.', 'image': '', 'audio': ''}
            ] if i == 1 else [
                {'text': '1번 선택지입니다.', 'image': '', 'audio': ''},
                {'text': '2번 선택지입니다.', 'image': '', 'audio': ''},
                {'text': '3번 선택지입니다.', 'image': '', 'audio': ''},
                {'text': '4번 선택지입니다.', 'image': '', 'audio': ''}
            ],
            'correctAnswer': 3 if i == 1 else 0
        })
    with open(os.path.join(VAULT_FOLDER, f"{paper_id}.json"), 'w', encoding='utf-8') as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)

@app.on_event("startup")
def on_startup():
    init_db()

# ----------------- PYDANTIC SCHEMAS -----------------
class StudentLoginReq(BaseModel):
    cardNo: str
    passcode: str

class StudentPapersReq(BaseModel):
    cardNo: str
    allowedPapers: Optional[str] = "ALL"

class SubmitExamReq(BaseModel):
    paperId: str
    paperTitle: str
    cardNo: str
    studentName: str
    userAnswers: Dict[str, Any]

class AdminLoginReq(BaseModel):
    passcode: str

class CreatePaperReq(BaseModel):
    title: str

class PaperStatusReq(BaseModel):
    status: str

class PaperModeReq(BaseModel):
    mode: str
    maxAttempts: int

class AddStudentReq(BaseModel):
    cardNo: str
    name: str
    nic: Optional[str] = ""
    passcode: str
    allowedPapers: Optional[str] = "ALL"

class StudentPermReq(BaseModel):
    allowedPapers: str

class ClearResultsReq(BaseModel):
    paperTitle: Optional[str] = "ALL"

class ResetAttemptReq(BaseModel):
    cardNo: str

# ----------------- PAGE ROUTES -----------------
@app.get("/", response_class=HTMLResponse)
async def student_page(request: Request, paper: Optional[str] = ""):
    return templates.TemplateResponse("index.html", {"request": request, "direct_paper_id": paper})

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})

# ----------------- STUDENT APIS -----------------
@app.post("/api/student/login")
async def student_login(payload: StudentLoginReq):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT card_no, name, nic, allowed_papers FROM students WHERE LOWER(card_no) = LOWER(?) AND passcode = ?",
        (payload.cardNo.strip(), payload.passcode.strip())
    )
    row = cur.fetchone()
    conn.close()
    
    if row:
        return {
            "success": True,
            "cardNo": row["card_no"],
            "name": row["name"],
            "nic": row["nic"] or "-",
            "allowedPapers": row["allowed_papers"] or "ALL"
        }
    raise HTTPException(status_code=401, detail="කාඩ්පත් අංකය හෝ Passcode එක වැරදියි!")

@app.post("/api/student/papers")
async def student_papers(payload: StudentPapersReq):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, title, status, mode, max_attempts FROM papers WHERE status = 'ACTIVE'")
    papers = cur.fetchall()
    
    allowed = payload.allowedPapers
    allowed_list = [p.strip() for p in allowed.split(",")] if allowed and allowed != "ALL" else None
    result = []
    
    for p in papers:
        p_id = p["id"]
        if allowed_list is None or p_id in allowed_list:
            cur.execute(
                "SELECT COUNT(*) FROM submissions WHERE paper_id = ? AND LOWER(card_no) = LOWER(?)",
                (p_id, payload.cardNo.strip())
            )
            user_attempts = cur.fetchone()[0]
            mode = p["mode"]
            max_att = p["max_attempts"]
            total_allowed = 1 if mode == "EXAM" else (1 + max_att)
            
            result.append({
                "paperId": p_id,
                "title": p["title"],
                "mode": mode,
                "maxAttempts": max_att,
                "userAttempts": user_attempts,
                "totalAllowed": total_allowed,
                "isOfficialDone": user_attempts >= 1,
                "isAllDone": user_attempts >= total_allowed
            })
    conn.close()
    return result

@app.get("/api/papers/{paper_id}/questions")
async def get_questions(paper_id: str):
    file_path = os.path.join(VAULT_FOLDER, f"{paper_id}.json")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="ප්‍රශ්න පත්‍රය හමු නොවීය.")
        
    with open(file_path, "r", encoding="utf-8") as f:
        full = json.load(f)
        
    sanitized = []
    for q in full:
        sanitized.append({
            "id": q["id"],
            "type": q["type"],
            "instruction": q.get("instruction", ""),
            "prompt": q.get("prompt", ""),
            "passage": q.get("passage", ""),
            "image": q.get("image", ""),
            "audioScript": q.get("audioScript", ""),
            "options": q.get("options", [])
        })
    return sanitized

@app.post("/api/student/submit")
async def submit_exam(payload: SubmitExamReq):
    file_path = os.path.join(VAULT_FOLDER, f"{payload.paperId}.json")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=400, detail="ප්‍රශ්න පත්‍ර දත්ත හමු නොවීය.")
        
    with open(file_path, "r", encoding="utf-8") as f:
        full_questions = json.load(f)
        
    score = 0
    for idx, q in enumerate(full_questions):
        user_ans = payload.userAnswers.get(str(idx))
        if user_ans is None:
            user_ans = payload.userAnswers.get(idx)
        if user_ans is not None and int(user_ans) == q.get("correctAnswer"):
            score += 1
            
    total = len(full_questions)
    percentage = f"{((score / total) * 100):.1f}%"
    exam_status = "PASS" if score >= 22 else "FAIL"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM submissions WHERE paper_id = ? AND LOWER(card_no) = LOWER(?)",
        (payload.paperId, payload.cardNo.strip())
    )
    prev_attempts = cur.fetchone()[0]
    current_attempt = prev_attempts + 1
    
    cur.execute('''
        INSERT INTO submissions (paper_id, paper_title, card_no, student_name, score, percentage, status, attempt_number, submitted_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (payload.paperId, payload.paperTitle, payload.cardNo.strip(), payload.studentName.strip(),
          score, percentage, exam_status, current_attempt, now_str))
    conn.commit()
    conn.close()
    
    return {
        "score": score,
        "total": total,
        "percentage": percentage,
        "status": exam_status,
        "attemptNumber": current_attempt
    }

# ----------------- ADMIN APIS -----------------
@app.post("/api/admin/login")
async def admin_login(payload: AdminLoginReq):
    if payload.passcode.strip() != "admin123":
        raise HTTPException(status_code=403, detail="වලංගු නොවන Admin Passcode එකකි!")
        
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("SELECT id, title, status, mode, max_attempts FROM papers")
    papers = [{"paperId": r["id"], "title": r["title"], "status": r["status"], "mode": r["mode"], "maxAttempts": r["max_attempts"]} for r in cur.fetchall()]
    
    cur.execute("SELECT card_no, name, nic, passcode, allowed_papers, created_at FROM students")
    students = [{"cardNo": r["card_no"], "name": r["name"], "nic": r["nic"], "passcode": r["passcode"], "allowedPapers": r["allowed_papers"], "date": r["created_at"]} for r in cur.fetchall()]
    
    cur.execute("SELECT submitted_at, paper_title, card_no, student_name, score, percentage, status FROM submissions ORDER BY id DESC")
    results = [{"time": r["submitted_at"], "paperTitle": r["paper_title"], "cardNo": r["card_no"], "name": r["student_name"], "score": r["score"], "percentage": r["percentage"], "status": r["status"]} for r in cur.fetchall()]
    
    conn.close()
    
    init_paper_id = papers[0]["paperId"] if papers else "Paper_1"
    file_path = os.path.join(VAULT_FOLDER, f"{init_paper_id}.json")
    with open(file_path, "r", encoding="utf-8") as f:
        questions = json.load(f)
        
    return {
        "papers": papers,
        "initialQuestions": questions,
        "students": students,
        "results": results
    }

@app.post("/api/admin/papers")
async def create_paper(payload: CreatePaperReq):
    new_id = f"Paper_{int(datetime.now().timestamp())}"
    now_str = datetime.now().strftime("%Y-%m-%d")
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO papers (id, title, status, mode, max_attempts, created_at) VALUES (?, ?, 'ACTIVE', 'EXAM', 1, ?)",
        (new_id, payload.title.strip(), now_str)
    )
    conn.commit()
    conn.close()
    
    save_default_paper(new_id, payload.title.strip())
    return {"paperId": new_id, "title": payload.title.strip(), "status": "ACTIVE", "mode": "EXAM", "maxAttempts": 1}

@app.put("/api/admin/papers/{paper_id}/status")
async def update_status(paper_id: str, payload: PaperStatusReq):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE papers SET status = ? WHERE id = ?", (payload.status, paper_id))
    conn.commit()
    conn.close()
    return {"message": f"Status updated to {payload.status}"}

@app.put("/api/admin/papers/{paper_id}/mode")
async def update_mode(paper_id: str, payload: PaperModeReq):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE papers SET mode = ?, max_attempts = ? WHERE id = ?", (payload.mode, payload.maxAttempts, paper_id))
    conn.commit()
    conn.close()
    return {"message": "Paper mode updated successfully"}

@app.delete("/api/admin/papers/{paper_id}")
async def delete_paper(paper_id: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM papers")
    if cur.fetchone()[0] <= 1:
        conn.close()
        raise HTTPException(status_code=400, detail="පද්ධතියේ ඇති අවසාන ප්‍රශ්න පත්‍රය මකා දැමිය නොහැක!")
        
    cur.execute("DELETE FROM papers WHERE id = ?", (paper_id,))
    cur.execute("DELETE FROM submissions WHERE paper_id = ?", (paper_id,))
    conn.commit()
    conn.close()
    
    file_path = os.path.join(VAULT_FOLDER, f"{paper_id}.json")
    if os.path.exists(file_path):
        os.remove(file_path)
    return {"message": "ප්‍රශ්න පත්‍රය සාර්ථකව මකා දමන ලදී!"}

@app.get("/api/admin/papers/{paper_id}/questions")
async def admin_get_questions(paper_id: str):
    file_path = os.path.join(VAULT_FOLDER, f"{paper_id}.json")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

@app.post("/api/admin/papers/{paper_id}/questions")
async def admin_save_questions(paper_id: str, questions: List[Dict[str, Any]]):
    file_path = os.path.join(VAULT_FOLDER, f"{paper_id}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)
    return {"message": "ප්‍රශ්න පත්‍රය සාර්ථකව Save කරන ලදී!"}

@app.post("/api/admin/students")
async def add_student(payload: AddStudentReq):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO students (card_no, name, nic, passcode, allowed_papers, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (payload.cardNo.strip(), payload.name.strip(), payload.nic.strip(), payload.passcode.strip(), payload.allowedPapers, datetime.now().strftime("%Y-%m-%d"))
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail=f"මෙම කාඩ්පත් අංකය ({payload.cardNo}) දැනටමත් ලියාපදිංචි කර ඇත!")
    conn.close()
    return {"message": "සිසුවා සාර්ථකව ඇතුළත් කරන ලදී!"}

@app.delete("/api/admin/students/{card_no}")
async def delete_student(card_no: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM students WHERE LOWER(card_no) = LOWER(?)", (card_no.strip(),))
    conn.commit()
    conn.close()
    return {"message": "සිසුවා සාර්ථකව ඉවත් කරන ලදී!"}

@app.put("/api/admin/students/{card_no}/permissions")
async def update_permissions(card_no: str, payload: StudentPermReq):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE students SET allowed_papers = ? WHERE LOWER(card_no) = LOWER(?)", (payload.allowedPapers, card_no.strip()))
    conn.commit()
    conn.close()
    return {"message": "ප්‍රවේශ අවසර සාර්ථකව යාවත්කාලීන කරන ලදී!"}

@app.post("/api/admin/results/clear")
async def clear_results(payload: ClearResultsReq):
    conn = get_db()
    cur = conn.cursor()
    if payload.paperTitle == "ALL":
        cur.execute("DELETE FROM submissions")
    else:
        cur.execute("DELETE FROM submissions WHERE paper_title = ?", (payload.paperTitle,))
    conn.commit()
    conn.close()
    return {"message": "ලකුණු වාර්තා සාර්ථකව Clear කරන ලදී!"}

@app.post("/api/admin/results/reset")
async def reset_attempt(payload: ResetAttemptReq):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM submissions WHERE LOWER(card_no) = LOWER(?)", (payload.cardNo.strip(),))
    conn.commit()
    conn.close()
    return {"message": f"සිසුවාගේ ({payload.cardNo}) attempt එක Reset කරන ලදී!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)