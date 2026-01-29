# Contributing to ARC-AGI

Thank you for your interest in contributing to ARC-AGI! This document provides guidelines and instructions for contributing to the project.

## Getting Started

### Prerequisites

- Python >= 3.12
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Git

### Development Setup

1. **Fork and clone the repository:**
   ```bash
   git clone https://github.com/your-username/ARC-AGI.git
   cd ARC-AGI
   ```

2. **Install dependencies:**
   ```bash
   # Using uv (recommended)
   uv sync --dev
   
   # Or using pip
   pip install -e ".[dev]"
   ```

3. **Install pre-commit hooks:**
   ```bash
   pre-commit install
   ```

4. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your API key (optional - anonymous key will be used if not provided)
   ```

## Development Workflow

### Making Changes

1. **Create a branch:**
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

2. **Make your changes** following the coding standards below.

3. **Run tests and checks:**
   ```bash
   # Run tests
   uv run -m unittest -v tests
   
   # Run type checking
   mypy arc_agi
   
   # Run linting and formatting
   ruff check .
   ruff format .
   ```

4. **Commit your changes:**
   ```bash
   git add .
   git commit -m "Description of your changes"
   ```
   
   Pre-commit hooks will automatically run ruff and mypy checks. Make sure all checks pass before committing.

5. **Push and create a pull request:**
   ```bash
   git push origin feature/your-feature-name
   ```

## Code Standards

### Code Style

- **Formatting**: We use [ruff](https://github.com/astral-sh/ruff) for both linting and formatting. The pre-commit hooks will automatically format your code.
- **Type Hints**: All code must include type hints. We use [mypy](https://mypy.readthedocs.io/) for type checking with strict mode enabled.
- **Imports**: Use absolute imports and organize them according to PEP 8 (standard library, third-party, local).

### Type Checking

We use strict type checking with mypy. All functions should have complete type annotations:

```python
def example_function(param1: str, param2: int) -> Optional[dict[str, Any]]:
    """Example function with proper type hints."""
    ...
```

### Documentation

- **Docstrings**: All public functions, classes, and methods should have docstrings following Google-style format:
  ```python
  def function_name(param1: str, param2: int) -> bool:
      """Brief description of the function.
      
      Longer description if needed, explaining what the function does,
      any important behavior, edge cases, etc.
      
      Args:
          param1: Description of param1.
          param2: Description of param2.
      
      Returns:
          Description of return value.
      
      Raises:
          ValueError: When something goes wrong.
      """
  ```

- **Comments**: Use comments to explain "why" rather than "what". Code should be self-documenting.

### Testing

- **Write tests** for new features and bug fixes.
- **Test coverage**: Aim for high test coverage, especially for critical paths.
- **Test structure**: Place tests in the `tests/` directory, mirroring the source structure.
- **Running tests**: Use `pytest` to run the test suite.

Example test structure:
```python
def test_feature_name():
    """Test description."""
    # Arrange
    arc = Arcade()
    
    # Act
    result = arc.some_method()
    
    # Assert
    assert result is not None
```

## Pull Request Process

1. **Update documentation** if you've changed functionality or added features.
2. **Add tests** for new functionality.
3. **Ensure all tests pass** and code quality checks are satisfied.
4. **Write a clear PR description** explaining:
   - What changes you made
   - Why you made them
   - How to test the changes
   - Any breaking changes

5. **Keep PRs focused**: Try to keep pull requests focused on a single feature or fix. Smaller PRs are easier to review.

## Areas for Contribution

We welcome contributions in the following areas:

- **Bug fixes**: Fix issues reported in the issue tracker
- **New features**: Propose new features via issues first to discuss before implementing
- **Documentation**: Improve documentation, add examples, fix typos
- **Tests**: Add test coverage for existing functionality
- **Performance**: Optimize existing code
- **Code quality**: Refactor code to improve maintainability

## Reporting Issues

When reporting issues, please include:

- **Description**: Clear description of the issue
- **Steps to reproduce**: Minimal steps to reproduce the problem
- **Expected behavior**: What you expected to happen
- **Actual behavior**: What actually happened
- **Environment**: Python version, operating system, package versions
- **Error messages**: Full error traceback if applicable

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers and help them learn
- Focus on constructive feedback
- Respect different viewpoints and experiences

## Questions?

If you have questions about contributing, feel free to:

- Open an issue for discussion
- Check existing issues and pull requests
- Review the codebase and documentation

Thank you for contributing to ARC-AGI!
