#
# -*-encoding:gb2312-*-

import urllib
from bencode import bdecode
from metainfo import BTMetaInfo
from utils import SpeedMonitor, generate_peer_id
from factory import ConnectionManager
from piecemanager import BTPieceManager
from trackerclient import BTTrackerClient


class BTConfig(object):
    def __init__(self, image_url, host=None, port=None):
        metainfo = bdecode(urllib.urlopen(image_url).read())
        #import pprint
        #pprint.pprint(metainfo)
        self.metainfo = BTMetaInfo(metainfo, host, port)
        
        self.info_hash = self.metainfo.info_hash

class BTManager (object):
    def __init__(self, app, config):
        self.app = app
        self.config = config
        self.metainfo = config.metainfo
        self.info_hash = self.metainfo.info_hash
        self.download_speed_monitor = SpeedMonitor(5)
        self.upload_speed_monitor = SpeedMonitor(5)
        self.my_peer_id = generate_peer_id()
        self.connection_manager = ConnectionManager(self)
        self.piece_manager = BTPieceManager(self)
        self.tracker_client = BTTrackerClient(self)
        
        self.status = None

    def start_download(self):
        self.piece_manager.start()

        self.connection_manager.start()
        
        self.download_speed_monitor.start()
        self.upload_speed_monitor.start()

        self.tracker_client.start()

        self.status = 'running'

    def stop_download(self):
        self.piece_manager.stop()

        self.connection_manager.stop()
        
        self.download_speed_monitor.stop()
        self.upload_speed_monitor.stop()

        self.tracker_client.stop()

        self.status = 'stopped'

    def get_speed(self):
        """Returns the speed in kibibit per second (Kibit/s).
        """
        return {
            "down": self.download_speed_monitor.get_speed(),
            "up":   self.upload_speed_monitor.get_speed()  }

    def get_num_connections(self):
        return {
            "client": len(self.connection_manager.client_factory.active_connection),
            "server": len(self.connection_manager.server_factory.active_connection)}

    def exit(self):
        if self.status == 'running' :
            self.stop_download()

        for i in self.__dict__ :
            del self.__dict__[i]
    
    def add_peers(self, peers):
        """Adds peers to the torrent for downloading pieces.

        @param peers list of tuples e.g. [('173.248.194.166', 12005),
            ('192.166.145.8', 13915)]
        """
        self.connection_manager.client_factory.update_tracker_peers(peers)

