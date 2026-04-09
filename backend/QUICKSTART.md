# FinAI Quick Start Guide

## 🚀 Get Running in 5 Minutes

### Prerequisites
- Docker Desktop installed ([download](https://www.docker.com/products/docker-desktop))
- Anthropic API key from [console.anthropic.com](https://console.anthropic.com/api/keys)
- Port 80, 443, 5432 available on your machine

---

## Step 1️⃣: Create Configuration

```bash
# Navigate to backend folder
cd backend

# Copy example config
cp .env.example .env
```

### Edit `.env` (Windows: use Notepad++, Mac/Linux: use nano)

Find these lines and update:
```env
ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE
DB_PASSWORD=your-strong-password-123
SECRET_KEY=your-random-32-character-secret-key
DOMAIN=localhost
```

---

## Step 2️⃣: Add Frontend

```bash
# Create static directory
mkdir static

# Copy frontend HTML
copy ..\FinAI_Platform_v7.html static\FinAI_Platform.html
```

---

## Step 3️⃣: Start Everything

```bash
# Launch all services (API + Database + Nginx)
docker compose up -d

# Wait 30 seconds for startup...

# Verify all running
docker compose ps
```

You should see 3 containers:
- ✅ finai_api
- ✅ finai_db
- ✅ finai_nginx

---

## Step 4️⃣: Access Your App

**Frontend:** http://localhost  
**API Docs:** http://localhost:8000/api/docs  
**Health:** http://localhost:8000/health  

---

## ⚠️ Troubleshooting

**Docker not found?**
- Install [Docker Desktop](https://www.docker.com/products/docker-desktop)
- Restart your machine

**Port already in use?**
```bash
# Change ports in docker-compose.yml
# Change "80:80" to "8080:80" to use port 8080 instead
```

**Database won't start?**
```bash
docker compose down -v
docker compose up -d
```

**Can't access frontend?**
```bash
# Confirm static folder contains HTML
ls -la static/

# Check nginx logs
docker compose logs nginx
```

---

## ✅ Test It Works

```bash
# Should return "healthy"
curl http://localhost:8000/health

# Should return list of datasets
curl http://localhost:8000/api/datasets

# Should say "Welcome to FinAI"
curl http://localhost/
```

---

## 🛑 Stop Everything

```bash
docker compose down

# Or with volume cleanup (deletes data)
docker compose down -v
```

---

## 📞 Need Help?

See full deployment guide: [DEPLOY.md](DEPLOY.md)
