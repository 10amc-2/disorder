# NAMD control script

set randomseed ###RANDOM_SEED
set psffile ###PSF_FILE
set pdbfile ###PDB_FILE
set alchpdbfile ###ALCH_PDB_FILE
set fixedpdbfile ###FIXED_PDB_FILE

# -- structure parameters
structure $psffile
coordinates $pdbfile

# -- variables parameters
set temperature 298.15; # temperature in Kelvin
set outname namdrun.namdout; # base name for output files

# -- forcefield parameters
paraTypeCharmm on
parameters /home/anthill/cs86/students/lab2/par_all27_prot_na.prm
parameters /home/anthill/jack/cs86/disorder/psfgen/par_all36_prot.prm
parameters /home/anthill/jack/cs86/disorder/psfgen/par_all36_na.prm
parameters /home/anthill/jack/cs86/disorder/psfgen/toppar_all36_prot_na_combined.str
exclude scaled1-4
1-4scaling 1
cutoff 12
switching on
switchdist 10
pairlistdist 13.5

# -- initialization parameters
temperature $temperature

# -- integrator parameters
timestep 1; ###TIMESTEP; # time step in fs
rigidBonds all; # needs to be 'all' for 2 fs/step
nonbondedFreq 1
fullElectFrequency 1
stepspercycle 10
seed $randomseed; # random number generator seed

# -- io parameters
outputName $outname
outputEnergies 100; ###ENERGY_OUTPUT_FREQ
dcdfreq 100; ###DCD_OUTPUT_FREQ

# -- boundary conditions parameters
###CELLVECTORS
# cellBasisVector1 49.34110155105591 0 0
# cellBasisVector2 0 40.610599231719966 0
# cellBasisVector3 0 0 39.12574949264526
# cellOrigin -3.887061595916748 -0.13141199946403503 -0.6728770732879639
wrapAll on

fixedAtoms     on
fixedAtomsFile $fixedpdbfile
fixedAtomsCol  B

# -- FEP
alch                on
alchType            fep
alchFile            $alchpdbfile
alchCol             B
alchOutfile         namdrun.fepout
alchOutFreq         5
alchEquilSteps      5000
alchElecLambdaStart 1
alchVdwShiftCoeff   0.05

# -- relax structure
alchLambda   0.0
alchLambda2  0.0
minimize 1000

# -- run FEP
set N 10
for {set i 0} {$i < $N} {incr i} {
  alchLambda  [expr $i*1.0/$N]
  alchLambda2 [expr ($i+1)*1.0/$N]
  run 2000000; # 2 ns
}
