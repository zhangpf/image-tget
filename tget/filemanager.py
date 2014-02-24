#
# -*-encoding:utf-8-*-

import os
import hashlib
import logging

from twisted.python import log
from twisted.internet import reactor, defer

from bitfield import BitField

from utils import sleep

class BTFileError (Exception) :
    pass

class BTHashTestError (Exception):
    pass

class BTFile:
    def __init__(self, metainfo, saveDir):
        self.metainfo = metainfo
        self.path = os.path.join(saveDir, metainfo.path)
        self.length = metainfo.file_length
        self.piece_len = metainfo.piece_length
        self.hash_array = metainfo.pieces_hash
        self.pieces_size = metainfo.pieces_size
        self.fd = None
        
        logging.info("the saved file path is %s" % self.path)
        if os.path.exists(self.path):
            self.fd = open(self.path, 'rb+')
        else:
            dirname = os.path.dirname(self.path)
            if not os.path.exists(dirname):
                os.makedirs(dirname)
            self.fd = open(self.path, 'wb')
        
        #print self.abs_pos0, self.abs_pos1, self.piece_len, self.idx0_piece, self.idx1_piece

        h, t = os.path.split(self.path)
        if not os.path.exists(h):
            os.makedirs(h)

    def write(self, begin, data):
        if begin < 0:
            raise BTFileError("Invalid write begin position.")
        elif len(data) + begin > self.length:
            raise BTFileError("Invalid write end position.")

        self.fd.seek(begin)
        self.fd.write(data)
        
    def read(self, begin, length):
        if length < 0:
            raise BTFileError("Invalid read length.")
        elif begin < 0:
            raise BTFileError("Invalid read begin position.")
        elif begin + length > self.length:
            raise BTFileError("Invalid read end position.")

        self.fd.seek(begin)
        data = self.fd.read(length)
        return data

    def close(self):
        if self.fd :
            self.fd.close()
        self.fd = None
    
    def get_bitfield(self):
        bf_need = BitField(self.pieces_size)
        bf_have = BitField(self.pieces_size)
        for i in xrange(self.pieces_size):
            try :
                data = self[i]
                if data and self.do_hash_test(i, data):
                    bf_have[i] = 1
                    bf_need[i] = 0
                else:
                    bf_have[i] = 0
                    bf_need[i] = 1
            except BTFileError as error :
                pass
            
        print bf_have
        print bf_need
        return bf_have, bf_need
    
    def do_hash_test(self, idx, data):
        return hashlib.sha1(data).digest() == self.hash_array[idx]
    
    def __getitem__(self, idx):
        end = min((idx + 1) * self.piece_len, self.length)
        return self.read(idx * self.piece_len, end - idx * self.piece_len)

    def __setitem__(self, idx, data):
        self.write(idx * self.piece_len, data) 
            
class BTFileManager :
    
    def __init__(self, btm):
        self.btm = btm
        self.config = btm.config

        metainfo = self.config.metainfo

        self.metainfo = metainfo
        self.piece_length = metainfo.piece_length
        self.pieces_size = metainfo.pieces_size

        self.btfile = BTFile(metainfo, self.btm.app.save_dir)
        self.bitfield_have, self.bitfield_need = self.btfile.get_bitfield()
        self.buffer_max_size = 100 * 2**20 / self.piece_length
        self.buffer = {}        
        self.buffer_record = [] 
        self.buffer_dirty = {} 

    def start(self) :
        self.status = 'started'

        reactor.callLater(2, self.deamon_write)
        reactor.callLater(2, self.deamon_read)

    def stop(self) :
        for idx, data in self.buffer_dirty.iteritems():
            self.write(idx, data)

        self.buffer_dirty.clear()

        self.buffer.clear()

        del self.buffer_record[:]

        self.status = 'stopped'

    @defer.inlineCallbacks
    def deamon_write(self):
        while self.status == 'started':
            self.__thread_write()
            yield sleep(2)
    
    def __thread_write(self):
        if not hasattr(self, '__thread_write_status') :
            self.__thread_write_status = 'stopped'

        if self.__thread_write_status == 'running' :
            return

        if not self.buffer_dirty :
            return
        
        bfd = self.buffer_dirty.copy()

        def call_in_thread():
            # Writing to disk 
            for idx in sorted(bfd.keys()) :
                data = bfd[idx]
                self.write(idx, data)
            reactor.callFromThread(call_from_thread)

        def call_from_thread():
            self.__thread_write_status = 'stopped'
            for idx, data in bfd.iteritems() :
                if data is self.buffer_dirty[idx] :
                    del self.buffer_dirty[idx]

        if self.__thread_write_status == 'stopped' :
            self.__thread_write_status = 'running'
            reactor.callInThread(call_in_thread)

    @defer.inlineCallbacks
    def deamon_read(self):
        while self.status == 'started':
            size = len(self.buffer)
            if size > self.buffer_max_size :
                remove_count = size - self.buffer_max_size
                remove_count += self.buffer_max_size / 5
                for idx in self.buffer_record[:remove_count] :
                    del self.buffer[idx]
                del self.buffer_record[:remove_count]

            yield sleep(10)

    ############################################################

    def read_piece(self, index) :
        if not (0 <= index < self.pieces_size) :
            raise BTFileError('index is out of range')
        if not self.bitfield_have[index] :
            raise BTFileError('index is not downloaded')

        if index in self.buffer :
            data = self.buffer[index]
            self.buffer_record.remove(index)
            self.buffer_record.append(index)
            return data

        else:
            for idx in [index, index+1, index+2, index+3] :
                if 0 <= idx < self.pieces_size and idx not in self.buffer :
                    data = self.read(idx)
                    assert data
                    self.buffer[idx] = data
                    self.buffer_record.append(idx)

            data = self.read_piece(index)

            return data
            
    def write_piece(self, index, data) :
        if not (0 <= index < self.pieces_size) :
            raise BTFileError('index is out of range')
        if not self.bitfield_need[index] :
            raise BTFileError('index is not need')

        if not self.btfile.do_hash_test(index, data):
            raise BTHashTestError()

        else:
            self.bitfield_have[index] = 1
            self.bitfield_need[index] = 0

            if index in self.buffer :
                self.buffer[index] = data

            self.buffer_dirty[index] = data
            
            if self.bitfield_have.allOne():
                logging.info('almost done!')

            return True

    def read(self, index):
        if index in self.buffer_dirty:
            return self.buffer_dirty[index]
        return self.btfile[index]

    def write(self, index, data) :
        self.btfile[index] = data
        
