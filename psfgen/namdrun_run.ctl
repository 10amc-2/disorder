# NAMD control script

# -- structure parameters
structure 2mx4_m1_full.psf
coordinates 2mx4_m1_full.pdb

# -- variables parameters
set temperature 298.15; # temperature in Kelvin
set outname namdrun_run.namdout; # base name for output files

# -- forcefield parameters
paraTypeCharmm on
parameters par_all36_prot.prm
parameters par_all36_na.prm
parameters toppar_all36_prot_na_combined.str
exclude scaled1-4
1-4scaling 1
cutoff 12
switching on
switchdist 10
pairlistdist 13.5

# -- initialization parameters
temperature $temperature

# -- integrator parameters
timestep 1; # time step in fs
rigidBonds all; # needs to be 'all' for 2 fs/step
nonbondedFreq 1
fullElectFrequency 1
stepspercycle 10

# -- io parameters
outputName $outname
outputEnergies 100
dcdfreq 100

#-- COMMANDS
minimize 1000

