# Grafana Dashboard Export Tool

⚠️ **WARNING: This tool is under construction and is not officially supported by Grafana Labs. Use at your own risk.**

This tool exports Grafana dashboards and folders to Terraform configuration. It generates both the Terraform resources and the dashboard JSON files.

## Prerequisites

- Python 3.6 or higher
- `requests` Python package
- Grafana instance with API access
- Grafana API key with admin privileges

## Installation

1. Clone this repository
2. Install the required Python package:
```bash
pip install requests
```

## Usage

```bash
python grafana_export.py --url "https://your-grafana-url" --api-key "your-api-key" [options]
```

### Required Arguments

- `--url`: Your Grafana instance URL (e.g., https://grafana.example.com)
- `--api-key`: Your Grafana API key with admin privileges

### Optional Arguments

- `--folder-names`: List of folder names to include (e.g., "Folder1" "Folder2")
- `--skip-resources`: Comma-delimited list of dashboard resource names to skip in Terraform (e.g., d_cardinality_management,d_cardinality_management_metrics_detail)
- `--timeout`: Timeout in seconds for API requests (default: 300)

### Examples

Export all dashboards from all folders:
```bash
python grafana_export.py --url "https://grafana.example.com" --api-key "your-api-key"
```

Export dashboards from specific folders:
```bash
python grafana_export.py --url "https://grafana.example.com" --api-key "your-api-key" --folder-names "Folder1" "Folder2"
```

Skip specific dashboards:
```bash
python grafana_export.py --url "https://grafana.example.com" --api-key "your-api-key" --skip-resources "d_dashboard1,d_dashboard2"
```

Increase timeout for large dashboards:
```bash
python grafana_export.py --url "https://grafana.example.com" --api-key "your-api-key" --timeout 600
```

## Output

The script generates:

1. `grafana.tf`: Terraform configuration file containing:
   - Grafana provider configuration
   - Folder resources
   - Dashboard resources

2. `dashboards/` directory containing:
   - JSON files for each dashboard
   - Filenames match the dashboard UIDs

## Notes

- The script automatically skips the "GrafanaCloud" folder
- Dashboard resources are named with the prefix "d_" followed by the dashboard UID
- The script makes dashboards editable and removes version/id/gnetId fields
- All dashboard JSON files are stored in the `dashboards` directory

## Error Handling

The script handles various errors:
- API errors with detailed messages
- Timeout errors with configurable timeout
- Missing folders with warning messages
- Invalid API keys with error messages

## Contributing

Feel free to submit issues and enhancement requests! 