# Student Database CRUD

A dependency-free Python command-line application for managing student records
in SQLite. It supports creating, reading, updating, deleting, searching, and
sorting records through parameterized SQL queries.

## Features

- SQLite database created automatically on first run
- Create, list, view, update, and delete student records
- Case-insensitive email uniqueness
- Search by name, email, or course
- Filter by course and sort by any column
- Input validation with clear error messages
- Interactive menu and scriptable subcommands
- Unit tests using Python's built-in `unittest`

## Requirements

Python 3.10 or newer. No third-party packages are required.

## Quick start

Run the commands from this directory.

```powershell
# Start the interactive menu (creates students.db if needed)
python main.py

# Add a student
python main.py add --name "Aarav Sharma" --email "aarav@example.com" --age 20 --course "Computer Science"

# List all students
python main.py list

# Search and filter
python main.py list --search "aarav"
python main.py list --course "Computer Science" --sort age --desc

# View one student
python main.py show 1

# Update one or more fields
python main.py update 1 --course "Data Science" --age 21

# Delete a student
python main.py delete 1

# Delete without the confirmation prompt
python main.py delete 1 --yes
```

Use `--db` before the command to choose a different database file:

```powershell
python main.py --db school.db list
```

## Interactive menu

Running `python main.py` without a command opens a menu:

```text
1. Add student
2. List students
3. Show student
4. Update student
5. Delete student
6. Search students
0. Quit
```

When updating, leave a field blank to keep its current value.

## Command reference

| Command | Description |
| --- | --- |
| `add` | Add a student with `--name`, `--email`, `--age`, and `--course` |
| `list` | List students with optional `--search`, `--course`, `--sort`, `--desc`, and `--limit` |
| `show ID` | Display a single student record |
| `update ID` | Update any of `--name`, `--email`, `--age`, `--course`, or `--enrollment-date` |
| `delete ID` | Delete a student, with `-y`/`--yes` to skip confirmation |

Run `python main.py --help` or `python main.py <command> --help` for all options.

## Database schema

The application creates this table and its indexes automatically:

```sql
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
```

`email` uses `COLLATE NOCASE` with a `UNIQUE` constraint, so
`AARAV@example.com` and `aarav@example.com` are treated as the same address.

## SQL operations

The data layer in `student_db.py` uses parameterized statements so values are
never interpolated into SQL text.

Create:

```sql
INSERT INTO students (name, email, age, course, enrollment_date)
VALUES (?, ?, ?, ?, ?);
```

Read:

```sql
SELECT * FROM students WHERE id = ?;
SELECT * FROM students WHERE email = ? COLLATE NOCASE;
SELECT * FROM students
WHERE name LIKE ? COLLATE NOCASE
   OR email LIKE ? COLLATE NOCASE
   OR course LIKE ? COLLATE NOCASE
ORDER BY name COLLATE NOCASE ASC, id ASC;
```

Update:

```sql
UPDATE students
SET name = ?, age = ?, updated_at = datetime('now')
WHERE id = ?;
```

Delete:

```sql
DELETE FROM students WHERE id = ?;
```

Sort columns are selected from a fixed allowlist, not from raw user input.

## Project structure

```text
student-database-crud/
├── main.py             # CLI and interactive menu
├── student_db.py       # Validation, schema, and SQL operations
├── test_student_db.py  # Unit tests
├── README.md
└── students.db         # Created at runtime, ignored by Git
```

## Running tests

```powershell
python -m unittest discover -v
```

The tests use temporary database files, so your `students.db` is not modified.
