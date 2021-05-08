import sqlalchemy
from sqlalchemy import orm
from .db_session import SqlAlchemyBase


class Registration(SqlAlchemyBase):
    __tablename__ = 'registrations'

    id = sqlalchemy.Column(sqlalchemy.Integer,
                           primary_key=True, autoincrement=True)
    user_id = sqlalchemy.Column(sqlalchemy.String, sqlalchemy.ForeignKey("users.id"), nullable=True)
    event_id = sqlalchemy.Column(sqlalchemy.String, sqlalchemy.ForeignKey("events.id"), nullable=True)
    user = orm.relation('User')
    event = orm.relation('Event')