import builtins


_orig_print = builtins.print

n
def hooked_print(*args, **kwargs):
    new_args = tuple(
        str(arg).replace("@SIRZIPP", "@Kenobe21") if isinstance(arg, str) else arg 
        for arg in args
    )
    return _orig_print(*new_args, **kwargs)


builtins.print = hooked_print


import zipp
