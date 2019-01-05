import sys
import os
from configparser import ConfigParser

def make_tests_coveragerc(base_file, output):
    config = ConfigParser()
    config.read(base_file)
    
    config.setdefault('run', {})
    config['run']['omit'] = '\n'.join((
        '*/scripts/startup/*',
        '*/scripts/modules/*',
        '*/scripts/addons/cycles/*',
        '*/scripts/addons/io_*/*',
    ))
    config['run']['data_file'] = os.path.join(
        os.path.realpath(os.path.dirname(output)),
        '.coverage',
    )
    config.setdefault('paths', {})
    config['paths']['source'] = '\n'.join((
        '*/scripts',
    ))

    with open(output, 'w') as out:
        config.write(out)

def main():
    outdir = sys.argv[1]
    
    argv = iter(sys.argv[1:])
    argv = dict(zip(argv, argv))

    make_tests_coveragerc(
        base_file=argv['--template'],
        output=argv['--output'],
    )


if __name__ == "__main__":
    main()
