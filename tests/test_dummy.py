"""
Just a script to make it easy to test testing infrastracture itself.
"""
import coverage
import os
import subprocess
import sys

def subprocess_main():
    print('subprocess_main')

def main():
    if sys.argv[1:] == ['subprocess']:
        print('subprocess')
        cov = coverage.process_startup()
        subprocess_main()
    elif sys.argv[1:] == []:
        print('process')
        subprocess.check_call((sys.executable, __file__, 'subprocess'))

if __name__ == "__main__":
    main()

