# sci-business-areas

This repository contains code for creating business areas and supporting data
products.

A business area is a zone containing a spatial cluster of businesses that 
share some common character. "Character" here is defined by 
a set of attributes describing properties of the immediate vicinity. That is,
"localized" attributes indicate, for a given business, things like "there are a lot
of restaurants around here" or "there are a lot of white-collar employers nearby".

In the course of determining business areas, you also create business category labels,
road network data files, 
localized business attributes, inter-business driving distances, and maybe some other stuff.

The code here is set up to support fully automated processing once a small set of 
data files is staged in a certain way. For any given MSA to be processed, you will need
to set up files with the organization and format of things in the directory named
`proto`. I.e. `proto` is a prototype for a correctly staged MSA directory -- you would typically
change its name to the MSA name, like 'boston' or 'duluth'.

The directory named `eero` contains all the required python code. The code is hard-wired 
to operate on a directory structured like the `proto` directory.

All processing gets kicked off using the unix `make` utility. Just get into the 
`proto` directory and type `make`. All processing will then happen automatically, 
God willing.


