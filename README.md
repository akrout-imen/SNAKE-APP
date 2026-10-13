# 🐍 SNAKE-APP

**Web app for booking shared lab equipment, built with Python, Streamlit and SQLite.**

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.51-FF4B4B?logo=streamlit&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white)
![Plotly](https://img.shields.io/badge/Plotly-3F4F75?logo=plotly&logoColor=white)

In a research lab, instruments are shared between many people and tracking who
uses what, when, and how close each instrument is to its next maintenance quickly
becomes a problem. SNAKE replaces the paper sheets and shared spreadsheets with a
single web app: users book equipment on a calendar, admins manage equipment,
users and permissions, and everyone sees the lab schedule in real time.

<!--
Screenshots: add images to a docs/ folder and reference them here, e.g.
![Home page](docs/home.png)
-->

---

## ✨ Features

### For lab users
- **Email-based login and sign-up.** New accounts stay pending until an admin validates them.
- **Home dashboard** with the lab news board, my upcoming reservations, today's birthdays, and a filterable equipment table (by room and category).
- **Calendar booking.** Users can reserve a whole day or choose a time range in 30-minute steps.
- **Automatic conflict checks.** A booking is refused if it:
  - overlaps an existing reservation;
  - overlaps an all-day reservation or a scheduled maintenance;
  - exceeds the maximum number of days allowed for that equipment.
- **Editing and cancelling.** Users can move or cancel their own reservations.
- **Category view.** A resource calendar shows every instrument of one category side by side.

### For admins
- **User management.** Admins validate new users and manage admin profiles.
- **Per-equipment booking permissions.** Some instruments can only be booked by authorised users.
- **Equipment management** in an editable table:
  - rooms, people in charge and maintenance dates;
  - usage quotas, with an automatic "maintenance needed" flag when the quota is exceeded;
  - **Excel import / export**.
- **Projects and news board** for lab-wide communication.
- **Usage statistics** per instrument and per period, shown as interactive Plotly charts.
- **Full history** of reservations and cancellations.
- **Email notifications** over SMTP:
  - admins are notified when someone signs up;
  - users are notified when their account is validated.

### Public schedule
- A separate, **read-only, mobile-first page** (`public_schedule.py`) shows the
  equipment schedule without any login, and can be opened from a **QR code**
  displayed in the lab.

---

## 🛠️ Tech stack

| Layer | Tools |
|---|---|
| Language | Python 3.13 |
| Web framework | Streamlit (multi-page app) |
| Calendar UI | streamlit-calendar (FullCalendar) |
| Database | SQLite |
| Data & charts | pandas, Plotly |
| Other | smtplib (email), email-validator, openpyxl (Excel), qrcode |

---

## 🧠 Technical choices

- **Hashed admin password.** The admin password is hashed with SHA-256 before
  being stored in the database.
- **Secrets kept out of the code.** SMTP credentials and the initial admin
  password live in `.streamlit/secrets.toml`, which git ignores.
- **Read-only public page.** `public_schedule.py` opens SQLite in `mode=ro`, so
  the public page cannot write to the database, even if it has a bug. It also
  hides project names and free-text comments.
- **Non-blocking email.** The notification functions never raise an exception.
  If SMTP is not configured or fails, sign-up and validation still work.
- **Automatic backups.** The database is copied to `db/backups/` once a day, and
  only the 30 most recent copies are kept.
- **Schema migrations.** `init_db()` creates any missing tables and adds any new
  columns when the app starts, so existing databases are updated automatically.

---

## 📁 Project structure

```
├── app.py                      # Home page: login, sign-up, dashboard
├── Pages/
│   ├── 1_Reservation-Annulation.py   # Booking, editing and cancelling
│   ├── 2_Category_View.py            # Resource calendar by category
│   └── 3_Admin.py                    # Admin dashboard
├── public_schedule.py          # Public read-only schedule (mobile)
├── db/database.py              # Database schema and migrations
├── email_utils.py              # SMTP notifications
├── utils.py                    # QR code generation for the public page
├── .streamlit/secrets.toml.example
└── requirements.txt
```

---

## 🚀 Getting started

```bash
# 1. Clone the repository
git clone https://github.com/akroutimen1-ui/SNAKE-APP.git
cd SNAKE-APP

# 2. Install dependencies (a virtual environment is recommended)
pip install -r requirements.txt

# 3. Configure secrets
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
#    then edit .streamlit/secrets.toml: set the admin password
#    (the email section is optional)

# 4. Run the app
streamlit run app.py
```

The SQLite database (`db/lab.db`) is created automatically on first launch.

To run the public schedule page as well:

```bash
streamlit run public_schedule.py --server.port 8502
```

---

## 👤 Author

**akroutimen1-ui** · [GitHub profile](https://github.com/akroutimen1-ui)
