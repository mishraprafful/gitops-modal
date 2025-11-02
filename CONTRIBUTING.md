# Contributing to Modal GitOps Operator

First off, thank you for considering contributing to the Modal GitOps Operator! It's people like you that make this project better for everyone.

## Table of Contents

- [Contributing to Modal GitOps Operator](#contributing-to-modal-gitops-operator)
  - [Table of Contents](#table-of-contents)
  - [Code of Conduct](#code-of-conduct)
  - [How Can I Contribute?](#how-can-i-contribute)
    - [Reporting Bugs](#reporting-bugs)
    - [Suggesting Features](#suggesting-features)
    - [Improving Documentation](#improving-documentation)
    - [Contributing Code](#contributing-code)
  - [Development Setup](#development-setup)
  - [Pull Request Process](#pull-request-process)
  - [Coding Guidelines](#coding-guidelines)
    - [Python Code Style](#python-code-style)
    - [YAML Style](#yaml-style)
    - [Git Practices](#git-practices)
  - [Testing Guidelines](#testing-guidelines)
    - [Required Tests](#required-tests)
    - [Running Tests](#running-tests)
    - [Test Coverage](#test-coverage)
  - [Commit Message Guidelines](#commit-message-guidelines)
    - [Format](#format)
    - [Types](#types)
    - [Examples](#examples)
    - [Rules](#rules)
  - [Community](#community)
    - [Getting Help](#getting-help)
    - [Staying Updated](#staying-updated)
    - [Recognition](#recognition)
  - [Questions?](#questions)

## Code of Conduct

This project and everyone participating in it is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the [existing issues](https://github.com/mishraprafful/gitops-modal/issues) to avoid duplicates.

When you create a bug report, please include as many details as possible:

- **Use the bug report template** when creating the issue
- **Use a clear and descriptive title**
- **Describe the exact steps to reproduce the problem**
- **Provide the ModalDeployment YAML** (sanitize any secrets)
- **Include operator logs** and any error messages
- **Specify versions**: Operator, Kubernetes, Modal CLI
- **Describe the expected behavior** and what actually happened

### Suggesting Features

Feature suggestions are welcome! Before creating a feature request:

- **Check existing issues and discussions** for similar ideas
- **Use the feature request template**
- **Clearly describe the problem** this feature would solve
- **Provide examples** of how the feature would be used
- **Consider backwards compatibility** and potential breaking changes

### Improving Documentation

Documentation improvements are always appreciated:

- Fixing typos or clarifying existing docs
- Adding examples or use cases
- Improving installation or troubleshooting guides
- Adding diagrams or screenshots
- Translating documentation

Use the documentation issue template or submit a PR directly for minor fixes.

### Contributing Code

We love code contributions! Here's how to get started:

1. **Fork the repository** and create a branch from `main`
2. **Set up your development environment** (see below)
3. **Make your changes** following our coding guidelines
4. **Add tests** for your changes
5. **Update documentation** as needed
6. **Submit a pull request**

## Development Setup

Detailed development setup instructions are in [DEVELOPMENT.md](DEVELOPMENT.md). Quick start:

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/gitops-modal.git
cd gitops-modal

# Create a kind cluster for testing
kind create cluster --name modal-test

# Set up Modal credentials
cat > .env << EOF
MODAL_TOKEN_ID=your-token-id
MODAL_TOKEN_SECRET=your-token-secret
EOF

# Build and deploy
make deploy
```

## Pull Request Process

1. **Create a feature branch**:

   ```bash
   git checkout -b feat/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

2. **Make your changes**:
   - Follow the coding guidelines
   - Add tests for new functionality
   - Update documentation
   - Keep commits atomic and well-described

3. **Test your changes**:

   ```bash
   # Run tests
   make test

   # Test locally with kind
   make deploy
   kubectl apply -f examples/function-deployment.yaml
   ```

4. **Update CHANGELOG.md**:
   - Add a brief description of your changes under "Unreleased"
   - Follow the Keep a Changelog format used in the repository

5. **Submit the PR**:
   - Fill out the pull request template completely
   - Link related issues
   - Provide clear description and testing evidence
   - Ensure CI passes

6. **Address review feedback**:
   - Respond to comments
   - Make requested changes
   - Push updates to your branch

7. **Merge**:
   - Maintainers will merge once approved
   - Your PR will be included in the next release

## Coding Guidelines

### Python Code Style

- **Follow PEP 8** style guide
- **Use type hints** where appropriate
- **Write docstrings** for functions and classes
- **Keep functions focused** and small
- **Use meaningful variable names**

Example:

```python
def deploy_modal_app(deployment: ModalDeployment, namespace: str) -> DeploymentStatus:
    """
    Deploy a Modal application from a ModalDeployment resource.

    Args:
        deployment: The ModalDeployment resource
        namespace: Kubernetes namespace

    Returns:
        DeploymentStatus with app ID and URL

    Raises:
        DeploymentError: If deployment fails
    """
    # Implementation
    pass
```

### YAML Style

- **Use 2 spaces** for indentation
- **Keep consistent** with existing files
- **Add comments** for complex configurations
- **Validate** YAML before committing

### Git Practices

- **Keep commits atomic** - one logical change per commit
- **Write clear commit messages** (see below)
- **Don't commit secrets** or credentials
- **Don't commit generated files** unless necessary

## Testing Guidelines

### Required Tests

- **Unit tests** for new functions
- **Integration tests** for operator logic
- **End-to-end tests** for new CRD features
- **Manual testing** in a real cluster

### Running Tests

NOTE: Assuming you have a kind cluster running.

```bash

# Test in kind cluster and apply examples
make deploy
make test-examples
```

### Test Coverage

- Test both **success and failure** cases
- Test **edge cases** and error handling

## Commit Message Guidelines

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

### Format

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks, dependencies
- `ci`: CI/CD changes
- `perf`: Performance improvements

### Examples

```
feat(crd): add support for private git repositories

Add support for SSH key and PAT authentication for private repos.
Includes new secretRef field in git source configuration.

Fixes #42
```

```
fix(controller): prevent race condition in status updates

Use optimistic locking to prevent concurrent status updates
from overwriting each other.
```

```
docs: update installation guide for kind clusters
```

### Rules

- Use **present tense** ("add feature" not "added feature")
- Use **imperative mood** ("move cursor to..." not "moves cursor to...")
- **Don't capitalize** first letter
- **No period** at the end
- Reference issues and PRs in the footer

## Community

### Getting Help

- **GitHub Issues**: Report bugs, request features

### Staying Updated

- **Watch** the repository for notifications
- **Star** the project to show support

### Recognition

All contributors will be:

- Listed in release notes
- Acknowledged in the README (future)
- Granted contributor badge

## Questions?

Don't hesitate to ask questions:

- Open a discussion on GitHub
- Comment on an issue
- Ask in your PR

We're here to help! Thank you for contributing! 🎉
