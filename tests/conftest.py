import pytest


def pytest_collection_modifyitems(items):
    for item in items:
        path = str(item.fspath).replace("\\", "/")
        if "/tests/integration/" in path:
            item.add_marker(pytest.mark.integration)
        elif "/tests/unit/" in path:
            item.add_marker(pytest.mark.unit)
