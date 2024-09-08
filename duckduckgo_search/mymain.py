from pathlib import Path
import sys

if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).parents[1]))
    __package__ = 'duckduckgo_search'

    from . import myadapter
    myadapter.main()
