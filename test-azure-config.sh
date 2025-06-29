#!/bin/bash

# Test script to validate Azure deployment configuration
# This script checks that all required files and configurations are present

set -e

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

test_count=0
pass_count=0

run_test() {
    local test_name="$1"
    local test_command="$2"
    
    test_count=$((test_count + 1))
    echo_info "Test $test_count: $test_name"
    
    if eval "$test_command"; then
        echo -e "  ${GREEN}✓ PASS${NC}"
        pass_count=$((pass_count + 1))
    else
        echo -e "  ${RED}✗ FAIL${NC}"
    fi
    echo
}

echo_info "Starting Azure deployment configuration tests..."
echo

# Test 1: Check azure.yaml exists and is valid
run_test "azure.yaml file exists and is valid YAML" \
    "[ -f azure.yaml ] && python -c 'import yaml; yaml.safe_load(open(\"azure.yaml\"))'"

# Test 2: Check Bicep files exist
run_test "Bicep infrastructure files exist" \
    "[ -f infra/main.bicep ] && [ -f infra/core/security/staticwebapp.bicep ]"

# Test 3: Check parameters file is valid JSON
run_test "Parameters file is valid JSON" \
    "[ -f infra/main.parameters.json ] && python -c 'import json; json.load(open(\"infra/main.parameters.json\"))'"

# Test 4: Check Static Web App config is valid JSON
run_test "Static Web App config is valid JSON" \
    "[ -f flutter_gamatrix/staticwebapp.config.json ] && python -c 'import json; json.load(open(\"flutter_gamatrix/staticwebapp.config.json\"))'"

# Test 5: Check deployment scripts exist and are executable
run_test "Deployment scripts exist and are executable" \
    "[ -x deploy-flutter.sh ] && [ -f deploy-flutter.ps1 ]"

# Test 6: Check GitHub Actions workflow is valid YAML
run_test "GitHub Actions workflow is valid YAML" \
    "[ -f .github/workflows/deploy-flutter.yml ] && python -c 'import yaml; yaml.safe_load(open(\".github/workflows/deploy-flutter.yml\"))'"

# Test 7: Check documentation files exist
run_test "Documentation files exist" \
    "[ -f AZURE_DEPLOYMENT.md ] && grep -q 'Flutter Gamatrix Azure Deployment' AZURE_DEPLOYMENT.md"

# Test 8: Check azure.yaml has required services configuration
run_test "azure.yaml has required services configuration" \
    "python -c 'import yaml; config=yaml.safe_load(open(\"azure.yaml\")); assert \"services\" in config and \"web\" in config[\"services\"]'"

# Test 9: Check Bicep template has IP restrictions parameter
run_test "Bicep template supports IP restrictions" \
    "grep -q 'allowedCidrs' infra/core/security/staticwebapp.bicep"

# Test 10: Check Flutter app structure
run_test "Flutter app structure is correct" \
    "[ -d flutter_gamatrix ] && [ -f flutter_gamatrix/pubspec.yaml ]"

# Test 11: Check deployment script help functionality
run_test "Deployment script help works" \
    "./deploy-flutter.sh --help | grep -q 'Usage:'"

# Test 12: Check justfile has Flutter deployment recipes
run_test "Justfile contains Flutter deployment recipes" \
    "grep -q 'deploy-flutter' justfile"

echo_info "Test Results: $pass_count/$test_count tests passed"

if [ $pass_count -eq $test_count ]; then
    echo_info "All tests passed! Azure deployment configuration is ready."
    exit 0
else
    echo_error "Some tests failed. Please review the configuration."
    exit 1
fi