🤖 Door_Openbot & Monitoring Dashboard
A comprehensive system for request collection and monitoring. It features a high-performance Telegram bot built with Aiogram 3 and a robust web administration panel powered by FastAPI.

🌟 Key Features
📱 Telegram Bot
Automated Data Collection: Streamlined user polling for SITEID, Surname, and Phone number.

Input Validation: Strict RegEx validation for SITEID (5 digits) and phone formats (+7/8).

Status Updates: Quick "open"/"close" status reporting via Reply Keyboards.

Asynchronous Engine: Built on aiosqlite for non-blocking database operations.

### 📸 screenshots

#### Telegram Bot
![Telegram Bot Demo](screenshots/bot_demo.png)

#### Admin Panel
![Admin Panel Demo](screenshots/panel_dark.png)
![Admin Panel Demo](screenshots/panel_light.png)

💻 Web Admin Dashboard
Authentication: Secure session-based login with role-based access control (RBAC).

Role Model:

admin: Full access — view, edit, delete records, and export data.

user: Restricted access — can only view records matching their own surname.

Advanced Filtering: Search and sort by SITEID, status, and date ranges.

Data Export: Instant download of the entire database in CSV and Excel (.xlsx) formats.

🛠 Tech Stack
Backend: Python 3.12, FastAPI, Uvicorn.

Telegram: Aiogram 3.x.

Database: SQLite (via aiosqlite).

Data Processing: Pandas, Openpyxl (for Excel generation).

Frontend: Jinja2 Templates, HTML/CSS.

Deployment: Docker & Docker Compose.



