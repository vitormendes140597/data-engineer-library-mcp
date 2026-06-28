# Repository Guidelines

## Project Structure & Module Organization

This Python service ingests PDF blobs, extracts markdown and images, chunks content, creates embeddings, and persists searchable data in PostgreSQL with pgvector.

- `src/` contains runtime code. Key entry points are `src/ingestion_worker.py`, `src/reprocessor.py`, and `src/cli.py`.
- Domain modules live under `src/blob/`, `src/events/`, `src/extraction/`, `src/chunking/`, `src/embeddings/`, `src/persistence/`, and `src/reprocessing/`.
- `tests/` contains unit and integration tests named `test_*.py`.
- `alembic/` and `alembic.ini` manage database migrations.
- Runtime configuration is loaded from process env first, then `.env`, then defaults in `src/config.py`.

## Build, Test, and Development Commands

Create and activate a local environment, then install pinned dependencies:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Run local dependencies from the parent project root when Docker Compose is available:

```bash
docker compose up -d azurite postgres
```

Apply database migrations:

```bash
alembic upgrade head
```

Run service entry points:

```bash
python -m src.ingestion_worker
python -m src.reprocessor
python -m src.cli bootstrap
```

## Coding Style & Naming Conventions

Use Python 3.10+ and keep modules focused by pipeline responsibility. Follow existing naming: snake_case for modules, functions, variables, and test files; PascalCase for classes. Format and sort imports before submitting:

```bash
black src tests
isort src tests
flake8 src tests --max-line-length=100
```

Prefer typed, explicit configuration access through `src/config.py`.

### Comments
Follows the pep 8 styling guide for comments.

#### Inline Comments
Inline comments provide short descriptions of variables and simple operations and are written on the same line as the code statement:

#### Block Comments
Block comments are used to describe complex logic in the code. Block comments in Python are constructed similarly to inline comments — the only difference is that block comments are written on a separate line:

#### Python Docstring Comments
In Python, docstrings are multi-line comments that explain how to use a given function or class. The documentation of your code is improved by the creation of high-quality docstrings. While working with a function or class and using the built-in help(obj) function, docstrings might be helpful in giving an overview of the object.

Use Python PEP 257 to provide a standard method of declaring docstrings.

### Development Guide
Uses when applicable:
    - generators instead of python lists
    - Development design patterns such as: Decorator, Strategy, Factory, Observer and Facade
    - Iterators
    - Use models to represent the application data
    - Functions should never depend on a single type implementation

## Testing Guidelines

Tests use `pytest`, `pytest-cov`, and integration helpers such as `testcontainers`. Run the full suite with coverage:

```bash
pytest tests/ --cov=src
```

Name new tests `tests/test_<feature>.py` and test functions `test_<behavior>`. Add or update integration tests when changes touch Azure Blob/Queue behavior, database persistence, migrations, or end-to-end ingestion/reprocessing flows.

## Commit & Pull Request Guidelines

Git history currently uses short imperative summaries, for example `created codebase` and `fixed terraform container issues`. Keep commits concise and action-oriented; mention the affected area when useful, such as `fix reprocessor retry scheduling`.

Pull requests should include a brief problem statement, implementation summary, test results, and any migration or configuration impact. Link related issues when available. Include logs or screenshots only for user-visible CLI output or operational behavior changes.

## Security & Configuration Tips

Do not commit real Azure credentials or production connection strings. Keep local secrets in `.env`, and prefer `EMBEDDING_PROVIDER=fake` for local tests unless validating Azure AI Foundry integration.
