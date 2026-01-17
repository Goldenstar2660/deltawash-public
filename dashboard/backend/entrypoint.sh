#!/bin/bash
set -e

echo "Starting backend initialization..."

# Wait for database to be fully ready
echo "Waiting for database to be ready..."
until PGPASSWORD=$POSTGRES_PASSWORD psql -h db -U $POSTGRES_USER -d $POSTGRES_DB -c '\q' 2>/dev/null; do
  echo "Database is unavailable - sleeping"
  sleep 2
done

echo "Database is ready!"

# Run migrations
echo "Running database migrations..."
cd /app
python src/scripts/init_db.py

# Create admin user if it doesn't exist
echo "Checking for admin user..."
USER_COUNT=$(PGPASSWORD=$POSTGRES_PASSWORD psql -h db -U $POSTGRES_USER -d $POSTGRES_DB -t -c "SELECT COUNT(*) FROM users WHERE email='admin@hospital.com';" 2>/dev/null | xargs)

if [ "$USER_COUNT" = "0" ]; then
  echo "Creating admin user..."
  python src/scripts/create_user.py --email admin@hospital.com --password admin123 --role org_admin
else
  echo "Admin user already exists."
fi

# Check if database is empty (no sessions exist)
SESSION_COUNT=$(PGPASSWORD=$POSTGRES_PASSWORD psql -h db -U $POSTGRES_USER -d $POSTGRES_DB -t -c "SELECT COUNT(*) FROM sessions;" 2>/dev/null | xargs)

echo "Current session count: $SESSION_COUNT"

if [ "$SESSION_COUNT" = "0" ]; then
  echo "Database is empty. Seeding demo data..."
  python src/scripts/seed_demo_data.py --seed 42
  
  echo "Refreshing materialized views..."
  python src/scripts/refresh_views.py
else
  echo "Database already contains data. Skipping seed."
fi

echo "Backend initialization complete!"

# Start the application
echo "Starting FastAPI application..."
exec "$@"
