#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import numpy as np

try:
    import vedo.vtkclasses as vtk
except ImportError:
    import vtkmodules.all as vtk


__docformat__ = "google"

__doc__ = """
Submodule to work with transformations <br>

![](https://vedo.embl.es/images/basic/pca.png)
"""

__all__ = ["LinearTransform"]

###################################################
def _is_sequence(arg):
    if hasattr(arg, "strip"):
        return False
    if hasattr(arg, "__getslice__"):
        return True
    if hasattr(arg, "__iter__"):
        return True
    return False


###################################################
class LinearTransform:
    """Work with linear transformations."""

    def __init__(self, T=None):
        """Init."""

        if T is None:
            T = vtk.vtkTransform()

        elif isinstance(T, vtk.vtkMatrix4x4):
            S = vtk.vtkTransform()
            S.SetMatrix(T)
            T = S

        elif isinstance(T, vtk.vtkLandmarkTransform):
            S = vtk.vtkTransform()
            S.SetMatrix(T.GetMatrix())
            T = S

        elif _is_sequence(T):
            S = vtk.vtkTransform()
            M = vtk.vtkMatrix4x4()
            n = len(T)
            for i in range(n):
                for j in range(n):
                    M.SetElement(i, j, T[i][j])
            S.SetMatrix(M)
            T = S
        
        self.T = T
        self.T.PostMultiply()
        self.inverse_flag = False


    def __str__(self):
        return "Transformation Matrix 4x4:\n" + str(self.matrix)

    def __repr__(self):
        return "Transformation Matrix 4x4:\n" + str(self.matrix)


    def apply_to(self, obj):
        """Apply transformation."""
        if _is_sequence(obj):
            v = self.T.TransformFloatPoint(obj)
            return np.array(v)

        obj.transform = self

        m = self.T.GetMatrix()
        M = [[m.GetElement(i, j) for j in range(4)] for i in range(4)]
        if np.allclose(M - np.eye(4), 0):
            return

        tp = vtk.vtkTransformPolyDataFilter()
        tp.SetTransform(self.T)
        tp.SetInputData(obj)
        tp.Update()
        out = tp.GetOutput()

        obj.DeepCopy(out)
        obj.point_locator = None
        obj.cell_locator = None
        obj.line_locator = None


    def reset(self):
        """Reset transformation."""
        self.T.Identity()
        return self

    def pop(self):
        """Delete the transformation on the top of the stack 
        and sets the top to the next transformation on the stack."""
        self.T.Pop()
        return self

    def invert(self):
        """Invert transformation."""
        self.T.Inverse()
        self.inverse_flag = bool(self.T.GetInverseFlag())
        return self

    def compute_inverse(self):
        """Compute inverse."""
        return LinearTransform(self.T.GetInverse())

    def clone(self):
        """Clone."""
        return LinearTransform(self.T.Clone())

    def concatenate(self, T, pre_multiply=False):
        """Post multiply."""
        if pre_multiply:
            self.T.PreMultiply()
        self.T.Concatenate(T.T)
        self.T.PostMultiply()
        return self

    def get_concatenated_transform(self, i):
        """Get intermediate matrix by concatenation index."""
        return LinearTransform(self.T.GetConcatenatedTransform(i))

    @property
    def n_concatenated_transforms(self):
        """Get number of concatenated transforms."""
        return self.T.GetNumberOfConcatenatedTransforms()

    def translate(self, p):
        """Translate."""
        self.T.Translate(*p)
        return self

    def scale(self, s=None, origin=True):
        """Scale."""
        if not _is_sequence(s):
            s = [s, s, s]
        if origin is True:
            p = np.array(self.T.GetPosition())
            if np.linalg.norm(p) > 0:
                self.T.Translate(-p)
                self.T.Scale(*s)
                self.T.Translate(p)
            else:
                self.T.Scale(*s)
        elif _is_sequence(origin):
            p = np.array(self.T.GetPosition())
            self.T.Translate(-p)
            self.T.Scale(*s)
            self.T.Translate(p)
        else:
            self.T.Scale(*s)
        return self

    def rotate(self, angle, axis=(1, 0, 0), point=(0, 0, 0), rad=False):
        """
        Rotate around an arbitrary `axis` passing through `point`.

        Example:
            ```python
            from vedo import *
            c1 = Cube()
            c2 = c1.clone().c('violet').alpha(0.5) # copy of c1
            v = vector(0.2,1,0)
            p = vector(1,0,0)  # axis passes through this point
            c2.rotate(90, axis=v, point=p)
            l = Line(-v+p, v+p).lw(3).c('red')
            show(c1, l, c2, axes=1).close()
            ```
            ![](https://vedo.embl.es/images/feats/rotate_axis.png)
        """
        if rad:
            anglerad = angle
        else:
            anglerad = np.deg2rad(angle)
        axis = np.asarray(axis) / np.linalg.norm(axis)
        a = np.cos(anglerad / 2)
        b, c, d = -axis * np.sin(anglerad / 2)
        aa, bb, cc, dd = a * a, b * b, c * c, d * d
        bc, ad, ac, ab, bd, cd = b * c, a * d, a * c, a * b, b * d, c * d
        R = np.array(
            [
                [aa + bb - cc - dd, 2 * (bc + ad), 2 * (bd - ac)],
                [2 * (bc - ad), aa + cc - bb - dd, 2 * (cd + ab)],
                [2 * (bd + ac), 2 * (cd - ab), aa + dd - bb - cc],
            ]
        )
        rv = np.dot(R, self.T.GetPosition() - np.asarray(point)) + point

        if rad:
            angle *= 180.0 / np.pi
        # this vtk method only rotates in the origin of the object:
        self.T.RotateWXYZ(angle, axis[0], axis[1], axis[2])
        self.T.Translate(rv - np.array(self.T.GetPosition()))
        return self

    def _rotatexyz(self, axe, angle, rad, around):
        if rad:
            angle *= 180 / np.pi

        rot = dict(x=self.T.RotateX, y=self.T.RotateY, z=self.T.RotateZ)

        if around is None:
            # rotate around its origin
            rot[axe](angle)
        else:
            # displacement needed to bring it back to the origin
            self.T.Translate(-np.asarray(around))
            rot[axe](angle)
            self.T.Translate(around)
        return self

    def rotate_x(self, angle, rad=False, around=None):
        """
        Rotate around x-axis. If angle is in radians set `rad=True`.

        Use `around` to define a pivoting point.
        """
        return self._rotatexyz("x", angle, rad, around)

    def rotate_y(self, angle, rad=False, around=None):
        """
        Rotate around y-axis. If angle is in radians set `rad=True`.

        Use `around` to define a pivoting point.
        """
        return self._rotatexyz("y", angle, rad, around)

    def rotate_z(self, angle, rad=False, around=None):
        """
        Rotate around z-axis. If angle is in radians set `rad=True`.

        Use `around` to define a pivoting point.
        """
        return self._rotatexyz("z", angle, rad, around)

    def set_position(self, p):
        """Set position."""
        if len(p) == 2:
            p = np.array([p[0], p[1], 0])
        q = np.array(self.T.GetPosition())
        self.T.Translate(p - q)
        return self

    def set_scale(self, s):
        """Set absolute scale."""
        if not _is_sequence(s):
            s = [s, s, s]
        s0, s1, s2 = 1, 1, 1
        b = self.T.GetScale()
        if b[0]:
            s0 = s[0] / b[0]
        if b[1]:
            s1 = s[1] / b[1]
        if b[2]:
            s2 = s[2] / b[2]
        self.T.Scale(s0, s1, s2)
        return self
    
    def get_scale(self):
        """Get current scale."""
        return np.array(self.T.GetScale())

    @property
    def orientation(self):
        """Compute orientation."""
        return np.array(self.T.GetOrientation())

    @property
    def position(self):
        """Compute position."""
        return np.array(self.T.GetPosition())

    @property
    def matrix(self):
        """Get trasformation matrix."""
        m = self.T.GetMatrix()
        M = [[m.GetElement(i, j) for j in range(4)] for i in range(4)]
        return np.array(M)

    @matrix.setter
    def matrix(self, M):
        """Set trasformation by assigning a 4x4 or 3x3 numpy matrix."""
        m = vtk.vtkMatrix4x4()
        n = len(M)
        for i in range(n):
            for j in range(n):
                m.SetElement(i, j, M[i][j])
        self.T.SetMatrix(m)

    @property
    def matrix3x3(self):
        """Get matrix."""
        m = self.T.GetMatrix()
        M = [[m.GetElement(i, j) for j in range(3)] for i in range(3)]
        return np.array(M)


    # TODO: implement this
    def set_orientation(self, newaxis=None, rotation=0, concatenate=False, xyplane=False, rad=False):
    #     """
    #     Set/Get object orientation.

    #     Arguments:
    #         rotation : (float)
    #             rotate object around newaxis.
    #         concatenate : (bool)
    #             concatenate the orientation operation with the previous existing transform (if any)
    #         xyplane : (bool)
    #             make an extra rotation to keep the object aligned to the xy-plane
    #         rad : (bool)
    #             set to True if angle is expressed in radians.

    #     Example:
    #         ```python
    #         from vedo import *
    #         center = np.array([581/2,723/2,0])
    #         objs = []
    #         for a in np.linspace(0, 6.28, 7):
    #             v = vector(cos(a), sin(a), 0)*1000
    #             pic = Picture(dataurl+"images/dog.jpg").rotate_z(10)
    #             pic.orientation(v, xyplane=True)
    #             pic.origin(center)
    #             pic.pos(v - center)
    #             objs += [pic, Arrow(v, v+v)]
    #         show(objs, Point(), axes=1).close()
    #         ```
    #         ![](https://vedo.embl.es/images/feats/orientation.png)

    #     Examples:
    #         - [gyroscope2.py](https://github.com/marcomusy/vedo/tree/master/examples/simulations/gyroscope2.py)

    #         ![](https://vedo.embl.es/images/simulations/50738942-687b5780-11d9-11e9-97f0-72bbd63f7d6e.gif)
    #     """
    #     if self.top is None or self.base is None:
    #         initaxis = (0, 0, 1)
    #     else:
    #         initaxis = utils.versor(self.top - self.base)

    #     newaxis = utils.versor(newaxis)
    #     p = np.array(self.GetPosition())
    #     crossvec = np.cross(initaxis, newaxis)

    #     angleth = np.arccos(np.dot(initaxis, newaxis))

    #     T = vtk.vtkTransform()
    #     if concatenate:
    #         try:
    #             M = self.GetMatrix()
    #             T.SetMatrix(M)
    #         except:
    #             pass
    #     T.PostMultiply()
    #     T.Translate(-p)
    #     if rotation:
    #         if rad:
    #             rotation *= 180.0 / np.pi
    #         T.RotateWXYZ(rotation, initaxis)
    #     if xyplane:
    #         angleph = np.arctan2(newaxis[1], newaxis[0])
    #         T.RotateWXYZ(np.rad2deg(angleph + angleth), initaxis)  # compensation
    #     T.RotateWXYZ(np.rad2deg(angleth), crossvec)
    #     T.Translate(p)

    #     self.actor.SetOrientation(T.GetOrientation())

    #     self.point_locator = None
    #     self.cell_locator = None
        return self
