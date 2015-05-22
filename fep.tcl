# NAMD control script

set outdir ###OUTDIR
set randomseed ###RANDOM_SEED

# -- structure parameters
structure ###PSF_FILE
coordinates ###PDB_FILE

# -- variables parameters
set temperature 298.15; # temperature in Kelvin
set outname $outdir/namdrun.namdout; # base name for output files

# -- forcefield parameters
paraTypeCharmm on
parameters /home/anthill/cs86/students/lab2/par_all27_prot_na.prm
exclude scaled1-4
1-4scaling 1
cutoff 12
switching on
switchdist 10
pairlistdist 13.5

# -- initialization parameters
temperature $temperature

# -- integrator parameters
timestep ###TIMESTEP; # time step in fs
rigidBonds all; # needs to be 'all' for 2 fs/step
nonbondedFreq 1
fullElectFrequency 1
stepspercycle 10
seed $randomseed; # random number generator seed

# -- simulation parameters
langevin on; # do Langevin dynamics?
langevinDamping 5; # damping coefficient (gamma), e.g. 5/ps
langevinTemp $temperature
langevinHydrogen off; # couple Langevin bath to hydrogens?

# -- io parameters
outputName $outname
outputEnergies ###ENERGY_OUTPUT_FREQ
dcdfreq ###DCD_OUTPUT_FREQ

# -- boundary conditions parameters
cellBasisVector1 ###CBV_1X ###CBV_1Y ###CBV_1Z
cellBasisVector2 ###CBV_2X ###CBV_2Y ###CBV_2Z
cellBasisVector3 ###CBV_3X ###CBV_3Y ###CBV_3Z
cellOrigin ###ORIGIN_X ###ORIGIN_Y ###ORIGIN_Z
wrapAll on

# -- constant pressure parameters
useGroupPressure yes
useFlexibleCell no
useConstantRatio no
useConstantArea no
langevinPiston on
langevinPistonTarget 1.01325; # pressure in bar
langevinPistonPeriod 100
langevinPistonDecay 50
langevinPistonTemp $temperature

# -- make sure Ca/Mg ions are not diffusing away from the binding site
fixedAtoms     on
fixedAtomsFile ###FIXED_PDB_FILE
fixedAtomsCol  B

# -- FEP
alch                on
alchType            fep
alchFile            ###ALCHEMY_PDB_FILE
alchCol             B
alchOutfile         $outdir/fep.out
alchOutFreq         ###ALCHEMY_OUTPUT_FREQ
alchEquilSteps      ###ALCHEMY_EQUIL_STEPS
alchElecLambdaStart 1
alchVdwShiftCoeff   0.05
alchDecouple		on

# -- relax structure
alchLambda   0.0
alchLambda2  0.0
minimize ###MINIMIZE_STEPS

# -- run FEP
set N 10
for {set i 0} {$i < $N} {incr i} {
  alchLambda  [expr $i*1.0/$N]
  alchLambda2 [expr ($i+1)*1.0/$N]
  run ###TOTAL_STEPS
}
