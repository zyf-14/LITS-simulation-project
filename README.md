# LITS Simulation Project 🚗💡

![Build Status](https://github.com/zyf-14/LITS-simulation-project/actions/workflows/ci.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)

**A full‑stack simulation of a low‑inertia transit system (LITS) for autonomous RC‑car research.**  
The repo contains 3‑D CAD models, Arduino/ESP32 firmware, and Raspberry Pi control software.

## Table of Contents
- [Overview](#overview)
- [Live Demo](#live-demo)
- [Folder Structure](#folder-structure)
- [Quick Start](#quick-start)
- [Hardware Build Guide](#hardware-build-guide)
- [Software Setup](#software-setup)
- [Testing](#testing)
- [Contributing](#contributing)
- [License](#license)
- [3D CAD schematics](https://cad.onshape.com/documents/3a9c78263ff22dc350c29a50/w/96404cf1ed0ead9f22eaefd4/e/8b10ad415629b44db3a26b1b?renderMode=0&uiState=69db475893e9b9c5b1197a1b)

## Overview
- **Simulation core** – Python‑based vehicle dynamics (`virtual_test.py`).  
- **Firmware** – Arduino/ESP32 code for motor/servo control (`firmware/src/`).  
- **Hardware** – STL files for chassis, PCB layouts, and a complete BOM (`hardware/cad/`, `hardware/pcb/`).  

## Live Demo
![RC Car on Track](media/demo.gif)

## Folder Structure
