"""Updates statistics and process achievements script"""
import os, sys, getopt
import json
import logging
from logging.handlers import RotatingFileHandler
import datetime as DT

import bb2
from web import db, app
from services import SheetService, StockService, AdminNotificationService

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

    STATS_FILE = app.config['MATCH_FILE']
    
    header = {
        "division":"division",
        "round":"round",
        "match_uuid":"match_uuid",
        "homeCoachId":"homeCoachId",
        "homeCoachName":"homeCoachName",
        "homeTeamId":"homeTeamId",
        "homeTeamName":"homeTeamName",
        "homeTeamRace":"homeTeamRace",
        "homeScore":"homeScore",
        "awayCoachId":"awayCoachId",
        "awayCoachName":"awayCoachName",
        "awayTeamId":"awayTeamId",
        "awayTeamName":"awayTeamName",
        "awayTeamRace":"awayTeamRace",
        "awayScore":"awayScore"
    }
    matches = []
    try:
        for league in leagues:
            for round in rounds:
                data = agent.slim_round(league,season,round)
                matches.extend(data)
    except Exception as exc:
        logger.error(exc)
        AdminNotificationService.notify(str(exc))
        raise exc

    logger.info("Matches colleted")
    # filter out unplayed and not in export rounds
    matches_to_export = [match for match in matches if match['match_uuid'] and match['round'] in rounds_export]
    #sort by match uuid
    matches_to_export = sorted(matches_to_export, key=lambda x: x['match_uuid'])

    #strip team names
    for match in matches_to_export:
        match['homeTeamName'] = match['homeTeamName'].strip()
        match['awayTeamName'] = match['awayTeamName'].strip()

    #insert header
    matches_to_export.insert(0, header)
    # turn dict to list
    matches_to_export = [list(match.values()) for match in matches_to_export]

    try:
        SheetService.update_matches(matches_to_export)
    except Exception as exc:
        logger.error(exc)
        AdminNotificationService.notify(str(exc))
        raise exc

    logger.info("Matches exported to sheet")

    try:
        file = open(STATS_FILE, "w")
        file.write(json.dumps(matches))
        file.close()
    except Exception as exp:
        logger.error(exp)
        raise exp
    logger.info("Matches stored to file")

    try:
        StockService.update()
    except Exception as exc:
        logger.error(exc)
        AdminNotificationService.notify(str(exc))
        raise exc

    logger.info("DB update")
    AdminNotificationService.notify("Match data has been refreshed successfully")
if __name__ == "__main__":
    main(sys.argv[1:])
