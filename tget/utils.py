'''
Created on Dec 29, 2013

@author: zpfalpc23
'''

import logging
import os
import time
import ConfigParser
from datetime import datetime
from exception import *
from socket import inet_aton
from struct import pack
import shelve
import hashlib

from twisted.internet import reactor, defer

TRACKER_LOG_PATH = os.path.expanduser(
                '~/.tget/log/tracker-%s.log' % datetime.now().strftime('%Y-%m-%d-%H-%M-%S'))
PEER_LOG_PATH= os.path.expanduser(
                '~/.tget/log/peer-%s.log' % datetime.now().strftime('%Y-%m-%d-%H-%M-%S'))
TRACKER_DB_PATH = os.path.expanduser('~/.tget/db/tracker.db')

TRACKER_CONFIG_PATH = os.path.expanduser('~/.tget/conf/tracker.conf')

IMAGE_BASE_PREFIX = os.path.expanduser('~/.tget/image/')
TORRENT_BASE_PREIFX = os.path.expanduser('~/.tget/torrent')

PEER_IMAGE_DIR = os.path.expanduser('~/.tget/peer-image/')

# Some global constants.
PEER_INCREASE_LIMIT = 30
DEFAULT_ALLOWED_PEERS = 50
MAX_ALLOWED_PEERS = 55
INFO_HASH_LEN = PEER_ID_LEN = 20

# HTTP Error Codes for BitTorrent Tracker
INVALID_REQUEST_TYPE = 100
MISSING_INFO_HASH = 101
MISSING_PEER_ID = 102
MISSING_PORT = 103
INVALID_INFO_HASH = 150
INVALID_PEER_ID = 151
INVALID_NUMWANT = 152
GENERIC_ERROR = 900 

def setup_logging(log_path, debug=True):
    """Setup application logging.
    """
    if debug:
        level = logging.DEBUG
    else:
        level = logging.INFO
        
    dirname = os.path.dirname(log_path)
    if not os.path.exists(dirname):
        os.makedirs(dirname)
    
    #log_handler = logging.handlers.RotatingFileHandler(log_path)
    log_handler = logging.StreamHandler() 
    root_logger = logging.getLogger('')
    root_logger.setLevel(level)
    format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    formatter = logging.Formatter(format)
    log_handler.setFormatter(formatter)
    root_logger.addHandler(log_handler)



class Config:
    """Provide a single entry point to the Configuration.
    """
    __shared_state = {}

    def __init__(self):
        """Borg pattern. All instances will have same state.
        """
        self.__dict__ = self.__shared_state

    def get(self):
        """Get the config object.
        """
        if not hasattr(self, '__config'):
            self.__config = ConfigParser.RawConfigParser()
            if self.__config.read(TRACKER_CONFIG_PATH) == []:
                raise ConfigError(TRACKER_CONFIG_PATH)
        return self.__config

    def close(self):
        """Close config connection
        """
        if not hasattr(self, '__config'):
            return 0
        del self.__config


class Database:
    """Provide a single entry point to the database.
    """
    __db = None
    __shared_state = {}

    def __init__(self):
        """Borg pattern. All instances will have same state.
        """
        self.__dict__ = self.__shared_state

    def get(self):
        """Get the shelve object.
        """
        if self.__db == None:
            dirname = os.path.dirname(TRACKER_DB_PATH)
            if not os.path.exists(dirname):
                os.makedirs(dirname)
            self.__db = shelve.open(TRACKER_DB_PATH, 'n', writeback=True)
        return self.__db

    def close(self):
        """Close db connection
        """
        if not hasattr(self, '__db'):
            return 0
        self.__db.close()
        del self.__db


def get_config():
    """Get a connection to the configuration.
    """
    return Config().get()


def get_db():
    """Get a persistent connection to the database.
    """
    return Database().get()


def close_db():
    """Close db connection.
    """
    Database().close()
    
    
def number_of_seeders(info_hash):
    """Number of peers with the entire file, aka "seeders".
    """
    db = get_db()
    count = 0
    if db.has_key(info_hash):
        for peer_info in db[info_hash]:
            if peer_info[3] == 'completed':
                count += 1
    return count


def number_of_leechers(info_hash):
    """Number of non-seeder peers, aka "leechers".
    """
    db = get_db()
    count = 0
    if db.has_key(info_hash):
        for peer_info in db[info_hash]:
            if peer_info[3] == 'started':
                count += 1
    return count

def store_peer_info(info_hash, peer_id, ip, port, status):
    """Store the information about the peer.
    """
    db = get_db()
    logging.info('db = %r' % db)
    if db.has_key(info_hash):
        if (peer_id, ip, port, status) not in db[info_hash]:
            db[info_hash].append((peer_id, ip, port, status))
    else:
        db[info_hash] = [(peer_id, ip, port, status)]

def get_peer_list(info_hash, numwant, compact, no_peer_id, peer_id=None):
    """Get all the peer's info with peer_id, ip and port.
    Eg: [{'peer_id':'#1223&&IJM', 'ip':'162.166.112.2', 'port': '7887'}, ...]
    """
    db = get_db()
    if compact:
        byteswant = numwant * 6
        compact_peers = ""
        # make a compact peer list
        if db.has_key(info_hash):
            for peer_info in db[info_hash]:
                if peer_id == peer_info[0]:
                    continue
                ip = inet_aton(peer_info[1])
                port = pack('>H', int(peer_info[2]))
                compact_peers += (ip+port)
        logging.debug('compact peer list: %r' %compact_peers[:byteswant])
        return compact_peers[:byteswant]
    else:
        peers = []
        if db.has_key(info_hash):
            for peer_info in db[info_hash]:
                if peer_id == peer_info[0]:
                    continue
                p = {}
                p['peer_id'], p['ip'], p['port'], _ = peer_info
                if no_peer_id: del p['peer_id']
                peers.append(p)
        logging.debug('peer list: %r' %peers[:numwant])
        return peers[:numwant]
    
def get_peer_parent(peer_id, ip, port, compact, no_peed_id):
    return {}

def sleep(timeout):
    df = defer.Deferred()

    start_time = time.time()
    
    def callback():
        dt = time.time() - start_time
        df.callback(dt)
        
    reactor.callLater(timeout, callback)
    
    return df

def generate_peer_id():
    myid = 'M' + '7-2-0' + '--' # 8
    myid += hashlib.sha1(str(time.time())+ ' ' + str(os.getpid())).hexdigest()[-12:] # 12
    assert len(myid) == 20
    return myid

class SpeedMonitor (object):
    """A generic network speed monitor.
    
    @param period the time window for each individual measurement; if this is
    not set, the SpeedMonitor will not take measurements! 
    """
    def __init__(self, period=None):
        self.bytes = 0
        self.start_time = None

        self.period = period

        self.bytes_record = 0
        self.time_record = None
        self.speed = 0

        self.observer = None

    def register_observer(self, observer):
        self.observer = observer

    @defer.inlineCallbacks
    def start(self):
        self.bytes = 0
        self.start_time = time.time()
        self.status = 'started'

        while self.status == 'started':
            if not self.period:
                break
            self.bytes_record = self.bytes
            self.time_record = time.time()
            yield sleep(self.period)
            self.speed_calc()

    def stop(self):
        if self.observer:
            self.observer = None

        self.status = 'stopped'

    def add_bytes(self, bytes):
        self.bytes += bytes
        if self.observer:
            self.observer.add_bytes(bytes)
    
    def speed_calc(self):
        curTime = time.time()
        dq = self.bytes - self.bytes_record
        dt = curTime - self.time_record
        self.speed = float(dq) / dt
        self.time_record = curTime
        self.bytes_record = self.bytes

    def get_speed(self):
        """Returns the speed in kibibit per second (Kibit/s) no matter what the
        period was. Returns None is period is None. 

        """
        if self.speed and self.period:
            return self.speed  / 1024
        else:
            return 0
        