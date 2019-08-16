"""Updates statistics and process achievements script"""
import os, sys, getopt
import json
import logging
from logging.handlers import RotatingFileHandler
import datetime as DT

import bb2
from web import db, app
from services import SheetService, StockService

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
    
    leagues = [
        "REBBL - REL",
        "REBBL - Big O",
        "REBBL - GMan",
        #"ReBBL Playoffs",
        "GMAN Rampup",
        "REL RAMPUP",
    ]
    season = "season 12"
    rounds = [
        1#,2
    ]
    STATS_FILE = "matches.json"
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
        raise exc

    logger.info("Matches colleted")
    # filter out unplayed
    matches = [match for match in matches if match['match_uuid']]
    #sort by match uuid
    matches = sorted(matches, key=lambda x: x['match_uuid'])

    #strip tema names
    for match in matches:
        match['homeTeamName'] = match['homeTeamName'].strip()
        match['awayTeamName'] = match['awayTeamName'].strip()

    #insert header
    matches.insert(0, header)
    # turn dict to list
    matches = [list(match.values()) for match in matches]

    SheetService.update_matches(matches)
    logger.info("Matches exported to sheet")

    try:
        file = open(STATS_FILE, "w")
        file.write(json.dumps(matches))
        file.close()
    except Exception as exp:
        logger.error(exp)
        raise exp
    logger.info("Matches stored to file")

    StockService.update()
    logger.info("DB update")

if __name__ == "__main__":
    main(sys.argv[1:])
