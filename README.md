# 📚 Online Course Progress Tracker

> A full-stack web application that helps students track their learning progress across Udemy and Coursera — with streaks, coins, stage alerts, and daily email notifications.

![Python](https://img.shields.io/badge/Python-3.14-blue?logo=python)
![Django](https://img.shields.io/badge/Django-6.0-green?logo=django)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue?logo=postgresql)
![DRF](https://img.shields.io/badge/Django_REST_Framework-3.17-red)
![Docker](https://img.shields.io/badge/Docker-ready-blue?logo=docker)

---

## 🚀 Features

- 👤 **User Registration & Login** — Student and Mentor roles
- 🔗 **Connect Udemy & Coursera** — via API token
- 📊 **Progress Tracking** — completion % per course
- 🔴🟡🟢 **Stage Alerts** — Red (≤33%), Yellow (34–66%), Green (>66%)
- 🔥 **Streaks & Coins** — daily motivation system
- 📧 **Daily Email Notifications** — automated progress updates
- 👨‍🏫 **Mentor Dashboard** — monitor all students in one view

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, Django, Django REST Framework |
| Database | PostgreSQL |
| Frontend | HTML, CSS, JavaScript |
| Deployment | Docker, Docker Compose |

---

## 📁 Project Structure

```
course-tracker/
├── config/              # Django settings & URLs
├── users/               # Registration, login
├── courses/             # Courses, modules, lessons, enrollments
├── progress/            # Lesson completion, stage alerts
├── notifications/       # Daily email notifications
├── mentors/             # Mentor dashboard
├── frontend/            # HTML/CSS/JS frontend
└── schema.sql           # PostgreSQL database schema
```

---

## ⚙️ Setup & Installation

### Prerequisites
- Python 3.14+
- PostgreSQL
- pip

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/Padmapriya2121/course-tracker.git
cd course-tracker

# 2. Install dependencies
pip install django djangorestframework psycopg2-binary python-dotenv django-cors-headers

# 3. Create PostgreSQL database
psql -U postgres
CREATE DATABASE course_tracker;
\q

# 4. Load the schema
psql -U postgres -d course_tracker -f schema.sql

# 5. Update database settings in config/settings.py
# Set your PostgreSQL password

# 6. Run migrations
python manage.py migrate

# 7. Start the server
python manage.py runserver
```

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/users/register/` | Register a student or mentor |
| POST | `/api/users/login/` | Login |
| GET | `/api/courses/` | Get all courses |
| POST | `/api/courses/enroll/` | Enroll in a course |
| POST | `/api/progress/complete/` | Mark a lesson as complete |
| GET | `/api/progress/` | Get progress % for a course |
| POST | `/api/notifications/send/` | Send daily email to all students |
| GET | `/api/mentors/dashboard/` | Mentor view of all students |

---

## 🗄️ Database Schema

10 tables covering all features:

```
users              → students & mentors (with streaks & coins)
courses            → available courses
modules            → chapters inside a course
lessons            → individual lessons
enrollments        → student ↔ course links
progress           → completed lessons
platform_connections → Udemy/Coursera API tokens
alerts             → Red/Yellow/Green stage history
email_logs         → daily email history
mentor_students    → mentor ↔ student assignments
```

---

## 📧 Email Notification Sample

```
Subject: Your Daily Progress Update

Hello Padma,

Here is your daily progress update:

Course: Python Basics
Progress: 66.67%
Stage: 🟢 Green
Streak: 5 days
Coins: 50

Keep learning! 💪
```

---

## 👥 Team

Built as part of Project 16 — Online Course Progress Tracker

---

## 📄 License

MIT License
