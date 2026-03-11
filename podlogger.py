import environ, threading, logging
def log(msg, originator=__name__):
    logger = logging.getLogger(originator)
    env = environ.Env()
    d = False if "DEBUG" not in env else env.bool("DEBUG")
    thread_name = threading.current_thread().name
    if d:
        logger.info(f"{thread_name}: {msg}")
    else:
        logger.debug(f"{thread_name}: {msg}")

def logwarn(msg, originator=__name__):
    logger = logging.getLogger(originator)
    thread_name = threading.current_thread().name
    logger.warning(f"{thread_name}: {msg}")

def logerr(msg, originator=__name__):
    logger = logging.getLogger(originator)
    thread_name = threading.current_thread().name
    logger.error(f"{thread_name}: {msg}")

def loginfo(msg, originator=__name__):
    logger = logging.getLogger(originator)
    thread_name = threading.current_thread().name
    logger.info(f"{thread_name}: {msg}")