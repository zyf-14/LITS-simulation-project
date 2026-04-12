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

## Overview
- **Simulation core** – Python‑based vehicle dynamics (`virtual_test.py`).  
- **Firmware** – Arduino/ESP32 code for motor/servo control (`firmware/src/`).  
- **Hardware** – STL files for chassis, PCB layouts, and a complete BOM (`hardware/cad/`, `hardware/pcb/`).  

## Live Demo
![RC Car on Track](media/demo.gif)

## Folder Structure
