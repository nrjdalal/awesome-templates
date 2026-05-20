from src.user.infrastructure.di.user_container import UserContainer
from src.user.interface.worker.tasks import user_test_task


def create_user_container(user_container: UserContainer) -> None:
    user_container.wire(modules=[user_test_task])


def bootstrap_user_domain(user_container: UserContainer) -> None:
    create_user_container(user_container=user_container)
