import json
import inspect
from random import shuffle
from typing import Callable
from fastapi.responses import JSONResponse
from core.logger.logger import logger


async def default_response(callable_function: Callable, params: list = [], is_creation: bool = False, dict_response: bool = False):
    try:
        if is_async_callable(callable_function):
            result = await callable_function(*params)
        else:
            result = callable_function(*params)
        if not result["status"]:
            if not dict_response:
                return JSONResponse(status_code=400, content={"detail": result["message"]})
            return {"status": False, "message": result["message"]}

        status_code = 200 if not is_creation else 201
        if not dict_response:
            return JSONResponse(status_code=status_code, content={"message": result["message"], "data": result["data"]})
        return {"status": True, "message": result["message"], "data": result["data"]}
    except Exception as e:
        logger.exception(e)
        if not dict_response:
            return JSONResponse(status_code=500, content={"detail": "Erro interno com o servidor."})
        return {"status": False, "message": "Erro interno com o servidor."}


def update_default_dict(data: dict, json_targets: list[str] = [], decimal_targets: list[str] = [], date_targets: list[str] = []):
    new_data = {**data}

    if "createdAt" in new_data.keys():
        new_data["createdAt"] = str(new_data["createdAt"]) if new_data["createdAt"] is not None else None

    if "updatedAt" in new_data.keys():
        new_data["updatedAt"] = str(new_data["updatedAt"]) if new_data["updatedAt"] is not None else None

    if "lastLoginAt" in new_data.keys():
        new_data["lastLoginAt"] = str(new_data["lastLoginAt"]) if new_data["lastLoginAt"] is not None else None

    for json_target in json_targets:
        new_data[json_target] = json.loads(new_data[json_target])

    for decimal_target in decimal_targets:
        new_data[decimal_target] = float(new_data[decimal_target])

    for data_target in date_targets:
        new_data[data_target] = str(new_data[data_target])

    return new_data


def is_async_callable(fn: Callable) -> bool:
    return inspect.iscoroutinefunction(fn)


def generate_temp_code():
    numbers = list(map(str, range(10)))
    shuffle(numbers)

    base_password = numbers[:6]
    shuffle(base_password)
    return "".join(base_password)