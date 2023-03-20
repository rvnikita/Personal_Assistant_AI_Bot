import src.tglogging as logging

from sqlalchemy import Column, String, DateTime, Integer, create_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Session
import datetime
import os
import configparser

config = configparser.SafeConfigParser(os.environ)
config_path = os.path.dirname(__file__) + '/../config/' #we need this trick to get path to config folder
config.read(config_path + 'settings.ini')

logger = logging.get_logger()
logger.info('Starting ' + __file__ + ' in ' + config['BOT']['MODE'] + ' mode at ' + str(os.uname()))

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    username = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    status = Column(String)
    last_message_datetime = Column(DateTime)

#connect to postgresql
engine = create_engine(f"postgresql://{config['DB']['USER']}:{config['DB']['PASSWORD']}@{config['DB']['HOST']}:{config['DB']['PORT']}/{config['DB']['NAME']}")

session = Session(engine)