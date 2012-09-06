
def plugin_command(m):
    """ marks an attribute for identifying a plugin method as a command """
    m.cmd = True
    return m

