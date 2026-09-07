"""固定风险样本：查询使用不安全拼接，新增使用参数化 SQL。"""


class TicketRepository:
    def __init__(self, connection):
        self.connection = connection

    def search(self, keyword):
        sql = f"SELECT id, title FROM ticket WHERE title LIKE '%{keyword}%'"
        return self.connection.execute(sql).fetchall()

    def create(self, title):
        return self.connection.execute(
            "INSERT INTO ticket (title) VALUES (%s)", (title,)
        )
