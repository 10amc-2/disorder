"""Script to generate jobs for simulations."""

import os
import sys
import tempfile
import logging

try:
    import argparse
    import numpy as np
    from datetime import datetime
    import shutil
except ImportError:
    print('Use python3. Load it using: module load python/3.4.3')
    sys.exit(0)


if sys.version_info[0] < 3:
    print('Needs python3. Load it using: module load python/3.4.3')
    sys.exit(0)


JOB = """#!/bin/bash
# The name of the job, can be anything, simply used when displaying the list of running jobs
#$ -N %s
# Combining output/error messages into one file
#$ -j y
#$ -l vf=2.0G
#$ -l h_rt=72:00:00
# One needs to tell the queue system to use the current directory as the working directory
# Or else the script may fail as it will execute in your top level home directory /home/username
#$ -cwd
# then you tell it retain all environment variables (as the default is to scrub your environment)
#$ -V
# request only nodes that have access to the fast /home/ironfs filesystem
#$ -l ironfs

# start the job with a random delay (< 1 min), so that we do not start all simulations at the exact same time.
sleep %s

/home/anthill/cs86/students/bin/namd2-linux %s &> %s

# create a sym link for this job's logfile in directory where it can be accessed by slackbot
ln -s %s %s

exit 0
"""

BASE_DIR = os.environ['HOME']
CWD = os.path.dirname(os.path.abspath(__file__))

# 40 random ints generated using numpy.random.random_integers(1, 10000, 40)
RANDOM_INTS = [6012, 7146, 1572, 5017, 4932, 3200, 8521, 1315, 2002, 7949, 9286,
               1666, 4724, 4960, 7995, 7073, 3350, 9843, 6611, 1471, 2476, 7387,
               5685, 7999, 6173, 9285, 5784, 7026, 1926, 3658, 2952, 4629,   97,
               5639, 9757, 3595,  281, 5861, 4816, 8265]


def create_job(name, fep, joblogfile):
    dir = "%s/jobs" % BASE_DIR
    if not os.path.exists(dir):
        os.makedirs(dir)

    f = tempfile.NamedTemporaryFile(dir=dir, prefix=name+'-', suffix='.sh', mode='w', delete=False)

    # Add a unix 6 charcter suffix to job name, so that slackbot can find thie
    # job's log file (using its name) when this complets and can look for
    # errors and warnings in the log file.
    name = os.path.basename(f.name)[:-3]  # remove .sh extension

    # log file, saved in BASE_DIR, where slackbot can access it.
    logfile = os.path.join(dir, name + '.log')

    # start the job with a random delay (< 1 min)
    randtime = np.random.random_integers(1, 60)

    f.write(JOB % (name, randtime, fep, joblogfile, joblogfile, logfile))
    return f.name


def create_fep(templatefep, dir, run):
    """Return the name of new fep created for given run in given directory.

    Create a new fep file from template file for this run of simulation.
    The new fep file is saved in the given `dir`.

    Parameters
    ---------
    templatefep : string
        path of template fep to use for the simulation.
    dir : string
        directory where the simulation files (fep.tcl, output) should be saved.
    run : int
        run number.

    Returns
    -------
    outfile : string
        path of fep file to use for this simulation.
    """
    if run >= len(RANDOM_INTS):
        raise ValueError('run number %d higher than our random int set size. '
                         'Increase the random set the set.' % run)
    randomseed = RANDOM_INTS[run]
    fep = os.path.join(dir, 'fep_run%d.tcl' % run)

    # Create a new fep file for this run, replacing the output directory
    # and random seed variables in the template fep file.
    with open(templatefep, 'r') as fin:
        with open(fep, 'w') as fout:
            for line in fin:
                if line.startswith('set outdir'):
                    line = 'set outdir %s;\n' % dir
                elif line.startswith('set randomseed'):
                    line = 'set randomseed %d;\n' % randomseed
                fout.write(line)
    return fep


def main():
    parser = argparse.ArgumentParser(description='Script to generate jobs for simulations. '
                                     'The script saves job in ~/jobs directory and also '
                                     'prints the job path prefix with qsub, so that you can '
                                     'just submit jobs by piping the output to sh '
                                     'Usage: python jobgen.py --nruns 10 | sh')
    parser.add_argument('--nruns',
                        type=int,
                        help='Create jobs for these many runs of simulations')
    parser.add_argument('--run',
                        type=int,
                        help='Create job for this particular run number.')
    parser.add_argument('--fep',
                        type=str,
                        required=True,
                        default=None,
                        help='Template fep.tcl file')

    args = parser.parse_args()

    if args.nruns:
        runs = range(1, args.runs+1, 1)
    elif args.run:
        runs = [args.run]
    else:
        logging.error('Need either --nruns or --run argument.')

    for run in runs:
        rundir = os.path.join(CWD, 'run%d' % run)

        # If run directory already exists, back it up so we don't overwrite it.
        if os.path.exists(rundir):
            timestamp = int(datetime.now().timestamp())
            shutil.move(rundir, '%s.%d.bak' % (rundir, timestamp))

        # create new directory for this run
        os.makedirs(rundir)

        fep = create_fep(args.fep, rundir, run)

        # Job name, to show in qstat and on slack.
        jobname = 'dis_r%d' % run

        # where we want to save output from stdout and stderr for this job.
        joblogfile = os.path.join(rundir, 'namd.stdout')

        print('qsub %s' % create_job(jobname, fep, joblogfile))


if __name__ == "__main__":
    main()
