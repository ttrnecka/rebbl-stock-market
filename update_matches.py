"""Updates statistics and process achievements script"""
import os, sys, getopt
import json
import logging
from logging.handlers import RotatingFileHandler
import datetime as DT

import bb2
from web import db, app
from services import SheetService, StockService, AdminNotificationService, MatchService

app.app_context().push()

ROOT = os.path.dirname(__file__)

# run the application
def main(argv):
    """main()"""
    try:
        opts, args = getopt.getopt(argv,"h")
    except getopt.GetoptError:
        print('update_matches.py -h')
        sys.exit(2)
    refresh = False
    for opt, arg in opts:
        if opt == '-h':
            refresh = True
            print("Download all matches for rounds")
            sys.exit(0)
        
    logger = logging.getLogger('collector')
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(
        os.path.join(ROOT, 'logs/collector.log'),
        maxBytes=10000000, backupCount=5,
        encoding='utf-8', mode='a')
    handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
    logger.addHandler(handler)

    agent = bb2.REBBL_API()
    
    
    leagues = app.config['LEAGUES']
    season = app.config['SEASON']
    rounds = app.config['ROUNDS_COLLECT']
    rounds_export = app.config['ROUNDS_EXPORT']

    leagues_po = app.config['LEAGUES_PO']
    rounds_po = app.config['ROUNDS_COLLECT_PO']
    
    matches = []
    try:
        for league in leagues:
            for round in rounds:
                data = agent.slim_round(league,season,round)
                matches.extend(data)

        for league in leagues_po:
            for round in rounds_po:
                data = agent.slim_round(league,season,round)
                for match in data:
                    match["round"]+=13
                matches.extend(data)
    except Exception as exc:
        logger.error(exc)
        AdminNotificationService.notify(str(exc))
        raise exc

    logger.info("Matches colleted")
    MatchService.import_matches(matches)
    logger.info("Matches stored")
    # filter out unplayed and not in export rounds
    matches_to_export = MatchService.played()
    matches_to_export = [match for match in matches_to_export if match.round in rounds_export]
    #sort by match uuid and in round
    matches_to_export = sorted(matches_to_export, key=lambda x: x.match_uuid)

    try:
        SheetService.update_matches(matches_to_export)
    except Exception as exc:
        logger.error(exc)
        AdminNotificationService.notify(str(exc))
        raise exc

    logger.info("Matches exported to sheet")

    try:
        StockService.update()
    except Exception as exc:
        logger.error(exc)
        AdminNotificationService.notify(str(exc))
        raise exc

    logger.info("DB updated")
    AdminNotificationService.notify("Match data has been refreshed successfully")
if __name__ == "__main__":
    main(sys.argv[1:])
