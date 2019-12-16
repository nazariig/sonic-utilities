try:
    from sonic_platform.platform import Platform
except ImportError as e:
    raise ImportError("%s - required module not found" % str(e))
