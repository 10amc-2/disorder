"""Script to generate jobs for simulations."""

import os
import sys
import tempfile
import glob
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
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

# If we want to store output on ironfs
# OUTPUT_DIR = '/home/ironfs/scratch/shrirang/projects/disorder'

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


def string_after(line, after, till=[',', ' ', '\n']):
    """Return string in line `after` substring until one of the `till' substrings."""
    i = line.find(after)
    if i == -1:
        return ''
    value = ''
    for c in line[i+len(after):]:
        if c in till:
            break
        else:
            value += c
    return value


def ar_resources(arid):
    """Return resources reserved in given arid.

    Parameters
    ----------
    arid : int
        ARID

    Return
    ------
    vf : string
        memory per thread
    h_rt : int
        time limit in seconds for the job
    cores : int
        number of assigned cores for this AR.
    hostname : string
        hostname requested in AR. If none is requested, '' is returned.
    """
    cmd = 'qrstat -ar %d' % arid
    out, err = run_shell_command(cmd)
    if not out:
        raise ValueError('No AR found for %d' % arid)

    for line in out.split('\n'):
        if line.startswith('end_time'):
            end_time = datetime.strptime(' '.join(line.split()[1:]), '%m/%d/%Y %H:%M:%S').timestamp()
        elif line.startswith('resource_list'):
            if line.find('hostname') > 0:
                hostname = string_after(line, 'hostname=')
            if line.find('virtual_free') > 0:
                vf = string_after(line, 'virtual_free=')
            if line.find('h_rt') > 0:
                h_rt = int(string_after(line, 'h_rt='))
        elif line.startswith('granted_parallel_environment'):
            cores = int(string_after(line, 'smp slots '))

    dt = end_time - datetime.now().timestamp() - 600
    h_rt = min(h_rt, dt)
    return vf, h_rt, cores, hostname


JOB_MULTI_CORE = """#!/bin/bash
#$ -N %s
#$ -cwd
#$ -j y
#$ -S /bin/bash
#$ -pe smp %s
#$ -l vf=%s
#$ -l %s
#$ -l h_rt=%s
#$ -q short,medium,long
%s

# start the job with a random delay (< 1 min), so that we do not start simulations submitted together at the exact same time.
sleep %s

echo "Got $NSLOTS slots on: " "`cat $PE_HOSTFILE`"

/home/grigoryanlab/library/bin/charmrun +p$NSLOTS /home/grigoryanlab/library/bin/namd2 %s &> %s

# create a sym link for this job's logfile in directory where it can be accessed by slackbot
ln -s %s %s

exit 0
"""

JOB_SINGLE_CORE = """#!/bin/bash
#$ -N %s
#$ -cwd
#$ -j y
#$ -S /bin/bash
#$ -l vf=%s
#$ -l %s
#$ -l h_rt=%s
#$ -q short,medium,long
%s

# start the job with a random delay (< 1 min), so that we do not start all simulations at the exact same time.
sleep %s

/home/anthill/cs86/students/bin/namd2-linux %s &> %s

# create a sym link for this job's logfile in directory where it can be accessed by slackbot
ln -s %s %s

exit 0
"""


def create_job(name, fep, joblogfile, time='24:00:00', cores=16, arid=None, mem='2G', hostname=None):
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
    arid : int, optional, default None
        Advanced Reservation ID (ARID), if we have one.
        If an ARID is given, the resources for this job are set to the resources
        mentioned in the ARID.
    mem : string, optional, default 2G
        memory to use per thread
    hostname : string, optional, default None
        hostname to use. If None, '-l ironfs' is used instead

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

    if arid:
        ar = '#$ -ar %d' % arid
        mem, time, cores, hostname = ar_resources(arid)
    else:
        ar = ''

    if hostname:
        hostname = 'hostname=%s' % hostname
    else:
        hostname = 'ironfs'

    if cores > 1:
        f.write(JOB_MULTI_CORE % (name, cores, mem, hostname, time, ar, randtime, fep, joblogfile, joblogfile, logfile))
    elif cores == 1:
        f.write(JOB_SINGLE_CORE % (name, mem, hostname, time, ar, randtime, fep, joblogfile, joblogfile, logfile))
    else:
        raise ValueError('Invalid cores value: %f' % cores)
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


def get_rundir(pdb, run, suffix):
    """Return directory to use for this simulation run.

    Parameters
    ----------
    pdb : string
        pdb file path.
    run : int
        run number. If 0 (or less than 0), this method finds all (say n) rundirs
        corresponding to these parameters and uses run = n + 1.
    suffix : string
        suffix to use in run dir.

    Returns
    -------
    rundir : string
        path of run directory.
    """
    if run <= 0:
        pattern = os.path.join(OUTPUT_DIR, '%s_run*%s' % (filebasename(pdb), suffix))
        files = glob.glob(pattern)
        run = len(files) + 1
    rundir = os.path.join(OUTPUT_DIR, '%s_run%d%s' % (filebasename(pdb), run, suffix))

    # If run directory already exists, back it up so we don't overwrite it.
    if os.path.exists(rundir):
        timestamp = int(datetime.now().timestamp())
        shutil.move(rundir, '%s.%d.bak' % (rundir, timestamp))

    # create new directory for this run
    os.makedirs(rundir)
    return rundir


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
    parser.add_argument('--arid',
                        type=int,
                        default=None,
                        help='advanced reservatoin ID.')

    args = parser.parse_args()

    if args.nruns:
        runs = range(1, args.nruns+1, 1)
    elif args.run:
        runs = [args.run]
    else:
        runs = [-1]

    if args.suffix:
        # Separate the suffix in job name with underscore.
        args.suffix = '_' + args.suffix

    psffile = args.pdb[:-3] + 'psf'
    if not os.path.exists(psffile):
        raise IOError('File %s not found' % psffile)

    for run in runs:
        # Get a directory where we store the pdb, psf, and fep.tcl files, used
        # for this simulation run.
        # rundir name is added to job name.
        rundir = get_rundir(args.pdb, run, args.suffix)

        # copy pdb and psf files to run directory
        for fname in [args.pdb, psffile]:
            newfname = os.path.join(rundir, os.path.basename(fname))
            shutil.copy(fname, newfname)

        if run >= len(RANDOM_INTS):
            raise ValueError('run number %d higher than our random int set size. '
                             'Increase the random set the set.' % run)

        fep = create_fep(args.fep, rundir, args.pdb, RANDOM_INTS[run])

        # Job name, to show in qstat and on slack.
        jobname = 'dis_%s' % os.path.basename(rundir)

        # where we want to save output from stdout and stderr for this job.
        joblogfile = os.path.join(rundir, 'namd.stdout')

        job = create_job(jobname, fep, joblogfile, time=args.time, cores=args.cores, arid=args.arid)
        print('qsub %s' % job)

        # Also copy job to run dir, so we know which script we used for this simulation.
        shutil.copy(job, os.path.join(rundir, os.path.basename(job)))

if __name__ == "__main__":
    main()
