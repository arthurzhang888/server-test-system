# Server Test System

Hardware testing system for production line servers. Supports comprehensive hardware detection, stress testing, and multi-server management for generic, storage, compute, and AI server types.

## Features

### Hardware Detection (20 Detectors)
- **CPU**: Model, cores, threads, frequency, vendor
- **Memory**: Total, available, DIMM details
- **Storage**: Disks, NVMe health, RAID controllers
- **Network**: Interfaces, MAC, speed, InfiniBand
- **GPU**: NVIDIA, AMD, and domestic GPUs (Hygon, Cambricon, Huawei Ascend, Moore Threads)
- **BMC/IPMI**: Version, IP, sensors
- **BIOS**: Version, secure boot, characteristics
- **PCIe**: Device enumeration
- **USB**: Device detection
- **Chassis**: Type, serial numbers
- **TPM**: Presence, version
- **Security**: SGX, SEV, TXT, memory encryption
- **FPGA**: Device detection
- **Sensors**: Temperatures, fans
- **PSU**: Power supply status
- **Serial Ports**: RS-232, RS-485, USB serial

### Stress Testing
- **CPU Stress**: Multi-core load testing with configurable duration
- **GPU Stress**: Multi-vendor support (NVIDIA, AMD, domestic GPUs)
- **NVMe Stress**: Disk I/O testing with health monitoring
- **Network Throughput**: Bandwidth testing

### Server Types
- **Generic**: Standard server testing
- **AI Server**: Optimized for GPU workloads with domestic GPU support
- **Storage Server**: RAID focus with drive health checks
- **Compute Server**: CPU and memory intensive testing

### Report Formats
- **JSON**: Machine-readable output
- **HTML**: Responsive web reports with Jinja2 templates
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
│   ├── core/            # Test engine, scheduler, events
│   ├── detectors/       # Hardware detectors (20 types)
│   │   └── platform/    # Linux/Windows abstraction
│   ├── reporters/       # Report generators (JSON/HTML/CSV)
│   ├── server/          # Central server (FastAPI + WebSocket)
│   ├── stress_tests/    # Stress testing framework
│   └── cli/             # Command-line interface
├── config/
│   ├── server_types/    # Server-specific configs
│   │   ├── generic.yaml
│   │   ├── ai_server.yaml
│   │   ├── storage.yaml
│   │   └── compute.yaml
│   └── global.yaml      # Global settings
├── templates/           # Jinja2 HTML templates
│   ├── base.html
│   ├── report.html
│   └── static/css/
├── tests/               # Unit tests (237 tests)
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
```

## Testing

```bash
# Run all tests (237 tests)
pytest

# Run with coverage
pytest --cov=src

# Run specific test category
pytest tests/test_detectors/
pytest tests/test_reporters/
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

## Development

### Adding a New Detector

1. Create detector class in `src/detectors/{name}.py`
2. Inherit from `BaseDetector`
3. Implement `detect_real()` and `detect_mock()` methods
4. Add tests in `tests/test_detectors/test_{name}.py`

### Adding a New Stress Test

1. Create stress test class in `src/stress_tests/{name}_stress.py`
2. Inherit from `BaseStressTest`
3. Implement `run()` method with threshold monitoring

## License

MIT
