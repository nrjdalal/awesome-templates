from src._apps.worker.bootstrap import bootstrap_app
from src._apps.worker.broker import broker

# Run bootstrap (task registration and DI setup)
bootstrap_app(app=broker)

# Taskiq CLI entry point
app = broker
