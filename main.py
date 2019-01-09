import webapp2
import logging
import json
import time

from google.appengine.ext import ndb

def has_string_member(o, f):
    try:
        if f not in o:
            return False
        if False == isinstance(o[f], basestring):
            return False
        return True
    except:
        pass
    return False

def has_numeric_member(o, f):
    if False == has_string_member(o, f):
        return False
    try:
        v = int(o[f])
        return o[f] == str(v)
    except:
        pass
    return False

class ForwardingRecord(ndb.Model):
    tel = ndb.StringProperty()
    start = ndb.StringProperty()
    end = ndb.StringProperty()
    site = ndb.StringProperty()
    identify = ndb.StringProperty(indexed=False)

class MainPage(webapp2.RequestHandler):
    def post(self):
        self.response.headers['Content-Type'] = 'application/json'

        if 'tel' in self.request.POST:
            self.handle_register()
        elif 'cancel' in self.request.POST:
            self.handle_cancel()
        else:
            self.handle_query()
    
    def handle_register(self):
        post_data = self.request.POST
        err_msg = None

        # Ex: UnicodeMultiDict([(u'tel', u'12123123'), (u'site', u'D047'), (u'start', u'1546963200'), (u'end', u'1546963200')])
        logging.info('register: ' + str(self.request.POST))

        # 1. Data validation: 'tel' is 8-digits number. 'site' should be in the form of 'Dnnn'. 
        #                     'start' should be epoch seconds greater than now but no greater than 31 days.
        #                     'end' should be epoch seconds greater or equal to 'start' and the different between them should
        #                     be less than 31 days. Return error if any of the above assumption fails to hold.
        if (False == has_numeric_member(post_data, 'tel')) or (len(post_data['tel']) != 8):
            err_msg = 'Missing or incorrect \\"tel\\" data.'
        if (False == has_string_member(post_data, 'site')) or (post_data['site'][0] != 'D') or (False == post_data['site'][1:].isdigit()):
            err_msg = 'Missing or incorrect \\"site\\" data.'
        if (False == has_numeric_member(post_data, 'start')) or (False == has_numeric_member(post_data, 'end')):
            err_msg = 'Missing either \\"start\\" or \\"end\\" data.'
        if err_msg == None:
            cur_epoch = int(time.time())
            start_epoch = int(post_data['start'])
            end_epoch = int(post_data['end'])
            if start_epoch < cur_epoch:
                err_msg = '\\"start\\" is in the past.'
            elif start_epoch > (cur_epoch + 31*86400):
                err_msg = '\\"start\\" should be within a month from now.'
            elif end_epoch < start_epoch:
                err_msg = '\\"end\\" is before \\"start\\".'
            elif (end_epoch - start_epoch) > (31*86400):
                err_msg = '\\"end\\" should be within a month from \\"start\\".'
        
        if err_msg != None:
            self.response.status = 400
            self.response.write('{"error":"%s"}' % err_msg)
            return
         
        # 2. Check how many on-going forecasting rules matched with the given tel. Return error if there is too many.
        ongoing_records = ForwardingRecord.query(ForwardingRecord.tel == post_data['tel']).fetch(3)
        if len(ongoing_records) >= 3:
            self.response.status = 400
            self.response.write('{"error":"Too many on-going forwarding records for a tel number. (max: 3)"}')
            return

        # 3. Write to DB and return success.
        new_record = ForwardingRecord(tel=post_data['tel'], start=post_data['start'], end=post_data['end'], site=post_data['site'], identify="")
        k = new_record.put()
        logging.info('key for new_record: ' + str(k))
        self.response.status = 200
        self.response.write('{}')

    def handle_cancel(self):
        post_data = self.request.POST
        err_msg = None

        logging.info('cancel: ' + str(self.request.POST))

        if False == has_string_member(post_data, 'cancel'):
            err_msg = 'Missing \\"cancel\\" data.'

        key_to_delete = None
        if err_msg == None:
            try:
                key_to_delete = ndb.Key(urlsafe=post_data['cancel'])
            except:
                err_msg = 'Invalid \\"cancel\\" data.'
        
        if err_msg != None:
            self.response.status = 400
            self.response.write('{"error":"%s"}' % err_msg)
            return
        
        # no-op if the key does not exist
        key_to_delete.delete()

        self.response.status = 200
        self.response.write('{}')
    
    def handle_query(self):
        post_data = self.request.POST
        err_msg = None

        logging.info('query: ' + str(self.request.POST))
        
        if False == has_numeric_member(post_data, 'query_tel'):
            cnt = len(ForwardingRecord.query().fetch(keys_only=True))
            self.response.status = 200
            self.response.write('{"count":%d}' % cnt)
            return

        elif len(post_data['query_tel']) != 8:
            err_msg = 'Invalid \\"query\\" data.'
        
        if err_msg != None:
            self.response.status = 400
            self.response.write('{"error":"%s"}' % err_msg)
            return
        
        q = ForwardingRecord.query(ForwardingRecord.tel == post_data['query_tel']).order(ForwardingRecord.start)
        result_entries = q.fetch(3)

        results = { 'count': len(result_entries), 'records': [] }
        for r in result_entries:
            rd = {}
            rd['tel'] = r.tel
            rd['site'] = r.site
            rd['start'] = r.start
            rd['end'] = r.end
            rd['key'] = r.key.urlsafe()
            results['records'].append(rd)

        self.response.status = 200
        self.response.write(json.dumps(results))

app = webapp2.WSGIApplication([
    ('/api', MainPage),
], debug=True)
