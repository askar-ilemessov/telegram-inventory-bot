# Railway Deployment Checklist

## ✅ Current Status

### What's Working:
- ✅ Bot deployed and running on Railway
- ✅ PostgreSQL database connected
- ✅ All migrations applied
- ✅ Superuser created
- ✅ Bot polling successfully
- ✅ Bot live: @inventory_101_bot

### What Needs Configuration:

## 🔧 Required Environment Variables in Railway

Go to your Railway bot service → **Variables** tab and verify these are set:

### 1. SECRET_KEY
```
SECRET_KEY=&#tih9p=(b4%t#u)n=a9vs#6zzt)ls3p3z3lvg0^vcp9xl(+ye
```
**Status:** [ ] Set

### 2. DEBUG
```
DEBUG=False
```
**Status:** [ ] Set

### 3. ALLOWED_HOSTS
```
ALLOWED_HOSTS=*.railway.app
```
**Status:** [ ] Set

### 4. TELEGRAM_BOT_TOKEN
```
TELEGRAM_BOT_TOKEN=8172515469:AAEsDg1PUwB80vDUF2S6fimNwARQrXqbDlU
```
**Status:** [ ] Set

### 5. RAILWAY_ENVIRONMENT (Auto-set by Railway)
```
RAILWAY_ENVIRONMENT=production
```
**Status:** ✅ Auto-set by Railway

### 6. DATABASE_URL (Auto-set by Railway)
```
DATABASE_URL=postgresql://postgres:...@postgres.railway.internal:5432/railway
```
**Status:** ✅ Auto-linked from PostgreSQL service

---

## 📋 Post-Deployment Tasks

### 1. Create Staff Profile with Telegram ID

**Option A: Using Railway CLI**
```bash
railway run python manage.py shell
```

Then in the shell:
```python
from apps.core.models import StaffProfile, Location
from django.contrib.auth.models import User

# Get the superuser
user = User.objects.get(username='admin')

# Get or create location
location, _ = Location.objects.get_or_create(
    name="Bar",
    defaults={'address': 'Main St'}
)

# Create staff profile with your Telegram ID
staff, created = StaffProfile.objects.get_or_create(
    user=user,
    defaults={
        'telegram_id': 170680754,  # Your Telegram ID from @userinfobot
        'role': StaffProfile.Role.ADMIN,
        'location': location
    }
)

if created:
    print(f'✅ Staff profile created! Telegram ID: {staff.telegram_id}')
else:
    print(f'✅ Staff profile exists! Telegram ID: {staff.telegram_id}')
```

**Option B: Using Railway Dashboard**
1. Go to your bot service
2. Click "Deployments" → Latest deployment
3. Click "View Logs"
4. Find the deployment URL
5. Access Django admin at: `https://your-app.railway.app/admin`
6. Login with superuser credentials
7. Add staff profile manually

---

## 🧪 Testing

### 1. Test the Bot
- [ ] Send `/start` to @inventory_101_bot
- [ ] Verify you see the welcome message
- [ ] Try opening a shift
- [ ] Try making a sale

### 2. Test Django Admin (Optional)
- [ ] Get your Railway app URL from dashboard
- [ ] Access: `https://your-app.railway.app/admin`
- [ ] Login with superuser credentials
- [ ] Verify you can see all models

---

## 🚀 Next Steps

1. **Set all environment variables** in Railway dashboard
2. **Redeploy** if needed (Railway auto-redeploys on variable changes)
3. **Create staff profile** with your Telegram ID
4. **Test the bot** on Telegram
5. **Commit changes** to `release_railway` branch

---

## 📝 Files Modified for Railway

- ✅ `config/settings.py` - Added Railway ALLOWED_HOSTS handling
- ✅ `requirements.txt` - Has gunicorn + whitenoise

---

## 🔗 Useful Links

- Railway Dashboard: https://railway.app
- Your Bot: @inventory_101_bot
- Get Telegram ID: @userinfobot

---

## ⚠️ Important Notes

1. **Never commit `.env` files** with real credentials to GitHub
2. **Use Railway environment variables** for all secrets
3. **Keep `main` branch** for local Docker development
4. **Use `release_railway` branch** for Railway deployment

