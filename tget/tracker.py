#!/usr/bin/env python
#
# BitTorrent Tracker using Tornado
#
# @author: Sreejith K <sreejithemk@gmail.com>
# Created on 12th May 2011
# http://foobarnbaz.com


import sys
import argparse
import logging
import tornado.ioloop
import tornado.web
import tornado.httpserver

from optparse import OptionParser
from bencode import bencode, bdecode
from utils import *
from base64 import b64decode, b64encode
from mktorrent import get_torrent_file

class BaseHandler(tornado.web.RequestHandler):
    """Since I dont like some tornado craps :-)
    """
    def get_argument(self, arg, default=[], strip=True):
        """Convert unicode arguments to a string value.
        """
        value = super(BaseHandler, self).get_argument(arg, default, strip)
        if value != default:
            return str(value)
        return value


class TrackerStatsHandler(BaseHandler):
    """Shows the Tracker statistics on this page.
    """
    def get(self):
        logging.debug("path = %s" % self.request.path)
        self.send_error(404)


class AnnounceHandler(BaseHandler):
    """Track the torrents. Respond with the peer-list.
    """
    def get(self):
        failure_reason = ''
        warning_message = ''

        # get all the required parameters from the HTTP request.
        info_hash = b64decode(self.get_argument('info_hash'))
        peer_id = self.get_argument('peer_id')
        ip = self.request.remote_ip
        port = self.get_argument('port')

        # send appropirate error code.
        if not info_hash:
            return self.send_error(MISSING_INFO_HASH)
        if not peer_id:
            return self.send_error(MISSING_PEER_ID)
        if not port:
            return self.send_error(MISSING_PORT)
        if len(info_hash) != INFO_HASH_LEN:
            return self.send_error(INVALID_INFO_HASH)
        if len(peer_id) != PEER_ID_LEN:
            return self.send_error(INVALID_PEER_ID)

        # get the optional parameters.
        uploaded = int(self.get_argument('uploaded', 0))
        downloaded = int(self.get_argument('downloaded', 0))
        left = int(self.get_argument('left', 0))
        method = str(self.get_argument('method', 'Tget protocol'))
        compact = int(self.get_argument('compact', 0))
        no_peer_id = int(self.get_argument('no_peer_id', 0))
        event = self.get_argument('event', '')
        numwant = int(self.get_argument('numwant', DEFAULT_ALLOWED_PEERS))
        if numwant > MAX_ALLOWED_PEERS:
            # cannot request more than MAX_ALLOWED_PEERS.
            self.send_error(INVALID_NUMWANT)

        # FIXME: What to do with these parameters?
        key = self.get_argument('key', '')
        tracker_id = self.get_argument('trackerid', '')
        
        logging.info('info_hash = %s, peer_id= %s, ip = %s, port=%s' % (info_hash, peer_id, ip, port))
        # store the peer info
        if event:
            store_peer_info(info_hash, peer_id, ip, port, event)
        
        # generate response
        response = {}
        # Interval in seconds that the client should wait between sending 
        #    regular requests to the tracker.
        response['interval'] = get_config().getint('tracker', 'interval')
        # Minimum announce interval. If present clients must not re-announce 
        #    more frequently than this.
        response['min interval'] = get_config().getint('tracker', 'min_interval')
        # FIXME
        response['tracker id'] = tracker_id
        response['complete'] = number_of_seeders(info_hash)
        response['incomplete'] = number_of_leechers(info_hash)
        
        if method == 'BitTorrent protocol':
            # get the peer list for this announce
            response['peers'] = get_peer_list(info_hash, numwant, compact, no_peer_id, peer_id)
        elif method == 'Tget protocol':
            # get the parent peer for this annouce
            response['peers'] = [get_peer_parent(peer_id, ip, port, compact, no_peer_id, peer_id)]
        
        
        # set error and warning messages for the client if any.
        if failure_reason:
            response['failure reason'] = failure_reason
        if warning_message:
            response['warning message'] = warning_message

        # send the bencoded response as text/plain document.
        self.set_header('content-type', 'text/plain')
        self.write(bencode(response))


class ImageHandler(BaseHandler):
    """
    """
    def get(self, image_url):
        image_path = os.path.join(IMAGE_BASE_PREFIX, image_url)
        logging.info('image path = %s' % image_path)
        if not os.path.exists(image_path):
            self.send_error(404)
        
        torrent_path = os.path.join(TORRENT_BASE_PREIFX, image_url + '.torrent')
        
        logging.info('torrent path = %s' % torrent_path)
        
        if not os.path.exists(torrent_path):
            dirname = os.path.dirname(torrent_path)
            if not os.path.exists(dirname):
                os.makedirs(dirname)
            get_torrent_file(str(image_path), metainfo_file_path=torrent_path)
        
        metainfo = open(torrent_path).read()
        logging.info('size = %d' % len(metainfo))
        self.set_header('context-type', 'text/plain')
        self.write(metainfo)
        
    
class ScrapeHandler(BaseHandler):
    """Returns the state of all torrents this tracker is managing.
    """
    def get(self):
        info_hashes = self.get_arguments('info_hash')
        response = {}
        for info_hash in info_hashes:
            info_hash = str(info_hash)
            response[info_hash] = {}
            response[info_hash]['complete'] = number_of_seeders(info_hash)
            # FIXME: number of times clients have registered completion.
            response[info_hash]['downloaded'] = number_of_seeders(info_hash)
            response[info_hash]['incomplete'] = number_of_leechers(info_hash)
            response[info_hash]['name'] = bdecode(info_hash).get(name, '')

        # send the bencoded response as text/plain document.
        self.set_header('content-type', 'text/plain')
        self.write(bencode(response))


def run_tracker(port, debug=False):
    """Start Tornado IOLoop for this application.
    """
    tracker = tornado.web.Application([
        (r"/announce.*", AnnounceHandler),
        (r"/scrape.*", ScrapeHandler),
        (r"/image/(.*)", ImageHandler, dict()),
        (r"/", TrackerStatsHandler),
        (r"/index.htm", TrackerStatsHandler),
        (r"/index.html", TrackerStatsHandler)
    ])
    
    logging.info('Starting tget tracker on port %d' %port)
    http_server = tornado.httpserver.HTTPServer(tracker)
    http_server.listen(port)
    tornado.ioloop.IOLoop.instance().start()

def process_arguments():
    """
    Process the command line arguments of tracker
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', dest='port', type=int,
                    default=8000, help='Tracker listen port')
    parser.add_argument('-b', '--background', dest='background', action='store_true', 
                    default=False, help='Run as a background daemon')
    parser.add_argument('-d', '--debug', dest='debug', action='store_true', 
                    default=False, help='Run in debug mode')
    return parser.parse_args()


if __name__ == '__main__':
    args = process_arguments()
    # setup logging
    setup_logging(TRACKER_LOG_PATH, args.debug)
    try:
        # start the tget tracker
        run_tracker(args.port, args.debug)
    except KeyboardInterrupt:
        logging.info('Tracker Stopped.')
        close_db()
        sys.exit(0)
    except Exception, ex:
        logging.fatal('%s' %str(ex))
        close_db()
        sys.exit(-1)

