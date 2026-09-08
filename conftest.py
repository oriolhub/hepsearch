import os

# Keep later test setup safe when pytest-django has already configured Django.
os.environ.setdefault("SECRET_KEY", "test-only-not-for-deployment")
