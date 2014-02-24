'''
Created on 2013-12-19

@author: zpfalpc23
'''

_FATAL_EXCEPTION_FORMAT_ERRORS = False

class TgetException(Exception):
    """
    Base Tget Exception

    To correctly use this class, inherit from it and define
    a 'message' property. That message will get printf'd
    with the keyword arguments provided to the constructor.
    """
    message = "An unknown exception occurred"

    def __init__(self, message=None, *args, **kwargs):
        if not message:
            message = self.message
        try:
            message = message % kwargs
        except Exception:
            if _FATAL_EXCEPTION_FORMAT_ERRORS:
                raise
            else:
                # at least get the core message out if something happened
                pass

        super(TgetException, self).__init__(message)
        
class DirCreateFailed(TgetException):
    message ="The directory %(dir_name) can't be created."

class CheckDirPathFailed(TgetException):
    message = "The path %(path_name) is not a directory."
    
class PeerAlreadyRegistered(TgetException):
    message = "The peer %(addr):%(port) has already registered in this master"

class NoSuchUuidException(TgetException):
    message = "No such peer %(uuid) registered in master."
    
class NoSuchPeerException(TgetException):
    message = "No such peer (%(addr):%(port)) registered in master."

class InvalidRequestException(TgetException):
    message = "Master(peer) has receive an invalid request from client: %(reason)."
    
class ConfigError(TgetException):
    message = "No config at %(path)"
    

