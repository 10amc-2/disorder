"""Script to estimate completion time for a vmd simulation."""

import sys
import argparse
import time
import os
import numpy as np

if sys.version_info[0] < 3:
    print('Needs python3. Load it using: module load python/3.4.3')
    sys.exit(0)


def steps(file):
    with open(file, 'r') as fp:
        for line in fp:
            pass
    if not line.startswith('WRITING COORDINATES'):
        return -1
    return int(line.strip().split()[-1])


def main():
    parser = argparse.ArgumentParser(description='Script to estimate the '
                                     'completion time for a vmd simulation.')
    parser.add_argument('-f', '--file',
                        type=str,
                        dest='outfile',
                        required=True,
                        help='VMD namd.stdout')

    args = parser.parse_args()

    if not os.path.exists(args.outfile):
        raise IOError('File %s not found.' % args.outfile)

    print('Computing estimated time for simulation. Might take 2-3 minutes.')
    N = 6
    data = np.zeros((N, 2))
    data[0] = steps(args.outfile), time.time()
    j = 1
    while j < N:
        n, t = steps(args.outfile), time.time()
        if n > 0 and n != data[j-1, 0]:
            data[j] = n, t
            j += 1
        time.sleep(10)

    diff = data[1:] - data[:-1]
    speed = diff[:,0] / diff[:,1]

    print('Simulation speed: %.3f (+/- %.3f) steps/sec' % (speed.mean(), speed.std()))

    eta_seconds = 1e7 / speed  # 1e7 = 10 ns
    eta = eta_seconds / 60 / 60 / 24  # eta in days.

    print('Estimated time of 10 nsec: %.3f (+/- %.3f) days' % (eta.mean(), eta.std()))


if __name__ == "__main__":
    main()
