import base64, urllib
from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.protocols import basic
from twisted.python.failure import DefaultException
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
import json
import oauth2 as oauth
import time
from twisted.web import server,resource
from twisted.internet import endpoints
from twisted.web.server import Site

CONSUMER_KEY = 'Oxxxxxxxxxxxxxxxxxxxw'
CONSUMER_SECRET = '1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxp4'
# TWITTER_STREAM_API_HOST = 'stream.twitter.com'
# TWITTER_STREAM_API_PATH = '/1.1/statuses/sample.json'
# TWITTER_STREAM_API_PATH = '/1.1/statuses/filter.json?track=twitter'
ACCESS_TOKEN_FILE = 'OAUTH_ACCESS_TOKEN'

CONSUMER = oauth.Consumer(CONSUMER_KEY, CONSUMER_SECRET)

def callback(result):
    print result,':::'
def errback(error):
    print error,'///'

class StreamingParser(basic.LineReceiver):
    delimiter = '\r\n'

    def __init__(self, user_callback, user_errback):
        self.user_callback = user_callback
        self.user_errback = user_errback

    def lineReceived(self, line):
        d = Deferred()
        d.addCallback(self.user_callback)
        d.addErrback(self.user_errback)
        line = line.strip()
        # print line,'........'
        try:
            d.callback(json.loads(line))
        except ValueError, e:
            if self.user_errback:
                d.errback(e)

    def connectionLost(self, reason):
        if self.user_errback:
            d = Deferred()
            d.addErrback(self.user_errback)
            d.errback(DefaultException(reason.getErrorMessage()))

def _get_response(response, callback, errback):
    print 'got response......'
    response.deliverBody(StreamingParser(callback, errback))
    return Deferred()

def _shutdown(reason, errback):
    d = Deferred()
    d.addErrback(errback)
    d.errback(reason)
    if reactor.running:
        reactor.stop()

def save_access_token(key, secret):
    with open(ACCESS_TOKEN_FILE, 'w') as f:
	f.write("ACCESS_KEY=%s\n" % key)
	f.write("ACCESS_SECRET=%s\n" % secret)


def load_access_token():
    with open(ACCESS_TOKEN_FILE) as f:
	lines = f.readlines()

    str_key = lines[0].strip().split('=')[1]
    str_secret = lines[1].strip().split('=')[1]
    return oauth.Token(key=str_key, secret=str_secret)


def fetch_access_token():
    ACCESS_KEY="8xxxxxxxxxxxxxxxxxxxxxxxxxxxx3"
    ACCESS_SECRET="xxxxxxxxxxxxxxxxxxxxxxxxxxxt"
    access_token = oauth.Token(key=ACCESS_KEY, secret=ACCESS_SECRET)
    return (access_token.key, access_token.secret)


def make_header(access_token,brand):
    # url = "https://%s%s" % (TWITTER_STREAM_API_HOST, TWITTER_STREAM_API_PATH)
    TWITTER_STREAM_API_HOST = 'stream.twitter.com'
    TWITTER_STREAM_API_PATH = '/1.1/statuses/filter.json?track=%s'%(brand)
    url = "https://%s%s" % (TWITTER_STREAM_API_HOST, TWITTER_STREAM_API_PATH)

    params = {
     # "Authorization": "Oauth %s" % auth,
     "oauth_version": "1.0",
     "oauth_nonce": oauth.generate_nonce(),
     "oauth_timestamp": str(int(time.time())),
     "oauth_token": access_token.key,
     "oauth_consumer_key": CONSUMER.key
     }

    req = oauth.Request(method="POST", url=url, parameters=params, is_form_encoded=True)
    req.sign_request(oauth.SignatureMethod_HMAC_SHA1(), CONSUMER, access_token)
    header = req.to_header()['Authorization'].encode('utf-8')
    print "Authorization header:"
    print "     header = %s" % header
    return header
_dSet = []

def start_streaming(streamName):
    brand = streamName
    print 'streaming started...........'
    try:
        f = open(ACCESS_TOKEN_FILE)
    except IOError:
        access_token_key, access_token_secret = fetch_access_token()
        save_access_token(access_token_key, access_token_secret)

    access_token = load_access_token()
    auth_header = make_header(access_token,brand)
    # url = 'https://stream.twitter.com/1.1/statuses/sample.json'
    url='https://stream.twitter.com/1.1/statuses/filter.json?track=%s'%(streamName)
    headers = Headers({
        'User-Agent': ['TwistedSTreamReciever'],
        'Authorization': [auth_header]})
    agent = Agent(reactor)
    d = agent.request('POST', url, headers, None)
    # assign the open stream connection a name
    d._streamName = streamName
    # add to global collection of agent defferd's.
    _dSet.append(d)

    d.addCallback(_get_response, callback, errback)
    d.addBoth(_shutdown, errback)
    # reactor.run()

class _startStreaming(resource.Resource):
    isLeaf = True
    def render_GET(self, request):
        brand_to_track = request.args['track'][0]
        # timeoutCall = reactor.callLater(tracking_duration, d.cancel)
        start_streaming(brand_to_track)
        return "<html>streaming started...........%s</html>" % (time.ctime(),)

class _stopStreaming(resource.Resource):
    isLeaf = True
    def render_GET(self, request):
        brand_to_track = request.args['track'][0]
        print brand_to_track
        for index,d in enumerate(_dSet):
            if d._streamName == brand_to_track:
                del _dSet[index]
                d.cancel
        return "<html>############## streaming stopped ######################...........%s</html>" % (time.ctime(),)


class _currentlyTracking(resource.Resource):

    def render_GET(self, request):
        isLeaf = True
        resp =''
        for d in _dSet:
            resp = resp +"<tr><td>%s</td></tr>" % (d._streamName)
        return "<html><head><style>table{border: 1px solid black;}</style></head><body><table>%s</table></body></html>" % (resp)


if __name__ == "__main__":
    # try:
    #     f = open(ACCESS_TOKEN_FILE)
    # except IOError:
    #     access_token_key, access_token_secret = fetch_access_token()
    #     save_access_token(access_token_key, access_token_secret)
    #
    # access_token = load_access_token()
    # auth_header = make_header(access_token)
    # url = 'https://stream.twitter.com/1.1/statuses/sample.json'
    # headers = Headers({
    #     'User-Agent': ['TwistedSTreamReciever'],
    #     'Authorization': [auth_header]})

    root = resource.Resource()
    root.putChild('start',_startStreaming())
    root.putChild('stop',_stopStreaming())
    root.putChild('list',_currentlyTracking())

    factory = Site(root)
    endpoint = endpoints.TCP4ServerEndpoint(reactor, 8880)
    endpoint.listen(factory)
    reactor.run()
    #--------- issue the request
    # agent = Agent(reactor)
    # d = agent.request('GET', url, headers, None)
    # d.addCallback(_get_response, callback, errback)
    # d.addBoth(_shutdown, errback)
    # reactor.run()
