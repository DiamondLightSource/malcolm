HERE=$(dirname $(readlink -f $0))
dls-python -m unittest discover -s $HERE
