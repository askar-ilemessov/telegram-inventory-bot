# Inventory POS Bot

Telegram bot for inventory and sales management (bar/restaurant).

**Stack:** Python 3.9, Django 4.2, PostgreSQL, aiogram 3.x

---

## 🚀 Quick Start (Docker)

### 1. Start Containers

```bash
docker-compose up -d
```

### 2. Add Your Telegram ID

Get your Telegram ID from [@userinfobot](https://t.me/userinfobot), then run:

```bash
docker exec -it inventory_pos_bot python manage.py shell -c "
from apps.core.models import StaffProfile
from django.contrib.auth.models import User

user, _ = User.objects.get_or_create(
    username='admin',
    defaults={'first_name': 'Admin', 'is_staff': True, 'is_superuser': True}
)
user.set_password('admin123')
user.save()

profile, _ = StaffProfile.objects.get_or_create(
    user=user,
    defaults={'telegram_id': YOUR_TELEGRAM_ID}  # Replace with your ID
)
print(f'✅ Ready! Telegram ID: {profile.telegram_id}')
"
```

### 3. Access Django Admin (Optional)

Open http://localhost:8000/admin
- Username: `admin`
- Password: `admin123`

### 4. Test the Bot

Send `/start` to your bot on Telegram.

---

## 📋 Docker Commands

```bash
# Start
docker-compose up -d

# Stop
docker-compose down

# View logs
docker logs inventory_pos_bot -f

# Restart
docker-compose restart

# Rebuild
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Django shell
docker exec -it inventory_pos_bot python manage.py shell

# Run tests
docker exec -it inventory_pos_bot python manage.py test
```

---

## 🛠️ Local Development

### 1. Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure `.env`

```bash
cp .env.example .env
```

Edit `.env`:
```env
SECRET_KEY=your-secret-key
DEBUG=True
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/inventory_pos_db
TELEGRAM_BOT_TOKEN=your-bot-token-from-@BotFather
GOOGLE_SHEETS_ENABLED=False
```

### 3. Database

```bash
createdb inventory_pos_db
python manage.py migrate
python manage.py createsuperuser
```

### 4. Add Telegram ID

```bash
python manage.py shell
```

```python
from django.contrib.auth.models import User
from apps.core.models import StaffProfile, Location

location = Location.objects.create(name="Bar", address="Main St")
user = User.objects.create_user(username='admin', first_name='Admin')
staff = StaffProfile.objects.create(
    user=user,
    telegram_id=YOUR_TELEGRAM_ID,  # From @userinfobot
    role=StaffProfile.Role.ADMIN,
    location=location
)
```

### 5. Run

```bash
# Terminal 1: Bot
python manage.py run_bot

# Terminal 2: Admin (optional)
python manage.py runserver
```

---

## 📊 Features

- **Shift Management** - Open/close shifts, track staff
- **Sales** - Record sales with payment methods (cash/card/transfer)
- **Refunds** - Process refunds with stock adjustments
- **Reports** - 5 report types (general, financial, sales, refunds, inventory)
- **Logging** - All actions logged to files per shift
- **Stock Validation** - Prevent overselling
- **Concurrency Safe** - Uses `select_for_update` and `transaction.atomic`

---

## 🏗️ Architecture

### Apps
- **core** - Users, locations, staff profiles
- **inventory** - Products, categories
- **pos** - Shifts, transactions, payments (business logic)
- **integrations** - Google Sheets export (optional)
- **bot** - Telegram bot handlers, FSM, keyboards

### Key Principles
- **Single Source of Truth:** PostgreSQL only
- **Decimal for Money:** No floats, ever
- **Append-Only Transactions:** Cannot delete/edit transactions
- **Type Hints:** Everywhere
- **Service Layer:** Handlers → Services → Models

---

## 📁 Project Structure

```
inventory-transaction-system/
├── apps/
│   ├── core/          # StaffProfile, Location
│   ├── inventory/     # Product, Category
│   ├── pos/           # Shift, Transaction, Payment, services.py
│   └── integrations/  # Google Sheets
├── bot/
│   ├── handlers.py    # Telegram handlers
│   ├── keyboards.py   # Bot keyboards
│   ├── states.py      # FSM states
│   └── middlewares.py # Auth middleware
├── config/            # Django settings
├── shift_logs/        # Per-shift log files
├── docker-compose.yml
├── Dockerfile
├── .env.docker        # Docker environment
└── requirements.txt
```

---

## 🧪 Testing

```bash
# Local
python manage.py test

# Docker
docker exec -it inventory_pos_bot python manage.py test
```

**Current:** 16 tests, all passing

---

## 📝 Environment Variables

### Required
- `SECRET_KEY` - Django secret key
- `TELEGRAM_BOT_TOKEN` - From @BotFather
- `DATABASE_URL` (local) or `DB_*` variables (Docker)

### Optional
- `GOOGLE_SHEETS_ENABLED` - Enable Google Sheets export (default: False)
- `GOOGLE_SHEET_ID` - Spreadsheet ID
- `GOOGLE_SERVICE_ACCOUNT_FILE` - Service account JSON path

---

## 🔐 Roles

- **ADMIN** - Full access
- **MANAGER** - Open/close shifts, view reports
- **CASHIER** - Sales only

---

---

## 🌐 Production Deployment

### VPS Deployment

**One-command deployment:**

```bash
# On your VPS (Ubuntu 22.04+)
curl -fsSL https://raw.githubusercontent.com/askar-ilemessov/telegram-inventory-bot/main/deploy.sh | sudo bash -s https://github.com/askar-ilemessov/telegram-inventory-bot.git
```

**Or manual deployment:**

```bash
# 1. SSH to server
ssh root@your-server-ip

# 2. Clone and run deploy script
git clone https://github.com/askar-ilemessov/telegram-inventory-bot.git /opt/inventory-bot
cd /opt/inventory-bot
sudo ./deploy.sh https://github.com/askar-ilemessov/telegram-inventory-bot.git
```

**Access Django Admin:**
- URL: `http://YOUR_SERVER_IP:8000/admin`
- Default password: `admin123` (change after first login!)

### Deployment Options

| Platform | Cost | Difficulty | Guide |
|----------|------|------------|-------|
| **VPS (DigitalOcean/Hetzner)** | $6/mo | Easy | See [DEPLOYMENT.md](DEPLOYMENT.md) |
| **Railway.app** | Free-$5/mo | Easiest | See [DEPLOYMENT.md](DEPLOYMENT.md) |
| **Render.com** | Free-$7/mo | Easy | See [DEPLOYMENT.md](DEPLOYMENT.md) |

**Full deployment guide:** [DEPLOYMENT.md](DEPLOYMENT.md)

### Production Checklist

- [ ] Set `DEBUG=False`
- [ ] Use strong `SECRET_KEY` and database password
- [ ] Configure `ALLOWED_HOSTS`
- [ ] Set up HTTPS (Nginx + Let's Encrypt)
- [ ] Create separate admin user for end user
- [ ] Set up automated backups (`./backup.sh`)
- [ ] Configure firewall

---

## 🔄 Backup & Restore

**Create backup:**
```bash
./backup.sh
```

**Restore from backup:**
```bash
gunzip backup_YYYYMMDD_HHMMSS.sql.gz
docker exec -i inventory_pos_db psql -U postgres inventory_pos_db < backup_YYYYMMDD_HHMMSS.sql
```

**Automated daily backups (cron):**
```bash
# Add to crontab
0 2 * * * /opt/inventory-bot/backup.sh
```

---

## 📞 Support

Contact project administrator.

