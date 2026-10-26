"""SQLite data layer for the Student Database CRUD app."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    email TEXT NOT NULL COLLATE NOCASE UNIQUE,
    age INTEGER NOT NULL CHECK (age BETWEEN 1 AND 120),
    course TEXT NOT NULL CHECK (length(trim(course)) > 0),
    enrollment_date TEXT NOT NULL DEFAULT (date('now')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_students_name ON students (name);
CREATE INDEX IF NOT EXISTS idx_students_course ON students (course);
"""

SORT_COLUMNS = {
    "id": "id",
    "name": "name COLLATE NOCASE",
    "email": "email COLLATE NOCASE",
    "age": "age",
    "course": "course COLLATE NOCASE",
    "enrollment_date": "enrollment_date",
}

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class StudentError(Exception):
    """Base class for student database errors."""


class ValidationError(StudentError):
    """Raised when student data is invalid."""


class DuplicateEmailError(StudentError):
    """Raised when an email address is already in use."""


class StudentNotFoundError(StudentError):
    """Raised when a requested student does not exist."""


@dataclass(frozen=True, slots=True)
class Student:
    id: int
    name: str
    email: str
    age: int
    course: str
    enrollment_date: str
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Student":
        return cls(
            id=row["id"],
            name=row["name"],
            email=row["email"],
            age=row["age"],
            course=row["course"],
            enrollment_date=row["enrollment_date"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


def _clean_text(value: Any, field: str, max_length: int) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be text.")
    cleaned = " ".join(value.split())
    if not cleaned:
        raise ValidationError(f"{field} cannot be empty.")
    if len(cleaned) > max_length:
        raise ValidationError(f"{field} must be at most {max_length} characters.")
    return cleaned


def _clean_email(value: Any) -> str:
    if not isinstance(value, str):
        raise ValidationError("email must be text.")
    email = value.strip().lower()
    if not email:
        raise ValidationError("email cannot be empty.")
    if len(email) > 254 or not EMAIL_PATTERN.match(email):
        raise ValidationError("email must be a valid address, such as name@example.com.")
    return email


def _clean_age(value: Any) -> int:
    if isinstance(value, bool):
        raise ValidationError("age must be a whole number between 1 and 120.")
    try:
        age = int(value)
    except (TypeError, ValueError):
        raise ValidationError("age must be a whole number between 1 and 120.") from None
    if age < 1 or age > 120:
        raise ValidationError("age must be between 1 and 120.")
    return age


def _clean_enrollment_date(value: Any) -> str:
    if value is None or value == "":
        return date.today().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    try:
        return date.fromisoformat(str(value).strip()).isoformat()
    except ValueError:
        raise ValidationError("enrollment date must use YYYY-MM-DD format.") from None


def _duplicate_email_error() -> DuplicateEmailError:
    return DuplicateEmailError("A student with that email address already exists.")


class StudentDatabase:
    """A small, parameterized SQL wrapper around a SQLite students table."""

    def __init__(self, db_path: str | Path = "students.db") -> None:
        self.db_path = str(db_path)
        self._connection = sqlite3.connect(self.db_path)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def _create_schema(self) -> None:
        with self._connection:
            self._connection.executescript(SCHEMA)

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "StudentDatabase":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def create_student(
        self,
        name: str,
        email: str,
        age: int,
        course: str,
        enrollment_date: str | date | None = None,
    ) -> Student:
        clean_name = _clean_text(name, "name", 100)
        clean_email = _clean_email(email)
        clean_age = _clean_age(age)
        clean_course = _clean_text(course, "course", 100)
        clean_date = _clean_enrollment_date(enrollment_date)

        try:
            with self._connection:
                cursor = self._connection.execute(
                    """
                    INSERT INTO students (name, email, age, course, enrollment_date)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (clean_name, clean_email, clean_age, clean_course, clean_date),
                )
        except sqlite3.IntegrityError as exc:
            if "UNIQUE" in str(exc).upper() and "EMAIL" in str(exc).upper():
                raise _duplicate_email_error() from None
            raise

        student = self.get_student(cursor.lastrowid)
        if student is None:
            raise StudentError("The student record could not be loaded after insertion.")
        return student

    def get_student(self, student_id: int) -> Student | None:
        row = self._connection.execute(
            "SELECT * FROM students WHERE id = ?",
            (_clean_id(student_id),),
        ).fetchone()
        return Student.from_row(row) if row else None

    def find_by_email(self, email: str) -> Student | None:
        row = self._connection.execute(
            "SELECT * FROM students WHERE email = ? COLLATE NOCASE",
            (_clean_email(email),),
        ).fetchone()
        return Student.from_row(row) if row else None

    def list_students(
        self,
        search: str | None = None,
        course: str | None = None,
        sort: str = "name",
        descending: bool = False,
        limit: int | None = None,
    ) -> list[Student]:
        if sort not in SORT_COLUMNS:
            valid = ", ".join(SORT_COLUMNS)
            raise ValidationError(f"sort must be one of: {valid}.")
        if limit is not None and limit < 1:
            raise ValidationError("limit must be a positive number.")

        clauses: list[str] = []
        parameters: list[Any] = []

        if search and search.strip():
            term = f"%{search.strip()}%"
            clauses.append(
                "(name LIKE ? COLLATE NOCASE OR email LIKE ? COLLATE NOCASE "
                "OR course LIKE ? COLLATE NOCASE)"
            )
            parameters.extend((term, term, term))

        if course and course.strip():
            clauses.append("course = ? COLLATE NOCASE")
            parameters.append(course.strip())

        query = "SELECT * FROM students"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += f" ORDER BY {SORT_COLUMNS[sort]}"
        query += " DESC" if descending else " ASC"
        query += ", id ASC"

        if limit is not None:
            query += " LIMIT ?"
            parameters.append(int(limit))

        rows = self._connection.execute(query, parameters).fetchall()
        return [Student.from_row(row) for row in rows]

    def update_student(self, student_id: int, **fields: Any) -> Student:
        clean_id = _clean_id(student_id)
        if not fields:
            raise ValidationError("Provide at least one field to update.")

        allowed = {"name", "email", "age", "course", "enrollment_date"}
        unknown = set(fields) - allowed
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ValidationError(f"Unknown field(s): {names}.")
        if self.get_student(clean_id) is None:
            raise StudentNotFoundError(f"No student found with ID {clean_id}.")

        updates: dict[str, Any] = {}
        if "name" in fields:
            updates["name"] = _clean_text(fields["name"], "name", 100)
        if "email" in fields:
            updates["email"] = _clean_email(fields["email"])
        if "age" in fields:
            updates["age"] = _clean_age(fields["age"])
        if "course" in fields:
            updates["course"] = _clean_text(fields["course"], "course", 100)
        if "enrollment_date" in fields:
            updates["enrollment_date"] = _clean_enrollment_date(fields["enrollment_date"])

        assignments = ", ".join(f"{column} = ?" for column in updates)
        parameters = list(updates.values())
        parameters.append(clean_id)

        try:
            with self._connection:
                self._connection.execute(
                    f"UPDATE students SET {assignments}, updated_at = datetime('now') "
                    "WHERE id = ?",
                    parameters,
                )
        except sqlite3.IntegrityError as exc:
            if "UNIQUE" in str(exc).upper() and "EMAIL" in str(exc).upper():
                raise _duplicate_email_error() from None
            raise

        student = self.get_student(clean_id)
        if student is None:
            raise StudentNotFoundError(f"No student found with ID {clean_id}.")
        return student

    def delete_student(self, student_id: int) -> bool:
        with self._connection:
            cursor = self._connection.execute(
                "DELETE FROM students WHERE id = ?",
                (_clean_id(student_id),),
            )
        return cursor.rowcount > 0


def _clean_id(student_id: Any) -> int:
    if isinstance(student_id, bool):
        raise ValidationError("student ID must be a positive whole number.")
    try:
        clean_id = int(student_id)
    except (TypeError, ValueError):
        raise ValidationError("student ID must be a positive whole number.") from None
    if clean_id < 1:
        raise ValidationError("student ID must be a positive whole number.")
    return clean_id
