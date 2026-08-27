from sqlalchemy import inspect

from app import create_app
from app.extensions import db


app = create_app()


with app.app_context():
    db.create_all()
    tabelas = inspect(db.engine).get_table_names()
    print("Banco verificado com sucesso.")
    print("Tabelas encontradas:", ", ".join(sorted(tabelas)))
