import numpy as np

path = r"C:\Users\manue_6t240gh\Dropbox\SunAvangard_Dynamics\0 Ongoing Actions\Solatom\Report\RayTracing\Point_05\stray_rays.dat"

for dtype in ["<f8", ">f8"]:
    data = np.fromfile(path, dtype=dtype, count=30)
    print()
    print(dtype)
    print(data.reshape((-1, 6)))