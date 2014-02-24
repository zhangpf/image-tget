#
# -*-encoding:gb2312-*-

from twisted.internet import reactor
from twisted.internet import interfaces
from utils import SpeedMonitor
import logging
from zope.interface import implements

class BTUpload (object) :
    # producer interface implementation
    implements(interfaces.IPushProducer)
    
    def __init__(self, protocol):
        self.protocol = protocol

        self.peer_interested = None
        self.am_choke = None

        self.upload_speed_monitor = SpeedMonitor()

        self.upload_todo = []
        self.upload_doing = []
        self.upload_done = []

        self.status = None

    def start(self):
        if self.status == 'started' :
            return

        if not self.protocol:
            return

        self.btm = self.protocol.factory.btm
        self.piece_manager = self.btm.piece_manager

        self.upload_speed_monitor.start()
        self.upload_speed_monitor.register_observer(self.protocol.factory.upload_speed_monitor)

        self.choke(False)

        self.protocol.transport.registerProducer(self, True)

        self.status = 'started'

    def stop(self):
        if self.status == 'stopped':
            return

        self.upload_speed_monitor.stop()

        self.protocol.transport.unregisterProducer()
        
        del self.protocol
        del self.btm
        del self.piece_manager

        self.status = 'stopped'

    def pause(self):
        pass

    def resume(self):
        pass


    def _interested(self, val):
        self.peer_interested = bool(val)

    def _request(self, idx, begin, length):
        
        if not self.piece_manager.have(idx): # I don't have
            return
        
        #logging.info('%d %d %d' % (idx, begin, length))
        #self.upload_todo.append((idx, (begin, length)))

        data = self.piece_manager.get_piece_data(idx, begin, length)
        if data:
            self.protocol.send_piece(idx, begin, data)

        #if self.status == 'idle' :
        #    self.resumeProducing()

    def _cancel(self, idx, begin, length):
        task = idx, (begin, length)
        if task in self.upload_todo :
            self.upload_todo.remove(task)

    def choke(self, val):
        am_choke = bool(val)
        if self.am_choke is am_choke :
            return

        if am_choke :
            self.protocol.send_choke()
        else :
            self.protocol.send_unchoke()

        self.am_choke = am_choke

    def _upload_monitor(self, _type, data):
        self.upload_speed_monitor.add_bytes(len(data))

    # called by transport and do write
    def resumeProducing(self):
        for i in range(len(self.upload_todo)):
            idx, (begin, length) = self.upload_todo[i]
            data = self.piece_manager.get_piece_data(idx, begin, length)
            if data :
                self.protocol.send_piece(idx, begin, data)
                self.status = 'uploading'
                del self.upload_todo[i]
                break
            else:
                self.status = 'idle'

    def stopProducing(self):
        #logging.info("stop be called!")
        pass
    
    def pauseProducing(self):
        #logging.info("pause be called!")
        pass
