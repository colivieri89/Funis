"""Funis: equilibrium and form-finding of spatial compression paths.

Analytical Linear Arch Static Analysis (LASA) of a spatial compression path
under vertical and horizontal loads: supported paths with their lateral
reactions and contact conditions, paths without reactions, free curves found
from the loads and the initial force, and node equilibrium under concentrated
forces. The equations are those of C. Olivieri, *Equilibrium and form-finding
of spatial compression paths under multidirectional loading through Linear
Arch Static Analysis*.

Units: lengths in m, forces in kN, densities in kN per metre of projected
length, angles in degrees at the interface and in radians inside the solvers.
Tension is positive, so compression is S <= 0 and N <= 0.
"""

__version__ = "1.1.0"
__app_name__ = "Funis"
__tagline__ = "Equilibrium and form-finding of spatial compression paths"
__organization__ = "Funis"
