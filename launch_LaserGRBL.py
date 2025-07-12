#!/usr/bin/env python3
 # 
 # This file is part of the InkBurn distribution (https://github.com/lgiuliani/InkBurn).
 # Copyright (c) 2025 LLaurent Giuliani.
 # 
 # This program is free software: you can redistribute it and/or modify  
 # it under the terms of the GNU General Public License as published by  
 # the Free Software Foundation, version 3.
 #
 # This program is distributed in the hope that it will be useful, but 
 # WITHOUT ANY WARRANTY; without even the implied warranty of 
 # MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU 
 # General Public License for more details.
 #
 # You should have received a copy of the GNU General Public License 
 # along with this program. If not, see <http://www.gnu.org/licenses/>.
 #
import inkex
import subprocess
from sys import platform
from os import startfile, path

def get_output_file(document_path) -> str:
    """Return target filename with path"""
    inpath = document_path
    base = path.splitext(path.basename(inpath))[0]
    return path.join(path.dirname(inpath), base + '.nc')

def openfile(filename):
    """Open filename"""
    if platform == "win32":
        startfile(filename)
    else:
        opener = "open" if platform == "darwin" else "xdg-open"
        subprocess.call([opener, filename])

class LaunchLaserGRBL(inkex.Effect):
    """
    Launch LaserGRBL with saved Gcode file
    - Check if file exist
    - Cross-platform 
    - 
    """ 
    def effect(self) -> None:
        document_path = self.document_path() or ''
        filename = get_output_file(document_path)

        # Check if outfile exist or show an error message.
        if path.isfile(filename):
            openfile(filename)
        else:
            inkex.utils.debug(f"File {str(filename)} does not exist")


if __name__ == '__main__':
    LaunchLaserGRBL().run()

