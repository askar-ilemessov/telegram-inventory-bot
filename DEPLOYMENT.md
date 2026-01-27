# Deployment Guide

## 🚀 Recommended: Deploy to VPS (DigitalOcean, Hetzner, AWS EC2)

This is the **best option** for your use case - full control, affordable, easy to manage.

### Prerequisites
- VPS with Ubuntu 22.04+ (minimum 1GB RAM, 1 CPU)
- Domain name (optional but recommended)
- SSH access to server

---

## Option 1: Quick Deploy to VPS (Recommended)

### Step 1: Prepare Your Server

```bash
# SSH into your server
ssh root@your-server-ip

# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
apt install docker-compose -y

# Create app directory
mkdir -p /opt/inventory-bot
cd /opt/inventory-bot
```

### Step 2: Upload Your Project

**Option A: Using Git (Recommended)**
```bash
# On server
cd /opt/inventory-bot
git clone YOUR_REPO_URL .
```

**Option B: Using SCP (from your local machine)**
```bash
# From your local machine
scp -r /path/to/inventory-transcation-system/* root@your-server-ip:/opt/inventory-bot/
```

### Step 3: Configure Environment

```bash
# On server
cd /opt/inventory-bot

# Create production environment file
cat > .env.docker <<EOF
SECRET_KEY=$(openssl rand -base64 32)
DEBUG=False
ALLOWED_HOSTS=your-domain.com,your-server-ip

DB_NAME=inventory_pos_db
DB_USER=postgres
DB_PASSWORD=$(openssl rand -base64 16)
DB_HOST=db
DB_PORT=5432

TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN_HERE

GOOGLE_SHEETS_ENABLED=False
EOF

# Set secure permissions
chmod 600 .env.docker
```

### Step 4: Start Services

```bash
# Start containers
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker logs inventory_pos_bot -f
```

### Step 5: Access Django Admin

**Without Domain:**
```
http://YOUR_SERVER_IP:8000/admin
```

**With Domain (see Step 6 below):**
```
https://your-domain.com/admin
```

### Step 6: Setup Domain & SSL (Optional but Recommended)

Install Nginx and Certbot:

```bash
apt install nginx certbot python3-certbot-nginx -y
```

Create Nginx configuration:

```bash
cat > /etc/nginx/sites-available/inventory-bot <<'EOF'
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

# Enable site
ln -s /etc/nginx/sites-available/inventory-bot /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx

# Get SSL certificate
certbot --nginx -d your-domain.com
```

Now access at: **https://your-domain.com/admin**

---

## Option 2: Deploy to Railway.app (Easiest, Free Tier Available)

### Pros
- ✅ Free tier available
- ✅ Automatic HTTPS
- ✅ Easy deployment from GitHub
- ✅ Built-in PostgreSQL

### Steps

1. **Push to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin YOUR_GITHUB_REPO
   git push -u origin main
   ```

2. **Deploy on Railway**
   - Go to [railway.app](https://railway.app)
   - Sign up with GitHub
   - Click "New Project" → "Deploy from GitHub repo"
   - Select your repository
   - Add PostgreSQL database (click "+ New" → "Database" → "PostgreSQL")

3. **Configure Environment Variables**
   In Railway dashboard, add these variables:
   ```
   SECRET_KEY=<generate-random-string>
   DEBUG=False
   TELEGRAM_BOT_TOKEN=<your-token>
   DATABASE_URL=${{Postgres.DATABASE_URL}}
   ALLOWED_HOSTS=*.railway.app
   ```

4. **Access Admin**
   Railway will give you a URL like: `https://your-app.railway.app/admin`

---

## Option 3: Deploy to Render.com (Free Tier)

Similar to Railway, good alternative.

1. Push code to GitHub
2. Go to [render.com](https://render.com)
3. Create "New Web Service" from GitHub repo
4. Add PostgreSQL database
5. Configure environment variables
6. Access at provided URL

---

## 🔒 Production Security Checklist

Before giving access to end users:

- [ ] Set `DEBUG=False` in production
- [ ] Use strong `SECRET_KEY` (generate with `openssl rand -base64 32`)
- [ ] Use strong database password
- [ ] Set proper `ALLOWED_HOSTS`
- [ ] Enable HTTPS (use Nginx + Let's Encrypt or platform SSL)
- [ ] Create separate admin user for end user (don't share superuser)
- [ ] Set up regular database backups
- [ ] Configure firewall (allow only ports 80, 443, 22)

---

## 📊 Cost Comparison

| Option | Cost | Difficulty | Best For |
|--------|------|------------|----------|
| **VPS (DigitalOcean)** | $6-12/month | Medium | Full control, production |
| **Railway.app** | Free - $5/month | Easy | Quick start, testing |
| **Render.com** | Free - $7/month | Easy | Alternative to Railway |
| **AWS EC2** | $5-20/month | Hard | Enterprise |

---

## 🎯 Recommended Setup for Your Use Case

**Best option: VPS (DigitalOcean/Hetzner) + Domain + SSL**

**Why?**
- Full control over server
- Affordable ($6/month)
- Can run bot 24/7
- Easy to backup
- Professional with custom domain

**Quick Start:**
1. Buy VPS from DigitalOcean ($6/month) or Hetzner (€4/month)
2. Follow "Option 1" above
3. Buy domain from Namecheap ($10/year)
4. Setup SSL with Let's Encrypt (free)
5. Total cost: ~$8/month

---

## 📝 Next Steps

Which deployment option do you prefer? I can:
1. Create automated deployment script for VPS
2. Help you set up Railway/Render
3. Create backup scripts
4. Set up monitoring

Let me know!

