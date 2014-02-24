'''
Created on Dec 26, 2013

@author: zpfalpc23
'''

from bencode import *
from exception import *
import os
import argparse
import time
from hashlib import sha1

def get_hash_str(file_list, piece_length):
    hash_str = ""
    cur_length = 0
    cur_input = ""
    for file_item in file_list:
        f = open(file_item, 'rb')
        while True:
            input = f.read(piece_length - cur_length)
            if input == "":
                break
            else:
                cur_input += input
                cur_length = len(input)
                if cur_length == piece_length:
                    hash_str += sha1(cur_input).digest()
                    cur_length = 0
                    cur_input = ""
    if cur_length != 0:
        hash_str += sha1(cur_input).digest()
    return hash_str

def generate_metainfo(target_name, announce_list, file_list,
                      target_is_directory, torrent_name,
                      piece_length, private=False,
                      comment=None, no_creation_date=False,
                      web_seed_list=None):
    meta = {}
    if announce_list:
        meta['announce'] = announce_list[0]
        if len(announce_list) > 1:
            meta['announce-list'] = reduce(lambda x, y: [[x]] + [[y]], announce_list)
    
    if comment != None:
        meta['comment'] = comment
    
    meta['created by'] = 'python-mktorrent 0.1.0'
    
    if no_creation_date == False:
        meta['creation date'] = int(time.time())
        
    info = {}
    if not target_is_directory:
        info['length'] = os.path.getsize(file_list[0])
    else:
        files = []
        for file_item in file_list:
            file_path = file_item.replace(target_name, "", 1).strip().split('/')
            files.append({'length': os.path.getsize(file_item),
                          'path': file_path})
        info['files'] = files
    
    info['name'] = torrent_name
    info['piece length'] = piece_length
    info['pieces'] = get_hash_str(file_list, piece_length)
    if private:
        info['private'] = 1
    
    if web_seed_list != None:
        if len(web_seed_list) == 1:
            info['url-list'] = web_seed_list[0]
        elif len(web_seed_list) > 1:
            info['url-list'] = web_seed_list
            
    meta['info'] = info
    
    return meta

def get_torrent_file(target_name, announce_list=None, comment=None,
                     no_creation_date=False, piece_length=17,
                     torrent_name=None, private=False, num_threads=2,
                     web_seed_list=None, metainfo_file_path=None):
    if target_name == None:
        raise TgetException('Must specify the contents.')

    if not isinstance(target_name, str):
        raise TgetException('Must specify a valid file or directory name.')
    else:
        target = target_name.strip()
        if torrent_name == None:
            torrent_name = os.path.basename(target)
            
    if not metainfo_file_path:
        metainfo_file_path = os.getcwd() + '/' + torrent_name  + '.torrent'
    elif not os.path.isabs(metainfo_file_path):
        metainfo_file_path = os.getcwd() + '/' + metainfo_file_path
    
    if piece_length < 15 or piece_length > 28:
        raise TgetException('The piece length must be a number between 15 and 28.')
    
    piece_length = 1 << piece_length
    
    #if announce_list == None:
    #    raise TgetException('Must specify an announce URL.')
    
    if num_threads < 1 or num_threads > 20:
        raise TgetException('The number of threads must be a number between 1 and 20.')
    
 
    if os.path.isdir(target_name):
        dirname = os.path.abspath(target_name)
        target_is_directory = True
        file_list = []
        for sub_dir in os.walk(dirname):
            dirpath = sub_dir[0]
            for short_name in sub_dir[2]:
                file_path = dirpath + '/' + short_name
                if os.path.isfile(file_path):
                    file_list.append(file_path)
        file_list = sorted(file_list)
        
    elif os.path.isfile(target_name):
        dirname = ""
        target_is_directory = False
        file_list = [target_name]
    
    metadata = generate_metainfo(dirname + '/', announce_list, file_list,
                      target_is_directory, torrent_name,
                      piece_length, private,
                      comment, no_creation_date,
                      web_seed_list)
    
    with open(metainfo_file_path, 'wb') as f:
        f.write(bencode(metadata))

def process_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('target', help='target directory or filename')
    parser.add_argument('-a', '--announce', dest='announce_list', metavar='<URL>[,<URL>]',
                        action=ListAction, help="""
                        specify the full announce URLsat least 
                        one is required additional -a adds backup 
                        trackers""")
    parser.add_argument('-c', '--comment', dest='comment', help='add a comment to the metainfo')
    parser.add_argument('-d', '--no-date', dest='no_creation_date', action="store_true", 
                        default=False, help='don\'t write the creation date')
    parser.add_argument('-l', '--piece-length', dest='piece_length', type=int, default=17,
                        help="""set the piece length to 2^n bytes,
                                default is 24, that is 2^24 = 16mb""")
    parser.add_argument('-n', '--name', dest='torrent_name', 
                        help="""set the name of the torrent
                                default is the basename of the target""")
    parser.add_argument('-o', '--output', dest='metainfo_file_path',
                        help="""set the path and filename of the created file
                                default is <name>.torrent""")
    parser.add_argument('-p', '--private', dest='private', action="store_true", 
                        default=False, help='set the private flag')
    parser.add_argument('-t', '--threads', dest='num_threads', type=int, default=2,
                        help='use <n> threads for calculating hashes default is 2')
    parser.add_argument('-v', '--verbose', dest='verbose', action="store_true",
                        default=False, help='be verbose')
    parser.add_argument('-w', '--web-seed', dest='web_seed_list', 
                        metavar='<URL>[,<URL>]', action=ListAction,
                        help='add web seed URLs, additional -w adds more URLs')
    args = parser.parse_args()
    
    return args 

class ListAction(argparse.Action):
    def __call__(self, parser, namespace, value, option_string):
        announce_list = value.strip().split(',')
        cur_value =  getattr(namespace, self.dest)
        if cur_value == None:
            setattr(namespace, self.dest, announce_list)
        else:
            setattr(namespace, self.dest, cur_value + announce_list)
                
if __name__ == "__main__":
    args = process_arguments()
    get_torrent_file(args.target, args.announce_list, args.comment, \
                     args.no_creation_date, args.piece_length, \
                     args.torrent_name, args.private, args.num_threads,\
                     args.web_seed_list, args.metainfo_file_path) 
    #import pprint
    #pprint.pprint(bdecode(open('ubuntu-12.04.3-server-amd64.iso.torrent').read()))