"""Updates statistics and process achievements script"""
import os, sys, getopt
from sqlalchemy import asc

from web import db, app
from services import AdminNotificationService, OrderService, OrderNotificationService, StockService, UserService
from models import Order, User


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

        AdminNotificationService.notify("Recording gains...")
        for user in User.query.all():
            user.account().make_snapshot(app.config['ROUNDS_EXPORT'][-1])
        db.session.commit()
        AdminNotificationService.notify("Done")

        AdminNotificationService.notify("Awarding points...")
        sorted_users = UserService.week_gain(app.config['ROUNDS_EXPORT'][-1], 25)
        for i, user in enumerate(sorted_users):
            j = i +1
            user[1].award_points(POINTS[j], f"Top {j} gain in week {app.config['ROUNDS_EXPORT'][-1]}")
            OrderNotificationService.notify(f"{user[1].mention()}: Awarded {POINTS[j]} points for top {j} gain ({round(user[0],2)}) in week {app.config['ROUNDS_EXPORT'][-1]}")
        db.session.commit()
        AdminNotificationService.notify("Done")

    except Exception as exc:
        AdminNotificationService.notify(str(exc))
        raise exc

if __name__ == "__main__":
    main(sys.argv[1:])
