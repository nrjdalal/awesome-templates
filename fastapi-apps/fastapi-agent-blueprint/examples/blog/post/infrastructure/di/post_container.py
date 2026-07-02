from dependency_injector import containers, providers

# Cross-domain wiring import. After both domains are copied
# (`cp -r examples/blog/author src/author`), the concrete AuthorRepository is
# the class auto-discovery already registered under `src.author` — importing it
# from anywhere else would map a second AuthorModel onto the same `author`
# table and crash the boot. Unresolvable while this file lives under examples/.
from src.author.infrastructure.repositories.author_repository import (
    AuthorRepository,
)

from ...domain.services.post_service import PostService
from ..repositories.post_repository import (
    PostRepository,
)


class PostContainer(containers.DeclarativeContainer):
    core_container = providers.DependenciesContainer()

    post_repository = providers.Singleton(
        PostRepository,
        database=core_container.database,
    )

    # Wire the AuthorRepositoryProtocol to the concrete AuthorRepository.
    # This is the only place the post domain touches author infrastructure.
    author_repository = providers.Singleton(
        AuthorRepository,
        database=core_container.database,
    )

    post_service = providers.Factory(
        PostService,
        post_repository=post_repository,
        author_repository=author_repository,
    )
