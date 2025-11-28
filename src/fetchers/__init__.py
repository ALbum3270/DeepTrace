"""
Fetchers package
"""
from .base import BaseFetcher, FetchQuery
from .mock_fetcher import MockFetcher

__all__ = ["BaseFetcher", "FetchQuery", "MockFetcher"]
