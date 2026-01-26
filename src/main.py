from fastapi import FastAPI
from api.characters import character_router

app = FastAPI()
app.include_router(character_router)


@app.get("/health")
def hello():
    return "App is up and healthy"
