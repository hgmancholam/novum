# Backend Unit Testing Skill

## Description
Specialized knowledge for Python/pytest testing best practices, async testing, mocking, and achieving high test coverage.

## When to Use
- Writing unit tests for backend code
- Testing async functions
- Mocking HTTP calls and database
- Measuring test coverage
- Setting up test fixtures

## Tech Stack

- **Testing Framework**: pytest
- **Async Support**: pytest-asyncio
- **HTTP Mocking**: pytest-httpx
- **Database Testing**: pytest-postgresql
- **Coverage**: pytest-cov

## Test Structure

```
backend/tests/
├── conftest.py           # Shared fixtures
├── fixtures/             # Test data
│   └── runs/
│       └── golden_trace.jsonl
├── unit/                 # Unit tests
│   ├── test_models.py
│   ├── test_services.py
│   └── test_utils.py
├── integration/          # Integration tests
│   ├── test_api.py
│   └── test_database.py
└── e2e/                  # End-to-end tests
    └── test_workflows.py
```

## Pytest Configuration

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = [
    "-v",
    "--tb=short",
    "--cov=app",
    "--cov-report=term-missing",
    "--cov-report=html",
    "--cov-fail-under=80"
]
filterwarnings = [
    "ignore::DeprecationWarning"
]
```

## Async Testing Patterns

### Basic Async Test
```python
import pytest
from app.services import process_query

@pytest.mark.asyncio
async def test_process_query():
    """Test async query processing."""
    result = await process_query("What is Python?")
    
    assert result is not None
    assert result.status == "completed"
```

### Using AsyncMock
```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_with_mocked_dependency():
    """Test with mocked async dependency."""
    mock_client = AsyncMock()
    mock_client.fetch.return_value = {"data": "test"}
    
    with patch("app.services.client", mock_client):
        result = await my_service_function()
        
    mock_client.fetch.assert_called_once()
    assert result == {"data": "test"}
```

## Fixtures

### Shared conftest.py
```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from app.database import Base
from app.config import settings

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def db_engine():
    """Create test database engine."""
    engine = create_async_engine(
        settings.TEST_DATABASE_URL,
        echo=True
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
async def db_session(db_engine):
    """Create test database session."""
    async with AsyncSession(db_engine) as session:
        yield session
        await session.rollback()

@pytest.fixture
async def client(db_session):
    """Create test HTTP client."""
    from httpx import AsyncClient
    from app.main import app
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
```

### Factory Fixtures
```python
import factory
from app.models import User, Run

class UserFactory(factory.Factory):
    class Meta:
        model = User
    
    id = factory.LazyFunction(uuid.uuid4)
    token_hash = factory.LazyFunction(
        lambda: hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    )

class RunFactory(factory.Factory):
    class Meta:
        model = Run
    
    id = factory.LazyFunction(uuid.uuid4)
    query = factory.Faker("sentence")
    status = "pending"
    user = factory.SubFactory(UserFactory)

@pytest.fixture
def user_factory():
    return UserFactory

@pytest.fixture
def run_factory():
    return RunFactory
```

## HTTP Mocking with pytest-httpx

```python
import pytest
from httpx import Response

@pytest.mark.asyncio
async def test_external_api_call(httpx_mock):
    """Test with mocked external HTTP call."""
    httpx_mock.add_response(
        url="https://api.tavily.com/search",
        json={"results": [{"title": "Result 1"}]}
    )
    
    result = await search_service.search("test query")
    
    assert len(result.results) == 1
    assert result.results[0].title == "Result 1"

@pytest.mark.asyncio
async def test_api_error_handling(httpx_mock):
    """Test error handling for failed API calls."""
    httpx_mock.add_response(
        url="https://api.tavily.com/search",
        status_code=500,
        json={"error": "Internal Server Error"}
    )
    
    with pytest.raises(ExternalAPIError):
        await search_service.search("test query")
```

## Database Testing

### Using Real PostgreSQL
```python
import pytest
from pytest_postgresql import factories

postgresql_proc = factories.postgresql_proc(
    port=5433,
    host="localhost"
)
postgresql = factories.postgresql("postgresql_proc")

@pytest.fixture
async def db_session(postgresql):
    """Create session with real PostgreSQL."""
    engine = create_async_engine(
        f"postgresql+asyncpg://..."
    )
    # ... setup
```

### Testing Repositories
```python
@pytest.mark.asyncio
async def test_create_run(db_session, user_factory):
    """Test run creation in database."""
    user = user_factory()
    db_session.add(user)
    await db_session.commit()
    
    run = Run(
        user_id=user.id,
        query="Test query"
    )
    db_session.add(run)
    await db_session.commit()
    
    # Verify
    result = await db_session.get(Run, run.id)
    assert result is not None
    assert result.query == "Test query"
    assert result.status == "pending"
```

## API Testing

```python
@pytest.mark.asyncio
async def test_create_run_endpoint(client, auth_headers):
    """Test POST /api/runs endpoint."""
    response = await client.post(
        "/api/runs",
        json={"query": "What is Python?"},
        headers=auth_headers
    )
    
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["query"] == "What is Python?"
    assert data["status"] == "pending"

@pytest.mark.asyncio
async def test_create_run_validation_error(client, auth_headers):
    """Test validation error on invalid request."""
    response = await client.post(
        "/api/runs",
        json={},  # Missing required field
        headers=auth_headers
    )
    
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
```

## Coverage Requirements

### Running Coverage
```bash
# Run tests with coverage
pytest --cov=app --cov-report=term-missing

# Generate HTML report
pytest --cov=app --cov-report=html

# Fail if coverage below threshold
pytest --cov=app --cov-fail-under=80
```

### Coverage Configuration
```toml
# pyproject.toml
[tool.coverage.run]
source = ["app"]
omit = [
    "app/migrations/*",
    "app/__main__.py"
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError"
]
```

## Test Organization Tips

### Arrange-Act-Assert Pattern
```python
@pytest.mark.asyncio
async def test_example():
    # Arrange
    user = UserFactory()
    input_data = {"query": "test"}
    
    # Act
    result = await service.process(user, input_data)
    
    # Assert
    assert result.success is True
```

### Parametrized Tests
```python
@pytest.mark.parametrize("status,expected", [
    ("pending", True),
    ("running", True),
    ("completed", False),
    ("failed", False),
])
async def test_is_active(status, expected):
    run = RunFactory(status=status)
    assert run.is_active == expected
```

### Test Markers
```python
@pytest.mark.slow
@pytest.mark.asyncio
async def test_slow_operation():
    """Slow test, skip with: pytest -m 'not slow'"""
    pass

@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_workflow():
    """Integration test."""
    pass
```
