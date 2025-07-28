#!/usr/bin/env python3

import sys
import argparse
import numpy as np
from Bio.PDB import PDBParser

def get_atom(structure, chain_id, res_id, atom_name='CA'):
    """
    Return the BioPython Atom object for the given chain, residue number and atom name.
    """
    for model in structure:
        if chain_id not in model:
            continue
        chain = model[chain_id]
        for residue in chain:
            if residue.get_id()[1] == res_id:
                return residue[atom_name]
    raise ValueError(f"Atom {atom_name} in residue {res_id}.{chain_id} not found")

def compute_rotation_matrix(v_source, v_target):
    """
    Compute rotation matrix that aligns v_source to v_target using Rodrigues' formula.
    """
    v_source = v_source / np.linalg.norm(v_source)
    v_target = v_target / np.linalg.norm(v_target)
    axis = np.cross(v_source, v_target)
    norm = np.linalg.norm(axis)
    if norm < 1e-6:
        return np.eye(3)
    axis = axis / norm
    angle = np.arccos(np.clip(np.dot(v_source, v_target), -1.0, 1.0))
    K = np.array([[    0, -axis[2],  axis[1]],
                  [ axis[2],     0, -axis[0]],
                  [-axis[1],  axis[0],    0]], dtype=float)
    R = np.eye(3) + np.sin(angle) * K + (1 - np.cos(angle)) * (K @ K)
    return R

def build_coordinate_map(input_pdb, chain1, res1, chain2, res2, target_axis):
    """
    Parse input_pdb, compute rotation that aligns vector CA(chain1,res1)->CA(chain2,res2)
    to target_axis, and return a dict mapping atom serial numbers to new coords.
    """
    parser = PDBParser(QUIET=True)
    structure = parser.get_structure('prot', input_pdb)

    # pivot atoms
    a1 = get_atom(structure, chain1, res1, 'CA')
    a2 = get_atom(structure, chain2, res2, 'CA')
    coord1 = a1.get_coord()
    coord2 = a2.get_coord()
    vec = coord2 - coord1

    R = compute_rotation_matrix(vec, np.array(target_axis, dtype=float))

    coord_map = {}
    for model in structure:
        for chain in model:
            for residue in chain:
                for atom in residue:
                    serial = atom.get_serial_number()
                    shifted = atom.get_coord() - coord1
                    rotated = R.dot(shifted)
                    new_coord = rotated + coord1
                    coord_map[serial] = new_coord
    return coord_map

def rewrite_pdb_with_new_coords(input_pdb, output_pdb, coord_map):
    """
    Read input_pdb lines, replace coordinates of ATOM/HETATM by those in coord_map,
    and write to output_pdb preserving all other formatting and order.
    """
    with open(input_pdb, 'r') as inp, open(output_pdb, 'w') as out:
        for line in inp:
            if line.startswith(('ATOM  ', 'HETATM')):
                try:
                    serial = int(line[6:11])
                except ValueError:
                    out.write(line)
                    continue
                if serial in coord_map:
                    x, y, z = coord_map[serial]
                    # rebuild line: keep columns 0-30, then new x/y/z, then rest
                    new_line = (
                        line[:30]
                        + f"{x:8.3f}{y:8.3f}{z:8.3f}"
                        + line[54:]
                    )
                    out.write(new_line)
                    continue
            out.write(line)

def parse_args():
    p = argparse.ArgumentParser(
        description='Rotate a protein so vector between two CA atoms aligns to a chosen axis, \
preserving original atom order')
    p.add_argument('input_pdb', help='Input PDB file')
    p.add_argument('output_pdb', help='Output PDB file')
    p.add_argument('chain1', help='Chain ID of first pivot residue')
    p.add_argument('res1', type=int, help='Residue number of first pivot')
    p.add_argument('chain2', help='Chain ID of second pivot residue')
    p.add_argument('res2', type=int, help='Residue number of second pivot')
    p.add_argument(
        '--axis', choices=('X','Y','Z'), default='Z',
        help='Axis to align the vector to (default: Z)'
    )
    return p.parse_args()

if __name__ == '__main__':
    args = parse_args()
    axis_map = {'X': [1,0,0], 'Y': [0,1,0], 'Z': [0,0,1]}
    coord_map = build_coordinate_map(
        args.input_pdb, args.chain1, args.res1,
        args.chain2, args.res2, axis_map[args.axis]
    )
    rewrite_pdb_with_new_coords(args.input_pdb, args.output_pdb, coord_map)
    print(f"Aligned PDB saved to {args.output_pdb}")

