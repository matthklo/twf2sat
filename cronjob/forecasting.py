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
    
    forecasts = []
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
            if 'id="TableId3hr"' in line:
                copy = not copy
            if copy == True:
                tmpf.write(line)
        tmpf.seek(0)

        raw_content = tmpf.read()

        dfc1 = {}
        mo = re.search(r'<th id="PC3_D2"[^>]+>([^<]+)<br>([^<]+)</th>', raw_content)
        dfc1['date'] = mo.group(1)
        dfc1['weekday'] = mo.group(2).decode('utf-8')

        mo = re.search(r'<td headers="PC3_T PC3_D2 PC3_D2H12">[^>]+>([^<]+)<', raw_content)
        dfc1['high_temp'] = mo.group(1)

        mo = re.search(r'<td headers="PC3_T PC3_D2 PC3_D2H06">[^>]+>([^<]+)<', raw_content)
        dfc1['low_temp'] = mo.group(1)

        mo = re.search(r'<td colspan="2" headers="PC3_Po PC3_D2 PC3_D2H12[^>]+>([0-9,-]+)', raw_content)
        dfc1['rain_prob'] = mo.group(1)

        #print(str(dfc1))
        forecasts.append(dfc1)

        dfc2 = {}
        mo = re.search(r'<th id="PC3_D3"[^>]+>([^<]+)<br>([^<]+)</th>', raw_content)
        dfc2['date'] = mo.group(1)
        dfc2['weekday'] = mo.group(2).decode('utf-8')

        mo = re.search(r'<td headers="PC3_T PC3_D3 PC3_D3H12">[^>]+>([^<]+)<', raw_content)
        dfc2['high_temp'] = mo.group(1)

        mo = re.search(r'<td headers="PC3_T PC3_D3 PC3_D3H06">[^>]+>([^<]+)<', raw_content)
        dfc2['low_temp'] = mo.group(1)

        mo = re.search(r'<td colspan="2" headers="PC3_Po PC3_D3 PC3_D3H12[^>]+>([0-9,-]+)', raw_content)
        dfc2['rain_prob'] = mo.group(1)

        #print(str(dfc2))
        forecasts.append(dfc2)


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
                forecasts[0]['date'],
                forecasts[0]['weekday'],
                forecasts[0]['high_temp'],
                forecasts[0]['low_temp'],
                forecasts[0]['rain_prob'],
                forecasts[1]['date'],
                forecasts[1]['weekday'],
                forecasts[1]['high_temp'],
                forecasts[1]['low_temp'],
                forecasts[1]['rain_prob'])

            errmsg = 'Forward msg to tel:' + str(r['tel']) + ', text:"' + msg + '"'

            logger.log_text(errmsg, severity="DEBUG")

            thuraya_sms.send(r['tel'], u'機器人阿邦', msg, logger)

            cnt+=1

    errmsg = 'send out %d messages. delete %d records. ' % (cnt, len(keys_to_delete))
    logger.log_text(errmsg, severity='INFO')
    print(errmsg)

    client.delete_multi(keys_to_delete)

