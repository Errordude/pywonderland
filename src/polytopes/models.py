# -*- coding: utf-8 -*-
"""
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Classes for building models of 3D/4D uniform polytopes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This file implements an "interface" between Python and POV-Ray:
given the Coxeter-Dynkin diagram of a polytope P, this file
computes the vertex/edge/face data of P, and export them to a
POV-Ray '.inc' file for rendering.

See the doc: "https://neozhaoliang.github.io/polytopes/"

"""
from itertools import combinations
import numpy as np
import helpers
from todd_coxeter import CosetTable


class BasePolytope(object):
    """
    Base class for building polyhedron and polychoron using
    Wythoff's construction.
    """
    def __init__(self, coxeter_matrix, mirrors, init_dist, extra_relations=()):
        """
        parameters
        ----------
        :coxeter_matrix: Coxeter matrix of the symmetry group of this polytope.

        :mirrors: normal vectors of the mirrors.

        :init_dist: distances between the initial vertex and the mirrors.

        A presentation of a star polytope can be obtained by imposing more
        relations on the generators. For example "(ρ0ρ1ρ2ρ1)^n = 1" for some
        integer n, where n is the number of sides of a hole.

        See Coxeter's article

            "Regular skew polyhedra in three and four dimensions,
            and their topological analogues"

        """
        self.coxeter_matrix = coxeter_matrix
        # reflection transformations about the mirrors
        self.reflections = tuple(helpers.reflection_matrix(v) for v in mirrors)
        # the initial vertex
        self.init_v = helpers.get_init_point(mirrors, init_dist)
        # a mirror is active if and only if the initial vertex is off it
        self.active = tuple(bool(x) for x in init_dist)

        # generators of the symmetry group
        self.symmetry_gens = tuple(range(len(coxeter_matrix)))
        # relations between the generators
        self.symmetry_rels = tuple((i, j) * self.coxeter_matrix[i][j]
                                   for i, j in combinations(self.symmetry_gens, 2))

        self.symmetry_rels += tuple(extra_relations)

        # to be calculated later
        self.vtable = None
        self.num_vertices = None
        self.vertex_coords = []

        self.num_edges = None
        self.edge_indices = []
        self.edge_coords = []

        self.num_faces = None
        self.face_indices = []
        self.face_coords = []

    def build_geometry(self):
        self.get_vertices()
        self.get_edges()
        self.get_faces()

    def get_vertices(self):
        """
        This method computes the following data that will be needed later:
            1. a coset table for the symmetry group.
            2. a complete list of word representations of the symmetry group.
            3. coordinates of the vertices.
        """
        # generators of the stabilizing subgroup that fixes the initial vertex.
        vgens = [(i,) for i, active in enumerate(self.active) if not active]
        self.vtable = CosetTable(self.symmetry_gens, self.symmetry_rels, vgens)
        self.vtable.run()
        self.vwords = self.vtable.get_words()  # get word representations of the vertices
        self.num_vertices = len(self.vwords)
        # use words in the symmetry group to transform the initial vertex to other vertices.
        self.vertex_coords = tuple(self.transform(self.init_v, w) for w in self.vwords)

    def get_edges(self):
        """
        This method computes the indices and coordinates of all edges.

        1. if the initial vertex lies on the i-th mirror then the reflection
           about this mirror fixes v0 and there are no edges of type i.

        2. else v0 and its virtual image v1 about this mirror generates a base
           edge e, the stabilizing subgroup of e is generated by a single word (i,),
           again we use Todd-Coxeter's procedure to get a complete list of word
           representations for the edges of type i and use them to transform e to other edges.
        """
        for i, active in enumerate(self.active):
            if active:  # if there are edges of type i
                egens = [(i,)]  # generators of the stabilizing subgroup that fixes the base edge.
                etable = CosetTable(self.symmetry_gens, self.symmetry_rels, egens)
                etable.run()
                words = etable.get_words()  # get word representations of the edges
                elist = []
                for word in words:
                    v1 = self.move(0, word)
                    v2 = self.move(0, (i,) + word)
                    # avoid duplicates
                    if (v1, v2) not in elist and (v2, v1) not in elist:
                        elist.append((v1, v2))

                self.edge_indices.append(elist)
                self.edge_coords.append([(self.vertex_coords[x], self.vertex_coords[y])
                                         for x, y in elist])
        self.num_edges = sum([len(elist) for elist in self.edge_indices])

    def get_faces(self):
        """
        This method computes the indices and coordinates of all faces.

        The composition of the i-th and the j-th reflection is a rotation
        which fixes a base face f. The stabilizing group of f is generated
        by (i, j) or [(i,), (j,)] depends on whether the two mirrors are both
        active or exactly one of them is active and the they are not perpendicular
        to each other.
        """
        for i, j in combinations(self.symmetry_gens, 2):
            f0 = []
            if self.active[i] and self.active[j]:
                fgens = [(i, j)]
                for k in range(self.coxeter_matrix[i][j]):
                    # rotate the base edge m times to get the base f,
                    # where m = self.coxeter_matrix[i][j]
                    f0.append(self.move(0, (i, j) * k))
                    f0.append(self.move(0, (j,) + (i, j) * k))
            elif self.active[i] and self.coxeter_matrix[i][j] > 2:
                fgens = [(i,), (j,)]
                for k in range(self.coxeter_matrix[i][j]):
                    f0.append(self.move(0, (i, j) * k))
            elif self.active[j] and self.coxeter_matrix[i][j] > 2:
                fgens = [(i,), (j,)]
                for k in range(self.coxeter_matrix[i][j]):
                    f0.append(self.move(0, (i, j) * k))
            else:
                continue

            ftable = CosetTable(self.symmetry_gens, self.symmetry_rels, fgens)
            ftable.run()
            words = ftable.get_words()
            flist = []
            for word in words:
                f = tuple(self.move(v, word) for v in f0)
                if not helpers.check_duplicate_face(f, flist):
                    flist.append(f)

            self.face_indices.append(flist)
            self.face_coords.append([tuple(self.vertex_coords[x] for x in face)
                                    for face in flist])

        self.num_faces = sum([len(flist) for flist in self.face_indices])

    def transform(self, vector, word):
        """Transform a vector by a word in the symmetry group.
        """
        for w in word:
            vector = np.dot(vector, self.reflections[w])
        return vector

    def move(self, vertex, word):
        """Transform a vertex by a word in the symmetry group.
           Return the index of the resulting vertex.
        """
        for w in word:
            vertex = self.vtable[vertex][w]
        return vertex

    def export_pov(self, filename):
        raise NotImplementedError

    def get_latex_format(self, symbol=r"\rho", cols=3, snub=False):
        """Return the words of the vertices in latex format.
           `cols` is the number of columns of the output latex array.
        """
        def to_latex(word):
            if not word:
                return "e"
            else:
                if snub:
                    return "".join(symbol + "_{{{}}}".format(i // 2) for i in word)
                else:
                    return "".join(symbol + "_{{{}}}".format(i) for i in word)

        latex = ""
        for i, word in enumerate(self.vwords):
            if i > 0 and i % cols == 0:
                latex += r"\\"
            latex += to_latex(word)
            if i % cols != cols - 1:
                latex += "&"

        return r"\begin{{array}}{{{}}}{}\end{{array}}".format("l" * cols, latex)


class Polyhedra(BasePolytope):
    """
    Base class for 3d polyhedron.
    """

    def __init__(self, coxeter_matrix, mirrors, init_dist, extra_relations):
        if not len(coxeter_matrix) == len(mirrors) == len(init_dist) == 3:
            raise ValueError("Length error: the inputs must all have length 3")
        super().__init__(coxeter_matrix, mirrors, init_dist, extra_relations)

    def export_pov(self, filename="./povray/polyhedra-data.inc"):
        vstr = "Vertex({})\n"
        estr = "Edge({}, {})\n"
        fstr = "Face({}, {}, vertices_list)\n"
        with open(filename, "w") as f:
            for v in self.vertex_coords:
                f.write(vstr.format(helpers.pov_vector(v)))

            for i, edge_list in enumerate(self.edge_coords):
                for edge in edge_list:
                    f.write(estr.format(i, helpers.pov_vector_list(edge)))

            for i, face_list in enumerate(self.face_coords):
                for face in face_list:
                    f.write(helpers.pov_array(face))
                    f.write(fstr.format(i, len(face)))


class Snub(Polyhedra):
    """
    A snub polyhedra is generated by the subgroup that consists of only
    rotations in the full symmetry group. This subgroup has presentation

        <r, s | r^p = s^q = (rs)^2 = 1>

    where r = ρ0ρ1, s = ρ1ρ2 are two rotations.
    Again we solve all words in this subgroup and then use them to
    transform the initial vertex to get all vertices.
    """

    def __init__(self, coxeter_matrix, mirrors, init_dist=(1.0, 1.0, 1.0)):
        super().__init__(coxeter_matrix, mirrors, init_dist, extra_relations=())
        # the representaion is not in the form of a Coxeter group,
        # we must overwrite the relations.
        self.symmetry_gens = (0, 1, 2, 3)
        self.symmetry_rels = ((0,) * self.coxeter_matrix[0][1],
                              (2,) * self.coxeter_matrix[1][2],
                              (0, 2) * self.coxeter_matrix[0][2],
                              (0, 1), (2, 3))
        # order of the generator rotations
        self.rotations = {(0,): self.coxeter_matrix[0][1],
                          (2,): self.coxeter_matrix[1][2],
                          (0, 2): self.coxeter_matrix[0][2]}

    def get_vertices(self):
        self.vtable = CosetTable(self.symmetry_gens, self.symmetry_rels, coxeter=False)
        self.vtable.run()
        self.vwords = self.vtable.get_words()
        self.num_vertices = len(self.vwords)
        self.vertex_coords = tuple(self.transform(self.init_v, w) for w in self.vwords)

    def get_edges(self):
        for rot in self.rotations:
            elist = []
            e0 = (0, self.move(0, rot))
            for word in self.vwords:
                e = tuple(self.move(v, word) for v in e0)
                if e not in elist and e[::-1] not in elist:
                    elist.append(e)

            self.edge_indices.append(elist)
            self.edge_coords.append([(self.vertex_coords[i], self.vertex_coords[j])
                                    for i, j in elist])
        self.num_edges = sum(len(elist) for elist in self.edge_indices)

    def get_faces(self):
        orbits = (tuple(self.move(0, (0,) * k) for k in range(self.rotations[(0,)])),
                  tuple(self.move(0, (2,) * k) for k in range(self.rotations[(2,)])),
                  (0, self.move(0, (2,)), self.move(0, (0, 2))))
        for f0 in orbits:
            flist = []
            for word in self.vwords:
                f = tuple(self.move(v, word) for v in f0)
                if not helpers.check_duplicate_face(f, flist):
                    flist.append(f)

            self.face_indices.append(flist)
            self.face_coords.append([tuple(self.vertex_coords[v] for v in face)
                                    for face in flist])

        self.num_faces = sum([len(flist) for flist in self.face_indices])

    def transform(self, vertex, word):
        for g in word:
            if g == 0:
                vertex = np.dot(vertex, self.reflections[0])
                vertex = np.dot(vertex, self.reflections[1])
            else:
                vertex = np.dot(vertex, self.reflections[1])
                vertex = np.dot(vertex, self.reflections[2])
        return vertex


class Polychora(BasePolytope):
    """
    Base class for 4d polychoron.
    """

    def __init__(self, coxeter_matrix, mirrors, init_dist, extra_relations):
        if not len(coxeter_matrix) == len(mirrors) == len(init_dist) == 4:
            raise ValueError("Length error: the inputs must all have length 4")
        super().__init__(coxeter_matrix, mirrors, init_dist, extra_relations)

    def export_pov(self, filename="./povray/polychora-data.inc"):
        vstr = "Vertex({})\n"
        estr = "Edge({}, {})\n"
        extent = np.max([np.linalg.norm(helpers.proj3d(v)) for v in self.vertex_coords])

        with open(filename, "w") as f:
            f.write("#declare extent = {};\n".format(extent))

            for v in self.vertex_coords:
                f.write(vstr.format(helpers.pov_vector(v)))

            for i, edge_list in enumerate(self.edge_coords):
                for edge in edge_list:
                    f.write(estr.format(i, helpers.pov_vector_list(edge)))

            for i, face_list in enumerate(self.face_coords):
                for face in face_list:
                    isplane, center, radius, facesize = helpers.get_sphere_info(face)
                    f.write(helpers.pov_array(face))
                    f.write(helpers.export_face(i, face, isplane, center,
                                                radius, facesize))
