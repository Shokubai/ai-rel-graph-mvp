# 1. Setup environment and dependencies
make setup

# 2. Start all services
make docker-up

# 3. Wait for services to initialize, then run migrations
sleep 10
make db-upgrade

# 4. Verify everything works
./scripts/test-setup.sh

# 5. View service URLs
make urls