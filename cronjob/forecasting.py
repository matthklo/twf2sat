#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

from google.cloud import datastore

import httplib, urllib
import sys
import re
import time
import thuraya_sms

def fetch(target):
    urlpath = '/V7/forecast/entertainment/7Day/%s.htm' % target

    headers = { "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8"}
    conn = httplib.HTTPSConnection("www.cwb.gov.tw")
    conn.request("GET", urlpath, "", headers)
    response = conn.getresponse()
    if str(response.status) != '200':
        print(('Failed on fetching %s' % urlpath) + ' status code:' + str(response.status), file=sys.stderr)
        sys.exit(1)
    body = response.read()

    forecasts = [ [{}, {}], [{}, {}], [{}, {}], [{}, {}] ]

    row_entries = re.findall(r'<tr.+?</tr>', body, re.DOTALL)
    if len(row_entries) != 12:
        print('Unexpected content for %s' % urlpath + ' (number of row)', file=sys.stderr)
    
    """
        row_entries index:
         0: Weekdays
         1: Day/Night
         2: Weather Icons
         3: High Temp
         4: Low Temp
         5: Wind
         6: Wind dir
         7: Humidity
         8: High Body Temp
         9: Low Body Temp
        10: Rain prob.
        11: Ultraviolet light
    """

    entry_idx = 0
    for entry in re.finditer(r'<td colspan="2">.*</td>', row_entries[0]):
        #print(str(entry.group(0)).decode('utf-8').encode('big5'))
        weekday = re.sub(r'<.*?>', ' ', str(entry.group(0))).split()
        #print(str(e).decode('utf-8').encode('big5'))
        forecasts[entry_idx][0]['date'] = weekday[0]
        forecasts[entry_idx][0]['weekday'] = weekday[1].decode('utf-8')
        forecasts[entry_idx][1]['date'] = weekday[0]
        forecasts[entry_idx][1]['weekday'] = weekday[1].decode('utf-8')
        entry_idx += 1
        if entry_idx >= len(forecasts):
            break

    entry_idx = 0
    for entry in re.finditer(r'<td>(.*)</td>', row_entries[3]):
        idx = entry_idx//2
        forecasts[idx][entry_idx%2]['high_temp'] = entry.group(1)
        entry_idx += 1
        if entry_idx >= (len(forecasts) * 2):
            break
    
    entry_idx = 0
    for entry in re.finditer(r'<td>(.*)</td>', row_entries[4]):
        idx = entry_idx//2
        forecasts[idx][entry_idx%2]['low_temp'] = entry.group(1)
        entry_idx += 1
        if entry_idx >= (len(forecasts) * 2):
            break

    entry_idx = 0
    for entry in re.finditer(r'<td>(.*)%</td>', row_entries[10]):
        probtxt = 'n/a'
        if entry.groups() != None:
            probtxt = entry.group(1)
        idx = entry_idx//2
        forecasts[idx][entry_idx%2]['rain_prob'] = probtxt
        entry_idx += 1
        if entry_idx >= (len(forecasts) * 2):
            break

    return forecasts


if __name__ == '__main__':
    client = datastore.Client()

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
        if r['end'] < cur_epoch:
            keys_to_delete.append(r.key)
        else:
            forecasts = fetch(r['site'])

            msg = u'%s(%s) 溫:%s-%s 雨:%s%%, %s(%s) 溫:%s-%s 雨:%s%%, %s(%s) 溫:%s-%s 雨:%s%%' % (
                forecasts[0][0]['date'],
                forecasts[0][0]['weekday'][(len(forecasts[0][0]['weekday'])-1):],
                forecasts[0][0]['high_temp'],
                forecasts[0][0]['low_temp'],
                forecasts[0][0]['rain_prob'],
                forecasts[1][0]['date'],
                forecasts[1][0]['weekday'][(len(forecasts[1][0]['weekday'])-1):],
                forecasts[1][0]['high_temp'],
                forecasts[1][0]['low_temp'],
                forecasts[1][0]['rain_prob'],
                forecasts[2][0]['date'],
                forecasts[2][0]['weekday'][(len(forecasts[2][0]['weekday'])-1):],
                forecasts[2][0]['high_temp'],
                forecasts[2][0]['low_temp'],
                forecasts[2][0]['rain_prob'])

            thuraya_sms.send(r['tel'], u'機器人阿邦', msg)
            
            cnt+=1

    print('send out %d messages. delete %d records. ' % (cnt, len(keys_to_delete)))

    client.delete_multi(keys_to_delete)
