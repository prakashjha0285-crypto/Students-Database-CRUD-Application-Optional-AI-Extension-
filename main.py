"""FastAPI application: Students CRUD API (+ optional AI endpoint)."""
import sqlite3
from contextlib import asynccontextmanager
from datetime import date
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError

from . import ai, crud
from .database import get_db, init_db
from .schemas import AskRequest, AskResponse, StudentCreate, StudentOut, StudentUpdate


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()  # create the SQLite file/table on first start
    yield


app = FastAPI(
    title="Students Database API",
    version="1.0.0",
    description="CRUD API for student records (FastAPI + SQLite) with an optional "
    "local-AI question endpoint powered by Ollama.",
    lifespan=lifespan,
)


def _not_found(student_id: int) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Student with id {student_id} not found")


def _duplicate_email() -> HTTPException:
    return HTTPException(status_code=409, detail="A student with this email already exists")


@app.get("/", include_in_schema=False)
def root():
    return {"message": "Students Database API", "docs": "/docs"}


@app.get("/health", tags=["System"])
def health():
    return {"status": "ok"}


# ------------------------------------------------------------------ CREATE
@app.post("/students", response_model=StudentOut, status_code=201, tags=["Students"])
def create_student(student: StudentCreate, db: sqlite3.Connection = Depends(get_db)):
    """Create a new student record."""
    try:
        return crud.create_student(db, student.model_dump(mode="json"))
    except crud.DuplicateEmailError:
        raise _duplicate_email()


# -------------------------------------------------------------------- READ
@app.get("/students", response_model=List[StudentOut], tags=["Students"])
def list_students(
    response: Response,
    name: Optional[str] = Query(None, description="Name contains (case-insensitive)"),
    course: Optional[str] = Query(None, description="Course contains (case-insensitive)"),
    email: Optional[str] = Query(None, description="Exact email"),
    born_after: Optional[date] = Query(None, description="Date of birth strictly after (YYYY-MM-DD)"),
    born_before: Optional[date] = Query(None, description="Date of birth strictly before (YYYY-MM-DD)"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: sqlite3.Connection = Depends(get_db),
):
    """List students, optionally filtered. Total match count is returned in the
    `X-Total-Count` response header."""
    filters = dict(name=name, course=course, email=email, born_after=born_after, born_before=born_before)
    response.headers["X-Total-Count"] = str(crud.count_students(db, **filters))
    return crud.list_students(db, limit=limit, offset=offset, **filters)


@app.get("/students/{student_id}", response_model=StudentOut, tags=["Students"])
def get_student(student_id: int, db: sqlite3.Connection = Depends(get_db)):
    """Retrieve one student by ID."""
    student = crud.get_student(db, student_id)
    if student is None:
        raise _not_found(student_id)
    return student


# ------------------------------------------------------------------ UPDATE
@app.put("/students/{student_id}", response_model=StudentOut, tags=["Students"])
def replace_student(student_id: int, student: StudentCreate, db: sqlite3.Connection = Depends(get_db)):
    """Replace all details of a student (full update)."""
    try:
        updated = crud.replace_student(db, student_id, student.model_dump(mode="json"))
    except crud.DuplicateEmailError:
        raise _duplicate_email()
    if updated is None:
        raise _not_found(student_id)
    return updated


@app.patch("/students/{student_id}", response_model=StudentOut, tags=["Students"])
def update_student(student_id: int, changes: StudentUpdate, db: sqlite3.Connection = Depends(get_db)):
    """Update only the supplied fields (partial update)."""
    existing = crud.get_student(db, student_id)
    if existing is None:
        raise _not_found(student_id)

    merged = {field: existing.get(field) for field in crud.FIELDS}
    merged.update(changes.model_dump(exclude_unset=True, mode="json"))

    try:
        validated = StudentCreate.model_validate(merged)
    except ValidationError as exc:
        detail = [
            {"loc": ["body", *e["loc"]], "msg": e["msg"], "type": e["type"]}
            for e in exc.errors(include_url=False, include_context=False)
        ]
        raise HTTPException(status_code=422, detail=jsonable_encoder(detail))

    try:
        updated = crud.replace_student(db, student_id, validated.model_dump(mode="json"))
    except crud.DuplicateEmailError:
        raise _duplicate_email()
    return updated


# ------------------------------------------------------------------ DELETE
@app.delete("/students/{student_id}", status_code=204, tags=["Students"])
def delete_student(student_id: int, db: sqlite3.Connection = Depends(get_db)):
    """Delete a student."""
    if not crud.delete_student(db, student_id):
        raise _not_found(student_id)
    return Response(status_code=204)


# ------------------------------------------------------- OPTIONAL: LOCAL AI
@app.post("/ai/ask", response_model=AskResponse, tags=["AI (optional)"])
def ask(request: AskRequest, db: sqlite3.Connection = Depends(get_db)):
    """Ask a natural-language question about the stored students.

    The backend retrieves matching records with fixed, parameterized queries and
    gives only those to the local Ollama model - the model never runs SQL."""
    try:
        return ai.answer_question(db, request.question)
    except ai.OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
