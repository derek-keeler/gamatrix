#!/bin/bash

# Deploy Flutter Gamatrix to Azure Static Web Apps
# This script can be used locally or in CI/CD pipelines

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

echo_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if required tools are installed
check_requirements() {
    echo_info "Checking requirements..."
    
    if ! command -v flutter &> /dev/null; then
        echo_error "Flutter is not installed. Please install Flutter SDK."
        exit 1
    fi
    
    if ! command -v azd &> /dev/null; then
        echo_error "Azure Developer CLI (azd) is not installed. Please install azd."
        exit 1
    fi
    
    echo_info "All requirements satisfied."
}

# Build Flutter web app
build_flutter_app() {
    echo_info "Building Flutter web application..."
    
    cd flutter_gamatrix
    
    echo_info "Installing Flutter dependencies..."
    flutter pub get
    
    echo_info "Building for web..."
    flutter build web --release --web-renderer html
    
    cd ..
    
    echo_info "Flutter build completed."
}

# Deploy using AZD
deploy_to_azure() {
    echo_info "Deploying to Azure Static Web Apps..."
    
    # Check if already logged in to Azure
    if ! azd auth login --check-status &> /dev/null; then
        echo_warn "Not logged in to Azure. Please run 'azd auth login' first."
        exit 1
    fi
    
    # Set environment name if not already set
    if [ -z "$AZURE_ENV_NAME" ]; then
        export AZURE_ENV_NAME="gamatrix-flutter-$(date +%s)"
        echo_info "Using auto-generated environment name: $AZURE_ENV_NAME"
    fi
    
    # Set location if not already set
    if [ -z "$AZURE_LOCATION" ]; then
        export AZURE_LOCATION="eastus2"
        echo_info "Using default location: $AZURE_LOCATION"
    fi
    
    echo_info "Provisioning Azure resources..."
    azd provision --no-prompt
    
    echo_info "Deploying application..."
    azd deploy --no-prompt
    
    echo_info "Deployment completed!"
    
    # Get the deployed URL
    URL=$(azd env get-values | grep STATIC_WEB_APP_URL | cut -d'=' -f2 | tr -d '"')
    if [ -n "$URL" ]; then
        echo_info "Your Flutter app is now available at: $URL"
    fi
}

# Main execution
main() {
    echo_info "Starting Flutter Gamatrix deployment to Azure Static Web Apps"
    
    check_requirements
    build_flutter_app
    deploy_to_azure
    
    echo_info "Deployment process completed successfully!"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --help, -h           Show this help message"
            echo "  --build-only         Only build the Flutter app, don't deploy"
            echo "  --deploy-only        Only deploy, skip building"
            echo ""
            echo "Environment variables:"
            echo "  AZURE_ENV_NAME       Azure environment name (auto-generated if not set)"
            echo "  AZURE_LOCATION       Azure location (defaults to eastus2)"
            echo "  AZURE_SUBSCRIPTION_ID Azure subscription ID"
            echo ""
            echo "Prerequisites:"
            echo "  - Flutter SDK installed and in PATH"
            echo "  - Azure Developer CLI (azd) installed and logged in"
            echo "  - Azure subscription configured"
            exit 0
            ;;
        --build-only)
            echo_info "Build-only mode enabled"
            check_requirements
            build_flutter_app
            echo_info "Build completed!"
            exit 0
            ;;
        --deploy-only)
            echo_info "Deploy-only mode enabled"
            if ! command -v azd &> /dev/null; then
                echo_error "Azure Developer CLI (azd) is not installed."
                exit 1
            fi
            deploy_to_azure
            exit 0
            ;;
        *)
            echo_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
    shift
done

# Run main function if no specific options were provided
main