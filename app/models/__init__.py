from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from models.user import User
from models.todo import Todo
from models.api_token import ApiToken
from models.sync_job import SyncJob
