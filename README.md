# Server Test System

Hardware testing system for production servers - supports generic, storage, compute, and AI server types.

## Features

- **4 Server Types**: Generic, Storage, Compute, AI Server
- **7 Hardware Detectors**: CPU, Memory, Storage, Network, GPU, BMC, PCIe
- **2 Test Modes**: Automatic (batch) and Interactive (wizard)
- **3 Report Formats**: JSON, HTML, CSV
- **Mock/Real Mode**: Test without hardware, deploy with real detection

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run in mock mode (no hardware required)
python -m src.main run --mock

# Run with specific config
python -m src.main run --config config/global.yaml

# Interactive wizard mode
python -m src.main interactive
```

## Project Structure

```
server-master/
├── src/
│   ├── config/      # Configuration management
│   ├── core/        # Test engine and state
│   ├── detectors/   # Hardware detectors
│   ├── reporters/   # Report generators
│   └── cli/         # Command-line interface
├── config/          # YAML configurations
├── tests/           # Unit tests
└── docs/            # Documentation
```

## Configuration

Edit `config/global.yaml` to customize:
- Server type
- Tests to run
- Output formats
- Mock/real mode

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src
```

## License

MIT
