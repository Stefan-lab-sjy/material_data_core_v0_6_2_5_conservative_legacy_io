from pathlib import Path


def write_vasp_folder(root: Path, *, optics: bool = False, extra: bool = True, variant: str = 'A') -> Path:
    root.mkdir(parents=True, exist_ok=True)
    incar = """ENCUT = 400
EDIFF = 1E-6 ! convergence comment
GGA = PE
NSW = 0
IBRION = -1
"""
    if optics:
        incar += "LOPTICS = .TRUE.\nCSHIFT = 0.1\nNEDOS = 2000\n"
    (root/'INCAR').write_text(incar, encoding='utf-8')
    # Same defaults unless explicitly varied by test.
    (root/'KPOINTS').write_text("Gamma mesh\n0\nGamma\n6 6 1\n0 0 0\n", encoding='utf-8')
    (root/'POSCAR').write_text("SiS2\n1.0\n3 0 0\n0 3 0\n0 0 20\nSi S\n1 2\nDirect\n0 0 0\n0.3 0.3 0.5\n0.6 0.6 0.5\n", encoding='utf-8')
    (root/'POTCAR').write_text("POTCAR-DEMO\n", encoding='utf-8')

    # These outputs intentionally depend on variant, modelling separate completed calculations.
    output_text = {
        'OUTCAR': f'OUTCAR-{variant}\nGeneral timing and accounting informations for this job:\n',
        'OSZICAR': f' 1 F= -10.{1 if variant == "A" else 2} E0= -10.0 d E =0.0 [{variant}]\n',
        'CONTCAR': f'CONTCAR-{variant}\n',
        'DOSCAR': f'DOSCAR-{variant}\n',
        'EIGENVAL': f'EIGENVAL-{variant}\n',
        'PROCAR': f'PROCAR-{variant}\n',
        'CHGCAR': f'CHGCAR-{variant}\n',
        'WAVECAR': f'WAVECAR-{variant}\n',
        'XDATCAR': f'XDATCAR-{variant}\n',
        'vasprun.xml': f'<modeling variant="{variant}"></modeling>\n',
    }
    for name, text in output_text.items():
        (root/name).write_text(text, encoding='utf-8')

    if extra:
        (root/'REPORT').write_text(f'REPORT-{variant}\n', encoding='utf-8')
        (root/'WAVEDER').write_text(f'WAVEDER-{variant}\n', encoding='utf-8')
        (root/'CUSTOM_NOTE.foo').write_text(f'CUSTOM-{variant}\n', encoding='utf-8')
    return root
