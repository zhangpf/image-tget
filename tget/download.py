#
# -*-encoding:gb2312-*-

from twisted.internet import reactor, defer

from utils import SpeedMonitor, sleep
from bitfield import BitField

class BTDownload(object) :

    task_max_size = 5
    
    def __init__(self, protocol):
        self.protocol = protocol

        self.piece_doing = []
        self.piece_done = []

        self.peer_choke = None
        self.interested = None

        self.download_speed_monitor = SpeedMonitor()

        self.task_max_size = 5

    def start(self):
        if not self.protocol:
            return

        self.status = 'running'
        
        self.btm = self.protocol.factory.btm
        self.piece_manager = self.btm.piece_manager

        pm = self.piece_manager
        self.peer_bitfield = BitField(pm.pieces_size)

        self.download_speed_monitor.start()
        self.download_speed_monitor.register_observer(self.protocol.factory.download_speed_monitor)

        reactor.callLater(0, self._interested, True)

    def stop(self):
        for task in self.piece_doing:
            self.piece_manager.failed_piece_task(*task)

        del self.piece_doing[:]
            
        self.download_speed_monitor.stop()

        del self.protocol
        del self.btm
        del self.piece_manager

        self.status = 'stopped'

    def _choke(self, val):
        self.peer_choke = bool(val)
        
        if val:
            pass
        else:
            self.__piece_request()

    def _interested(self, val):
        # 发送
        interested = bool(val)
        if self.interested is interested :
            return

        if interested :
            self.protocol.send_interested()
        else :
            self.protocol.send_not_interested()

        self.interested = interested

    def cancel(self, task):
        idx, (beg, length) = task
        self.protocol.send_cancel(idx, beg, length)

    def _download_monitor(self, data):
        self.download_speed_monitor.add_bytes(len(data))        

    def __piece_request(self):
        if self.interested==True and self.peer_choke==False:
            if self.piece_doing :
                return

            new_task = self.__get_task()
            if new_task :
                self.__send_task_request(new_task)
            
    def __get_task(self, size=None):
        if size is None :
            size = self.task_max_size
            
        pm = self.piece_manager
        new_task = pm.get_more_piece_task(self.peer_bitfield, size)

        return new_task

    @defer.inlineCallbacks
    def __send_task_request(self, new_task, timeout=None):
        if not new_task:
            return

        if timeout is None:
            timeout = len(new_task) * 60

        for task in new_task :
            i, (begin, size) = task
            self.protocol.send_request(i, begin, size)
            self.piece_doing.append(task)

        yield sleep(timeout)
        self.__check_timeout(new_task)

    def __check_timeout(self, task):
        if self.status == 'stopped' :
            return
        
        #self.transport.loseConnection()
        task_set = set(task)
        task_doing_set = set(self.piece_doing)

        set_undo = task_set & task_doing_set
        set_new = task_doing_set - task_set

        task_size = self.task_max_size - len(set_undo)
        if set_new:
            task_size += 1

        if task_size < 1:
            task_size = 1
        elif task_size > BTDownload.task_max_size :
            task_size = BTDownload.task_max_size

        self.task_max_size = task_size

        if not set_undo:
            return

        new_task = self.__getTask(self.task_max_size)

        for task in set_undo:
            self.cancel(task)
            self.piece_doing.remove(task)
            self.piece_manager.failed_piece_task(*task)

        if new_task:
            self.__send_task_request(new_task)

    def _piece(self, index, begin, piece):
        # 接收发来的piece
        task = index, (begin, len(piece))

        if task not in self.piece_doing: 
            return

        self.piece_manager.finish_piece_task(index, (begin, len(piece)), piece)
        
        self.piece_doing.remove(task)

        if len(self.piece_doing) == 0:
            self.__piece_request()

    def _bitfield(self, data):
        
        pm = self.piece_manager
        bf = BitField(pm.pieces_size, data)

        self.peer_bitfield = bf
        
        if self.piece_manager.interested(bf):
            self._interested(True)
            self.__piece_request()
        else:
            self._interested(False)

        #print 'interested ', self.am_interested, 'bitfield', bf.any()

    def _have(self, index):
        # 接收
        self.peer_bitfield[index] = 1

        if self.piece_manager.interested(index) :
            self._interested(True)
            self.__piece_request()

        #self.protocol.btm.connectionManager.broadcastHave(index)
