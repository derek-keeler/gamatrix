# Deploy Flutter Gamatrix to Azure Static Web Apps
# PowerShell script for Windows users

param(
    [switch]$BuildOnly,
    [switch]$DeployOnly,
    [switch]$Help
)

# Colors for output
$ErrorColor = "Red"
$InfoColor = "Green"
$WarnColor = "Yellow"

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor $InfoColor
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor $WarnColor
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor $ErrorColor
}

function Show-Help {
    Write-Host "Usage: .\deploy-flutter.ps1 [options]"
    Write-Host "Options:"
    Write-Host "  -Help                Show this help message"
    Write-Host "  -BuildOnly           Only build the Flutter app, don't deploy"
    Write-Host "  -DeployOnly          Only deploy, skip building"
    Write-Host ""
    Write-Host "Environment variables:"
    Write-Host "  AZURE_ENV_NAME       Azure environment name (auto-generated if not set)"
    Write-Host "  AZURE_LOCATION       Azure location (defaults to eastus2)"
    Write-Host "  AZURE_SUBSCRIPTION_ID Azure subscription ID"
    Write-Host ""
    Write-Host "Prerequisites:"
    Write-Host "  - Flutter SDK installed and in PATH"
    Write-Host "  - Azure Developer CLI (azd) installed and logged in"
    Write-Host "  - Azure subscription configured"
}

function Test-Requirements {
    Write-Info "Checking requirements..."
    
    try {
        $null = Get-Command flutter -ErrorAction Stop
    } catch {
        Write-Error-Custom "Flutter is not installed or not in PATH. Please install Flutter SDK."
        exit 1
    }
    
    try {
        $null = Get-Command azd -ErrorAction Stop
    } catch {
        Write-Error-Custom "Azure Developer CLI (azd) is not installed. Please install azd."
        exit 1
    }
    
    Write-Info "All requirements satisfied."
}

function Build-FlutterApp {
    Write-Info "Building Flutter web application..."
    
    Push-Location flutter_gamatrix
    
    try {
        Write-Info "Installing Flutter dependencies..."
        flutter pub get
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to install Flutter dependencies"
        }
        
        Write-Info "Building for web..."
        flutter build web --release --web-renderer html
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to build Flutter web app"
        }
        
        Write-Info "Flutter build completed."
    } catch {
        Write-Error-Custom $_.Exception.Message
        Pop-Location
        exit 1
    } finally {
        Pop-Location
    }
}

function Deploy-ToAzure {
    Write-Info "Deploying to Azure Static Web Apps..."
    
    # Check if already logged in to Azure
    try {
        azd auth login --check-status 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Warn "Not logged in to Azure. Please run 'azd auth login' first."
            exit 1
        }
    } catch {
        Write-Warn "Not logged in to Azure. Please run 'azd auth login' first."
        exit 1
    }
    
    # Set environment name if not already set
    if (-not $env:AZURE_ENV_NAME) {
        $timestamp = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
        $env:AZURE_ENV_NAME = "gamatrix-flutter-$timestamp"
        Write-Info "Using auto-generated environment name: $($env:AZURE_ENV_NAME)"
    }
    
    # Set location if not already set
    if (-not $env:AZURE_LOCATION) {
        $env:AZURE_LOCATION = "eastus2"
        Write-Info "Using default location: $($env:AZURE_LOCATION)"
    }
    
    try {
        Write-Info "Provisioning Azure resources..."
        azd provision --no-prompt
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to provision Azure resources"
        }
        
        Write-Info "Deploying application..."
        azd deploy --no-prompt
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to deploy application"
        }
        
        Write-Info "Deployment completed!"
        
        # Get the deployed URL
        $envValues = azd env get-values
        $urlLine = $envValues | Where-Object { $_ -match "STATIC_WEB_APP_URL=" }
        if ($urlLine) {
            $url = ($urlLine -split "=", 2)[1].Trim('"')
            Write-Info "Your Flutter app is now available at: $url"
        }
    } catch {
        Write-Error-Custom $_.Exception.Message
        exit 1
    }
}

function Main {
    Write-Info "Starting Flutter Gamatrix deployment to Azure Static Web Apps"
    
    Test-Requirements
    Build-FlutterApp
    Deploy-ToAzure
    
    Write-Info "Deployment process completed successfully!"
}

# Main execution logic
if ($Help) {
    Show-Help
    exit 0
}

if ($BuildOnly) {
    Write-Info "Build-only mode enabled"
    Test-Requirements
    Build-FlutterApp
    Write-Info "Build completed!"
    exit 0
}

if ($DeployOnly) {
    Write-Info "Deploy-only mode enabled"
    try {
        $null = Get-Command azd -ErrorAction Stop
    } catch {
        Write-Error-Custom "Azure Developer CLI (azd) is not installed."
        exit 1
    }
    Deploy-ToAzure
    exit 0
}

# Run main function if no specific options were provided
Main