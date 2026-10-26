"""Command-line interface for the Student Database CRUD app."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Any, Sequence

from student_db import (
    SORT_COLUMNS,
    Student,
    StudentDatabase,
    StudentError,
    StudentNotFoundError,
    ValidationError,
)

DEFAULT_DB_PATH = Path("students.db")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="student-database",
        description="Create, read, update, and delete student records in SQLite.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        metavar="FILE",
        help="SQLite database file (default: students.db)",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    add_parser = subparsers.add_parser("add", help="add a student")
    add_parser.add_argument("--name", required=True, help="student name")
    add_parser.add_argument("--email", required=True, help="unique email address")
    add_parser.add_argument("--age", required=True, type=int, help="age from 1 to 120")
    add_parser.add_argument("--course", required=True, help="course or program")
    add_parser.add_argument(
        "--enrollment-date",
        dest="enrollment_date",
        metavar="YYYY-MM-DD",
        help="enrollment date (default: today)",
    )

    list_parser = subparsers.add_parser("list", help="list or search students")
    list_parser.add_argument("--search", help="match name, email, or course")
    list_parser.add_argument("--course", help="filter by exact course name")
    list_parser.add_argument(
        "--sort",
        choices=tuple(SORT_COLUMNS),
        default="name",
        help="sort column (default: name)",
    )
    list_parser.add_argument("--desc", action="store_true", help="sort descending")
    list_parser.add_argument("--limit", type=int, help="maximum records to show")

    show_parser = subparsers.add_parser("show", help="show one student")
    show_parser.add_argument("id", type=int, help="student ID")

    update_parser = subparsers.add_parser("update", help="update a student")
    update_parser.add_argument("id", type=int, help="student ID")
    update_parser.add_argument("--name", help="new name")
    update_parser.add_argument("--email", help="new unique email")
    update_parser.add_argument("--age", type=int, help="new age from 1 to 120")
    update_parser.add_argument("--course", help="new course or program")
    update_parser.add_argument(
        "--enrollment-date",
        dest="enrollment_date",
        metavar="YYYY-MM-DD",
        help="new enrollment date",
    )

    delete_parser = subparsers.add_parser("delete", help="delete a student")
    delete_parser.add_argument("id", type=int, help="student ID")
    delete_parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="delete without asking for confirmation",
    )

    return parser


def format_students(students: Sequence[Student]) -> str:
    if not students:
        return "No student records found."

    headers = ("ID", "Name", "Email", "Age", "Course", "Enrolled")
    rows = [
        (
            str(student.id),
            student.name,
            student.email,
            str(student.age),
            student.course,
            student.enrollment_date,
        )
        for student in students
    ]
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        for index in range(len(headers))
    ]

    def render(row: tuple[str, ...]) -> str:
        cells = [row[index].ljust(widths[index]) for index in range(len(headers))]
        return "| " + " | ".join(cells) + " |"

    border = "+-" + "-+-".join("-" * width for width in widths) + "-+"
    lines = [border, render(headers), border]
    lines.extend(render(row) for row in rows)
    lines.append(border)
    return "\n".join(lines)


def format_student(student: Student) -> str:
    return "\n".join(
        (
            f"ID:              {student.id}",
            f"Name:            {student.name}",
            f"Email:           {student.email}",
            f"Age:             {student.age}",
            f"Course:          {student.course}",
            f"Enrollment date: {student.enrollment_date}",
            f"Created:         {student.created_at}",
            f"Updated:         {student.updated_at}",
        )
    )


def _show_list(students: Sequence[Student]) -> None:
    print(format_students(students))
    if students:
        print(f"\n{len(students)} record(s) found.")


def handle_command(db: StudentDatabase, args: argparse.Namespace) -> int:
    if args.command == "add":
        student = db.create_student(
            name=args.name,
            email=args.email,
            age=args.age,
            course=args.course,
            enrollment_date=args.enrollment_date,
        )
        print(f"Added student #{student.id}: {student.name}")
        return 0

    if args.command == "list":
        students = db.list_students(
            search=args.search,
            course=args.course,
            sort=args.sort,
            descending=args.desc,
            limit=args.limit,
        )
        _show_list(students)
        return 0

    if args.command == "show":
        student = db.get_student(args.id)
        if student is None:
            raise StudentNotFoundError(f"No student found with ID {args.id}.")
        print(format_student(student))
        return 0

    if args.command == "update":
        changes = {
            field: value
            for field, value in (
                ("name", args.name),
                ("email", args.email),
                ("age", args.age),
                ("course", args.course),
                ("enrollment_date", args.enrollment_date),
            )
            if value is not None
        }
        if not changes:
            raise ValidationError("Provide at least one field to update.")
        student = db.update_student(args.id, **changes)
        print(f"Updated student #{student.id}: {student.name}")
        return 0

    if args.command == "delete":
        student = db.get_student(args.id)
        if student is None:
            raise StudentNotFoundError(f"No student found with ID {args.id}.")
        if not args.yes:
            answer = input(f"Delete student #{student.id} ({student.name})? [y/N]: ")
            if answer.strip().lower() not in {"y", "yes"}:
                print("Cancelled.")
                return 0
        if db.delete_student(student.id):
            print(f"Deleted student #{student.id}: {student.name}")
            return 0
        raise StudentNotFoundError(f"No student found with ID {args.id}.")

    raise ValidationError("No command was provided.")


MENU = """
Student Database CRUD
---------------------
1. Add student
2. List students
3. Show student
4. Update student
5. Delete student
6. Search students
0. Quit
"""


def _prompt_age(current: int | None = None) -> int | None:
    label = f"Age [{current}]: " if current is not None else "Age: "
    value = input(label).strip()
    if not value and current is not None:
        return None
    try:
        return int(value)
    except ValueError:
        raise ValidationError("age must be a whole number.") from None


def _interactive_add(db: StudentDatabase) -> None:
    print("\nAdd Student")
    name = input("Name: ").strip()
    email = input("Email: ").strip()
    age = _prompt_age()
    course = input("Course: ").strip()
    enrollment_date = input("Enrollment date YYYY-MM-DD [today]: ").strip() or None
    student = db.create_student(
        name=name,
        email=email,
        age=age,
        course=course,
        enrollment_date=enrollment_date,
    )
    print(f"\nAdded student #{student.id}: {student.name}")


def _interactive_list(db: StudentDatabase) -> None:
    _show_list(db.list_students())


def _interactive_show(db: StudentDatabase) -> None:
    student_id = input("Student ID: ").strip()
    student = db.get_student(student_id)
    if student is None:
        print(f"No student found with ID {student_id}.")
        return
    print()
    print(format_student(student))


def _interactive_update(db: StudentDatabase) -> None:
    student_id = input("Student ID: ").strip()
    student = db.get_student(student_id)
    if student is None:
        print(f"No student found with ID {student_id}.")
        return

    print("\nLeave a field blank to keep its current value.")
    name = input(f"Name [{student.name}]: ").strip()
    email = input(f"Email [{student.email}]: ").strip()
    age = _prompt_age(student.age)
    course = input(f"Course [{student.course}]: ").strip()
    enrollment_date = input(
        f"Enrollment date [{student.enrollment_date}]: "
    ).strip()

    changes: dict[str, Any] = {}
    if name:
        changes["name"] = name
    if email:
        changes["email"] = email
    if age is not None:
        changes["age"] = age
    if course:
        changes["course"] = course
    if enrollment_date:
        changes["enrollment_date"] = enrollment_date

    if not changes:
        print("No changes made.")
        return

    updated = db.update_student(student.id, **changes)
    print(f"\nUpdated student #{updated.id}: {updated.name}")


def _interactive_delete(db: StudentDatabase) -> None:
    student_id = input("Student ID: ").strip()
    student = db.get_student(student_id)
    if student is None:
        print(f"No student found with ID {student_id}.")
        return
    answer = input(f"Delete student #{student.id} ({student.name})? [y/N]: ")
    if answer.strip().lower() not in {"y", "yes"}:
        print("Cancelled.")
        return
    db.delete_student(student.id)
    print(f"Deleted student #{student.id}: {student.name}")


def _interactive_search(db: StudentDatabase) -> None:
    term = input("Search name, email, or course: ").strip()
    _show_list(db.list_students(search=term))


def run_interactive(db: StudentDatabase) -> int:
    actions = {
        "1": _interactive_add,
        "2": _interactive_list,
        "3": _interactive_show,
        "4": _interactive_update,
        "5": _interactive_delete,
        "6": _interactive_search,
    }

    print(MENU)
    while True:
        try:
            choice = input("Choose an option: ").strip()
            if choice in {"0", "q", "quit", "exit"}:
                print("Goodbye.")
                return 0
            action = actions.get(choice)
            if action is None:
                print("Invalid option. Choose 0-6.")
                continue
            action(db)
        except (StudentError, ValueError, sqlite3.Error) as exc:
            print(f"Error: {exc}")
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye.")
            return 0
        print()


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        with StudentDatabase(args.db) as db:
            if args.command is None:
                return run_interactive(db)
            return handle_command(db, args)
    except (StudentError, sqlite3.Error) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
