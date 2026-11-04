# Database, accounts and file storage

## Accounts

| Role | How the account is created |
|---|---|
| Admin | `python -m app.seed` creates `admin@hiresense.app`. The password is `ADMIN_PASSWORD` from `backend/.env`, or generated and printed **once** in the console when that is empty. |
| Student, recruiter | Sign-up page (recruiters can be set to need admin approval) |
| Mentor | Created by the admin in *Admin → Users* |

There are **no demo accounts or sample users**. The seed only adds reference data: interview categories and question
bank, rubrics, badges, reward rules, challenges and four starter assessments. The backend logs a security warning at
startup while any admin account still uses the old published password `Admin@12345`.

- **Lost the admin password?** From `backend/` run `venv\Scripts\python -m app.reset_admin` to generate and print a
  new one, or `venv\Scripts\python -m app.reset_admin "YourNewPassword"` to set your own.
- **Forgot password:** the sign-in page has a "Forgot password?" link. With email set up (`SMTP_*` in `backend/.env`)
  the reset link is emailed; without email it is printed in the backend console so the placement office can pass it
  on. Links expire after 30 minutes and work only once.
- **Deleting an account:** students can permanently delete their own account and data under *Account settings →
  Delete my account*.
- **AI data consent:** when the language-model provider is hosted (Gemini), AI endpoints return 428 until the student
  agrees; the time is stored in `users.ai_data_consent_at` with an audit entry, and it can be withdrawn in Settings.

## MongoDB

Settings in `backend/.env`:

```
MONGODB_URL=mongodb://127.0.0.1:27017     # or mongodb+srv://user:password@cluster.example.net for Atlas
MONGODB_DB=hiresense
UPLOAD_DIR=                                # optional; default backend/uploads
```

- One collection per model in `backend/app/models.py`; ids are integers from the `_counters` collection.
- No migrations are needed: indexes and unique constraints are created at startup (`database.init_db()`), and a
  field added to a model later simply gets its default when older documents are read.
- `ON DELETE CASCADE / SET NULL` rules declared on the models are applied by the data layer, so deleting a user
  removes their resumes, interviews, applications, etc.
- Uploaded resumes are files on local disk under `backend/uploads/<user id>/`; MongoDB stores only the path.
- **Backup:** `GET /api/admin/backup` (admin only, e.g. from http://127.0.0.1:8000/docs) returns a zip with every collection as MongoDB Extended JSON
  (restore one with `mongoimport --db hiresense --collection <name> --file <name>.json --jsonArray`), or run
  `mongodump --db hiresense`. Copy `backend/uploads/` as well.
- The old SQLite files (`backend/hiresense*.db`) are no longer used and were not imported (they held test and demo
  data: the admin and the three demo accounts with their test interviews). Delete them once you no longer need them.

---
