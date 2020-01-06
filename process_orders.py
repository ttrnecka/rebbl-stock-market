"""Updates statistics and process achievements script"""
import os, sys, getopt
from sqlalchemy import asc

from web import db, app
from services import AdminNotificationService, OrderService, OrderNotificationService, StockService, UserService
from models import Order, User
from misc.helpers import current_round


app.app_context().push()

ROOT = os.path.dirname(__file__)

POINTS = {
    1: 15,
    2: 12,
    3: 10,
    4: 9,
    5: 8,
    6: 7,
    7: 6,
    8: 5,
    9: 4,
    10: 3,
    11: 2,
    12: 2,
    13: 2,
    14: 2,
    15: 2,
    16: 1,
    17: 1,
    18: 1,
    19: 1,
    20: 1,
    21: 1,
    22: 1,
    23: 1,
    24: 1,
    25: 1,
}
# run the application
def main(argv):
    """main()"""
    try:
        opts, args = getopt.getopt(argv,"h")
    except getopt.GetoptError:
        print('process_orders.py -h')
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print("Process all queued orders")
            sys.exit(0)
        
    try:
        def chunk_orders(orders):
            group_count = 10
            order_chunks = [orders[i:i+group_count] for i in range(0, len(orders), group_count)]
            for chunk in order_chunks:
                msg = []
                for order in chunk:
                    order = OrderService.process(order)
                    msg.append(f"{order.user.mention()}: {order.result}")

                OrderNotificationService.notify("\n".join(msg))
            
        AdminNotificationService.notify("Updating DB ...")
        StockService.update()
        AdminNotificationService.notify("Done")
        AdminNotificationService.notify("Closing market ...")
        OrderService.close()
        AdminNotificationService.notify("Done")

        AdminNotificationService.notify("Processing SELL orders...")
        orders = Order.query.order_by(asc(Order.date_created)).filter(Order.processed == False, Order.operation == "sell").all()
        chunk_orders(orders)
        AdminNotificationService.notify("Done")

        AdminNotificationService.notify("Processing BUY orders...")
        orders = Order.query.order_by(asc(Order.date_created)).filter(Order.processed == False, Order.operation == "buy").all()
        chunk_orders(orders)
        AdminNotificationService.notify("Done")
        
        AdminNotificationService.notify("Opening market...")
        OrderService.open()
        AdminNotificationService.notify("Done")

        # points and gains only after allowed
        if app.config['ALLOW_TRACKING']:
            AdminNotificationService.notify("Recording gains...")
            for user in User.query.all():
                user.account().make_snapshot(current_round())
            db.session.commit()
            AdminNotificationService.notify("Done")

            AdminNotificationService.notify("Recording positions...")
            sorted_users = UserService.week_gain(current_round(), User.query.count())
            for i, (position, value, user) in enumerate(sorted_users):
                user.record_position(position)
            db.session.commit()
            AdminNotificationService.notify("Done")
            
            AdminNotificationService.notify("Awarding points...")
            for i, (position, value, user) in enumerate(sorted_users):
                if position > 25:
                    break
                user.award_points(POINTS[position], f"Top {position} gain in week {current_round()}")
                OrderNotificationService.notify(f"{user.mention()}: Awarded {POINTS[position]} points for top {position} gain ({round(value,2)}) in week {current_round()}")
            db.session.commit()
            AdminNotificationService.notify("Done")
        else:
            AdminNotificationService.notify("Point awards skipped")

    except Exception as exc:
        AdminNotificationService.notify(str(exc))
        raise exc

if __name__ == "__main__":
    main(sys.argv[1:])
