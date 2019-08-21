"""web process"""
import os
import json
from datetime import timedelta

from flask import Flask
from flask_migrate import Migrate
from sqlalchemy.orm import raiseload

from models.base_model import db
from services import AdminNotificationService, WebHook, StockNotificationService

os.environ["YOURAPPLICATION_SETTINGS"] = "config/config.py"
ROOT = os.path.dirname(__file__)

def create_app():
    """return initialized flask app"""
    fapp = Flask(__name__)
    fapp.config["DEBUG"] = True
    fapp.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    fapp.config.from_envvar('YOURAPPLICATION_SETTINGS')
    db.init_app(fapp)
    
    AdminNotificationService.register_notifier(
        WebHook(fapp.config['DISCORD_WEBHOOK_ADMIN']).send
    )
    StockNotificationService.register_notifier(
        WebHook(fapp.config['DISCORD_WEBHOOK_STOCK']).send
    )

    return fapp

app = create_app()
migrate = Migrate(app, db)

if __name__ == "__main__":
    app.run()
