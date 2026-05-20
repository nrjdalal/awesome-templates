from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query

from examples.todo.domain.services.todo_service import TodoService
from examples.todo.infrastructure.di.todo_container import TodoContainer
from examples.todo.interface.server.schemas.todo_schema import (
    CreateTodoRequest,
    TodoResponse,
    UpdateTodoRequest,
)
from src._core.application.dtos.base_response import SuccessResponse

router = APIRouter()


@router.post(
    "/todo",
    summary="Create todo",
    response_model=SuccessResponse[TodoResponse],
    response_model_exclude={"pagination"},
)
@inject
async def create_todo(
    item: CreateTodoRequest,
    todo_service: TodoService = Depends(Provide[TodoContainer.todo_service]),
) -> SuccessResponse[TodoResponse]:
    data = await todo_service.create_data(entity=item)
    return SuccessResponse(data=TodoResponse(**data.model_dump()))


@router.get(
    "/todos",
    summary="List todos",
    response_model=SuccessResponse[list[TodoResponse]],
)
@inject
async def list_todos(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, alias="pageSize", ge=1, le=100),
    todo_service: TodoService = Depends(Provide[TodoContainer.todo_service]),
) -> SuccessResponse[list[TodoResponse]]:
    datas, pagination = await todo_service.get_datas(page=page, page_size=page_size)
    return SuccessResponse(
        data=[TodoResponse(**d.model_dump()) for d in datas],
        pagination=pagination,
    )


@router.get(
    "/todo/{todo_id}",
    summary="Get todo",
    response_model=SuccessResponse[TodoResponse],
    response_model_exclude={"pagination"},
)
@inject
async def get_todo(
    todo_id: int,
    todo_service: TodoService = Depends(Provide[TodoContainer.todo_service]),
) -> SuccessResponse[TodoResponse]:
    data = await todo_service.get_data_by_data_id(data_id=todo_id)
    return SuccessResponse(data=TodoResponse(**data.model_dump()))


@router.put(
    "/todo/{todo_id}",
    summary="Update todo",
    response_model=SuccessResponse[TodoResponse],
    response_model_exclude={"pagination"},
)
@inject
async def update_todo(
    todo_id: int,
    item: UpdateTodoRequest,
    todo_service: TodoService = Depends(Provide[TodoContainer.todo_service]),
) -> SuccessResponse[TodoResponse]:
    data = await todo_service.update_data_by_data_id(data_id=todo_id, entity=item)
    return SuccessResponse(data=TodoResponse(**data.model_dump()))


@router.delete(
    "/todo/{todo_id}",
    summary="Delete todo",
    response_model=SuccessResponse,
    response_model_exclude={"data", "pagination"},
)
@inject
async def delete_todo(
    todo_id: int,
    todo_service: TodoService = Depends(Provide[TodoContainer.todo_service]),
) -> SuccessResponse:
    success = await todo_service.delete_data_by_data_id(data_id=todo_id)
    return SuccessResponse(success=success)
