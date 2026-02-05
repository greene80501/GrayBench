# Reference Environment

This document specifies the reference environment for graybench to ensure reproducible results.

## Operating System

- **OS**: Ubuntu 24.04.3 LTS (WSL2 or native)
- **Architecture**: x86_64

Ubuntu 24.04 is chosen for:
- Long-term support
- Widespread availability
- Compatibility with all dependencies

## Python Version

- **Version**: Python 3.10.x (3.10.12 recommended)

Python 3.10 is required because:
- Qiskit 1.4+ requires Python ≥3.10
- Stable, well-tested version
- Full typing support

### Installing Python 3.10 on Ubuntu 24.04

```bash
# Python 3.10 should be available
sudo apt update
sudo apt install python3.10 python3.10-venv python3.10-dev

# Create virtual environment
python3.10 -m venv venv
source venv/bin/activate
```

## Core Dependencies

### Qiskit Ecosystem

| Package | Version | Purpose |
|---------|---------|---------|
| qiskit | ~=1.4.0 | Core quantum computing |
| qiskit-aer | ~=0.14.0 | Local simulator |
| qiskit-ibm-runtime | ~=0.20.0 | IBM Quantum access |

These versions are chosen to match the Qiskit HumanEval dataset (v0.1.2, April 2025).

### AI Provider SDKs

| Package | Version | Purpose |
|---------|---------|---------|
| openai | >=1.12.0 | OpenAI API client |
| anthropic | >=0.18.0 | Anthropic API client |
| google-generativeai | >=0.4.0 | Google Gemini client |
| httpx | >=0.26.0 | HTTP client (for custom APIs) |

### CLI and Utilities

| Package | Version | Purpose |
|---------|---------|---------|
| typer | >=0.9.0 | CLI framework |
| rich | >=13.0.0 | Terminal formatting |
| python-dotenv | >=1.0.0 | Environment variables |
| pyyaml | >=6.0 | Configuration files |

### Data and Storage

| Package | Version | Purpose |
|---------|---------|---------|
| datasets | >=2.14.0 | HuggingFace datasets |
| huggingface-hub | >=0.19.0 | HuggingFace API |
| numpy | >=1.24.0 | Numerical computing |

## Installation

### Full Installation

```bash
# 1. Clone repository
git clone https://github.com/grayarealabs/graybench.git
cd graybench

# 2. Create virtual environment
python3.10 -m venv venv
source venv/bin/activate

# 3. Install package
pip install -e .

# 4. Verify installation
graybench --version
graybench validate environment
```

### Requirements Lock

For exact reproducibility, use the locked requirements:

```bash
pip install -r requirements-lock.txt
```

## Environment Variables

Required API keys (set in `.env` or shell):

```bash
# Provider API keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
DEEPSEEK_API_KEY=...
MOONSHOT_API_KEY=...

# Optional: IBM Quantum
IBM_QUANTUM_TOKEN=...
```

## Verification

Run the validation suite to ensure correct setup:

```bash
# Check Python and packages
graybench validate environment

# Verify canonical solutions pass
graybench validate canonical -s normal --limit 10

# Check required imports
graybench validate imports
```

Expected output:
- All canonical solutions should pass
- Environment check should show all packages installed
- API keys should be detected for configured providers

## Troubleshooting

### Qiskit Import Errors

```bash
# Ensure all Qiskit packages are installed
pip install qiskit qiskit-aer qiskit-ibm-runtime
```

### IBM Runtime Issues

If tasks using `qiskit_ibm_runtime` fail:

1. Ensure `IBM_QUANTUM_TOKEN` is set
2. Check token validity at quantum.ibm.com
3. For local testing, Aer simulator may work as fallback

### Memory Issues

Some quantum simulations are memory-intensive:

```bash
# Increase available memory (if using containers)
# Or reduce concurrent workers
graybench run -p openai -m gpt-4o -w 2
```

## Docker Alternative

While not required, a Docker environment is available:

```dockerfile
FROM python:3.10-slim

RUN apt-get update && apt-get install -y git

WORKDIR /app
COPY . .
RUN pip install -e .

ENTRYPOINT ["graybench"]
```

```bash
docker build -t graybench .
docker run -v ~/.graybench:/root/.graybench \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  graybench run -p openai -m gpt-4o
```
