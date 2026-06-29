# Server Test System

Hardware testing system for production line servers. Supports comprehensive hardware detection, stress testing, and multi-server management for generic, storage, compute, and AI server types.

## Features

### Hardware Detection (21 Detectors)
| Category | Detectors | Details |
|----------|-----------|---------|
| **Compute** | CPU, Memory, DIMM | Cores, frequency, DIMM slots, total/populated |
| **Storage** | Storage, NVMe Health, RAID | Disks, SMART data, RAID controllers (LSI/Adaptec/HP) |
| **Network** | Network, InfiniBand, DPU | Interfaces, MAC, speed, IB devices, BlueField DPU |
| **GPU** | GPU | NVIDIA, AMD, domestic (Hygon, Cambricon, Huawei Ascend, Moore Threads) |
| **Management** | BMC, BIOS, TPM, Chassis | IPMI version, firmware, secure boot, asset tags |
| **Bus/IO** | PCIe, USB, Serial | Device enumeration, USB controllers, RS-232/485 |
| **Power/Cooling** | PSU, Sensors | Power supply status, temperatures, fans |
| **Security** | Security, FPGA | SGX/SEV/TXT, FPGA accelerators (Xilinx/Intel)

### Stress Testing (9 Test Types)
| Test | Description | Thresholds |
|------|-------------|------------|
| **CPU** | Multi-core load with stress-ng fallback | Temperature, utilization, frequency |
| **GPU** | Multi-vendor (NVIDIA/AMD/domestic) | Memory temp, utilization, power |
| **Memory** | RAM bandwidth and stability | Error rate, bandwidth |
| **NVMe** | Disk I/O with health monitoring | Temperature, health %, media errors |
| **Storage** | fio-based IOPS/bandwidth tests | IOPS, latency, temperature |
| **Network** | Throughput and latency tests | Bandwidth, packet loss, latency |
| **PCIe** | Link bandwidth validation | Link speed, errors |
| **Power** | PSU load and efficiency | Voltage, wattage, load % |
| **FPGA** | Accelerator card stress | Temperature, power utilization |

### Advanced Features

| Feature | Description |
|---------|-------------|
| **Grouped Execution** | Detectors organized by category (compute/storage/network/etc), groups execute sequentially, detectors within group run in parallel |
| **Auto SN Detection** | Automatic server serial number and model detection from DMI/BIOS (sysfs/dmidecode/ipmitool) |
| **Timeout Enforcement** | Signal-based (SIGALRM) and executor-based timeout for detector execution |
| **Dynamic Thresholds** | Load stress test thresholds from YAML configuration with per-test customization |
| **EMS Integration** | Auto-upload test reports to EMS (Equipment Management System) via HTTP/Webhook |
| **Performance Charts** | Interactive Chart.js visualizations in HTML reports (status distribution, duration charts, temperature graphs) |

### Server Types
- **Generic**: Standard server testing
- **AI Server**: Optimized for GPU workloads with domestic GPU support
- **Storage Server**: RAID focus with drive health checks
- **Compute Server**: CPU and memory intensive testing

### Report Formats
- **JSON**: Machine-readable output
- **HTML**: Responsive web reports with Jinja2 templates and Chart.js performance charts
- **CSV**: Spreadsheet compatible

### Central Server (Server Mode)
FastAPI-based central server for managing multiple test clients:
- WebSocket real-time communication
- Job queue management
- Client registration and heartbeat
- Test progress streaming

### Platform Support
- **Linux**: Native detection via `/proc`, `sysfs`, `dmidecode`, `lspci`
- **Windows**: WMI and PowerShell-based detection

### Execution Strategies

The scheduler supports three execution strategies:

| Strategy | Description | Use Case |
|----------|-------------|----------|
| `sequential` | Run detectors one at a time | Resource-constrained environments |
| `parallel` | Run all detectors concurrently | Fast execution on powerful systems |
| `grouped` | Execute by category (compute→storage→network→...) | **Default** - balanced resource usage |

Groups execute sequentially, but detectors within each group run in parallel. This prevents resource contention while maximizing throughput.

### EMS Auto-Upload

Configure automatic report upload to your Equipment Management System:

```yaml
# config/global.yaml
ems:
  enabled: true
  auto_upload: true
  type: http          # or webhook
  endpoint: "http://ems.company.com/api/reports"
  api_key: "your-api-key"
```

Reports are automatically uploaded after test completion when `auto_upload` is enabled.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run in mock mode (no hardware required)
python -m src.main run --mock

# Run with specific server type
python -m src.main run --config config/server_types/ai_server.yaml

# Start central server
python -m src.server.main

# Interactive wizard mode
python -m src.main interactive
```

## Project Structure

```
server-master/
├── src/
│   ├── config/          # Configuration management
│   ├── core/            # Test engine, scheduler, events, state
│   │   ├── engine.py    # Main test orchestration with auto SN detection
│   │   ├── scheduler.py # Parallel/grouped/sequential execution strategies
│   │   └── stress_engine.py # Stress test coordination
│   ├── detectors/       # 21 hardware detectors
│   │   ├── base.py      # BaseDetector abstract class
│   │   ├── cpu.py, memory.py, dimm.py
│   │   ├── storage.py, nvme_health.py, raid.py
│   │   ├── network.py, infiniband.py, dpu.py
│   │   ├── gpu.py       # Multi-vendor GPU support
│   │   ├── bmc.py, bios.py, tpm.py, chassis.py
│   │   ├── pcie.py, usb.py, serial.py
│   │   ├── psu.py, sensor.py
│   │   └── security.py, fpga.py
│   ├── reporters/       # Report generators (JSON/HTML/CSV)
│   ├── server/          # Central server (FastAPI + WebSocket)
│   ├── stress_tests/    # 9 stress test types
│   │   ├── base.py      # BaseStressTest abstract class
│   │   ├── cpu_stress.py, gpu_stress.py, memory_stress.py
│   │   ├── nvme_stress.py, storage_stress.py
│   │   ├── network_stress.py, pcie_stress.py
│   │   ├── power_stress.py, fpga_stress.py
│   │   └── thresholds.py  # Dynamic threshold loading
│   ├── utils/           # Utility functions
│   │   └── system_info.py # Server SN/model auto-detection
│   └── cli/             # Command-line interface
├── config/
│   ├── server_types/    # Server-specific configs
│   └── global.yaml      # Global settings
├── templates/           # Jinja2 HTML templates
├── tests/               # 584+ unit tests
│   ├── test_detectors/  # 177 detector tests
│   ├── test_stress/     # 333 stress test tests
│   ├── test_core/       # Core engine and scheduler tests
│   ├── test_reporters/  # Reporter tests
│   ├── test_functional/ # Functional tests
│   └── test_utils/      # Utility function tests
└── docs/                # Documentation
```

## Configuration

### Server Type Configuration

Each server type has a YAML configuration defining which tests to run:

```yaml
# config/server_types/ai_server.yaml
server_type: ai_server
tests:
  - name: cpu_test
    required: true
    params:
      check_cores: true
  - name: gpu_test
    required: true
    params:
      supported_vendors: ["NVIDIA", "AMD", "Hygon", "Cambricon"]
      detect_hygon: true
      detect_cambricon: true
```

### RAID Controller Support

RAID detection supports multiple vendor tools with automatic fallback:

| Vendor | Tool | Controllers |
|--------|------|-------------|
| LSI/Broadcom | StorCLI | MegaRAID, SAS controllers |
| Adaptec | arcconf | Series 6/7/8 RAID controllers |
| HP/HPE | ssacli/hpacucli | Smart Array controllers |

Detection uses layered approach: lspci for initial discovery, vendor tools for detailed array/drive info.

### Stress Test Configuration

Stress tests support configurable thresholds:

```yaml
stress_tests:
  cpu:
    duration: 300
    threads: 0  # 0 = auto (all cores)
    thresholds:
      max_temperature: 85
      warning_temperature: 75
  gpu:
    duration: 300
    vendors: ["nvidia", "amd", "hygon"]
    thresholds:
      max_memory_temp: 95
      max_utilization: 100
  nvme:
    duration: 300
    thresholds:
      max_temperature: 85
      health_percent_min: 90
      max_media_errors: 0
```

## Testing

```bash
# Run all tests (584+ tests across all categories)
pytest

# Run with coverage
pytest --cov=src

# Run specific test categories
pytest tests/test_detectors/      # 177 hardware detection tests
pytest tests/test_stress/         # 333 stress test tests
pytest tests/test_reporters/      # Reporter tests
pytest tests/test_core/           # Core engine and scheduler tests
pytest tests/test_functional/     # Functional tests
pytest tests/test_utils/          # System info utility tests
```

## API Documentation (Server Mode)

### HTTP Endpoints

- `GET /` - Server status
- `POST /jobs` - Submit new test job
- `GET /jobs/{job_id}` - Get job status
- `GET /clients` - List connected clients
- `GET /results` - Get test results

### WebSocket

- `ws://host/ws/{client_id}` - Real-time test progress

## Features Highlights

### Domestic Hardware Support
Full support for Chinese domestic hardware:
- **GPUs**: Hygon DCU, Cambricon MLU, Huawei Ascend, Moore Threads
- **DPU**: NVIDIA BlueField-3/4 with DOCA support
- **FPGA**: Xilinx Alveo, Intel Stratix/Agilex

### Production Ready
- Mock mode for development/testing without hardware
- Real-time WebSocket progress streaming
- Multi-server management via central server
- Threshold-based pass/fail determination
- Comprehensive error handling and logging
- Signal-based detector timeout enforcement
- Automatic server identification via DMI/BIOS
- Grouped execution for optimal resource usage
- EMS integration for automated reporting

## Development

### Adding a New Detector

1. Create detector class in `src/detectors/{name}.py`
2. Inherit from `BaseDetector`
3. Implement `detect_real()` and `detect_mock()` methods
4. Update `src/detectors/__init__.py` to export
5. Add tests in `tests/test_detectors/test_{name}.py`

Example:
```python
from .base import BaseDetector, DetectorMode

class MyDetector(BaseDetector):
    def detect_real(self) -> Dict[str, Any]:
        # Hardware detection logic
        return {"present": True, "data": ...}

    def detect_mock(self) -> Dict[str, Any]:
        # Simulated data for testing
        return {"present": True, "data": ...}
```

### Adding a New Stress Test

1. Create stress test class in `src/stress_tests/{name}_stress.py`
2. Inherit from `BaseStressTest`
3. Implement `start_stress()`, `stop_stress()`, `collect_metrics()`
4. Define thresholds in `thresholds.py`
5. Add tests in `tests/test_stress/test_{name}_stress.py`

## License

MIT
