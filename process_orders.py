"""Updates statistics and process achievements script"""
import os, sys, getopt
from sqlalchemy import asc

from web import db, app
from services import AdminNotificationService, OrderService, OrderNotificationService, StockService
from models import Order


app.app_context().push()

ROOT = os.path.dirname(__file__)

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
    except Exception as exc:
        AdminNotificationService.notify(str(exc))
        raise exc

if __name__ == "__main__":
    main(sys.argv[1:])
