import pytest
from unittest.mock import patch, MagicMock
from backend.services.monitor import APIMonitor, TOMTOM_DAILY_LIMIT

@pytest.fixture
def mock_redis():
    with patch('backend.services.monitor.redis.Redis') as mock_redis_class:
        mock_instance = MagicMock()
        mock_redis_class.return_value = mock_instance
        yield mock_instance

def test_check_budget_ok(mock_redis):
    mock_redis.get.return_value = "100"  # 100 calls, <80%
    monitor = APIMonitor()
    result = monitor.check_budget()
    assert result["count"] == 100
    assert result["limit"] == TOMTOM_DAILY_LIMIT
    assert result["pct"] == (100 / TOMTOM_DAILY_LIMIT) * 100
    assert result["status"] == "ok"

def test_check_budget_warning(mock_redis):
    count = int(TOMTOM_DAILY_LIMIT * 0.85)  # 85% >80%
    mock_redis.get.return_value = str(count)
    monitor = APIMonitor()
    result = monitor.check_budget()
    assert result["status"] == "warning"

def test_check_budget_critical(mock_redis):
    count = TOMTOM_DAILY_LIMIT + 10  # >100%
    mock_redis.get.return_value = str(count)
    monitor = APIMonitor()
    result = monitor.check_budget()
    assert result["status"] == "critical"

def test_check_budget_zero(mock_redis):
    mock_redis.get.return_value = None  # No key, count=0
    monitor = APIMonitor()
    result = monitor.check_budget()
    assert result["count"] == 0
    assert result["status"] == "ok"

@patch('backend.services.monitor.logger')
def test_log_budget_status_warning(mock_logger, mock_redis):
    count = int(TOMTOM_DAILY_LIMIT * 0.85)
    mock_redis.get.return_value = str(count)
    monitor = APIMonitor()
    monitor.log_budget_status()
    mock_logger.warning.assert_called_once()

@patch('backend.services.monitor.logger')
def test_log_budget_status_critical(mock_logger, mock_redis):
    count = TOMTOM_DAILY_LIMIT + 10
    mock_redis.get.return_value = str(count)
    monitor = APIMonitor()
    monitor.log_budget_status()
    mock_logger.error.assert_called_once()

@patch('backend.services.monitor.logger')
def test_log_budget_status_ok(mock_logger, mock_redis):
    mock_redis.get.return_value = "100"
    monitor = APIMonitor()
    monitor.log_budget_status()
    mock_logger.warning.assert_not_called()
    mock_logger.error.assert_not_called()