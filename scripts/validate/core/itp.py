"""A linter for GROMACS topology (.itp) files carrying Martini parameters.

Scope, stated plainly because it matters for how results are read: this
validates **syntax, internal consistency, and force-field compatibility**. It
does not and cannot validate whether a parameter set reproduces experiment.
Scientific validation remains expert review, and eventually the per-parameter
validation metadata carried by the Martini Database.

What it does catch is the class of defect that expert review reliably misses
because it requires arithmetic rather than judgement: an atom index one past
the end of the molecule, a bead name that is not valid Martini 3, a molecule
whose partial charges sum to 0.9999 instead of 1, a pair of beads given both a
bond and a constraint, or a fragment silently disconnected from the rest of the
molecule.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Martini 3 bead-type grammar (Souza et al., Nat. Methods 2021):
#   [size prefix] class [polarity level] [labels]
# e.g. P6, SN4a, TC5, Q5n, SP1d, W, SW, TW.
#
# A grammar rather than a hardcoded list because the definitive list lives in
# martini_v300.itp, which is distributed through the S3 download library rather
# than committed here; a hand-vendored copy would silently drift from the force
# field. So a name that fits the grammar but names no real bead is a warning,
# not an error.
BEAD_TYPE_RE = re.compile(
    r"^(?P<size>[ST])?"
    r"(?P<klass>P|N|C|X|Q|D|W|U)"
    r"(?P<level>[1-6])?"
    r"(?P<labels>[adehnpqrvw+-]*)$"
)

SECTION_RE = re.compile(r"^\[\s*(?P<name>[A-Za-z_0-9]+)\s*\]")
PREPROCESSOR_RE = re.compile(r"^#\s*(?P<directive>\w+)")

KNOWN_SECTIONS = {
    "moleculetype", "atoms", "bonds", "pairs", "pairs_nb", "angles",
    "dihedrals", "constraints", "exclusions", "settles", "virtual_sites1",
    "virtual_sites2", "virtual_sites3", "virtual_sites4", "virtual_sitesn",
    "position_restraints", "distance_restraints", "dihedral_restraints",
    "orientation_restraints", "angle_restraints", "angle_restraints_z",
    "defaults", "atomtypes", "bondtypes", "constrainttypes", "angletypes",
    "dihedraltypes", "nonbond_params", "pairtypes", "implicit_genborn_params",
    "system", "molecules", "cmaptypes",
}

# Sections whose first N columns are atom indices into [ atoms ].
INDEX_COLUMNS = {
    "bonds": 2, "pairs": 2, "pairs_nb": 2, "angles": 3, "dihedrals": 4,
    "constraints": 2, "exclusions": None, "settles": 1,
    "virtual_sites1": 2, "virtual_sites2": 3, "virtual_sites3": 4,
    "virtual_sites4": 5, "virtual_sitesn": None,
    "position_restraints": 1, "angle_restraints": 4,
    "distance_restraints": 2, "dihedral_restraints": 4,
}

# Physically plausible ranges for Martini bonded parameters. Outside these a
# value is usually a unit error or a typo, so they are warnings, not errors.
BOND_LENGTH_NM = (0.05, 1.5)
BOND_FORCE_KJ = (0.0, 100_000.0)
ANGLE_DEGREES = (0.0, 180.0)


@dataclass
class Atom:
    index: int
    type: str
    resnr: int
    residue: str
    name: str
    cgnr: int
    charge: float
    mass: float | None
    line: int


@dataclass
class Molecule:
    name: str
    nrexcl: int | None
    line: int
    atoms: list[Atom] = field(default_factory=list)
    # section name -> list of (line_number, [fields])
    sections: dict[str, list[tuple[int, list[str]]]] = field(default_factory=dict)


@dataclass
class ItpIssue:
    rule: str
    severity: str          # "error" | "warning"
    line: int | None
    message: str
    hint: str | None = None


def strip_comment(line: str) -> str:
    """Remove a `;` comment. Semicolons are never quoted in .itp files."""
    index = line.find(";")
    return line if index == -1 else line[:index]


def parse_itp(text: str) -> tuple[list[Molecule], list[ItpIssue]]:
    """Parse into molecules, reporting structural problems as it goes.

    Preprocessor directives are recorded but not expanded: expanding
    `#include` would require the whole force field, which lives in S3. Their
    presence is reported so a reviewer knows the file is not self-contained.
    """
    issues: list[ItpIssue] = []
    molecules: list[Molecule] = []

    current_section: str | None = None
    current_molecule: Molecule | None = None
    pending_continuation = ""

    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = strip_comment(raw).rstrip()

        if pending_continuation:
            line = pending_continuation + " " + line.strip()
            pending_continuation = ""
        if line.endswith("\\"):
            pending_continuation = line[:-1].rstrip()
            continue

        stripped = line.strip()
        if not stripped:
            continue

        directive = PREPROCESSOR_RE.match(stripped)
        if directive:
            name = directive.group("directive")
            if name == "include":
                issues.append(ItpIssue(
                    "itp.include-directive", "warning", lineno,
                    f"File uses #{name}, so it is not self-contained.",
                    "Included files cannot be checked here. Make sure every "
                    "dependency is either standard Martini or submitted "
                    "alongside this file.",
                ))
            continue

        section = SECTION_RE.match(stripped)
        if section:
            current_section = section.group("name").lower()
            if current_section not in KNOWN_SECTIONS:
                issues.append(ItpIssue(
                    "itp.unknown-section", "error", lineno,
                    f"Unknown section [ {current_section} ].",
                    "Check the spelling against the GROMACS topology format.",
                ))
            elif current_section == "moleculetype":
                current_molecule = None   # created when its data line arrives
            elif current_molecule is not None:
                current_molecule.sections.setdefault(current_section, [])
            continue

        fields = stripped.split()

        if current_section == "moleculetype":
            if len(fields) < 2:
                issues.append(ItpIssue(
                    "itp.moleculetype-fields", "error", lineno,
                    "[ moleculetype ] needs a name and an nrexcl value.",
                    "For example:  MOLNAME   1",
                ))
                nrexcl = None
            else:
                try:
                    nrexcl = int(fields[1])
                except ValueError:
                    nrexcl = None
                    issues.append(ItpIssue(
                        "itp.nrexcl-not-integer", "error", lineno,
                        f"nrexcl must be a whole number, found {fields[1]!r}.",
                        "Martini topologies normally use 1.",
                    ))
                else:
                    if not 0 <= nrexcl <= 3:
                        issues.append(ItpIssue(
                            "itp.nrexcl-range", "warning", lineno,
                            f"nrexcl is {nrexcl}; Martini topologies normally "
                            f"use 1.",
                            "Values above 3 exclude far more pairs than "
                            "intended.",
                        ))
            current_molecule = Molecule(
                name=fields[0] if fields else "?", nrexcl=nrexcl, line=lineno
            )
            molecules.append(current_molecule)
            continue

        if current_molecule is None:
            continue

        if current_section == "atoms":
            atom = _parse_atom(fields, lineno, issues)
            if atom:
                current_molecule.atoms.append(atom)
            continue

        if current_section:
            current_molecule.sections.setdefault(current_section, []).append(
                (lineno, fields)
            )

    return molecules, issues


def _parse_atom(fields, lineno, issues) -> Atom | None:
    # nr type resnr residue atom cgnr charge [mass]
    if len(fields) < 7:
        issues.append(ItpIssue(
            "itp.atom-fields", "error", lineno,
            f"[ atoms ] row has {len(fields)} column(s); at least 7 are "
            f"required.",
            "Columns are: nr type resnr residue atom cgnr charge [mass]",
        ))
        return None
    try:
        index = int(fields[0])
        resnr = int(fields[2])
        cgnr = int(fields[5])
        charge = float(fields[6])
    except ValueError:
        issues.append(ItpIssue(
            "itp.atom-numeric", "error", lineno,
            "An [ atoms ] column that must be numeric is not.",
            "Columns 1 (nr), 3 (resnr), 6 (cgnr) are integers and column 7 "
            "(charge) is a number.",
        ))
        return None

    mass = None
    if len(fields) >= 8:
        try:
            mass = float(fields[7])
        except ValueError:
            issues.append(ItpIssue(
                "itp.atom-mass", "error", lineno,
                f"Mass column is not a number: {fields[7]!r}.", None,
            ))

    return Atom(index, fields[1], resnr, fields[3], fields[4], cgnr, charge,
                mass, lineno)


def check_molecule(mol: Molecule) -> list[ItpIssue]:
    issues: list[ItpIssue] = []
    issues.extend(_check_atoms(mol))
    issues.extend(_check_indices(mol))
    issues.extend(_check_bonded_consistency(mol))
    issues.extend(_check_connectivity(mol))
    return issues


def _check_atoms(mol: Molecule) -> list[ItpIssue]:
    issues: list[ItpIssue] = []

    if not mol.atoms:
        return [ItpIssue(
            "itp.no-atoms", "error", mol.line,
            f"Molecule {mol.name!r} has no [ atoms ] section.",
            "Every moleculetype needs at least one atom.",
        )]

    for position, atom in enumerate(mol.atoms, start=1):
        if atom.index != position:
            issues.append(ItpIssue(
                "itp.atom-numbering", "error", atom.line,
                f"Atom numbering jumps: expected {position}, found "
                f"{atom.index}.",
                "Atom numbers must run 1, 2, 3, ... with no gaps. GROMACS "
                "uses row position, so a gap silently shifts every bonded "
                "index after it.",
            ))
            break

        if not BEAD_TYPE_RE.match(atom.type):
            issues.append(ItpIssue(
                "itp.bead-type-grammar", "warning", atom.line,
                f"Bead type {atom.type!r} does not look like a Martini 3 bead "
                f"name.",
                "Expected [S|T]<class><level><labels>, e.g. P6, SN4a, TC5, "
                "Q5n, W.",
            ))

        if atom.mass is not None and atom.mass < 0:
            issues.append(ItpIssue(
                "itp.negative-mass", "error", atom.line,
                f"Atom {atom.index} has a negative mass ({atom.mass}).", None,
            ))

    total_charge = sum(a.charge for a in mol.atoms)
    if abs(total_charge - round(total_charge)) > 1e-4:
        issues.append(ItpIssue(
            "itp.non-integral-charge", "warning", mol.line,
            f"Molecule {mol.name!r} has a total charge of {total_charge:.4f}, "
            f"which is not a whole number.",
            "Almost always a typo in one partial charge. A non-integral "
            "system charge cannot be neutralised exactly.",
        ))

    return issues


def _check_indices(mol: Molecule) -> list[ItpIssue]:
    issues: list[ItpIssue] = []
    natoms = len(mol.atoms)

    for section, rows in mol.sections.items():
        count = INDEX_COLUMNS.get(section)
        if count is None and section not in ("exclusions", "virtual_sitesn"):
            continue

        for lineno, fields in rows:
            if section in ("exclusions", "virtual_sitesn"):
                # Every numeric leading field is an atom index. For
                # virtual_sitesn the second field is the function type.
                candidates = fields[:1] if section == "virtual_sitesn" else fields
                candidates = [f for f in candidates if f.lstrip("-").isdigit()]
                if section == "virtual_sitesn":
                    candidates += [f for f in fields[2:] if f.lstrip("-").isdigit()]
            else:
                candidates = fields[:count]

            for value in candidates:
                try:
                    index = int(value)
                except ValueError:
                    issues.append(ItpIssue(
                        "itp.index-not-integer", "error", lineno,
                        f"[ {section} ] expects an atom index but found "
                        f"{value!r}.", None,
                    ))
                    continue
                if index < 1 or index > natoms:
                    issues.append(ItpIssue(
                        "itp.index-out-of-range", "error", lineno,
                        f"[ {section} ] refers to atom {index}, but the "
                        f"molecule has {natoms} atom(s).",
                        "Atom indices are 1-based and local to the "
                        "moleculetype. This would crash grompp, or silently "
                        "bond the wrong beads.",
                    ))
    return issues


def _check_bonded_consistency(mol: Molecule) -> list[ItpIssue]:
    issues: list[ItpIssue] = []
    natoms = len(mol.atoms)

    def pairs_of(section: str) -> dict[tuple[int, int], int]:
        found: dict[tuple[int, int], int] = {}
        for lineno, fields in mol.sections.get(section, []):
            if len(fields) < 2:
                continue
            try:
                i, j = int(fields[0]), int(fields[1])
            except ValueError:
                continue
            if i == j:
                issues.append(ItpIssue(
                    "itp.self-bond", "error", lineno,
                    f"[ {section} ] connects atom {i} to itself.", None,
                ))
                continue
            key = (min(i, j), max(i, j))
            if key in found:
                issues.append(ItpIssue(
                    "itp.duplicate-bonded", "error", lineno,
                    f"[ {section} ] defines the pair {key[0]}-{key[1]} twice "
                    f"(first at line {found[key]}).",
                    "Duplicate entries are applied cumulatively, doubling the "
                    "effective force constant.",
                ))
            else:
                found[key] = lineno
        return found

    bonds = pairs_of("bonds")
    constraints = pairs_of("constraints")

    for key, lineno in constraints.items():
        if key in bonds:
            issues.append(ItpIssue(
                "itp.bond-and-constraint", "error", lineno,
                f"Atoms {key[0]}-{key[1]} have both a bond (line "
                f"{bonds[key]}) and a constraint.",
                "The geometry is over-determined. Keep one of the two.",
            ))

    for lineno, fields in mol.sections.get("bonds", []):
        if len(fields) >= 5:
            _range_check(issues, lineno, "bond length", fields[3], BOND_LENGTH_NM, "nm")
            _range_check(issues, lineno, "force constant", fields[4], BOND_FORCE_KJ,
                         "kJ/mol/nm^2")

    for lineno, fields in mol.sections.get("constraints", []):
        if len(fields) >= 4:
            _range_check(issues, lineno, "constraint length", fields[3],
                         BOND_LENGTH_NM, "nm")

    for lineno, fields in mol.sections.get("angles", []):
        if len(fields) >= 5:
            _range_check(issues, lineno, "equilibrium angle", fields[4],
                         ANGLE_DEGREES, "degrees")

    if natoms > 1 and not bonds and not constraints \
            and not mol.sections.get("settles") \
            and not any(k.startswith("virtual_sites") for k in mol.sections):
        issues.append(ItpIssue(
            "itp.no-bonded-terms", "warning", mol.line,
            f"Molecule {mol.name!r} has {natoms} atoms but no bonds, "
            f"constraints, or virtual sites.",
            "Its beads would diffuse apart independently. Intended only for "
            "genuinely monatomic species.",
        ))

    return issues


def _range_check(issues, lineno, label, value, bounds, unit) -> None:
    try:
        number = float(value)
    except ValueError:
        return
    low, high = bounds
    if not low <= number <= high:
        issues.append(ItpIssue(
            "itp.parameter-out-of-range", "warning", lineno,
            f"{label.capitalize()} {number} {unit} is outside the usual "
            f"Martini range ({low}-{high} {unit}).",
            "Check the units; this is usually a factor-of-ten or "
            "nm-versus-angstrom slip.",
        ))


def _check_connectivity(mol: Molecule) -> list[ItpIssue]:
    """Report molecules that fall into disconnected fragments."""
    natoms = len(mol.atoms)
    if natoms < 2:
        return []

    parent = list(range(natoms + 1))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    linked = False
    for section in ("bonds", "constraints", "settles", "virtual_sites2",
                    "virtual_sites3", "virtual_sites4", "virtual_sitesn"):
        for _, fields in mol.sections.get(section, []):
            # Only the leading columns are atom indices. Reading further would
            # pick up the function type -- which, being a small integer, looks
            # like a valid atom index and silently links every fragment
            # together, making this check pass unconditionally.
            count = INDEX_COLUMNS.get(section)
            if section == "virtual_sitesn":
                columns = fields[:1] + fields[2:]
            elif count is None:
                columns = fields
            else:
                columns = fields[:count]

            indices = []
            for value in columns:
                try:
                    index = int(value)
                except ValueError:
                    continue
                if 1 <= index <= natoms:
                    indices.append(index)

            for other in indices[1:]:
                union(indices[0], other)
                linked = True

    if not linked:
        return []

    roots = {find(i) for i in range(1, natoms + 1)}
    if len(roots) > 1:
        return [ItpIssue(
            "itp.disconnected-fragments", "warning", mol.line,
            f"Molecule {mol.name!r} separates into {len(roots)} disconnected "
            f"fragments.",
            "Unless this is deliberate, a bond is missing: the fragments "
            "would drift apart during simulation.",
        )]
    return []


def lint(text: str) -> list[ItpIssue]:
    """Full lint of one .itp file."""
    molecules, issues = parse_itp(text)

    seen: dict[str, int] = {}
    for mol in molecules:
        if mol.name in seen:
            issues.append(ItpIssue(
                "itp.duplicate-moleculetype", "error", mol.line,
                f"Molecule name {mol.name!r} is defined twice (first at line "
                f"{seen[mol.name]}).",
                "GROMACS silently uses one of them. Rename or remove.",
            ))
        else:
            seen[mol.name] = mol.line
        issues.extend(check_molecule(mol))

    if not molecules:
        issues.append(ItpIssue(
            "itp.no-moleculetype", "error", 1,
            "File defines no [ moleculetype ].",
            "A parameter contribution must define at least one molecule.",
        ))

    return sorted(issues, key=lambda i: (i.line or 0, i.rule))
