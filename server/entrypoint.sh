#!/bin/sh

# Wait for database if needed (e.g., using wait-for-it or sleep)
# ./wait-for-it.sh db:5432 -- timeout could be here if using compose

# Only run db init if migrations folder does not exist
if [ ! -d "migrations" ]; then
  flask db init
fi

flask db migrate -m "autogenerate"
flask db upgrade

# Start the app
exec flask run --host=0.0.0.0 --port=5000