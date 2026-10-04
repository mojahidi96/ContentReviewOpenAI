import os

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("INTERNAL_SERVICE_TOKEN", "test-token-value-0123456789abcdef")
os.environ.setdefault("VECTOR_STORE_PATH", "/tmp/contentreview-test-chroma")
os.environ.setdefault("METADATA_DB_PATH", "/tmp/contentreview-test.sqlite3")
