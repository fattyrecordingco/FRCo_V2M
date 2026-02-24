# Development Guide

## Implementation Order Followed

1. Repository scaffold reset and structure replacement.
2. Frontend 4-step wizard mocked scaffolding.
3. Backend offline note conversion.
4. Backend drum transcription and chord conversion.
5. Frontend/backend integration with live endpoints.
6. Persistent archive, file rename, and ZIP export.
7. Desktop and plugin scaffolds.
8. Tests, CI, and docs.

## Local Commands

### Backend

```bash
cd backend
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Tests

```bash
python -m pytest
```

### Coverage

```bash
python -m pytest --cov=backend/app --cov-report=term
```

Latest baseline in this rebuild: `64%` total backend coverage with algorithm and export-path unit tests.

### Lint

```bash
python -m ruff check .
cd frontend && npm run lint
```
