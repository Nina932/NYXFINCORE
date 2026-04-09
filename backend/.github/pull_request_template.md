# Pull Request Template

## Description
Please include a summary of the changes and related context. Why is this change needed?

## Type of Change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to change)
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Code refactoring

## Related Issues
Closes #(issue number)

## Testing Done

- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing completed
- [ ] All tests pass (`pytest tests/ -v`)

## Code Quality

- [ ] Code follows the style guidelines (`black app/`)
- [ ] No linting errors (`flake8 app/`)
- [ ] Type hints added where appropriate
- [ ] Docstrings added/updated
- [ ] Comments added for complex logic

## Documentation

- [ ] README updated if needed
- [ ] API documentation updated
- [ ] .env.example updated if new variables added
- [ ] Deployment guide updated if needed

## Database Changes

- [ ] No database changes
- [ ] Database migration included
- [ ] Schema documented in migration
- [ ] Backwards compatible
- [ ] Tested with PostgreSQL and SQLite

## Security

- [ ] No secrets in code
- [ ] No hardcoded credentials
- [ ] SQL injection prevention verified
- [ ] CORS properly configured
- [ ] Input validation added

## Performance

- [ ] No N+1 queries
- [ ] Database indexes appropriate
- [ ] Caching considered where needed
- [ ] Memory usage acceptable

## Breaking Changes

- [ ] No breaking changes
- [ ] API breaking changes documented
- [ ] Deprecation warnings added for old endpoints
- [ ] Migration guide provided

## Checklist

- [ ] My code follows the project style guidelines
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing tests pass locally with my changes
- [ ] Any dependent changes have been merged and published

## Screenshots (if applicable)
<!-- Add screenshots if this PR includes UI changes -->

## Additional Notes
<!-- Any additional information that reviewers should know -->
