# Quickstrap

**A lightweight, profile-based installation framework for Python projects**

Quickstrap provides a simple, reusable installation system that handles both Python packages (pip) and system packages (apt/dpkg on Linux), with support for multiple installation profiles and post-install hooks. **Works on both Linux and Windows.**

## Features

- **Cross-Platform Support** - Full Linux and Windows support with platform-specific configuration
- **Profile-Based Installation** - Define multiple installation profiles (e.g. minimal, standard, full, development)
- **Hybrid Package Management** - Manages both system packages (apt on Linux, PowerShell checks on Windows) and Python packages (pip)
- **Platform-Specific Requirements** - Separate Python requirements and system checks per platform
- **Virtual Environment** - Automatic venv creation and management
- **Feature Detection** - Applications can detect which features were installed
- **Post-Install Hooks** - Run custom scripts after installation (bash on Linux, PowerShell on Windows)
- **Windows EXE Builder** - Create standalone Windows executables with PyInstaller
- **Template-Driven** - No code changes needed, just configure INI files
- **Copy-and-Go** - Clone, configure, and you're ready to deploy

## Quick Start

### For New Projects

1. **Clone Quickstrap into your project:**

   ```bash
   git clone https://github.com/Stefan-Schmidbauer/quickstrap.git my-project
   cd my-project
   # Rename Quickstrap README to make room for your project's README
   mv README.md README.quickstrap.md
   ```

2. **Configure your application:**
   Edit `quickstrap/installation_profiles.ini`:

   - Set your app name, config directory, and start command
   - Define your features
   - Uncomment and customize profiles as needed

3. **Add your dependencies:**

   - Edit `quickstrap/requirements_python_linux.txt` - add your Python packages for Linux
   - Edit `quickstrap/requirements_python_windows.txt` - add your Python packages for Windows
   - Edit `quickstrap/requirements_system_linux.txt` - add your Linux system packages (APT)
   - Edit `quickstrap/scripts/check_system_windows.ps1` - add Windows system checks

4. **Add your application code:**

   ```bash
      # Create your Python application
   ```

5. **Install and run:**

   **Linux:**
   ```bash
   ./install.py
   ./start.sh
   ```

   **Windows (PowerShell):**
   ```powershell
   python install.py
   .\start.ps1
   ```

![Interactive Installation](quickstrap/quickstrap_i12.png)

The interactive installation process guides users through profile selection and automatically verifies system requirements.

### For Existing Projects

1. **Add Quickstrap to your project:**

   ```bash
   cd your-existing-project
   git clone https://github.com/Stefan-Schmidbauer/quickstrap.git quickstrap-temp
   cp quickstrap-temp/install.py .
   cp quickstrap-temp/start.sh .
   cp quickstrap-temp/README.md README.quickstrap.md  # Keep Quickstrap docs as reference
   cp -r quickstrap-temp/quickstrap .
   rm -rf quickstrap-temp
   ```

2. **Configure and install:**
   - Edit `quickstrap/installation_profiles.ini`
   - Add dependencies to `quickstrap/requirements_*.txt`
   - Run `./install.py` (Linux) or `python install.py` (Windows)

## Platform-Specific Configuration

Quickstrap supports true cross-platform configuration using platform-specific suffixes (`_linux` and `_windows`):

### Basic Example (Cross-Platform)

```ini
[metadata]
app_name = My Application
config_dir = my-app
supported_platforms = linux,windows  # Optional, default is both

# Platform-specific start commands
start_command_linux = python3 src/main.py
start_command_windows = python src/main.py

# Platform-specific after-install messages
after_install_linux = Start with: ./start.sh
after_install_windows = Start with: .\start.ps1

[profile:standard]
name = Standard Installation
features = gui,database

# Separate Python requirements per platform
python_requirements_linux = quickstrap/requirements_python_linux.txt
python_requirements_windows = quickstrap/requirements_python_windows.txt

# Platform-specific system checks
system_requirements_linux = quickstrap/requirements_system_linux.txt      # APT packages
system_check_script_windows = quickstrap/scripts/check_system_windows.ps1 # PowerShell script
```

### Platform Support Declaration

Restrict your application to specific platforms:

```ini
[metadata]
# Linux-only application
supported_platforms = linux

# Windows-only application
supported_platforms = windows

# Cross-platform (default)
supported_platforms = linux,windows
```

When users try to install on an unsupported platform, they'll get a clear error message.

### Python Requirements

Each platform has its own requirements file to handle platform-specific packages:

- `quickstrap/requirements_python_linux.txt` - Linux packages (e.g., `python-daemon`)
- `quickstrap/requirements_python_windows.txt` - Windows packages (e.g., `pywin32`, `wmi`)

Both files can contain common packages like `requests`, `numpy`, etc.

### System Requirements

**Linux**: APT/DEB package list in `requirements_system_linux.txt`
```txt
# quickstrap/requirements_system_linux.txt
python3-tk
libpq-dev
```

**Windows**: PowerShell check script in `scripts/check_system_windows.ps1`
```powershell
# Checks for required software, outputs JSON
$installed = @()
$missing = @()

if (Get-Command git -ErrorAction SilentlyContinue) {
    $installed += "Git"
} else {
    $missing += "Git"
}

@{installed = $installed; missing = $missing} | ConvertTo-Json
```

See `quickstrap/scripts/check_system_windows_example.ps1` for comprehensive examples.

## Installation Profiles

Profiles allow you to define different installation scenarios with platform-specific configuration:

```ini
[profile:minimal]
name = Minimal Installation
description = CLI-only installation
features = cli
python_requirements_linux = quickstrap/requirements_python_linux.txt
python_requirements_windows = quickstrap/requirements_python_windows.txt
system_requirements_linux = quickstrap/requirements_system_linux.txt
system_check_script_windows = quickstrap/scripts/check_system_windows.ps1

[profile:full]
name = Full Installation
description = Complete installation with all features
features = gui,pdf,database,printing,api
python_requirements_linux = quickstrap/requirements_python_full_linux.txt
python_requirements_windows = quickstrap/requirements_python_full_windows.txt
system_requirements_linux = quickstrap/requirements_system_full_linux.txt
system_check_script_windows = quickstrap/scripts/check_system_full_windows.ps1
post_install_scripts_linux = quickstrap/scripts/init_database.sh
post_install_scripts_windows = quickstrap/scripts/init_database.ps1
```

## Feature Detection

Your application can detect which features were installed by reading the configuration file created by Quickstrap:

```python
from pathlib import Path
from configparser import ConfigParser

def get_installed_features(config_dir_name: str) -> set:
    """Read installed features from Quickstrap config."""
    config_file = Path.home() / '.config' / config_dir_name / 'installation_profile.ini'

    if not config_file.exists():
        return set()

    config = ConfigParser()
    config.read(config_file)

    features_str = config.get('installation', 'features', fallback='')
    return set(f.strip() for f in features_str.split(',') if f.strip())

# Usage:
features = get_installed_features('my-app')

if 'gui' in features:
    import tkinter
    # Enable GUI features

if 'pdf' in features:
    from reportlab.pdfgen import canvas
    # Enable PDF generation
```

The configuration is stored at: `~/.config/{your-config-dir}/installation_profile.ini`

## Pre-Install Scripts

Pre-install scripts run **before** the virtual environment is created and packages are installed. This prevents wasting time installing packages when critical requirements are missing (e.g., GPU drivers for CUDA applications).

Add pre-install scripts to your profile:

```ini
[profile:cuda]
name = CUDA Installation
...
pre_install_scripts = quickstrap/scripts/check_nvidia_driver.sh
```

### How Pre-Install Scripts Work

1. **Timing**: Scripts run after system package verification but before venv creation
2. **Failure Handling**: If a script fails, the user is prompted to continue or abort
3. **Multiple Scripts**: Comma-separated list, all scripts run in order
4. **Exit Codes**: Script exit 0 = success, non-zero = failure

**Windows Note:** Pre-install scripts are bash scripts and will be skipped on Windows with a warning message. If you need pre-install checks on Windows, you'll need to perform them manually before running `python install.py`.

### Example: NVIDIA Driver Verification

Quickstrap includes a template for verifying NVIDIA GPU drivers:

`quickstrap/scripts/check_nvidia_driver.sh` - Verify NVIDIA drivers for CUDA applications

Uncomment and customize the template to check for:

- nvidia-smi availability
- GPU detection
- Minimum driver version requirements

**Example script:**

```bash
#!/bin/bash
if ! command -v nvidia-smi >/dev/null 2>&1; then
    echo "Error: NVIDIA driver not found (nvidia-smi not available)"
    echo ""
    echo "Install NVIDIA drivers:"
    echo "  1. Check available versions: apt search nvidia-driver"
    echo "  2. Install driver: sudo apt install nvidia-driver-XXX"
    echo "  3. Reboot system"
    exit 1
fi
echo "✓ NVIDIA driver found"
exit 0
```

### User Experience

When a pre-install script fails:

```
Step 2: Pre-Installation Scripts
ℹ Running pre-install script: quickstrap/scripts/check_nvidia_driver.sh
Error: NVIDIA driver not found (nvidia-smi not available)

Install NVIDIA drivers:
  1. Check available versions: apt search nvidia-driver
  2. Install driver: sudo apt install nvidia-driver-XXX
  3. Reboot system

✗ Pre-install script failed: quickstrap/scripts/check_nvidia_driver.sh

⚠ Warning: Pre-installation scripts failed
Continue anyway? [y/N]: _
```

The user can choose to:

- Press `N` or `Enter` to abort (recommended)
- Press `y` to continue despite the failed script

## Post-Install Scripts

Add custom setup scripts that run after package installation:

```ini
[profile:standard]
...
post_install_scripts = quickstrap/scripts/init_database.sh,quickstrap/scripts/check_deps.sh
```

Quickstrap includes template scripts in `quickstrap/scripts/`:

**Pre-Install Scripts** (run before venv creation):

- `check_nvidia_driver.sh` - Verify NVIDIA GPU drivers for CUDA applications
- `check_docker.sh` - Verify Docker and Docker Compose availability
- `check_port_available.sh` - Check if required ports are free for web applications
- `check_python_version.sh` - Verify Python version meets requirements

**Post-Install Scripts** (run after package installation):

- `init_sqlite_database.sh` - Initialize SQLite database
- `setup_config_directory.sh` - Create config directories
- `setup_desktop_entry.sh` - Create .desktop file for desktop integration
- `check_file_exists.sh` - Verify required files exist
- `check_cups_printing.sh` - Verify CUPS printing system

Simply uncomment and customize these templates for your needs. All templates include extensive examples showing common use cases.

If the script fails, the installation fails.

**Windows Note:** Post-install scripts are bash scripts and will be skipped on Windows with a warning message. If your application requires post-install setup on Windows, you'll need to run these steps manually or create PowerShell equivalents.

### Environment Variables Available to Scripts

Post-install scripts have access to these environment variables:

- `QUICKSTRAP_APP_NAME` - The application name from metadata
- `QUICKSTRAP_CONFIG_DIR` - The config directory name from metadata
- `VIRTUAL_ENV` - Path to the virtual environment (e.g., `/path/to/project/venv`)
- `PATH` - Automatically updated to include the venv's `bin` directory first. This ensures that when your script calls `python`, `pip`, or any installed Python tools, the versions from the virtual environment are used instead of system versions. You can directly use commands like `python script.py` without specifying the full venv path.

Example usage in a script:

```bash
#!/bin/bash
echo "Setting up $QUICKSTRAP_APP_NAME..."
CONFIG_PATH="$HOME/.config/$QUICKSTRAP_CONFIG_DIR"
mkdir -p "$CONFIG_PATH"
```

## Usage

### Interactive Installation

**Linux:**
```bash
./install.py
```

**Windows:**
```powershell
python install.py
```

Presents a menu to choose from available profiles.

### Direct Profile Installation

**Linux:**
```bash
./install.py --profile standard
```

**Windows:**
```powershell
python install.py --profile standard
```

Installs the specified profile directly.

### Rebuild Virtual Environment

**Linux:**
```bash
./install.py --rebuild-venv
# Or with specific profile:
./install.py --profile standard --rebuild-venv
```

**Windows:**
```powershell
python install.py --rebuild-venv
# Or with specific profile:
python install.py --profile standard --rebuild-venv
```

Deletes and recreates the virtual environment from scratch.

### Dry Run

**Linux:**
```bash
./install.py --dry-run
```

**Windows:**
```powershell
python install.py --dry-run
```

Shows what would be installed without making changes.

### Validate Configuration

```bash
./install.py --validate
```

Validates your profile configuration without installing anything. Checks:

- Required fields in all profiles
- All referenced files exist
- Script executability
- Metadata completeness

Useful before committing configuration changes or when setting up a new project.

### Update Python Packages

Check for Python package updates:

```bash
./install.py --check-update-python
```

Shows which Python packages have newer versions available.

Update Python packages:

```bash
./install.py --update-python
```

Updates all Python packages in the virtual environment to match requirements.

### Start Application

**Linux:**
```bash
./start.sh
```

**Windows:**
```powershell
.\start.ps1
```

Activates the virtual environment and starts your application.

### Start Application with Parameters

**Linux:**
```bash
./start.sh [arguments...]
```

**Windows:**
```powershell
.\start.ps1 [arguments...]
```

All arguments are passed to your application. Examples:

**Linux:**
```bash
./start.sh --help              # Show application help
./start.sh --config production # Start with production config
./start.sh process --verbose   # Run command with options
```

**Windows:**
```powershell
.\start.ps1 --help              # Show application help
.\start.ps1 --config production # Start with production config
.\start.ps1 process --verbose   # Run command with options
```

### Developer Mode (Activate Virtual Environment)

To work directly in the virtual environment with environment variables set:

**Linux:**
```bash
source quickstrap/activate.sh
```

**Windows:**
```powershell
. .\quickstrap\activate.ps1
```

This activates the venv and sets `QUICKSTRAP_APP_NAME`, `QUICKSTRAP_CONFIG_DIR`, and `QUICKSTRAP_PROJECT_ROOT` environment variables.

This provides:

- Activated virtual environment
- Quickstrap environment variables (`QUICKSTRAP_APP_NAME`, `QUICKSTRAP_CONFIG_DIR`)
- Updated `PATH` with venv binaries
- Persistent activation (use `deactivate` to exit)

This is useful when you want to:

- Run Python commands directly without `./start.sh`
- Use development tools (pytest, mypy, black, etc.)
- Debug or explore code interactively
- Work with multiple terminal sessions

## Building Standalone Executables

Quickstrap includes built-in support for creating standalone executables using PyInstaller. This allows you to distribute your Quickstrap-based application without requiring users to install Python.

**Note**: This feature is for your application project that uses Quickstrap, not for Quickstrap itself.

### Quick Build

**On Windows** (PowerShell or CMD):

```powershell
.\quickstrap\scripts\build_windows_exe.ps1
```

**On Linux**:

```bash
./quickstrap/scripts/build_linux_binary.sh
```

**Important**: PyInstaller builds for the platform it runs on:
- Run `build_windows_exe.ps1` on Windows to create a `.exe`
- Run `build_linux_binary.sh` on Linux to create a Linux binary

This will:
1. Automatically install PyInstaller if needed
2. Read your application configuration
3. Create a standalone executable in the `dist/` directory

### Advanced Configuration

For more control over the build process, create a custom PyInstaller spec file:

```bash
# Copy the template
cp quickstrap/pyinstaller.spec.template quickstrap/pyinstaller.spec

# Edit the configuration
nano quickstrap/pyinstaller.spec
```

Customize these settings in `pyinstaller.spec`:

```python
# Main script (entry point)
MAIN_SCRIPT = 'src/main.py'

# Application name
APP_NAME = 'MyApp'

# Icon file (optional)
ICON_FILE = 'app.ico'

# Additional data files to include
DATAS = [
    ('config', 'config'),
    ('templates', 'templates'),
]

# Hide console window for GUI apps
CONSOLE = False  # Set to True for CLI apps
```

Then run the build script - it will automatically use your custom spec file.

### Common Build Scenarios

**GUI Application** (no console window):
```python
CONSOLE = False
```

**Include config files**:
```python
DATAS = [('config', 'config')]
```

**Hidden imports** (modules PyInstaller misses):
```python
HIDDEN_IMPORTS = ['package.module']
```

**Reduce EXE size** (exclude unused modules):
```python
EXCLUDES = ['tkinter', 'matplotlib']
```

### Distribution

The generated executable in `dist/` is fully standalone:
- No Python installation required on target system
- All dependencies bundled
- Can be distributed as a single file

**Platform-specific distribution:**
- **Windows**: Share the `.exe` file with Windows users
- **Linux**: Share the binary with Linux users (ensure executable permission: `chmod +x`)

### Troubleshooting

**Build fails**: Check that your main script path in `installation_profiles.ini` is correct.

**Missing modules**: Add them to `HIDDEN_IMPORTS` in `pyinstaller.spec`.

**Large EXE size**: Add unused modules to `EXCLUDES` in `pyinstaller.spec`.

**Runtime errors**: Check for dynamic imports or file path issues in your code.

## Configuration Reference

### Metadata Section (`[metadata]`)

Global application configuration:

| Field           | Required | Description                                                     |
| --------------- | -------- | --------------------------------------------------------------- |
| `app_name`      | Yes      | Display name of your application                                |
| `config_dir`    | Yes      | Directory name under `~/.config/` for storing installation info |
| `start_command` | Yes      | Command to start your application (e.g., `python3 src/main.py`) |
| `after_install` | No       | Message displayed after successful installation                 |

### Profile Section (`[profile:NAME]`)

Installation profile configuration:

| Field                  | Required | Description                                                                   |
| ---------------------- | -------- | ----------------------------------------------------------------------------- |
| `name`                 | Yes      | Display name of the profile                                                   |
| `description`          | Yes      | Description of what this profile includes                                     |
| `features`             | Yes      | Comma-separated feature list (used by your app for feature detection)         |
| `python_requirements`  | Yes      | Path to Python packages file (e.g., `quickstrap/requirements_python.txt`)     |
| `system_requirements`  | Yes      | Path to system packages file (e.g., `quickstrap/requirements_system.txt`)     |
| `pre_install_scripts`  | No       | Comma-separated list of pre-install scripts (run before venv creation)        |
| `post_install_scripts` | No       | Comma-separated list of post-install scripts (run after package installation) |

### Example Configuration

```ini
[metadata]
app_name = My Amazing App
config_dir = my-amazing-app
start_command = python3 src/main.py
after_install = Start with: ./start.sh

[profile:standard]
name = Standard Installation
description = Complete installation with all features
features = gui,pdf,database,printing
python_requirements = quickstrap/requirements_python.txt
system_requirements = quickstrap/requirements_system.txt
pre_install_scripts = quickstrap/scripts/check_nvidia_driver.sh
post_install_scripts = quickstrap/scripts/init_database.sh
```

## Requirements

### Linux (Debian/Ubuntu)

**Install these system packages:**

```bash
sudo apt install python3 python3-pip python3-venv
```

Required:

- Python 3.6 or higher
- pip (Python package installer)
- venv (Virtual environment support)
- dpkg (Debian package manager - for system package verification)

### Windows

**Requirements:**

- Python 3.6 or higher (download from [python.org](https://www.python.org/downloads/))
- During Python installation, check "Add Python to PATH"
- PowerShell (included with Windows)

**PowerShell Execution Policy:**

If you get a "scripts are disabled" error, run PowerShell as Administrator and execute:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

**Note on Windows:** System package checking (`dpkg`) is not available on Windows. Quickstrap will skip system package verification and display a list of any required system packages that you may need to install manually.

## Quickstrap Structure

Example structure:

```
your-project/
├── README.quickstrap.md               # Quickstrap documentation (this file)
├── install.py                         # Quickstrap installer (cross-platform)
├── start.sh                           # Linux starter script
├── start.ps1                          # Windows starter script (PowerShell)
├── quickstrap/                        # Quickstrap configuration directory
│   ├── installation_profiles.ini      # Your profiles configuration
│   ├── requirements_python.txt        # Your Python dependencies
│   ├── requirements_system.txt        # Your system dependencies
│   ├── activate.sh                    # Linux developer mode activation
│   ├── activate.ps1                   # Windows developer mode activation
│   └── scripts/                       # Installation scripts (templates)
│       ├── check_nvidia_driver.sh     # Pre: GPU/CUDA check
│       ├── check_docker.sh            # Pre: Docker availability check
│       ├── check_port_available.sh    # Pre: Port availability check
│       ├── check_python_version.sh    # Pre: Python version check
│       ├── init_sqlite_database.sh    # Post: Database initialization
│       ├── setup_config_directory.sh  # Post: Config directory setup
│       ├── setup_desktop_entry.sh     # Post: Desktop integration
│       ├── check_file_exists.sh       # Post: File verification
│       └── check_cups_printing.sh     # Post: Printing system check
└── venv/                              # Virtual environment (created by install.py)
```

**Note:** Quickstrap keeps these items in your project root: `install.py`, `start.sh` (Linux), `start.ps1` (Windows), and optionally `README.quickstrap.md`. All other files are in the `quickstrap/` subdirectory to minimize conflicts with your project.

## Why Quickstrap?

Most Python projects use pip and requirements.txt, but many applications also need:

- System dependencies (GUI libraries, printing systems, databases)
- Different deployment scenarios (minimal vs full installation)
- Post-install initialization (database setup, config files)
- Feature detection (conditional imports based on what's installed)

Quickstrap provides all of this in a simple, reusable framework that requires no code changes - just configuration.

## Design Philosophy

Quickstrap's design decisions are intentional and optimized for real-world Python application deployment:

**INI over YAML/JSON**: Simpler syntax, fewer syntax errors, more accessible to non-programmers. No need for complex parsers or strict indentation rules.

**Pre-Install Scripts**: Check critical requirements (GPU drivers, Docker, etc.) *before* spending time installing 2GB+ of packages. Prevents wasted time and provides early feedback.

**Template-Driven Approach**: Copy-paste ready scripts for common scenarios. No learning curve - just uncomment and customize existing examples.

**Minimal Root Pollution**: Only 3-4 files in project root (`install.py`, `start.sh`/`start.ps1`, optional `README.quickstrap.md`). Everything else stays in `quickstrap/` subdirectory.

**Feature Detection**: Applications can adapt their behavior based on which profile was installed. Enables conditional imports and adaptive UIs.

## Ideal Use Cases

Quickstrap excels in these scenarios:

- **Desktop GUI Applications** - tkinter, PyQt, GTK apps that need system libraries
- **PDF/Printing Applications** - Projects using WeasyPrint, ReportLab, CUPS
- **ML/AI Tools with GPU Requirements** - CUDA applications with driver dependencies
- **Multi-Profile Applications** - Projects with minimal/standard/full deployment scenarios
- **Hybrid Dependency Projects** - Applications requiring both system packages and Python packages

If your project needs system dependencies beyond pip, or you want to provide different installation options, Quickstrap is designed for you.

## Troubleshooting

### Linux: Scripts Not Executable

```bash
chmod +x install.py start.sh
chmod +x quickstrap/scripts/*.sh
```

### Linux: Virtual Environment Issues

```bash
# Rebuild the virtual environment
./install.py --rebuild-venv
```

### Linux: Missing System Packages

```bash
sudo apt install <package-name>
./install.py
```

### Windows: PowerShell Execution Policy Error

If you see "running scripts is disabled on this system":

```powershell
# Run as Administrator
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### Windows: Python Not Found

Ensure Python is installed and added to PATH. During installation from [python.org](https://www.python.org/downloads/), check the "Add Python to PATH" option.

To verify Python is in PATH:

```powershell
python --version
```

### Windows: Virtual Environment Issues

```powershell
# Rebuild the virtual environment
python install.py --rebuild-venv
```

### Windows: "venv" Module Not Found

Some Python installations don't include the `venv` module. Reinstall Python from [python.org](https://www.python.org/downloads/) ensuring you check all optional features.

## FAQ

### Supported Platforms

Quickstrap supports **Linux** (Debian/Ubuntu-based) and **Windows** (10/11 with PowerShell).

| Feature | Linux | Windows |
|---------|-------|---------|
| Python venv creation | ✓ | ✓ |
| Python package installation | ✓ | ✓ |
| Profile selection | ✓ | ✓ |
| Feature detection | ✓ | ✓ |
| System package verification | ✓ (dpkg) | ✗ (manual) |
| Pre/Post-install bash scripts | ✓ | ✗ (skipped) |
| Config file location | `~/.config/` | `%LOCALAPPDATA%` |

### Adding Python Packages

Edit `quickstrap/requirements_python.txt` and rebuild:

**Linux:**
```bash
./install.py --rebuild-venv
```

**Windows:**
```powershell
python install.py --rebuild-venv
```

### Pre-Install vs Post-Install Scripts

- **Pre-install**: Run before venv creation (e.g., check GPU drivers)
- **Post-install**: Run after packages installed (e.g., init database)

**Note for Windows users:** Pre-install and post-install scripts are bash scripts (`.sh`) and will be skipped on Windows. If your application requires these scripts, you'll need to run them manually or create PowerShell equivalents.

## License

MIT License - see [LICENSE](quickstrap/LICENSE) file for details.

Copyright (c) 2025 Stefan Schmidbauer

## Contributing

Contributions welcome! Open issues or submit pull requests on GitHub.
