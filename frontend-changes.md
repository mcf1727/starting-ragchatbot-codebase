# Frontend Changes

No frontend changes were made in this implementation.

This feature added backend testing infrastructure only:
- `backend/tests/conftest.py` — shared pytest fixtures and the `_StubStaticFiles` helper that allows `app.py` to be imported in the test environment without requiring the `../frontend` directory.
- `backend/tests/test_api_endpoints.py` — 22 tests covering `POST /api/query`, `GET /api/courses`, `DELETE /api/session/{id}`, and `GET /`.
- `pyproject.toml` — added `httpx>=0.27.0` dependency and `[tool.pytest.ini_options]` with `testpaths`, `pythonpath`, and `addopts`.
