if [ $# -eq 0 ]
  then
    echo "No arguments supplied"
    exit -1
fi

echo "
mol load pdb $1
source ~cs86/students/lab2/get_cell.tcl
get_cell
" | ~cs86/students/bin/vmd  -dispdev text -eofexit | grep cell
