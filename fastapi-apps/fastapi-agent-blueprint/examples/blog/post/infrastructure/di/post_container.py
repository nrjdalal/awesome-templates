from dependency_injector import containers, providers

from examples.blog.author.infrastructure.repositories.author_repository import (
    AuthorRepository,
)
from examples.blog.post.domain.services.post_service import PostService
from examples.blog.post.infrastructure.repositories.post_repository import (
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
