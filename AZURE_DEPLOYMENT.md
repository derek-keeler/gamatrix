# Flutter Gamatrix Azure Deployment

This document explains how to deploy the Flutter Gamatrix application to Azure Static Web Apps using Azure Developer CLI (AZD).

## Prerequisites

Before deploying, ensure you have the following installed:

1. **Flutter SDK** (>= 3.0.0)
   - Download from: https://flutter.dev/docs/get-started/install
   - Verify installation: `flutter --version`

2. **Azure Developer CLI (AZD)**
   - Install: https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/install-azd
   - Verify installation: `azd version`

3. **Azure Account**
   - Active Azure subscription
   - Appropriate permissions to create resources

## Quick Start

### Option 1: Using the Deployment Script (Recommended)

#### Linux/macOS:
```bash
# Make the script executable
chmod +x deploy-flutter.sh

# Deploy the application
./deploy-flutter.sh
```

#### Windows (PowerShell):
```powershell
# Deploy the application
.\deploy-flutter.ps1
```

### Option 2: Using AZD Commands Directly

1. **Login to Azure:**
   ```bash
   azd auth login
   ```

2. **Set environment variables (optional):**
   ```bash
   export AZURE_ENV_NAME="gamatrix-flutter-prod"
   export AZURE_LOCATION="eastus2"
   ```

3. **Initialize and deploy:**
   ```bash
   azd up
   ```

## Configuration

### IP Address Restrictions

The deployment automatically configures IP address restrictions based on the `allowedCidrs` parameter in the infrastructure. By default, it includes:

- `127.0.0.1/32` (localhost)
- `192.168.0.0/24` (private network range)

To customize allowed IP addresses, modify the `allowedCidrs` array in `infra/main.parameters.json`:

```json
{
  "parameters": {
    "allowedCidrs": {
      "value": [
        "203.0.113.0/24",
        "198.51.100.0/24",
        "192.0.2.0/24"
      ]
    }
  }
}
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AZURE_ENV_NAME` | Unique environment name | Auto-generated |
| `AZURE_LOCATION` | Azure region for deployment | `eastus2` |
| `AZURE_SUBSCRIPTION_ID` | Target Azure subscription | Current default |

## Deployment Architecture

The deployment creates the following Azure resources:

- **Resource Group**: `rg-{environmentName}`
- **Static Web App**: `swa-{environmentName}-gamatrix`
  - SKU: Free tier
  - IP restrictions configured
  - SPA routing enabled

## Build Process

The deployment process:

1. **Dependencies**: Installs Flutter packages (`flutter pub get`)
2. **Build**: Creates optimized web build (`flutter build web --release --web-renderer html`)
3. **Deploy**: Uploads build artifacts to Azure Static Web Apps

## Static Web App Configuration

The app includes a `staticwebapp.config.json` file that configures:

- SPA routing (all routes serve `index.html`)
- MIME types for Flutter web assets
- Cache control headers
- 404 fallback handling

## Troubleshooting

### Common Issues

1. **Flutter not found**
   ```
   Error: flutter: command not found
   ```
   **Solution**: Install Flutter SDK and add to PATH

2. **AZD not logged in**
   ```
   Error: not logged in to Azure
   ```
   **Solution**: Run `azd auth login`

3. **Insufficient permissions**
   ```
   Error: authorization failed
   ```
   **Solution**: Ensure your Azure account has Contributor permissions

4. **Build failures**
   ```
   Error: Flutter build failed
   ```
   **Solution**: Check Flutter dependencies with `flutter doctor`

### Deployment Script Options

Both deployment scripts support the following options:

- `--build-only` / `-BuildOnly`: Only build the Flutter app
- `--deploy-only` / `-DeployOnly`: Only deploy (skip build)
- `--help` / `-Help`: Show usage information

### Manual Deployment Steps

If you prefer manual control:

1. **Build Flutter app:**
   ```bash
   cd flutter_gamatrix
   flutter pub get
   flutter build web --release
   cd ..
   ```

2. **Provision infrastructure:**
   ```bash
   azd provision
   ```

3. **Deploy application:**
   ```bash
   azd deploy
   ```

## Security Considerations

- **IP Restrictions**: Only specified IP addresses can access the application
- **HTTPS**: All traffic is automatically encrypted via Azure Static Web Apps
- **No Authentication**: The application doesn't implement user authentication (as per requirements)

## Monitoring and Management

After deployment:

1. **View deployment status**: `azd env get-values`
2. **Check application logs**: Access via Azure Portal
3. **Update deployment**: Re-run deployment scripts
4. **Clean up resources**: `azd down`

## Cost Optimization

The deployment uses Azure Static Web Apps Free tier, which includes:
- 100 GB bandwidth per month
- 0.5 GB storage
- No cost for hosting

For production workloads, consider upgrading to Standard tier for additional features and higher limits.

## Support

For issues related to:
- **Flutter app**: Check the main repository README
- **Azure deployment**: Review Azure Static Web Apps documentation
- **AZD tooling**: Visit Azure Developer CLI documentation