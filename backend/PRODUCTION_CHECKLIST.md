# FinAI Production Deployment Checklist

## Pre-Deployment Preparation (1-2 days before)

### Environment & Secrets
- [ ] Anthropic API key is valid and has sufficient quota
- [ ] Generate strong passwords (min 32 chars, mixed case + numbers + symbols)
- [ ] Create `.env` file with all secrets (never commit to git)
- [ ] Database password changed from default
- [ ] SECRET_KEY generated with: `openssl rand -base64 32`
- [ ] JWT_SECRET different from SECRET_KEY
- [ ] LOG_LEVEL set to "INFO" (not "DEBUG" in production)

### Server Infrastructure
- [ ] Server provisioned (AWS EC2, DigitalOcean, etc.)
- [ ] SSH key configured and secured
- [ ] Firewall rules: Allow ports 22 (SSH), 80 (HTTP), 443 (HTTPS)
- [ ] 4GB+ RAM verified
- [ ] 50GB+ disk space available
- [ ] Domain name registered
- [ ] DNS A record points to server IP

### SSL/TLS Certificates
- [ ] Domain verified with Let's Encrypt or CA
- [ ] SSL certificates downloaded/generated
- [ ] Certificates placed in `ssl/` directory:
  - `ssl/fullchain.pem` (certificate + chain)
  - `ssl/privkey.pem` (private key)
- [ ] Certificate validity checked (not expired)
- [ ] Certificate renewal process planned (Let's Encrypt auto-renewal)

### Backup & Disaster Recovery
- [ ] Database backup strategy documented
- [ ] Automated daily backups configured (cron job or cloud service)
- [ ] Backup storage location verified (S3, Azure Blob, etc.)
- [ ] Restore procedure tested
- [ ] Disaster recovery runbook written

### Monitoring & Logging
- [ ] Logging service subscribed (CloudWatch, Datadog, ELK, etc.)
- [ ] Error alerts configured
- [ ] Uptime monitoring service set up (StatusPage, Uptime Robot)
- [ ] Discord/Slack notifications configured for alerts
- [ ] Log retention policy defined

---

## Deployment Day Checklist

### Pre-Launch Testing
- [ ] All environment variables in `.env` verified
- [ ] Docker images build locally: `docker compose build`
- [ ] Health check endpoint responds: `curl /health`
- [ ] Database connection test passes
- [ ] File upload test succeeds: POST to `/api/datasets/upload`
- [ ] AI agent responds: POST to `/api/agent/chat`
- [ ] Analytics endpoints work: GET `/api/analytics/p-and-l`

### Deployment Execution
- [ ] Pull latest code from repository
- [ ] Copy `.env` to server (secure method)
- [ ] Copy SSL certificates to `ssl/` directory
- [ ] Copy frontend HTML to `static/FinAI_Platform.html`
- [ ] Run deployment: `docker compose up -d`
- [ ] Wait 60 seconds for startup
- [ ] Verify all 3 containers running: `docker compose ps`

### Post-Launch Verification (First Hour)
- [ ] Frontend loads at `https://yourdomain.com`
- [ ] API responds to health check: `curl https://yourdomain.com/health`
- [ ] API docs accessible: `https://yourdomain.com/api/docs`
- [ ] Test file upload with small CSV
- [ ] Test AI agent with simple query
- [ ] Test analytics endpoints
- [ ] Check logs for errors: `docker compose logs api`
- [ ] Monitor resource usage: `docker stats`
- [ ] Database connection stable
- [ ] No 500 errors in logs

### Post-Launch Monitoring (First 24 Hours)
- [ ] Refresh health check every 15 minutes
- [ ] Monitor CPU/memory/disk usage
- [ ] Check logs hourly for errors/warnings
- [ ] Test database backup runs successfully
- [ ] Verify SSL certificate validity
- [ ] Confirm CORS headers correct
- [ ] Monitor API response times

### Post-Launch Monitoring (Days 2-7)
- [ ] Daily health checks
- [ ] Review error logs daily
- [ ] Test report generation
- [ ] Test data export functionality
- [ ] Verify database backups running
- [ ] Monitor server resource usage
- [ ] Test SSL certificate renewal process

---

## Security Hardening Checklist

- [ ] CORS_ORIGINS restricted to production domain only
- [ ] DEBUG mode disabled (DEBUG=false)
- [ ] APP_ENV set to "production"
- [ ] API rate limiting implemented
- [ ] HTTPS enforced (HTTP → HTTPS redirect)
- [ ] Security headers configured in nginx:
  - [ ] X-Frame-Options: DENY
  - [ ] X-Content-Type-Options: nosniff
  - [ ] X-XSS-Protection: 1; mode=block
  - [ ] Strict-Transport-Security configured
- [ ] File upload size limited (50MB)
- [ ] Allowed file extensions restricted (.xlsx, .csv only)
- [ ] Database user has minimal required permissions
- [ ] SSH access restricted to known IPs (if possible)
- [ ] Fail2ban or similar configured
- [ ] Regular security updates (docker pull & rebuild weekly)

---

## Operational Procedures

### Daily Tasks
```bash
# Check system health
docker stats

# Review recent logs
docker compose logs --tail 100 api

# Verify backups completed
ls -lah backups/
```

### Weekly Tasks
```bash
# Update images
docker compose pull
docker compose up -d

# Clean unused resources
docker system prune -a

# Check SSL certificate expiration
openssl x509 -in ssl/fullchain.pem -noout -dates
```

### Monthly Tasks
- [ ] Review error logs for patterns
- [ ] Test database restore from backup
- [ ] Update dependencies: `pip install --upgrade -r requirements.txt`
- [ ] Review and update firewall rules
- [ ] Audit user access logs
- [ ] Test disaster recovery procedure

### Quarterly Tasks
- [ ] Security audit of `.env` variables
- [ ] Review and rotate API keys if needed
- [ ] Database optimization and indexing review
- [ ] Capacity planning (disk, memory, CPU)
- [ ] Update documentation
- [ ] Performance optimization review

---

## Rollback Procedure

If deployment fails:

```bash
# Stop everything
docker compose down

# Verify stopped
docker compose ps

# Restore previous version
git checkout previous-version
docker compose build
docker compose up -d

# Or restore from database backup
docker compose down -v
docker compose up -d
docker compose exec db psql -U finai finai_db < backup.sql
```

---

## Incident Response

### API Down
```bash
# Check status
docker compose ps

# View logs
docker compose logs api | tail -50

# Restart API only
docker compose restart api

# If still failing, rebuild
docker compose down
docker compose up -d
```

### Database Issues
```bash
# Check database status
docker compose logs db

# Connect to database
docker compose exec db psql -U finai -c "SELECT 1;"

# If corrupted, restore from backup
docker compose down -v
docker compose up -d
# Restore backup...
```

### Out of Disk Space
```bash
# Check disk usage
df -h

# Clean old logs (be careful)
docker compose logs --tail 1000 > logs-archive.txt
docker system prune -a

# If needed, expand volume (cloud provider dependent)
```

### High Memory Usage
```bash
# Check process usage
docker stats

# Increase Docker memory limit in Desktop settings

# Or reduce log retention
```

---

## Performance Baseline

Expected metrics under normal load:

| Metric | Expected | Alert If |
|--------|----------|----------|
| API Response Time | 50-200ms | > 500ms |
| CPU Usage | 5-15% | > 80% |
| Memory Usage | 256MB-500MB | > 1GB |
| Database Connections | 5-10 | > 50 |
| Disk Usage | Growing slowly | > 90% |
| Requests/sec | 10-100 | N/A |

---

## Contact & Support

- **Architecture/Deployment Issues**: See [DEPLOY.md](DEPLOY.md)
- **API Issues**: Check [/api/docs](http://localhost:8000/api/docs)
- **Database Issues**: PostgreSQL docs or DBA
- **Anthropic Issues**: https://support.anthropic.com
- **Docker Issues**: https://docs.docker.com
