"""
apps/discussions/admin.py
Discussion data lives in MongoDB, not MySQL — so there's nothing to register
with the Django admin. This file exists to satisfy Django's app conventions.
Admin access to MongoDB data is available via:
  - Django shell: python manage.py shell
  - MongoDB Compass / mongosh (dev: localhost:27017)
"""
