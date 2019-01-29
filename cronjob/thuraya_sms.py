#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import httplib, urllib
from google.cloud import logging


def send(number, sender, message, logger=None):
    if (type(number) != str) and (type(number) != unicode):
        raise TypeError
    elif type(sender) != unicode:
        raise TypeError
    elif type(message) != unicode:
        raise TypeError

    if None != logger:
        if str(number) == '00000000':
            logger.log_text('Skip thuraya web api call due to debug number.', severity='DEBUG')
            return

    tlength = 160 - len(sender) - len(message) + 1
    params = urllib.urlencode({'msisdn':number.encode('utf-8'), 'from': sender.encode('utf-8'), 'message': message.encode('utf-8'), 'tlength': str(tlength)})
    #print(str(params))

    headers = {"Content-type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8"}
    conn = httplib.HTTPSConnection("sms.thuraya.com")
    conn.request("POST", "/sms.php", params, headers)
    response = conn.getresponse()

    errmsg = 'Response: status= ' + str(response.status) + ', reason= ' + str(response.reason)
    if None != logger:
        logger.log_text('Thuraya WEB API ' + errmsg, severity='DEBUG')
    print (errmsg)
    print (str(response.getheaders()))
    
    data = response.read()
    print(str(data))
    conn.close()


if __name__ == '__main__':
    send('69461796',u'Lo中文',u'test 空格 中文')
