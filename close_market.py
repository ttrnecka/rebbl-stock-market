"""Updates statistics and process achievements script"""
import os, sys, getopt
from web import app
from services import AdminNotificationService, OrderService


ROOT = os.path.dirname(__file__)

# run the application
def main(argv):
    """main()"""
    try:
        opts, args = getopt.getopt(argv,"h")
    except getopt.GetoptError:
        print('close_market.py -h')
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print("Close the market")
            sys.exit(0)
        
    try:
        OrderService.close()
    except Exception as exc:
        AdminNotificationService.notify(str(exc))
        raise exc

    AdminNotificationService.notify("Market closed!")
if __name__ == "__main__":
    main(sys.argv[1:])
