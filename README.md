# todo list and good to know commands

for an initial setup/test

1. Initial setup                                                                                                                  ✔  00:24:42 
    make setup

2. Start services  
    make docker-up

3. Wait a few seconds, then run migrations
        sleep 10
    make db-upgrade

4. Test everything
    ./scripts/test-setup.sh

5. View service URLs
    make urls


# Daily development
make docker-up          # Start everything
make docker-logs        # Watch logs
make health-check       # Verify services
make docker-down        # Stop everything

# Making changes
make format             # Format code
make lint               # Check code quality
make test               # Run tests

# Database work
make db-migrate         # Create migration
make db-upgrade         # Apply migrations
make db-shell           # Open psql

# Troubleshooting
make docker-rebuild     # Rebuild containers
make docker-logs-backend # Check backend logs
make docker-status      # Check what's running