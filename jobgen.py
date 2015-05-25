"""Script to generate jobs for simulations."""

import os
import sys
import tempfile
import logging

from subprocess import Popen, PIPE

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


#####################################################################
# Template job from gevorg
#####################################################################
# #!/bin/sh
# #$ -cwd
# #$ -j y
# #$ -S /bin/bash
# #$ -pe smp 16
# #$ -q long
# #$ -l vf=2G
# #$ -l hostname='gridiron*'
# #$ -l ironfs
# #$ -l h_rt=240:00:00

# echo "Got $NSLOTS slots on: " "`cat $PE_HOSTFILE`"

# /home/grigoryanlab/library/bin/charmrun +p$NSLOTS /home/grigoryanlab/library/bin/namd2 namdrun_run.ctl >& namdrun_run.out

# exit 0
#####################################################################

BASE_DIR = os.environ['HOME']
CWD = os.path.dirname(os.path.abspath(__file__))

# 40 random ints generated using numpy.random.random_integers(1, 10000, 40)
RANDOM_INTS = [6012, 7146, 1572, 5017, 4932, 3200, 8521, 1315, 2002, 7949, 9286,
               1666, 4724, 4960, 7995, 7073, 3350, 9843, 6611, 1471, 2476, 7387,
               5685, 7999, 6173, 9285, 5784, 7026, 1926, 3658, 2952, 4629,   97,
               5639, 9757, 3595,  281, 5861, 4816, 8265]


def run_shell_command(cmd):
    """Run a shell command and return output and error log."""
    if isinstance(cmd, str):
        cmd = cmd.split()
    p = Popen(cmd, stdout=PIPE, stderr=PIPE)
    out, err = p.communicate()
    if sys.version_info[0] == 3:
        out = out.decode('utf-8')
        err = err.decode('utf-8')
    return out.strip(), err


def get_vols(pdb):
    """Return a string with cell vectors for the solvated pdb file."""
    script = 'getsize.sh'
    if not os.path.exists(script):
        raise ValueError('Script getsize.sh not found in current directory.')
    cmd = 'sh %s %s' % (script, pdb)
    out, err = run_shell_command(cmd)
    # if out == '':
    #     raise ValueError('Could not find cell vectors for the solvated pdb.')
    return out


def filebasename(fname):
    """Return file basename without extension."""
    fname = os.path.basename(fname)
    return '.'.join(fname.split('.')[:-1])


def queue(time):
    """Return queue for the given time in string. Time format: %H:%M:%S."""
    if time.find(':') == -1 or len(time.split(':')) != 3:
        raise ValueError('Time %s is not valid format: %H:%M:%S' % time)

    fields = time.split(':')
    hr = int(fields[0])
    mn = int(fields[1])
    sec = int(fields[2])
    seconds = hr * 60 * 60 + mn * 60 + sec
    if seconds <= 10800:  # 3 hour
        return 'short'
    elif seconds <= 86400:  # 24 hour
        return 'medium'
    else:
        return 'long'


JOB = """#!/bin/bash
#$ -N %s
#$ -cwd
#$ -j y
#$ -S /bin/bash
#$ -pe smp %s
#$ -l vf=2.0G
#$ -l ironfs
#$ -l h_rt=%s
#$ -q %s

# start the job with a random delay (< 1 min), so that we do not start simulations submitted together at the exact same time.
sleep %s

echo "Got $NSLOTS slots on: " "`cat $PE_HOSTFILE`"

/home/grigoryanlab/library/bin/charmrun +p$NSLOTS /home/grigoryanlab/library/bin/namd2 %s &> %s

# create a sym link for this job's logfile in directory where it can be accessed by slackbot
ln -s %s %s

exit 0
"""


def create_job(name, fep, joblogfile, time='24:00:00', cores=16):
    """Create a job (.sh) to submit to anthill and save it in ~/jobs directory.

    Parameters
    ----------
    name : string
        Job name prefix
    fep : string
        fep file path
    joblogfile : string
        path of log file where the VMD simulation output should be stored.
    time : string, optional, default 24:00:00
        time limit for the job
    cores : int, optional, default 16
        number of cores to request for this job.

    Return
    ------
    out : string
        Path of the created job script.
    """
    dir = "%s/jobs" % BASE_DIR
    if not os.path.exists(dir):
        os.makedirs(dir)

    f = tempfile.NamedTemporaryFile(dir=dir, prefix=name+'-', suffix='.sh', mode='w', delete=False)

    # Add a unix 6 charcter suffix to job name, so that slackbot can find thie
    # job's log file (using its name) when this complets and can look for
    # errors and warnings in the log file.
    name = filebasename(f.name)

    # log file, saved in BASE_DIR, where slackbot can access it.
    logfile = os.path.join(dir, name + '.log')

    # start the job with a random delay (< 1 min)
    randtime = np.random.random_integers(1, 60)

    f.write(JOB % (name, cores, time, queue(time), randtime, fep, joblogfile, joblogfile, logfile))
    return f.name


def create_fep(templatefep, dir, pdb, randomseed):
    """Return the name of new fep created in given directory.

    Create a new fep file from template file for simulation.
    The new fep file is saved in the directory where pdb file is saved.
    This method expects the corresponding psf file to be in the same
    directory as the pdb file, otherwise it raises a ValueError.

    This method replaces following things in the templatefep:
    - random seed
    - pdb file name
    - psf file name
    - cell vectors : the are determined using the getsize.sh script.

    Parameters
    ---------
    templatefep : string
        path of template fep to use for the simulation.
    dir : string
        directory where the fep file should be created.
        This should be the run directory.
    pdb : string
        pdb file path.
    randomseed : int
        use this random seed in the fep tcl.

    Returns
    -------
    outfile : string
        path of fep file to use for this simulation.
    """
    fep = os.path.join(dir, 'fep.tcl')

    # Create a new fep file for this run, replacing the output directory
    # and random seed variables in the template fep file.
    cellvectors = get_vols(pdb)
    basename = filebasename(pdb)
    with open(templatefep, 'r') as fin:
        with open(fep, 'w') as fout:
            for line in fin:
                if line.startswith('set outdir'):
                    line = 'set outdir %s;\n' % dir
                elif line.startswith('set randomseed'):
                    line = 'set randomseed %d;\n' % randomseed
                elif line.startswith('set psffile'):
                    line = 'set psffile %s.psf;\n' % basename
                elif line.startswith('set pdbfile'):
                    line = 'set pdbfile %s.pdb;\n' % basename
                elif line.startswith('###CELLVECTORS'):
                    line = '%s\n' % cellvectors
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
    parser.add_argument('--pdb',
                        type=str,
                        required=True,
                        default=None,
                        help='PDB file.')
    parser.add_argument('--time',
                        type=str,
                        default='24:00:00',
                        help='Time limit for the job. Default 24:00:00')
    parser.add_argument('--cores',
                        type=int,
                        default=1,
                        help='Number of cores to request for the job. Default 1.')
    parser.add_argument('--suffix',
                        type=str,
                        default='',
                        help='Suffix to add to job name and rundir. Default: None')

    args = parser.parse_args()

    if args.nruns:
        runs = range(1, args.nruns+1, 1)
    elif args.run:
        runs = [args.run]
    else:
        logging.error('Need either --nruns or --run argument.')

    basename = filebasename(args.pdb)  # pdb file name without the extension.
    psffile = os.path.join(os.path.dirname(args.pdb), '%s.psf' % basename)
    if not os.path.exists(psffile):
        raise IOError('File %s not found' % psffile)

    for run in runs:
        # Create a directory where we store the pdb, psf, and fep.tcl files, used
        # for this simulation run.
        # rundir name is added to job name.
        rundir = os.path.join(CWD, '%s_run%d_%s' % (basename, run, args.suffix))

        if run >= len(RANDOM_INTS):
            raise ValueError('run number %d higher than our random int set size. '
                             'Increase the random set the set.' % run)
        randomseed = RANDOM_INTS[run]

        # If run directory already exists, back it up so we don't overwrite it.
        if os.path.exists(rundir):
            timestamp = int(datetime.now().timestamp())
            shutil.move(rundir, '%s.%d.bak' % (rundir, timestamp))

        # create new directory for this run
        os.makedirs(rundir)

        # copy pdb and psf files to run directory
        for fname in [args.pdb, psffile]:
            newfname = os.path.join(rundir, os.path.basename(fname))
            shutil.copy(fname, newfname)

        fep = create_fep(args.fep, rundir, args.pdb, randomseed)

        # Job name, to show in qstat and on slack.
        jobname = 'dis_%s' % os.path.basename(rundir)

        # where we want to save output from stdout and stderr for this job.
        joblogfile = os.path.join(rundir, 'namd.stdout')

        job = create_job(jobname, fep, joblogfile, time=args.time, cores=args.cores)
        print('qsub %s' % job)

        # Also copy job to run dir, so we know which script we used for this simulation.
        shutil.copy(job, os.path.join(rundir, os.path.basename(job)))

if __name__ == "__main__":
    main()
