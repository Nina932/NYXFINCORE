# GitHub Integration Guide for FinAI Backend

## Repository Setup

Your GitHub repository: `https://github.com/Nina932/fina`

---

## Quick Setup (5 Minutes)

### Step 1: Initialize Local Repository
```bash
cd backend

# Initialize git
git init

# Add GitHub remote
git remote add origin https://github.com/Nina932/fina.git

# Or if using SSH (requires SSH key):
git remote add origin git@github.com:Nina932/fina.git
```

### Step 2: Configure Git User
```bash
# Set your Git username and email
git config user.name "Your Name"
git config user.email "your.email@example.com"

# Or set globally (for all projects)
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

### Step 3: Create Initial Commit
```bash
# Check status
git status

# Add all files (respects .gitignore)
git add .

# Commit
git commit -m "Initial commit: FinAI Backend v2.0.0 - Production Ready"

# View commits
git log --oneline
```

### Step 4: Push to GitHub
```bash
# First, ensure you have the main branch
git branch -M main

# Push to GitHub
git push -u origin main

# For subsequent commits, just:
git push
```

---

## Development Workflow

### Create Feature Branch
```bash
# Create and switch to new branch
git checkout -b feature/new-endpoint

# Or using newer syntax
git switch -c feature/new-endpoint

# Make your changes...

# Commit changes
git add .
git commit -m "Feature: Add new analytics endpoint"

# Push to GitHub
git push -u origin feature/new-endpoint

# Create Pull Request on GitHub.com
```

### Standard Commit Messages
```bash
# Feature
git commit -m "Feature: Brief description of feature"

# Bug fix
git commit -m "Fix: Brief description of bug fix"

# Documentation
git commit -m "Docs: Update README"

# Code style
git commit -m "Style: Format code"

# Tests
git commit -m "Test: Add tests for new feature"

# Refactor
git commit -m "Refactor: Improve function structure"

# Chore
git commit -m "Chore: Update dependencies"
```

---

## Common Git Commands

### View Status & History
```bash
# Current status
git status

# View recent commits
git log --oneline -10

# View detailed commit info
git log --stat

# View changes in working directory
git diff

# View staged changes
git diff --staged
```

### Manage Branches
```bash
# List branches
git branch

# List all branches (local and remote)
git branch -a

# Switch to branch
git checkout main
git checkout feature/new-endpoint

# Delete branch
git branch -d feature/new-endpoint

# Rename current branch
git branch -m new-name
```

### Undo Changes
```bash
# Discard changes in working directory
git checkout -- filename.py

# Unstage a file
git reset HEAD filename.py

# Amend last commit (before pushing)
git commit --amend

# Revert commit (creates new commit that undoes changes)
git revert <commit-hash>

# Reset to previous commit (⚠️ destructive)
git reset --hard <commit-hash>
```

### Collaboration
```bash
# Fetch latest from GitHub
git fetch origin

# Pull latest changes
git pull origin main

# Update feature branch with latest main
git fetch origin
git rebase origin/main

# Merge feature into main
git checkout main
git merge feature/new-endpoint
```

---

## GitHub Setup

### Authentication

#### HTTPS (Easier for beginners)
```bash
# Just use the HTTPS URL
git remote add origin https://github.com/Nina932/fina.git
# GitHub will prompt for credentials or use token
```

#### SSH (Recommended for regular use)

**Setup SSH Key (if not already done):**
```bash
# Generate SSH key (press Enter for all prompts)
ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa

# Display public key (copy this)
cat ~/.ssh/id_rsa.pub

# On GitHub.com:
# 1. Settings → SSH and GPG keys
# 2. New SSH key
# 3. Paste public key
# 4. Save

# Test SSH connection
ssh -T git@github.com
```

**Use SSH Remote:**
```bash
git remote set-url origin git@github.com:Nina932/fina.git
```

---

## Branching Strategy

Recommended workflow:

```
Main Branch (main)
    ↑
    └── Pull Request ← Feature Branches
            ↑
            └── feature/new-endpoint
            └── feature/analytics
            └── bugfix/fix-parser
```

### Branch Naming Conventions
```
feature/description          - New features
bugfix/description           - Bug fixes
hotfix/description          - Critical fixes
docs/description            - Documentation
refactor/description        - Code refactoring
test/description            - Test additions
chore/description           - Dependency updates, etc.
```

---

## Pull Request Process

### 1. Create Pull Request
```bash
# Push your feature branch
git push -u origin feature/new-endpoint

# Open GitHub.com and create PR from web UI
```

### 2. Describe Changes
- Provide clear title: "Add user authentication endpoints"
- Describe changes: What? Why? How?
- Link issues if applicable: "Closes #123"
- Request reviewers

### 3. Add Checklist
```markdown
## Changes
- [ ] Added user auth endpoints
- [ ] Updated database schema
- [ ] Added tests
- [ ] Updated documentation

## Type of Change
- [ ] New feature
- [ ] Bug fix
- [ ] Breaking change
- [ ] Documentation update

## Testing Done
- [ ] Unit tests added
- [ ] Manual testing completed
- [ ] No regression observed
```

### 4. Review & Merge
- Wait for reviews
- Make requested changes
- Merge to main
- Delete feature branch

---

## GitHub Actions (CI/CD)

Create `.github/workflows/test.yml` for automated testing:

```yaml
name: Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.12'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-asyncio
    
    - name: Run tests
      run: pytest tests/ -v
```

---

## Collaboration Best Practices

### Before Starting Work
```bash
# Update your local main
git checkout main
git pull origin main

# Create feature branch
git checkout -b feature/your-feature
```

### While Working
```bash
# Commit frequently with clear messages
git commit -m "Feature: Add specific functionality"

# Push periodically
git push origin feature/your-feature

# Keep commits atomic (one logical change per commit)
```

### Before Pushing
```bash
# Verify tests pass
pytest tests/ -v

# Check code style
flake8 app/
black app/

# View changes
git diff

# Verify commits look good
git log --oneline -3
```

---

## Useful GitHub Features

### Issues
1. GitHub.com → Issues → New Issue
2. Describe bug/feature request
3. Add labels, assignees, milestones
4. Reference in commits: `Fixes #123`

### Projects
1. GitHub.com → Projects → New Project
2. Create kanban board
3. Add issues as cards
4. Track progress

### Discussions
1. GitHub.com → Discussions
2. Ask questions
3. Share ideas
4. Community engagement

---

## Troubleshooting

### Cannot Push
```bash
# Check remote
git remote -v

# Update remote if needed
git remote set-url origin https://github.com/Nina932/fina.git

# Fetch and try again
git fetch origin
git push -u origin main
```

### Merge Conflicts
```bash
# When pulling/merging and conflicts occur:

# 1. View conflicts
git status

# 2. Edit conflicted files (<<<<<<< ======== >>>>>>>>)

# 3. Mark as resolved
git add conflicted-file.py

# 4. Complete merge
git commit -m "Resolve merge conflicts"
```

### Accidentally Committed to Wrong Branch
```bash
# Create correct branch from last commit
git branch feature/correct-branch

# Reset current branch
git reset --hard HEAD~1

# Switch to correct branch
git checkout feature/correct-branch

# Push
git push origin feature/correct-branch
```

### Need to Undo Last Commit (before push)
```bash
# Keep changes, undo commit
git reset --soft HEAD~1

# Discard changes, undo commit
git reset --hard HEAD~1
```

---

## .gitignore

Already created in project. Key exclusions:

```
.env                  # Never commit secrets
.env.local
venv/                 # Virtual environment
__pycache__/          # Python cache
*.db                  # Local database
logs/                 # Application logs
uploads/              # User uploads
exports/              # Generated files
.vscode/              # IDE settings
.idea/
```

---

## Useful Aliases

```bash
# Create shortcuts for common commands
git config --global alias.st status
git config --global alias.co checkout
git config --global alias.br branch
git config --global alias.ci commit
git config --global alias.unstage 'reset HEAD --'
git config --global alias.last 'log -1 HEAD'
git config --global alias.visual 'log --graph --oneline --decorate --all'

# Usage:
git st              # same as git status
git co main         # same as git checkout main
git visual          # pretty commit graph
```

---

## Regular Maintenance

### Keep Fork Updated (if forked)
```bash
# Add upstream remote
git remote add upstream https://github.com/original/repo.git

# Keep fork in sync
git fetch upstream
git merge upstream/main
git push origin main
```

### Clean Up Old Branches
```bash
# Delete local branches that are merged
git branch --merged | grep -v main | xargs git branch -d

# Delete remote tracking branches
git remote prune origin
```

### Archive Release
```bash
# Create annotated tag
git tag -a v2.0.0 -m "Release version 2.0.0"

# Push tag
git push origin v2.0.0

# Push all tags
git push origin --tags
```

---

## Learning Resources

- **GitHub Docs**: https://docs.github.com
- **Git Documentation**: https://git-scm.com/doc
- **Interactive Git Tutorial**: https://learngitbranching.js.org
- **GitHub Skills**: https://skills.github.com

---

## Quick Reference

```bash
# Setup
git init
git remote add origin https://github.com/Nina932/fina.git
git config user.name "Name"

# Create & Push
git checkout -b feature/name
git add .
git commit -m "commit message"
git push -u origin feature/name

# Update
git fetch origin
git pull origin main
git merge origin/main

# Cleanup
git branch -d feature/name
git push origin --delete feature/name
```

---

**Happy coding! 🚀**

For more details, visit: https://github.com/Nina932/fina
