"""Pytest configuration and fixtures"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx


@pytest.fixture
def mock_response():
    """Mock HTTP response fixture"""
    response = MagicMock()
    response.status_code = 200
    response.json = MagicMock(return_value={"success": True})
    return response


@pytest.fixture
def mock_async_client():
    """Mock AsyncClient fixture"""
    client = AsyncMock()
    client.is_closed = False
    return client


@pytest.fixture
def mock_httpx_client(mock_async_client, mock_response):
    """Mock httpx.AsyncClient with proper context manager"""
    client = AsyncMock()
    client.is_closed = False

    # Configure response methods
    client.get = AsyncMock(return_value=mock_response)
    client.post = AsyncMock(return_value=mock_response)
    client.put = AsyncMock(return_value=mock_response)
    client.delete = AsyncMock(return_value=mock_response)
    client.aclose = AsyncMock()

    return client


@pytest.fixture
def api_key_env(monkeypatch):
    """Set API key environment variable for testing"""
    monkeypatch.setenv("BLOG_API_KEY", "test_api_key_123")
    return "test_api_key_123"


@pytest.fixture
def api_url_env(monkeypatch):
    """Set API URL environment variable for testing"""
    monkeypatch.setenv("BLOG_API_URL", "http://test-api.example.com")
    return "http://test-api.example.com"
