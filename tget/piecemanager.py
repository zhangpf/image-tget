# 
# -*-encoding:gb2312-*-

from bitfield import BitField
from filemanager import BTFileManager, BTHashTestError

class BTPieceManager:

    def __init__(self, btm):
        self.btm = btm
        self.metainfo = btm.metainfo
        self.connection_manager = btm.connection_manager

        self.btfile = BTFileManager(btm)

        self.bitfield = self.btfile.bitfield_have # 标记已经下载的块

        metainfo = self.metainfo
        self.piece_length = metainfo.piece_length
        self.pieces_size = metainfo.pieces_size
        self.pieces_hash = metainfo.pieces_hash

        self.buffer = {}        # 缓冲已完成的piece

        self.bf_need = self.btfile.bitfield_need   # 标记没有下载的块

        self.piece_download = {} # [idx]: [todo], [doing], [done] 
        self.piece_todo = {}
        self.piece_doing = {}
        self.piece_done = {}

    def start(self) :
        self.btfile.start()

    def stop(self) :
        self.btfile.stop()

    def do_slice(self, beg, end):
        slice_list = []

        r = range(beg, end, self.piece_length)
        for beg in r[:-1] :
            slice_list.append((beg, self.piece_length))
        slice_list.append((r[-1], end-r[-1]))

        return slice_list

    def __get_piece_slice(self, idx):
        if idx == self.pieces_size - 1:
            return self.do_slice(0, self.metainfo.last_piece_length)
        else:
            return self.do_slice(0, self.piece_length)
    
    def interested(self, idx):
        if type(idx) is BitField:
            for i in (self.bf_need & idx):
                return True
            else:
                return False
        else:
            return idx in self.bf_need

    def have(self, index):
        return self.bitfield[index]

    def get_more_piece_task(self, peer_bf, num_task=5):
        if num_task == 0:
            return None
        tasks = []
        for idx in (peer_bf & self.bf_need) :
            while True:
                task = self.get_piece_task(idx)
                if not task :
                    break
                tasks.append(task)            
        return tasks

    def get_piece_task(self, idx):
        assert idx in self.bf_need

        if idx not in self.piece_download:
            slice_list = self.__get_piece_slice(idx)
            self.piece_download[idx] = [slice_list, [], []]

        task_to_do, task_doing, task_done = self.piece_download[idx]

        if not task_to_do:
            return None

        my_task = task_to_do[0]
        del task_to_do[0]

        task_doing.append(my_task)

        return idx, my_task

    def failed_piece_task(self, idx, task):
        #log.err('下载失败 {0}{1}'.format(idx, task))
        task_to_do, task_doing, task_done = self.piece_download[idx]
        assert task in task_doing

        task_doing.remove(task)

        task_to_do.append(task)

    def finish_piece_task(self, idx, task, data):
        task_to_do, task_doing, task_done = self.piece_download[idx]

        assert task in task_doing

        task_doing.remove(task)

        task_done.append((task, data))

        if not task_to_do and not task_doing :
            task_done.sort(key=lambda x : x[0][0])
            data = ''.join(d for t, d in task_done)

            try:
                self.btfile.write_piece(idx, data)
                self.bitfield[idx] = 1
                self.bf_need[idx] = 0

            except BTHashTestError as error:
                del self.piece_download[idx]

            else:
                self.connection_manager.broadcast_have(idx)
                
    def get_piece_data(self, index, beg, length) :
        if not self.have(index) :
            return None
        piece = self.btfile.read_piece(index)
        if piece :
            return piece[beg:(beg+length)]
        else :
            return None

        
