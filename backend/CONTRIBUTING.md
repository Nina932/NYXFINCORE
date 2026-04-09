# Contributing to FinAI

Thank you for your interest in contributing to the FinAI Financial Intelligence Platform! This document provides guidelines and instructions for contributing.

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inspiring community for all. Please read and adhere to our Code of Conduct.

- Be respectful and inclusive
- Welcome new contributors
- Focus on constructive criticism
- Respect differing opinions
- Report unacceptable behavior

## Getting Started

### Prerequisites

- Python 3.12+
- Git
- GitHub account
- Anthropic API key (for testing)

### Development Setup

```bash
# Clone the repository
git clone https://github.com/Nina932/fina.git
cd fina/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Run development server
python dev_start.py
```

## Making Changes

### 1. Create a Feature Branch

```bash
git checkout -b feature/descriptive-name
```

Use these prefixes:
- `feature/` - New features
- `bugfix/` - Bug fixes
- `hotfix/` - Critical fixes
- `docs/` - Documentation
- `refactor/` - Code refactoring
- `test/` - Test additions
- `chore/` - Dependency updates

### 2. Make Your Changes

- One logical change per commit
- Keep commits focused and atomic
- Write clear commit messages

### 3. Write Commit Messages

Format:
```
<type>: <subject>

<body>

<footer>
```

Types:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation
- `style:` - Code style (formatting)
- `refactor:` - Code refactoring
- `perf:` - Performance improvement
- `test:` - Test addition/update
- `chore:` - Build, dependencies
- `ci:` - CI/CD configuration

Example:
```
feat: Add user authentication endpoints

Implement JWT-based authentication system with:
- User registration endpoint
- User login endpoint
- Token refresh mechanism

Closes #123
```

### 4. Test Your Changes

```bash
# Run tests
pytest tests/ -v

# Run with coverage
pytest --cov=app tests/

# Check code style
flake8 app/
black app/

# Check types (optional)
mypy app/
```

### 5. Commit and Push

```bash
# Stage changes
git add .

# Commit
git commit -m "type: description"

# Push
git push origin feature/descriptive-name
```

## Submitting a Pull Request

### Before Submitting

- [ ] Tests pass (`pytest tests/ -v`)
- [ ] Code is formatted (`black app/`)
- [ ] No linting errors (`flake8 app/`)
- [ ] Documentation is updated
- [ ] Commits are clean and well-described
- [ ] Branch is up-to-date with main (`git pull origin main`)

### Create Pull Request

1. Go to GitHub repository
2. Click "New Pull Request"
3. Select your feature branch
4. Fill in the PR template completely
5. Request reviewers
6. Submit for review

### PR Review Process

- At least one approval required
- All checks must pass (tests, linting, coverage)
- Documentation must be updated
- No merge conflicts
- All conversations resolved

## Code Standards

### Python Style

We follow PEP 8 and use `black` for formatting.

```python
# Good
def calculate_profit(transactions: List[Transaction]) -> float:
    """
    Calculate total profit from transactions.
    
    Args:
        transactions: List of transaction objects
        
    Returns:
        Total profit as float
    """
    return sum(t.amount for t in transactions if t.amount > 0)

# Format with black
black app/
```

### Type Hints

Use type hints for all functions:

```python
def get_transactions(
    dataset_id: str,
    limit: int = 100,
    offset: int = 0
) -> List[Transaction]:
    ...
```

### Docstrings

Use Google style docstrings:

```python
def my_function(param1: str, param2: int) -> bool:
    """
    Brief description of what the function does.
    
    Longer description if needed, explaining the purpose
    and behavior in more detail.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When X condition occurs
        
    Example:
        >>> result = my_function("test", 42)
        >>> print(result)
        True
    """
    ...
```

### Comments

Use comments for "why", not "what":

```python
# Bad
x = y + 1  # Add 1 to y

# Good
# Account for zero-based indexing
x = y + 1
```

## Testing

### Write Tests

Every new feature should have tests:

```python
# tests/test_feature.py
import pytest
from app.services import my_service

@pytest.mark.asyncio
async def test_calculate_profit():
    """Test profit calculation with sample data."""
    transactions = [
        Transaction(amount=100),
        Transaction(amount=-30),
    ]
    result = await my_service.calculate_profit(transactions)
    assert result == 70

@pytest.mark.asyncio
async def test_invalid_input():
    """Test error handling with invalid input."""
    with pytest.raises(ValueError):
        await my_service.calculate_profit(None)
```

### Coverage

Aim for >80% test coverage:

```bash
pytest --cov=app tests/
```

## Documentation

### Update Documentation

- Update README.md for user-facing changes
- Update code docstrings for API changes
- Update DEPLOY.md for deployment changes
- Add examples in docstrings

### API Documentation

Document new endpoints:

```python
@router.get("/api/new-endpoint")
async def new_endpoint(param: str = Query(...)) -> dict:
    """
    Brief description of endpoint.
    
    Args:
        param: Query parameter description
        
    Returns:
        Response schema description
        
    Raises:
        HTTPException: 404 if not found
    """
    ...
```

## Performance Considerations

- Avoid N+1 queries (use eager loading where needed)
- Add database indexes for frequently queried fields
- Use caching for expensive operations
- Monitor database performance
- Profile code before optimizing

## Security Guidelines

- Never commit secrets (use .env)
- Validate all user input
- Use parameterized queries (SQLAlchemy does this)
- Implement rate limiting
- Use HTTPS in production
- Keep dependencies updated
- Run security checks: `bandit app/`

## Dependency Updates

When updating dependencies:

```bash
# Update requirements.txt
pip install --upgrade package-name

# Regenerate requirements.txt if using pip install
pip freeze > requirements.txt

# Test thoroughly
pytest tests/ -v

# Commit
git commit -m "chore: Update package-name to X.Y.Z"
```

## Reporting Bugs

### Before Reporting

- Check if bug already exists on Issues page
- Try to reproduce the bug
- Check logs for error messages
- Note your environment (Python version, OS, etc.)

### Bug Report Contents

```markdown
## Description
Brief description of the bug

## Steps to Reproduce
1. Step one
2. Step two
3. ...

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Environment
- Python version: 3.12
- OS: Ubuntu 22.04
- Database: PostgreSQL / SQLite

## Logs
```
Error message and stack trace
```
```

## Feature Requests

Submit feature requests on GitHub Issues:

```markdown
## Description
What you want to build

## Use Case
Why do you need this feature

## Proposed Implementation
How you think it should work (optional)

## Examples
Show how it would be used
```

## Questions & Discussions

- Use GitHub Discussions for questions
- Check existing discussions before asking
- Be specific and provide context
- Help others with their questions

## Review Process

### As a Contributor

- Respond to review comments
- Make requested changes
- Push updates (don't force push)
- Re-request review after changes
- Be open to feedback

### As a Reviewer

- Provide constructive feedback
- Suggest improvements
- Approve when satisfied
- Request changes if needed
- Approve when issues resolved

## Merging

- Rebase commits for clean history (optional)
- Use "Squash and merge" for small changes
- Use "Create a merge commit" for features
- Delete feature branch after merge

## After Your PR is Merged

- Monitor for issues
- Help with related PRs
- Check if your change is in the next release

## Ongoing Development

### Stay Updated

```bash
# Fetch latest changes
git fetch origin

# Rebase your work
git rebase origin/main

# Or merge
git merge origin/main
```

### Help Others

- Review open PRs
- Help with issues
- Answer questions
- Improve documentation

## Credits

Contributors will be:
- Listed in CONTRIBUTORS.md
- Credited in release notes
- Mentioned on GitHub contributors page

## Questions?

- Ask in GitHub Discussions
- Check documentation
- Open an issue

Thank you for contributing to FinAI! 🚀
