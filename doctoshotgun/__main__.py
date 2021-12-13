import sys

from .cli import Application

def main():
    try:
        sys.exit(Application().main())
    except KeyboardInterrupt:
        print('Abort.')
        sys.exit(1)

if __name__ == '__main__':
    main()
