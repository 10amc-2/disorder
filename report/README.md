
# Team disorder project report

The main tex file (also called root) is `main.tex` and paper sections are included from separate tex files.

To generate a pdf run `python lmake.py` (or `./lmake.py`)

See `python lmake.py -h` for usage

```
$ ./lmake.py -h
usage: lmake.py [-h] [-c] [--submit] [--dspace] [--no-view] [--root ROOT]

Latex python based make file.

optional arguments:
  -h, --help   show this help message and exit
  -c, --clean  clean all temporary files after converting
  --submit     Generate SUBMIT version.
  --no-view    Do not open PDF.
  --root ROOT  Main (also called root) .tex file. Default: main.tex
```


## Resources

- [Using advice on git + latex workflow](http://stackoverflow.com/questions/6188780/git-latex-workflow)
