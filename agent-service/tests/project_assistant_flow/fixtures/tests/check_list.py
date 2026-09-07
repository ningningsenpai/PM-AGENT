"""当前样本仅覆盖列表查询。"""


def check_list(client):
    response = client.get("/tickets")
    assert response.status_code == 200
