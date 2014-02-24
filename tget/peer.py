"""
"""
import sys
import logging
import traceback
from utils import *
from argparse import ArgumentParser, Action
from twisted.internet import task
from twisted.internet.error import CannotListenError
from urlparse import urlparse

from factory import BTServerFactories
from manager import BTManager, BTConfig

class Peer:
    def __init__(self, save_dir=".", 
                       listen_port=6881, 
                       debug=False):
        """
        """
        self.save_dir = save_dir
        self.tasks = {}
        self.server_pool = BTServerFactories(listen_port)
        while True:
            try:
                reactor.listenTCP(listen_port, self.server_pool)
            except CannotListenError:
                listen_port += 1
            else:
                self.listen_port = listen_port
                break
        
        logging.info('peer listen on the port: %d' % listen_port)

    def add_torrent(self, config):
        info_hash = config.info_hash
        if info_hash in self.tasks:
            logging.info('%s is already in download list' % info_hash)
        else:
            btm = BTManager(self, config)
            self.tasks[info_hash] = btm
            btm.start_download()
            logging.info('new torrent %s' % btm.my_peer_id)
            return info_hash 

    def stop_torrent(self, key):
        info_hash = key
        if info_hash in self.tasks:
            btm = self.tasks[info_hash]
            btm.stop_download()
        
    def remove_torrent(self, key):
        info_hash = key
        if info_hash in self.tasks:
            btm = self.tasks[info_hash]
            btm.exit()

    def stop_all_torrents(self):
        for task in self.tasks.itervalues() :
            task.stop_download()

    def get_status(self):
        """Returns a dictionary of stats on every torrent and total speed.
        """
        status = {}
        for _, bt_manager in self.tasks.iteritems():
            pretty_hash = bt_manager.metainfo.pretty_info_hash
            speed = bt_manager.get_speed()
            num_connections = bt_manager.get_num_connections()

            status[pretty_hash] = {
                "state": bt_manager.status,
                "speed_up": speed["up"],
                "speed_down": speed["down"],
                "num_seeds": num_connections["server"],
                "num_peers": num_connections["client"],
                }
            try:
                status["all"]["speed_up"] += status[pretty_hash]["speed_up"] 
                status["all"]["speed_down"] += status[pretty_hash]["speed_down"] 
            except KeyError:
                status["all"] = {
                    "speed_up": status[pretty_hash]["speed_up"], 
                    "speed_down": status[pretty_hash]["speed_down"]
                    }


        return status

    def start_reactor(self):
        reactor.run()
        
def main(target_list=None, save_dir='.',
         listen_port=6881, debug=False, rpc_port=9527):
    app = Peer(save_dir=save_dir, 
                listen_port=listen_port, 
                debug=debug)
    
    setup_logging(PEER_LOG_PATH, debug)
    for image_url in target_list:
        try:
            url_info = urlparse(image_url)
            logging.info('Adding image url %s:%d' % (url_info.hostname, url_info.port))
            
            config = BTConfig(image_url, url_info.hostname, url_info.port)
            app.add_torrent(config)
        except Exception as e:
            print e
            print traceback.format_exc()
            logging.error("Failed to add %s" % image_url)

    app.start_reactor()
    
class ListAction(Action):
    def __call__(self, parser, namespace, value, option_string):
        target = value.strip().split(',')
        cur_value =  getattr(namespace, self.dest)
        if cur_value == None:
            setattr(namespace, self.dest, target)
        else:
            setattr(namespace, self.dest, cur_value + target)

def console(args):
    usage = 'usage: peer.py [options] url1, url2 ...'
    parser = ArgumentParser(prog='tget')
    parser.add_argument('target_list', help='target image urls', 
                      action=ListAction, metavar='url1, url2...')
    parser.add_argument('-o', '--output_dir', action='store', type=str,
                      dest='save_dir', default=PEER_IMAGE_DIR, 
                      help='save download file to which directory')
    parser.add_argument('-l', '--listen-port', action='store', type=int,
                     dest='listen_port', default=6881, 
                     help='the listen port')
    parser.add_argument("-d", "--debug", action="store_true", default=False,
                    dest="debug", help="enable debug mode") 
    parser.add_argument("-r", '--rpc_port', action="store", type=int,
                    dest="rpc_port", default=9527, help="the rpc operation port") 

    args = parser.parse_args(args)
    main(args.target_list, args.save_dir, args.listen_port,
             args.debug, args.rpc_port)
    
if __name__ == '__main__':
    console(sys.argv[1:])
