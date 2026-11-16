# Third-party notices

ZK Pull is Copyright (c) 2026 Abdulrahman Aloqayli and licensed under CC BY-NC-ND 4.0 (see
`LICENSE`). The Windows installer and portable zip also contain the components below, each under its
own licence; the full texts are in the `licenses` folder. Their licences, not ZK Pull's, apply to them.

| Component | Version | Licence | Text |
|---|---|---|---|
| Qt 6 (QtCore, QtGui, QtWidgets) and PySide6 / Shiboken6 | 6.12 | LGPL-3.0 | `licenses/LGPL-3.0.txt`, `licenses/GPL-3.0.txt` |
| Python | 3.12 | PSF License | `licenses/Python.txt` |
| openpyxl | 3.1 | MIT | `licenses/openpyxl.txt` |
| et-xmlfile | 2.0 | MIT | `licenses/et_xmlfile.txt` |
| defusedxml | 0.7 | PSF License 2.0 | `licenses/defusedxml.txt` |
| PyInstaller bootloader | 6 | GPL-2.0-or-later with the bootloader exception, which allows distributing it with programs under any licence | [pyinstaller.org](https://pyinstaller.org/en/stable/license.html) |
| App icon "Fingerprint" | | Icons8 free licence, with a link to [icons8.com](https://icons8.com) | |

## Qt and PySide6 (LGPL-3.0)

ZK Pull uses Qt and PySide6 as separate, unmodified library files (the `Qt6*.dll`, `PySide6` and
`shiboken6` files in the `_internal` folder), so you can replace them with your own builds of the
same version. Their source code is available from [qt.io](https://download.qt.io/official_releases/)
and [PySide6 on PyPI](https://pypi.org/project/PySide6-Essentials/#files). Qt includes third-party
code, listed at
[doc.qt.io/qt-6/licenses-used-in-qt.html](https://doc.qt.io/qt-6/licenses-used-in-qt.html).

As LGPL-3.0 section 4 requires for these libraries, nothing in ZK Pull's licence forbids modifying
the Qt and PySide6 files for your own use, or reverse engineering ZK Pull as far as needed to debug
such modifications.

## ZKTeco device protocol

The device client in `device.py` is ZK Pull's own code, written from the public description of the
ZKTeco standalone protocol; no third-party device library is included.
