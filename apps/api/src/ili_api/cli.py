import uvicorn


def run() -> None:
    uvicorn.run("ili_api.main:app", host="127.0.0.1", port=8000, reload=False)
