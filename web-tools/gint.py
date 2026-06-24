
class Font:
    def __init__(self, *args):
        self.args = args
    def __repr__(self):
        return f"Font({self.args})"

def font(*args):
    return Font(*args)

def image(*args):
    pass
