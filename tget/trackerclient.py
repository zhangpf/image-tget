#
# -*-encoding:gb2312-*-
from bencode import bdecode, BTFailure
from twisted.internet import defer
from twisted.web.client import getPage

from utils import sleep

from urllib import urlencode
from base64 import b64encode
import socket
import struct
import logging



class BTTrackerClient:
    def __init__(self, btm):
        self.btm = btm
        self.reciever = btm.connection_manager.client_factory
        self.timmer = {}
        self.interval = 15 * 60

    #@defer.inlineCallbacks
    def start(self):
        self.status = 'started'

        info_hash = self.btm.metainfo.info_hash
        peer_id = self.btm.my_peer_id
        port = self.btm.app.server_pool.listen_port
        request = {
            'info_hash' : b64encode(info_hash),
            'peer_id' : peer_id,
            'port' : port,
            'compact' : 1,
            'method' : 'BitTorrent protocol',
            'uploaded' : 0,
            'downloaded' : 0,
            'left' : 100,
            'event' : 'started'
            }
        request_encode = urlencode(request)
        self.get_peer_list(self.btm.metainfo.announce, request_encode)

    def stop(self):
        self.status = 'stopped'

    @defer.inlineCallbacks
    def get_peer_list(self, url, data):
        if self.status == 'stopped':
            return
        
        try:
            page = yield getPage(url + '?' + data)

        except Exception as error:
            logging.error('Failed to connect to tracker: %s' % url)

            yield sleep(self.interval)
            self.get_peer_list(url, data)

        else:
            try:
                res = bdecode(page)
            except BTFailure:
                logging.error("Received an invalid peer list from the tracker: %s" % url)
            else:
                if len(res) == 1:
                    return

                peers = res['peers']
                peers_list = []
                while peers:
                    addr = socket.inet_ntoa(peers[:4])
                    port = struct.unpack('!H', peers[4:6])[0]
                    peers_list.append((addr, port))
                    peers = peers[6:]

                self.btm.add_peers(peers_list)
            
                interval = self.interval

                yield sleep(interval)
                self.get_peer_list(url, data)

            
