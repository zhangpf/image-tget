# 
# -*-encoding:gb2312-*-

import hashlib
import logging
from bencode import bencode, bdecode

"""
    metainfo
    announce
    encoding
    method
    info_hash
    pretty_info_hash
    piece_length
    piece_hash
    piece_size
    path
    file_length
    total_length
    last_piece_length
"""
class BTMetaInfo:
    """ 
    """ 
    encoding = 'utf-8'
    def __init__(self, metainfo=None, host=None, port=80):

        self.metainfo = metainfo

        if 'annouce' in metainfo:
            self.announce = metainfo['announce']
        elif host:
            self.announce = 'http://%s:%d/announce' % (host, port)
            
        logging.info('announce url = %s' % self.announce)
            
            
        if 'encoding' in metainfo:
            self.encoding = metainfo['encoding']
            
        if 'method' in metainfo:
            self.method = metainfo['method']
        else:
            self.method = 'BitTorrent protocol'
            
        info = metainfo['info']
        temp = hashlib.sha1(bencode(info))
        self.info_hash =  temp.digest()
        self.pretty_info_hash =  temp.hexdigest()

        self.piece_length = info['piece length']

        hashes = info['pieces']
        self.pieces_hash = [hashes[i:i+20] for i in range(0, len(hashes), 20)]
        self.pieces_size = len(self.pieces_hash)

        name = info['name'].decode(self.encoding)
        self.path = name
        self.file_length= info['length']
        self.total_length = info['length']

        last_piece_length = self.total_length % self.piece_length
        if last_piece_length == 0 :
            last_piece_length = self.piece_length
        self.last_piece_length = last_piece_length
