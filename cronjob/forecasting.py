#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

from google.cloud import datastore
from google.cloud import logging

import httplib, urllib
import subprocess
import sys
import re
import time
import tempfile
import thuraya_sms

def fetch(target):
    urlpath = 'https://www.cwb.gov.tw/V8/C/L/Mountain/Mountain.html?QS=&PID=%s' % target

    with tempfile.TemporaryFile() as tmpout, tempfile.TemporaryFile() as tmpf:
        # On Ubuntu, install chromium-browser with command: 'apt install chromium-browser'
        chromium_path = '/usr/bin/chromium-browser'

        # Generate full web content with the help of headless Chromium browser
        subprocess.check_call([chromium_path, '--no-sandbox', '--no-default-browser-check', '--no-first-run',
            '--disable-default-apps', '--disable-popup-blocking', '--disable-translate',
            '--disable-background-timer-throttling', '--headless', '--disable-gpu', '--dump-dom',
            urlpath], stdout=tmpout)
        tmpout.seek(0)

        # Trim all lines except those within 'Mobile 3hr'
        copy = False
        for line in tmpout:
            if 'Mobile 3hr' in line:
                copy = not copy
            if copy == True:
                tmpf.write(line)
        tmpf.seek(0)

        # Note: the '?' after the '+' make it matches in non-greedy mode.
        row_entries = re.findall(r'panel-title.+?</h4>', tmpf.read(), re.DOTALL)

    forecasts_3hr = []
    for raw_entry in row_entries:
        fc = {}
        m1 = re.search(r'([0-9]{2}/[0-9]{2})\(([^)]+)\)([0-9]{2}:[0-9]{2})', raw_entry)
        fc['date'] = m1.group(1)
        fc['weekday'] = m1.group(2).decode('utf-8')
        fc['time'] = m1.group(3)

        m2 = re.search(r'tem-C is-active">([^<]+)<', raw_entry)
        fc['temp'] = m2.group(1)

        m3 = re.search(r'icon-umbrella" aria-hidden="true"></i><span>([^<]+)</span>', raw_entry)
        fc['rain_prob'] = m3.group(1) # Note: it includes '%'

        forecasts_3hr.append(fc)
        #print(str(fc))

    # Summary of 3hr forecast to be per day.
    # For tempratures: Record 'high_temp' and 'low_temp' from 3hr forecasts.
    # For rain probability: Record the maximum one from 3hr forecasts.
    forecasts = []
    dfc = None
    for fc in forecasts_3hr:
        if (dfc == None) or (dfc['date'] != fc['date']):
            if dfc != None:
                #print(str(dfc))
                forecasts.append(dfc)
            dfc = {}
            dfc['date'] = fc['date']
            dfc['weekday'] = fc['weekday']
            dfc['high_temp'] = fc['temp']
            dfc['low_temp'] = fc['temp']
            dfc['rain_prob'] = fc['rain_prob']
        else:
            #Update 'high_temp', 'low_temp', and 'rain_prob'
            if int(dfc['high_temp']) < int(fc['temp']):
                dfc['high_temp'] = fc['temp']
            if int(dfc['low_temp']) > int(fc['temp']):
                dfc['low_temp'] = fc['temp']
            if int(dfc['rain_prob'].strip('%')) < int(fc['rain_prob'].strip('%')):
                dfc['rain_prob'] = fc['rain_prob']
    if dfc != None:
        #print(str(dfc))
        forecasts.append(dfc)

    return forecasts

if __name__ == '__main__':
    client = datastore.Client()

    logging_client = logging.Client()
    log_name = 'climbsafe-cronjob'
    logger = logging_client.logger(log_name)

    cur_epoch = int(time.time())
    # Fetch all records which has a 'start' in the past.
    q = client.query(kind='ForwardingRecord')
    q.add_filter('start', '<=', cur_epoch)
    results = q.fetch()

    cnt = 0
    keys_to_delete = []
    # Iterate through results, collect the keys of record which
    # has a 'end' also in the past (expired) in keys_to_delete.
    # For others, perform weather forwarding.
    for r in results:
        if r['end'] + 86400 < cur_epoch:
            errmsg = 'Expiring rule for tel:' + str(r['tel']) + ', end:' + str(r['end']) + ', cur:' + str(cur_epoch)
            logger.log_text(errmsg, severity='INFO')
            keys_to_delete.append(r.key)
        else:
            forecasts = fetch(r['site'])

            sitename = ''
            if ('sitename' in r) and (r['sitename'] != None) and (len(r['sitename']) > 0):
                sitename = r['sitename']

            msg = u'%s %s(%s) 溫:%s~%s 雨:%s, %s(%s) 溫:%s~%s 雨:%s' % (
                sitename,
                forecasts[1]['date'],
                forecasts[1]['weekday'],
                forecasts[1]['high_temp'],
                forecasts[1]['low_temp'],
                forecasts[1]['rain_prob'],
                forecasts[2]['date'],
                forecasts[2]['weekday'],
                forecasts[2]['high_temp'],
                forecasts[2]['low_temp'],
                forecasts[2]['rain_prob'])

            errmsg = 'Forward msg to tel:' + str(r['tel']) + ', text:"' + msg + '"'
            logger.log_text(errmsg, severity="DEBUG")

            thuraya_sms.send(r['tel'], u'機器人阿邦', msg, logger)

            cnt+=1

    errmsg = 'send out %d messages. delete %d records. ' % (cnt, len(keys_to_delete))
    logger.log_text(errmsg, severity='INFO')
    print(errmsg)

    client.delete_multi(keys_to_delete)

