import tempfile
import unittest
from datetime import date
from pathlib import Path

from student_db import (
    DuplicateEmailError,
    StudentDatabase,
    StudentNotFoundError,
    ValidationError,
)


class StudentDatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.db_path = Path(self._temporary_directory.name) / "test_students.db"
        self.db = StudentDatabase(self.db_path)

    def tearDown(self) -> None:
        self.db.close()
        self._temporary_directory.cleanup()

    def add_student(self, **overrides: object):
        data = {
            "name": "Aarav Sharma",
            "email": "aarav@example.com",
            "age": 20,
            "course": "Computer Science",
            "enrollment_date": "2024-07-01",
        }
        data.update(overrides)
        return self.db.create_student(**data)

    def test_create_and_read_student(self) -> None:
        student = self.add_student(name="  Aarav   Sharma ", email="AARAV@EXAMPLE.COM")

        self.assertEqual(student.id, 1)
        self.assertEqual(student.name, "Aarav Sharma")
        self.assertEqual(student.email, "aarav@example.com")
        self.assertEqual(student.age, 20)
        self.assertEqual(student.course, "Computer Science")
        self.assertEqual(student.enrollment_date, "2024-07-01")
        self.assertTrue(student.created_at)
        self.assertTrue(student.updated_at)
        self.assertEqual(self.db.get_student(1), student)
        self.assertEqual(self.db.find_by_email("Aarav@Example.com"), student)

    def test_enrollment_date_defaults_to_today(self) -> None:
        student = self.add_student(enrollment_date=None)
        self.assertEqual(student.enrollment_date, date.today().isoformat())

    def test_duplicate_email_is_rejected_case_insensitively(self) -> None:
        self.add_student()

        with self.assertRaises(DuplicateEmailError):
            self.add_student(name="Another Student", email="AARAV@example.com")

        self.assertEqual(len(self.db.list_students()), 1)

    def test_list_search_filter_sort_and_limit(self) -> None:
        self.add_student(name="Zara Khan", email="zara@example.com", age=22)
        self.add_student(name="Amit Patel", email="amit@example.com", age=18)
        self.add_student(
            name="Meera Nair",
            email="meera@example.com",
            age=21,
            course="Mathematics",
        )

        self.assertEqual(
            [student.name for student in self.db.list_students()],
            ["Amit Patel", "Meera Nair", "Zara Khan"],
        )
        self.assertEqual(
            [student.name for student in self.db.list_students(descending=True)],
            ["Zara Khan", "Meera Nair", "Amit Patel"],
        )
        self.assertEqual(
            [student.name for student in self.db.list_students(search="math")],
            ["Meera Nair"],
        )
        self.assertEqual(
            [student.name for student in self.db.list_students(course="computer science")],
            ["Amit Patel", "Zara Khan"],
        )
        self.assertEqual(
            [student.name for student in self.db.list_students(sort="age", limit=2)],
            ["Amit Patel", "Meera Nair"],
        )

    def test_update_student(self) -> None:
        student = self.add_student()

        updated = self.db.update_student(
            student.id,
            name="Aarav S. Sharma",
            age=21,
            course="Data Science",
        )

        self.assertEqual(updated.id, student.id)
        self.assertEqual(updated.name, "Aarav S. Sharma")
        self.assertEqual(updated.email, student.email)
        self.assertEqual(updated.age, 21)
        self.assertEqual(updated.course, "Data Science")
        self.assertEqual(self.db.get_student(student.id), updated)

    def test_update_rejects_duplicate_email(self) -> None:
        first = self.add_student()
        self.add_student(name="Diya Rao", email="diya@example.com")

        with self.assertRaises(DuplicateEmailError):
            self.db.update_student(first.id, email="DIYA@example.com")

        self.assertEqual(self.db.get_student(first.id).email, "aarav@example.com")

    def test_update_missing_student_and_empty_fields(self) -> None:
        with self.assertRaises(StudentNotFoundError):
            self.db.update_student(999, name="Nobody")
        with self.assertRaises(ValidationError):
            self.db.update_student(1)

    def test_delete_student(self) -> None:
        student = self.add_student()

        self.assertTrue(self.db.delete_student(student.id))
        self.assertIsNone(self.db.get_student(student.id))
        self.assertFalse(self.db.delete_student(student.id))

    def test_validation_errors(self) -> None:
        cases = (
            {"name": "   "},
            {"email": "not-an-email"},
            {"age": 0},
            {"age": 121},
            {"course": ""},
            {"enrollment_date": "01-07-2024"},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                with self.assertRaises(ValidationError):
                    self.add_student(**overrides)

        with self.assertRaises(ValidationError):
            self.db.get_student(0)
        with self.assertRaises(ValidationError):
            self.db.list_students(sort="password")
        with self.assertRaises(ValidationError):
            self.db.list_students(limit=0)


if __name__ == "__main__":
    unittest.main()
