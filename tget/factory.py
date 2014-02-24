#
# -*-encoding:gb2312-*-

import abc
import logging

from twisted.python import log
from twisted.internet import reactor
from twisted.internet import protocol, defer

from utils import SpeedMonitor, sleep
from protocol import BTClientProtocol, BTServerProtocol

class IConnectionManager (object) :
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def start(self):
        pass

    @abc.abstractmethod
    def stop(self):
        pass

    @abc.abstractmethod
    def broadcast_have(self, idx):
        pass

    @abc.abstractmethod
    def redownload_piece(self, idx):
        pass

    @abc.abstractmethod
    def broadcast_cancel_piece(self, idx, begin, length):
        pass

    @abc.abstractmethod
    def is_already_connected(self, peer_id):
        pass

    @abc.abstractmethod
    def get_connection(self, peer_id) :
        pass

class ConnectionManager (IConnectionManager):
    def __init__(self, btm):
        self.btm = btm
        self.server_pool = self.btm.app.server_pool

        self.client_factory = BTClientFactory(btm) # 管理主动连接
        self.server_factory = BTServerFactory(btm) # 管理被动连接

    def start(self):
        self.client_factory.start()
        self.server_factory.start()

        self.server_pool.add_factory(self.server_factory)

    def stop(self):
        self.client_factory.stop()
        self.server_factory.stop()

        self.server_pool.remove_factory(self.server_factory)    

    def broadcast_have(self, idx):
        self.client_factory.broadcast_have(idx)
        self.server_factory.broadcast_have(idx)

    def redownload_piece(self, idx):
        self.client_factory.redownload_piece(idx)
        self.server_factory.redownload_piece(idx)

    def broadcast_cancel_piece(self, idx, begin, length):
        self.client_factory.broadcast_piece(idx, begin, length)
        self.server_factory.broadcast_piece(idx, begin, length)

    def is_already_connected(self, peer_id):
        return self.client_factory.is_already_connected(peer_id) \
            or self.server_factory.is_already_connected(peer_id)

    def get_connection(self, peer_id) :
        return self.client_factory.get_connection(peer_id) \
            or self.server_factory.get_connection(peer_id)


class ConnectionManagerBase (IConnectionManager):
    def __init__(self, btm):
        self.btm = btm
        self.info_hash = btm.metainfo.info_hash

        self.active_connection = {}

        self.download_speed_monitor = SpeedMonitor()
        self.download_speed_monitor.register_observer(btm.download_speed_monitor)

        self.upload_speed_monitor = SpeedMonitor()
        self.upload_speed_monitor.register_observer(btm.upload_speed_monitor)


    def add_active_connection(self, peer_id, connection):
        peer_id = connection.peer_id
        self.active_connection[peer_id] = connection

    def remove_active_connection(self, peer_id):
        if peer_id in self.active_connection:
            del self.active_connection[peer_id]

    def is_already_connected(self, peer_id) :
        return peer_id in self.active_connection
    
    def get_connection(self, peer_id) :
        return self.active_connection.get(peer_id, None)

    def broadcast_have(self, idx):
        for _, connection in self.active_connection.iteritems():
            connection.send_have(idx)

    def redownload_piece(self, idx):
        for _, connection in self.active_connection.iteritems():
            connection.redownload_piece(idx)

    def broadcast_cancel_piece(self, idx, begin, length):
        for _, connection in self.active_connection.iteritems():
            connection.send_cancel(idx, begin, length)

    def start(self):
        pass

    def stop(self):
        pass

class BTClientFactory(protocol.ClientFactory, ConnectionManagerBase):
    protocol = BTClientProtocol

    def __init__(self, btm):
        ConnectionManagerBase.__init__(self, btm)

        self.peers_connecting = set()
        self.peers_failed = set()
        self.peers_blacklist = set()

        self.peers_retry = {}

    def update_tracker_peers(self, new_peers):
        newPeers = set(new_peers)
        newPeers -= self.peers_connecting | self.peers_blacklist | self.peers_failed

        self.conncect_peers(new_peers)

    @defer.inlineCallbacks
    def conncect_peers(self, peers):
        for addr, port in peers:
            reactor.connectTCP(addr, port, self)
            yield sleep(0)
    
    def start_factory(self):
        pass

    def stop_factory(self):
        pass

    def started_connecting(self, connector):
        addr = self.get_peer_addr(connector)
        self.peers_connecting.add(addr)

    def client_connection_failed(self, connector, reason):
        #print '连接不上', connector.getDestination(), reason
        self.connect_retry(connector)

    def client_connection_lost(self, connector, reason):
        #print '连接丢失', connector.getDestination(), reason
        #self.connectRetry(connector)
        self.connect_retry(connector)

    @defer.inlineCallbacks
    def connect_retry(self, connector):
        addr = self.get_peer_addr(connector)

        if addr in self.peers_retry:
            retry = self.peers_retry[addr]
        else:
            retry = 0

        if retry > 50:
            self.peers_failed.add(addr)
            self.peers_connecting.remove(addr)
            del self.peers_retry[addr]
        else:
            yield sleep(5)
            connector.connect()
            retry += 1
            self.peers_retry[addr] = retry

    def get_peer_addr(self, connector):
        address = connector.getDestination()
        addr = address.host, address.port
        return addr

class BTServerFactory (protocol.ServerFactory, ConnectionManagerBase):
    '''
    监听端口 仅服务于 一个bt任务
    '''

    protocol = BTServerProtocol

    def __init__(self, btm):
        ConnectionManagerBase.__init__(self, btm)

    def reset_factory(self, protocol, info_hash):
        assert peer.factory is self
        return self

    def __getattr__(self, name):
        return getattr(self.btm.app.server_pool, name)
        
class BTServerFactories (protocol.ServerFactory):
    """ 
    """ 

    protocol = BTServerProtocol
    
    def __init__(self, listen_port=6881):
        self.maps = {}
        self.listen_port = listen_port
    
    def start_factory(self):
        pass

    def stop_factory(self):
        pass

    def add_factory(self, factory):
        info_hash = factory.info_hash
        if info_hash not in self.maps:
            factory.factories = self
            self.maps[factory.info_hash] = factory

    def remove_factory(self, factory):
        info_hash = factory.info_hash
        if info_hash in self.maps:
            try:
                del factory.maps
            except:
                pass
            try:
                del self.maps[info_hash]
            except:
                pass
    
    def reset_factory(self, protocol, info_hash):
        if info_hash in self.maps :
            protocol.factory = self.maps[info_hash]
            return protocol.factory
        else:
            return None
