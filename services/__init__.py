"""__init__"""
from sqlalchemy import event
from sqlalchemy.orm.attributes import flag_modified

from models.base_model import db
from models.data_models import Stock

from .sheet_service import SheetService
from .stock_service import StockService
from .user_service import UserService
from .order_service import OrderService, OrderError
from .notification_service import AdminNotificationService, StockNotificationService
from .web_hook_service import WebHook
from .match_service import MatchService
from .plotting import balance_graph


@event.listens_for(db.session,'before_flush')
#@event.listens_for(Share,'before_update')
def update_balance_history(session, flush_context, isinstances):
#    """If stock price changes, update balance history of all users owning it"""
    for instance in session.dirty:
        if not isinstance(instance, Stock):
            continue
        state = db.inspect(instance)

        if isinstance(instance, Stock):
            history = state.attrs.unit_price.load_history()

        # update all balances for the users owning this Stock
        if history.has_changes():
            if isinstance(instance, Stock) and "Index" not in instance.name:
                msg = f"Stock {instance.code} - {instance.name} changed by {round(instance.unit_price_change,2)} to {round(instance.unit_price,2)}"
                StockNotificationService.notify(msg)
                for share in instance.shares:
                    share.user.new_balance_history()
