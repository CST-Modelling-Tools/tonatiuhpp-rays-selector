import numpy as np

data = np.fromfile(
    r"C:\Users\manue_6t240gh\Dropbox\SunAvangard_Dynamics\0 Ongoing Actions\Solatom\Report\RayTracing\Point_05\stray_rays.dat",
    dtype=">f8"
).reshape((-1,6))

d = data[:,3:6]

norms = np.linalg.norm(d, axis=1)

print("min =", norms.min())
print("max =", norms.max())
print("mean =", norms.mean())
print("std =", norms.std())