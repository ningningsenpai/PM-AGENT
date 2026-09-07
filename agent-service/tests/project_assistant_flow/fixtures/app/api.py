"""工单接口样本，目前仅实现新增与查询。"""
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()
repository = None


class TicketInput(BaseModel):
    title: str


@app.get("/tickets")
def list_tickets(keyword: str = ""):
    return repository.search(keyword)


@app.post("/tickets")
def create_ticket(body: TicketInput):
    return repository.create(body.title)
