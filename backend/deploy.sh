#!/usr/bin/env bash
# FinAI Deployment Helper Script
# Usage: ./deploy.sh [setup|start|stop|logs|status|backup|restore]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
print_error() {
  echo -e "${RED}❌ $1${NC}"
}

print_success() {
  echo -e "${GREEN}✅ $1${NC}"
}

print_info() {
  echo -e "${YELLOW}ℹ️  $1${NC}"
}

# Check prerequisites
check_docker() {
  if ! command -v docker &> /dev/null; then
    print_error "Docker not found. Install from https://docs.docker.com/get-docker/"
    exit 1
  fi
  print_success "Docker found: $(docker --version)"
}

check_compose() {
  if ! docker compose version &> /dev/null; then
    print_error "Docker Compose not found."
    exit 1
  fi
  print_success "Docker Compose found: $(docker compose version)"
}

# Commands
setup() {
  print_info "Setting up FinAI..."
  
  # Check if .env exists
  if [ -f ".env" ]; then
    print_info ".env already exists, skipping copy"
  else
    check_file ".env.example"
    cp .env.example .env
    print_success ".env created from template"
    print_info "Edit .env with your configuration before running start"
  fi
  
  # Create directories
  mkdir -p static uploads exports logs ssl
  print_success "Directories created"
  
  print_info "Next steps:"
  print_info "1. Edit .env with your API key and database password"
  print_info "2. Copy FinAI_Platform.html to static/"
  print_info "3. Run: ./deploy.sh start"
}

start() {
  check_docker
  check_compose
  
  if [ ! -f ".env" ]; then
    print_error ".env not found. Run: ./deploy.sh setup"
    exit 1
  fi
  
  print_info "Starting FinAI stack..."
  docker compose up -d
  
  print_info "Waiting for services to start..."
  sleep 5
  
  docker compose ps
  
  print_success "FinAI started!"
  print_info "Access your app:"
  print_info "  Frontend: http://localhost (or https://yourdomain.com)"
  print_info "  API Docs: http://localhost:8000/api/docs"
  print_info "  Health:   http://localhost:8000/health"
}

stop() {
  print_info "Stopping FinAI..."
  docker compose down
  print_success "FinAI stopped"
}

logs() {
  CONTAINER=${1:-api}
  docker compose logs -f "$CONTAINER"
}

status() {
  docker compose ps
}

backup() {
  print_info "Backing up database..."
  BACKUP_FILE="backups/finai_backup_$(date +%Y%m%d_%H%M%S).sql"
  mkdir -p backups
  
  docker compose exec -T db pg_dump -U finai finai_db > "$BACKUP_FILE"
  print_success "Backup created: $BACKUP_FILE"
}

restore() {
  if [ -z "$1" ]; then
    print_error "Usage: ./deploy.sh restore <backup_file>"
    echo "Available backups:"
    ls -lah backups/ 2>/dev/null || echo "  No backups found"
    exit 1
  fi
  
  print_info "Restoring database from $1..."
  docker compose exec -T db psql -U finai finai_db < "$1"
  print_success "Database restored from $1"
}

health() {
  print_info "Checking health..."
  
  if curl -s http://localhost:8000/health | grep -q "healthy"; then
    print_success "API is healthy"
    echo $(curl -s http://localhost:8000/health | jq .)
  else
    print_error "API is not responding"
    exit 1
  fi
}

# Main
COMMAND=${1:-help}

case $COMMAND in
  setup)
    setup
    ;;
  start)
    start
    ;;
  stop)
    stop
    ;;
  logs)
    logs "$2"
    ;;
  status)
    status
    ;;
  backup)
    backup
    ;;
  restore)
    restore "$2"
    ;;
  health)
    health
    ;;
  *)
    echo "FinAI Deployment Helper"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  setup                  - Initialize configuration (.env, directories)"
    echo "  start                  - Start all services (API, DB, Nginx)"
    echo "  stop                   - Stop all services"
    echo "  status                 - Show container status"
    echo "  logs [container]       - View logs (default: api)"
    echo "  health                 - Check API health"
    echo "  backup                 - Backup database"
    echo "  restore <file>         - Restore database from backup"
    echo ""
    echo "Examples:"
    echo "  $0 setup"
    echo "  $0 start"
    echo "  $0 logs api"
    echo "  $0 backup"
    echo "  $0 restore backups/finai_backup_20250304_120000.sql"
    exit 1
    ;;
esac
