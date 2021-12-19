#!/usr/bin/env python3
import sys
from doctoshotgun.cli import Application


if __name__ == '__main__':
    try:
        sys.exit(Application().main())
    except KeyboardInterrupt:
        print('Abort.')
        sys.exit(1)
