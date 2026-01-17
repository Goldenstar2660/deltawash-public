"""
Test configuration and fixtures for integration tests.
"""
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

from src.database import Base, get_db
from src.main import app


# Use a dedicated test database
TEST_DATABASE_URL = "postgresql://dashboard_user:dashboard_password@db:5432/deltawash_dashboard_test"

# Create test engine
test_engine = create_engine(TEST_DATABASE_URL)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """
    Create all tables before tests run and drop them after.
    This ensures a clean database for each test session.
    """
    # Drop all tables first to ensure clean state
    Base.metadata.drop_all(bind=test_engine)
    # Create all tables fresh
    Base.metadata.create_all(bind=test_engine)
    yield
    # Clean up after all tests
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def db_session():
    """
    Create a new database session for each test.
    Truncates all tables after each test to ensure isolation.
    """
    session = TestSessionLocal()
    yield session
    
    # Truncate all tables to ensure clean state between tests
    # Must do this before closing the session
    try:
        # Get all table names in reverse order to handle foreign key constraints
        tables = Base.metadata.sorted_tables
        for table in reversed(tables):
            session.execute(table.delete())
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"Error during test cleanup: {e}")
    finally:
        session.close()


@pytest.fixture(scope="function", autouse=True)
def override_get_db(db_session):
    """
    Override the get_db dependency to use the test session.
    """
    def _get_test_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.clear()

