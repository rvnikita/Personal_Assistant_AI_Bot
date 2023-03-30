import src.tglogging as logging

from sqlalchemy import Column, String, DateTime, BigInteger, Integer, create_engine, Boolean
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Session
import datetime
import os
import configparser

config = configparser.ConfigParser(os.environ)
config_path = os.path.dirname(__file__) + '/../config/' #we need this trick to get path to config folder
config.read(config_path + 'settings.ini')

logger = logging.get_logger()

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = 'users'

    id = Column(BigInteger, primary_key=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    username = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    status = Column(String)
    last_message_datetime = Column(DateTime)
    requests_counter = Column(Integer, default=0)
    blacklisted = Column(Boolean, default=0)

#connect to postgresql
engine = create_engine(f"postgresql://{config['DB']['USER']}:{config['DB']['PASSWORD']}@{config['DB']['HOST']}:{config['DB']['PORT']}/{config['DB']['NAME']}")

session = Session(engine)