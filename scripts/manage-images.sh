#!/bin/bash

# Docker Image Management Script
# This script helps manage Docker image versions and releases

set -e

# Configuration
REGISTRY="ghcr.io"
REPOSITORY="justrunme/self-healing-infrastructure-chaos-engineering"
IMAGE_NAME="self-healing-controller"
FULL_IMAGE_NAME="${REGISTRY}/${REPOSITORY}/${IMAGE_NAME}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        log_error "Docker is not running or not accessible"
        exit 1
    fi
}

# Build image locally
build_image() {
    local tag=$1
    local context="./kubernetes/self-healing"
    
    log_info "Building image ${FULL_IMAGE_NAME}:${tag}"
    
    docker build \
        --platform linux/amd64,linux/arm64 \
        --tag "${FULL_IMAGE_NAME}:${tag}" \
        --file "${context}/Dockerfile" \
        "${context}"
    
    log_success "Image built successfully: ${FULL_IMAGE_NAME}:${tag}"
}

# Tag image
tag_image() {
    local source_tag=$1
    local target_tag=$2
    
    log_info "Tagging image ${FULL_IMAGE_NAME}:${source_tag} as ${FULL_IMAGE_NAME}:${target_tag}"
    
    docker tag "${FULL_IMAGE_NAME}:${source_tag}" "${FULL_IMAGE_NAME}:${target_tag}"
    
    log_success "Image tagged successfully"
}

# Push image to registry
push_image() {
    local tag=$1
    
    log_info "Pushing image ${FULL_IMAGE_NAME}:${tag} to registry"
    
    docker push "${FULL_IMAGE_NAME}:${tag}"
    
    log_success "Image pushed successfully: ${FULL_IMAGE_NAME}:${tag}"
}

# Pull image from registry
pull_image() {
    local tag=$1
    
    log_info "Pulling image ${FULL_IMAGE_NAME}:${tag} from registry"
    
    docker pull "${FULL_IMAGE_NAME}:${tag}"
    
    log_success "Image pulled successfully: ${FULL_IMAGE_NAME}:${tag}"
}

# List available tags
list_tags() {
    log_info "Available tags for ${FULL_IMAGE_NAME}:"
    
    # Try to get tags from registry (requires authentication)
    if command -v crane > /dev/null 2>&1; then
        crane ls "${FULL_IMAGE_NAME}" 2>/dev/null || log_warning "Could not fetch remote tags (authentication required)"
    fi
    
    # List local tags
    log_info "Local tags:"
    docker images "${FULL_IMAGE_NAME}" --format "table {{.Tag}}\t{{.CreatedAt}}\t{{.Size}}"
}

# Create release
create_release() {
    local version=$1
    
    if [[ -z "$version" ]]; then
        log_error "Version is required for release"
        echo "Usage: $0 release <version>"
        exit 1
    fi
    
    log_info "Creating release version ${version}"
    
    # Build with version tag
    build_image "${version}"
    
    # Tag as latest
    tag_image "${version}" "latest"
    
    # Push both tags
    push_image "${version}"
    push_image "latest"
    
    log_success "Release ${version} created and pushed successfully"
}

# Update Terraform variables
update_terraform() {
    local version=$1
    
    if [[ -z "$version" ]]; then
        log_error "Version is required for Terraform update"
        exit 1
    fi
    
    log_info "Updating Terraform variables with version ${version}"
    
    # Update terraform.tfvars if it exists
    if [[ -f "terraform/terraform.tfvars" ]]; then
        sed -i.bak "s|self_healing_controller_image = \".*\"|self_healing_controller_image = \"${FULL_IMAGE_NAME}:${version}\"|" terraform/terraform.tfvars
        log_success "Updated terraform/terraform.tfvars"
    fi
    
    # Update main.tf if it contains hardcoded image
    if grep -q "self-healing-controller:latest" terraform/main.tf; then
        sed -i.bak "s|self-healing-controller:latest|${FULL_IMAGE_NAME}:${version}|g" terraform/main.tf
        log_success "Updated terraform/main.tf"
    fi
}

# Clean up old images
cleanup_images() {
    local keep_count=${1:-5}
    
    log_info "Cleaning up old images, keeping ${keep_count} most recent"
    
    # Get list of images sorted by creation date
    local images=$(docker images "${FULL_IMAGE_NAME}" --format "{{.ID}}" | tail -n +$((keep_count + 1)))
    
    if [[ -n "$images" ]]; then
        echo "$images" | xargs -r docker rmi
        log_success "Cleaned up old images"
    else
        log_info "No old images to clean up"
    fi
}

# Show usage
show_usage() {
    cat << EOF
Docker Image Management Script

Usage: $0 <command> [options]

Commands:
    build <tag>              Build image with specified tag
    tag <source> <target>    Tag image from source to target
    push <tag>               Push image to registry
    pull <tag>               Pull image from registry
    list                     List available tags
    release <version>        Create a new release
    update-terraform <version> Update Terraform with new version
    cleanup [count]          Clean up old images (default: keep 5)
    help                     Show this help message

Examples:
    $0 build v1.0.0
    $0 release v1.0.0
    $0 update-terraform v1.0.0
    $0 cleanup 3

Environment Variables:
    REGISTRY                 Docker registry (default: ghcr.io)
    REPOSITORY               Repository name
    IMAGE_NAME               Image name

EOF
}

# Main script logic
main() {
    check_docker
    
    case "${1:-help}" in
        build)
            build_image "${2:-latest}"
            ;;
        tag)
            if [[ -z "$2" || -z "$3" ]]; then
                log_error "Source and target tags are required"
                exit 1
            fi
            tag_image "$2" "$3"
            ;;
        push)
            push_image "${2:-latest}"
            ;;
        pull)
            pull_image "${2:-latest}"
            ;;
        list)
            list_tags
            ;;
        release)
            create_release "$2"
            ;;
        update-terraform)
            update_terraform "$2"
            ;;
        cleanup)
            cleanup_images "$2"
            ;;
        help|--help|-h)
            show_usage
            ;;
        *)
            log_error "Unknown command: $1"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@" 