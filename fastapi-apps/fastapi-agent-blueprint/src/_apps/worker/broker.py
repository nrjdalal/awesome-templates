from src._core.infrastructure.di.core_container import CoreContainer

# Create and manage the broker instance via CoreContainer
container = CoreContainer()
broker = container.broker()
