from dependency_injector import containers, providers

from examples.todo.domain.services.todo_service import TodoService
from examples.todo.infrastructure.repositories.todo_repository import TodoRepository


class TodoContainer(containers.DeclarativeContainer):
    core_container = providers.DependenciesContainer()
    todo_repository = providers.Singleton(
        TodoRepository,
        database=core_container.database,
    )
    todo_service = providers.Factory(
        TodoService,
        todo_repository=todo_repository,
    )
