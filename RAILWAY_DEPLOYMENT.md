# Railway Deployment Guide

## 🚀 Quick Deploy to Railway

### Prerequisites
- GitHub account
- Railway account (sign up at https://railway.app)
- Telegram Bot Token (from @BotFather)

---

## Step 1: Push Code to GitHub

```bash
git add .
git commit -m "Prepare for Railway deployment"
git push origin main
```

---

## Step 2: Create Railway Project

1. Go to https://railway.app
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Choose your repository: `telegram-inventory-bot`
5. Railway will automatically detect the project

---

## Step 3: Add PostgreSQL Database

1. In your Railway project, click **"+ New"**
2. Select **"Database"** → **"PostgreSQL"**
3. Railway will automatically create a database and set `DATABASE_URL`

---

## Step 4: Configure Environment Variables

Click on your service → **"Variables"** tab → Add these:

### Required Variables:

```bash
SECRET_KEY=<generate-a-new-secret-key>
DEBUG=False
ALLOWED_HOSTS=*.railway.app
TELEGRAM_BOT_TOKEN=<your-bot-token-from-botfather>
```

### Generate SECRET_KEY:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### Optional (Railway provides DATABASE_URL automatically):
```bash
# Only if you want to override Railway's default DATABASE_URL
DATABASE_URL=postgresql://user:password@host:port/dbname
```

---

## Step 5: Deploy

1. Railway will automatically deploy after you add environment variables
2. Wait for deployment to complete (check logs)
3. Your bot should start automatically!

---

## Step 6: Create Superuser (Django Admin Access)

1. In Railway dashboard, click on your service
2. Go to **"Settings"** → **"Deploy Logs"**
3. Click **"Shell"** or use Railway CLI:

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# Link to your project
railway link

# Run shell
railway run python manage.py createsuperuser
```

Or use the web shell:
```bash
python manage.py createsuperuser
```

---

## Step 7: Access Django Admin

1. In Railway, go to your service → **"Settings"**
2. Click **"Generate Domain"** to get a public URL
3. Access admin at: `https://your-app.railway.app/admin`

---

## 📊 Monitoring

### View Logs:
- Railway Dashboard → Your Service → **"Deployments"** → Click latest deployment

### Check Bot Status:
- Look for: `Run polling for bot @inventory_101_bot`

### Database:
- Railway Dashboard → PostgreSQL service → **"Data"** tab

---

## 🔧 Troubleshooting

### Bot not starting?
**Check logs for:**
- Missing `TELEGRAM_BOT_TOKEN`
- Database connection errors
- Migration errors

**Fix:**
```bash
railway run python manage.py migrate
```

### Can't access admin?
**Generate domain:**
1. Service → Settings → Networking
2. Click "Generate Domain"

### Database issues?
**Check DATABASE_URL:**
```bash
railway variables
```

---

## 🔄 Update Deployment

```bash
# Make changes locally
git add .
git commit -m "Your changes"
git push origin main

# Railway auto-deploys on push!
```

---

## 💰 Pricing

- **Free Tier**: $5 credit/month (enough for small bots)
- **Hobby Plan**: $5/month (500 hours)
- **Pro Plan**: $20/month (unlimited)

**Estimated usage for this bot:**
- Bot service: ~730 hours/month
- PostgreSQL: ~730 hours/month
- **Total**: ~$10-15/month on Hobby plan

---

## 📝 Environment Variables Reference

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `SECRET_KEY` | ✅ | Django secret key | `django-insecure-xxx` |
| `DEBUG` | ✅ | Debug mode | `False` |
| `ALLOWED_HOSTS` | ✅ | Allowed hosts | `*.railway.app` |
| `TELEGRAM_BOT_TOKEN` | ✅ | Bot token | `123456:ABC-DEF...` |
| `DATABASE_URL` | Auto | PostgreSQL URL | Auto-provided by Railway |

---

## ✅ Post-Deployment Checklist

- [ ] Bot is running (check logs)
- [ ] Database migrations applied
- [ ] Superuser created
- [ ] Django admin accessible
- [ ] Staff profile created with Telegram ID
- [ ] Test bot in Telegram
- [ ] Test sale flow
- [ ] Test refund flow
- [ ] Test reports

---

## 🎯 Next Steps

1. **Custom Domain** (Optional):
   - Railway Settings → Networking → Custom Domain
   - Add your domain and configure DNS

2. **Backups**:
   - Railway automatically backs up PostgreSQL
   - Or use the backup script: `./backup.sh`

3. **Monitoring**:
   - Set up Railway notifications
   - Monitor bot logs regularly

---

## 🆘 Support

- Railway Docs: https://docs.railway.app
- Railway Discord: https://discord.gg/railway
- Project Issues: https://github.com/askar-ilemessov/telegram-inventory-bot/issues

---

**Your bot is now live on Railway! 🎉**

