import webapp2
import logging

class MainPage(webapp2.RequestHandler):
    def post(self):
        self.response.headers['Content-Type'] = 'application/json'
        self.response.write('{"result":"ok"}')

        # Ex: UnicodeMultiDict([(u'tel', u'12123123'), (u'site', u'D047'), (u'start', u'1546963200'), (u'end', u'1546963200')])
        logging.info(str(self.request.POST))

        # 1. Data validation: 'tel' is 8-digits number. 'site' should be in the form of 'Dnnn'. 
        #                     'start' should be epoch seconds greater than the begining of today but no greater than 31 days.
        #                     'end' should be epoch seconds greater or equal to 'start' and the different between them should
        #                     be less than 31 days. Return error if any of the above assumption fails to hold.
         
        # 2. Check how many on-going forecasting rules matched with the given tel. Return error if there is too many.

        # 3. Write to DB and return success.
        

app = webapp2.WSGIApplication([
    ('/api', MainPage),
], debug=True)
